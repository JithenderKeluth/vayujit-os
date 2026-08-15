from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product
from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
from vayujit_api.video.schemas import VideoQueueRequest, VideoType
from vayujit_api.video.service import queue


class VideoBulkRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    video_types: list[str] = Field(min_length=1, max_length=6)
    targets: list[str] = Field(min_length=1, max_length=6)
    duration_seconds: int = Field(default=10, ge=1, le=60)
    resolution: str = Field(default="320x240", pattern=r"^\d{3,4}x\d{3,4}$")
    idempotency_key: str = Field(min_length=1, max_length=160)


class VideoBulkRetryRequest(BaseModel):
    child_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class VideoBulkCancelRequest(BaseModel):
    child_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]
router = APIRouter(prefix="/api/v1/ai/video/bulk", tags=["ai-video-bulk"])


def _now() -> datetime:
    return datetime.now(UTC)


def _child_key(product_id: uuid.UUID, video_type: str, target: str) -> str:
    return hashlib.sha256(f"{product_id}:{video_type}:{target}".encode()).hexdigest()


def _owned_products(db: Session, owner: User, ids: list[uuid.UUID]) -> None:
    found = set(
        db.scalars(select(Product.id).where(Product.owner_id == owner.id, Product.id.in_(ids)))
    )
    if found != set(ids):
        raise HTTPException(404, "One or more Products were not found.")


def _counts(db: Session, bulk_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(VideoBulkChild.status, func.count())
        .where(VideoBulkChild.bulk_id == bulk_id)
        .group_by(VideoBulkChild.status)
    ).all()
    return {str(status): int(count) for status, count in rows}


def _sync(db: Session, operation: VideoBulkOperation) -> dict[str, int]:
    children = list(
        db.scalars(select(VideoBulkChild).where(VideoBulkChild.bulk_id == operation.id))
    )
    for child in children:
        if child.generation_id and child.status in {"queued", "running", "retry_wait"}:
            from vayujit_api.video.models import VideoGeneration, VideoOutput

            generation = db.get(VideoGeneration, child.generation_id)
            output = db.scalar(
                select(VideoOutput).where(VideoOutput.generation_id == child.generation_id)
            )
            if generation is not None:
                child.status = {
                    "succeeded": "needs_review",
                    "failed": "failed",
                    "cancelled": "cancelled",
                }.get(generation.status, generation.status)
                child.retryable = generation.status == "failed"
                child.failure_code = generation.failure_code
                child.safe_error_message = generation.safe_error_message
                child.output_id = output.id if output else child.output_id
    counts = _counts(db, operation.id)
    terminal = sum(
        counts.get(value, 0)
        for value in {"succeeded", "needs_review", "failed", "cancelled", "stale"}
    )
    if operation.cancellation_requested:
        operation.status = (
            "cancelled" if terminal == operation.total_children else "partially_cancelled"
        )
    elif terminal < operation.total_children:
        operation.status = (
            "queued" if counts.get("queued", 0) == operation.total_children else "running"
        )
    elif counts.get("failed", 0) or counts.get("stale", 0):
        operation.status = "partial_success" if counts.get("needs_review", 0) else "failed"
    else:
        operation.status = "succeeded"
    operation.updated_at = _now()
    return counts


@router.post("/preview")
def preview(data: VideoBulkRequest, db: DB, owner: Owner) -> dict[str, object]:
    _owned_products(db, owner, data.product_ids)
    total = len(data.product_ids) * len(data.video_types) * len(data.targets)
    if total > 60:
        raise HTTPException(422, "Video bulk output limit is 60 children.")
    return {
        "operation": "video_bulk_generation",
        "product_count": len(data.product_ids),
        "video_type_count": len(data.video_types),
        "target_count": len(data.targets),
        "total_outputs": total,
        "estimated_provider_calls": total,
        "estimated_bytes": total * 25_000_000,
        "provider": "deterministic_video_local",
        "blockers": [],
        "warnings": ["Videos remain pending review after generation."],
        "limits": {"max_products": 10, "max_outputs": 60, "max_duration_seconds": 60},
    }


@router.post("", status_code=202)
def enqueue(data: VideoBulkRequest, db: DB, owner: Owner) -> dict[str, object]:
    _owned_products(db, owner, data.product_ids)
    planned = preview(data, db, owner)
    existing = db.scalar(
        select(VideoBulkOperation).where(
            VideoBulkOperation.owner_id == owner.id,
            VideoBulkOperation.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return {
            "id": existing.id,
            "status": existing.status,
            "idempotent_reuse": True,
            "total_outputs": existing.total_children,
        }
    stamp = _now()
    total = int(cast(int, planned["total_outputs"]))
    operation = VideoBulkOperation(
        owner_id=owner.id,
        idempotency_key=data.idempotency_key,
        product_ids_json=[str(value) for value in data.product_ids],
        video_types_json=data.video_types,
        targets_json=data.targets,
        total_children=total,
        correlation_id=uuid.uuid4().hex[:32],
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(operation)
    db.flush()
    for product_id in data.product_ids:
        product = db.get(Product, product_id)
        if product is None:
            continue
        for video_type in data.video_types:
            for target in data.targets:
                child = VideoBulkChild(
                    owner_id=owner.id,
                    bulk_id=operation.id,
                    product_id=product.id,
                    video_type=cast(VideoType, video_type),
                    target_channel=target,
                    child_key=_child_key(product.id, video_type, target),
                    status="queued",
                    created_at=stamp,
                    updated_at=stamp,
                )
                db.add(child)
                db.flush()
                try:
                    generation = queue(
                        db,
                        owner,
                        VideoQueueRequest(
                            product_id=product.id,
                            brand_id=product.brand_id,
                            video_type=cast(VideoType, video_type),
                            target_channel=target,
                            duration_seconds=data.duration_seconds,
                            resolution=data.resolution,
                            idempotency_key=f"video-bulk:{operation.id}:{child.child_key}",
                        ),
                    )
                    child.generation_id = cast(uuid.UUID, generation["id"])
                except HTTPException as error:
                    child.status = "failed"
                    child.retryable = False
                    child.failure_code = "video.bulk_child_invalid"
                    child.safe_error_message = str(error.detail)
    record_event(
        db,
        actor_id=owner.id,
        action="video_bulk_created",
        entity_type="video_bulk_operation",
        entity_id=operation.id,
        metadata={"total_children": total},
    )
    db.commit()
    return {
        "id": operation.id,
        "status": operation.status,
        "idempotent_reuse": False,
        "total_outputs": total,
        "correlation_id": operation.correlation_id,
    }


@router.get("/{bulk_id}")
def status(bulk_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    operation = db.scalar(
        select(VideoBulkOperation).where(
            VideoBulkOperation.id == bulk_id, VideoBulkOperation.owner_id == owner.id
        )
    )
    if operation is None:
        raise HTTPException(404, "Video bulk operation was not found.")
    counts = _sync(db, operation)
    children = list(
        db.scalars(
            select(VideoBulkChild)
            .where(VideoBulkChild.bulk_id == bulk_id)
            .order_by(VideoBulkChild.created_at)
        )
    )
    db.commit()
    return {
        "id": operation.id,
        "status": operation.status,
        "total_outputs": operation.total_children,
        "counts": counts,
        "progress_percentage": round(
            100
            * sum(
                counts.get(value, 0)
                for value in {"succeeded", "needs_review", "failed", "cancelled", "stale"}
            )
            / max(1, operation.total_children),
            2,
        ),
        "children": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "video_type": item.video_type,
                "target_channel": item.target_channel,
                "generation_id": item.generation_id,
                "output_id": item.output_id,
                "status": item.status,
                "retryable": item.retryable,
                "failure_code": item.failure_code,
                "safe_error_message": item.safe_error_message,
            }
            for item in children
        ],
    }


@router.post("/{bulk_id}/retry")
def retry(
    bulk_id: uuid.UUID, data: VideoBulkRetryRequest, db: DB, owner: Owner
) -> dict[str, object]:
    operation = db.scalar(
        select(VideoBulkOperation).where(
            VideoBulkOperation.id == bulk_id, VideoBulkOperation.owner_id == owner.id
        )
    )
    if operation is None:
        raise HTTPException(404, "Video bulk operation was not found.")
    selected = set(data.child_ids)
    rows = list(
        db.scalars(
            select(VideoBulkChild).where(
                VideoBulkChild.bulk_id == bulk_id, VideoBulkChild.owner_id == owner.id
            )
        )
    )
    retried = 0
    for child in rows:
        if selected and child.id not in selected or child.status != "failed" or not child.retryable:
            continue
        child.status = "retry_wait"
        child.updated_at = _now()
        retried += 1
    db.commit()
    return {
        "bulk_id": bulk_id,
        "retried_count": retried,
        "status": "queued" if retried else operation.status,
    }


@router.post("/{bulk_id}/cancel")
def cancel(
    bulk_id: uuid.UUID, data: VideoBulkCancelRequest, db: DB, owner: Owner
) -> dict[str, object]:
    operation = db.scalar(
        select(VideoBulkOperation).where(
            VideoBulkOperation.id == bulk_id, VideoBulkOperation.owner_id == owner.id
        )
    )
    if operation is None:
        raise HTTPException(404, "Video bulk operation was not found.")
    selected = set(data.child_ids)
    rows = list(
        db.scalars(
            select(VideoBulkChild).where(
                VideoBulkChild.bulk_id == bulk_id, VideoBulkChild.owner_id == owner.id
            )
        )
    )
    cancelled = 0
    for child in rows:
        if selected and child.id not in selected or child.status not in {"queued", "retry_wait"}:
            continue
        child.status = "cancelled"
        child.cancellation_requested = True
        cancelled += 1
    if not selected:
        operation.cancellation_requested = True
    db.commit()
    return {"bulk_id": bulk_id, "cancelled_count": cancelled, "status": operation.status}
