from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product
from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
from vayujit_api.video.models import VIDEO_TYPES, VideoGeneration, VideoOutput, VideoUsage
from vayujit_api.video.schemas import VideoQueueRequest, VideoType
from vayujit_api.video.service import preview as video_preview
from vayujit_api.video.service import queue

BULK_LIMITS = {
    "max_products": 50,
    "max_video_types": 12,
    "max_targets": 6,
    "max_outputs": 60,
    "max_source_media": 5,
    "max_duration_seconds": 60,
    "max_concurrent_active_children": 20,
    "max_expected_output_bytes": 480_000_000,
}
ALLOWED_TARGETS = {"youtube", "instagram", "facebook", "amazon", "flipkart", "meesho", "campaign"}
TRANSIENT_FAILURES = {
    "ai.video.provider_unavailable",
    "ai.video.throttled",
    "ai.video.timeout",
    "unknown_transient",
}
TERMINAL_CHILD_STATES = {"succeeded", "failed", "stale", "cancelled"}


class VideoBulkRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    video_types: list[str] = Field(min_length=1, max_length=12)
    targets: list[str] = Field(min_length=1, max_length=6)
    duration_seconds: int = Field(default=10, ge=1, le=60)
    resolution: str = Field(default="320x240", pattern=r"^\d{3,4}x\d{3,4}$")
    idempotency_key: str = Field(min_length=1, max_length=160)
    preview_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    plan_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    confirm: bool = False
    source_media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
    source_media_by_product: dict[str, list[uuid.UUID]] = Field(default_factory=dict, max_length=50)
    script_id: uuid.UUID | None = None
    script_version: int | None = Field(default=None, ge=1)
    storyboard_id: uuid.UUID | None = None
    storyboard_version: int | None = Field(default=None, ge=1)
    style_id: uuid.UUID | None = None
    style_version: int | None = Field(default=None, ge=1)
    preset_id: uuid.UUID | None = None
    preset_version: int | None = Field(default=None, ge=1)
    failure_scenarios: dict[str, str] = Field(default_factory=dict, max_length=300)
    failure_scenario: str | None = Field(default=None, max_length=80)


class VideoBulkRetryRequest(BaseModel):
    child_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=160)


class VideoBulkCancelRequest(BaseModel):
    child_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=160)


DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]
router = APIRouter(prefix="/api/v1/ai/video/bulk", tags=["ai-video-bulk"])


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_detail(error: HTTPException) -> str:
    return (
        error.detail
        if isinstance(error.detail, str)
        else "The requested Bulk Video plan is not valid."
    )


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _child_key(
    owner_id: uuid.UUID,
    bulk_id: uuid.UUID,
    product_id: uuid.UUID,
    video_type: str,
    target: str,
    data: VideoBulkRequest,
    ordinal: int,
) -> str:
    semantic = {
        "owner": str(owner_id),
        "parent": str(bulk_id),
        "product": str(product_id),
        "type": video_type,
        "target": target,
        "script": [str(data.script_id) if data.script_id else None, data.script_version],
        "storyboard": [
            str(data.storyboard_id) if data.storyboard_id else None,
            data.storyboard_version,
        ],
        "style": [str(data.style_id) if data.style_id else None, data.style_version],
        "preset": [str(data.preset_id) if data.preset_id else None, data.preset_version],
        "ordinal": ordinal,
    }
    return hashlib.sha256(_json(semantic).encode()).hexdigest()


def _source_media(data: VideoBulkRequest, product_id: uuid.UUID) -> list[uuid.UUID]:
    values = data.source_media_by_product.get(str(product_id), data.source_media_ids)
    if len(values) > BULK_LIMITS["max_source_media"]:
        raise HTTPException(422, "Bulk Video source Media count exceeds the safe limit.")
    return values


def _validate_limits(data: VideoBulkRequest) -> None:
    total = len(data.product_ids) * len(data.video_types) * len(data.targets)
    if (
        len(set(data.product_ids)) != len(data.product_ids)
        or len(set(data.video_types)) != len(data.video_types)
        or len(set(data.targets)) != len(data.targets)
    ):
        raise HTTPException(
            422, "Bulk Video selections must be unique and within the configured safe limit."
        )
    if (
        len(data.product_ids) > BULK_LIMITS["max_products"]
        or len(data.video_types) > BULK_LIMITS["max_video_types"]
        or len(data.targets) > BULK_LIMITS["max_targets"]
        or total > BULK_LIMITS["max_outputs"]
    ):
        raise HTTPException(422, "Bulk Video workload exceeds the configured safe limit.")
    if any(value not in VIDEO_TYPES for value in data.video_types):
        raise HTTPException(422, "One or more Video types are unsupported.")
    if any(value not in ALLOWED_TARGETS for value in data.targets):
        raise HTTPException(422, "One or more Bulk Video targets are unsupported.")
    try:
        width, height = (int(value) for value in data.resolution.lower().split("x"))
    except (ValueError, TypeError):
        raise HTTPException(422, "Video resolution is invalid.") from None
    if width < 240 or height < 240 or width > 3840 or height > 3840:
        raise HTTPException(422, "Video resolution is outside safe limits.")
    if (
        total * max(width * height * data.duration_seconds // 8, 25_000)
        > BULK_LIMITS["max_expected_output_bytes"]
    ):
        raise HTTPException(422, "Bulk Video expected storage exceeds the safe limit.")


def _owned_products(db: Session, owner: User, ids: list[uuid.UUID]) -> list[Product]:
    products = list(
        db.scalars(select(Product).where(Product.owner_id == owner.id, Product.id.in_(ids)))
    )
    by_id = {row.id: row for row in products}
    if len(by_id) != len(ids):
        raise HTTPException(404, "One or more Products were not found.")
    for product in products:
        if str(getattr(product.status, "value", product.status)) == "archived":
            raise HTTPException(409, "Archived Products cannot be used for Bulk Video generation.")
    return [by_id[item] for item in ids]


def _plan(db: Session, owner: User, data: VideoBulkRequest) -> dict[str, Any]:
    _validate_limits(data)
    products = _owned_products(db, owner, data.product_ids)
    children: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    warnings = ["Generated Videos remain pending review; no downstream connector is called."]
    ordinal = 0
    for product in products:
        media_ids = _source_media(data, product.id)
        for video_type in data.video_types:
            for target in data.targets:
                ordinal += 1
                request = VideoQueueRequest(
                    product_id=product.id,
                    brand_id=product.brand_id,
                    video_type=cast(VideoType, video_type),
                    target_channel=target,
                    duration_seconds=data.duration_seconds,
                    resolution=data.resolution,
                    source_media_ids=media_ids,
                    script_id=data.script_id,
                    script_version=data.script_version,
                    storyboard_id=data.storyboard_id,
                    storyboard_version=data.storyboard_version,
                    style_id=data.style_id,
                    style_version=data.style_version,
                    preset_id=data.preset_id,
                    preset_version=data.preset_version,
                    idempotency_key=f"preview:{ordinal}",
                    failure_scenario="success",
                )
                try:
                    detail = video_preview(db, owner, request)
                except HTTPException as error:
                    blockers.append(
                        {
                            "code": "invalid_child",
                            "message": _safe_detail(error),
                            "product_id": str(product.id),
                        }
                    )
                    detail = {
                        "context_fingerprint": None,
                        "source_media_ids": [str(value) for value in media_ids],
                    }
                child = {
                    "ordinal": ordinal,
                    "product_id": str(product.id),
                    "brand_id": str(product.brand_id),
                    "video_type": video_type,
                    "target_channel": target,
                    "source_media_ids": list(cast(list[str], detail.get("source_media_ids") or [])),
                    "script_id": str(data.script_id) if data.script_id else None,
                    "script_version": detail.get("script_version", data.script_version),
                    "storyboard_id": str(data.storyboard_id) if data.storyboard_id else None,
                    "storyboard_version": detail.get("storyboard_version", data.storyboard_version),
                    "style_id": str(data.style_id) if data.style_id else None,
                    "style_version": detail.get("style_version", data.style_version),
                    "preset_id": str(data.preset_id) if data.preset_id else None,
                    "context_fingerprint": detail.get("context_fingerprint"),
                }
                child["semantic_key"] = hashlib.sha256(_json(child).encode()).hexdigest()
                children.append(child)
    snapshot = {
        "products": [str(value) for value in data.product_ids],
        "video_types": data.video_types,
        "targets": data.targets,
        "duration_seconds": data.duration_seconds,
        "resolution": data.resolution,
        "source_media_ids": [str(value) for value in data.source_media_ids],
        "source_media_by_product": {
            key: [str(value) for value in values]
            for key, values in data.source_media_by_product.items()
        },
        "script_id": str(data.script_id) if data.script_id else None,
        "script_version": data.script_version,
        "storyboard_id": str(data.storyboard_id) if data.storyboard_id else None,
        "storyboard_version": data.storyboard_version,
        "style_id": str(data.style_id) if data.style_id else None,
        "style_version": data.style_version,
        "preset_id": str(data.preset_id) if data.preset_id else None,
        "preset_version": data.preset_version,
        "children": children,
    }
    fingerprint = hashlib.sha256(_json(snapshot).encode()).hexdigest()
    return {
        "operation": "video_bulk_generation",
        "product_count": len(products),
        "video_type_count": len(data.video_types),
        "target_count": len(data.targets),
        "total_outputs": len(children),
        "estimated_provider_calls": len(children),
        "estimated_bytes": min(
            BULK_LIMITS["max_expected_output_bytes"], len(children) * 25_000_000
        ),
        "provider": "deterministic_video_local",
        "model": "local-slideshow-v1",
        "products": [str(value.id) for value in products],
        "video_types": list(data.video_types),
        "targets": list(data.targets),
        "children": children,
        "blockers": blockers,
        "warnings": warnings,
        "informational": ["Cost is unavailable because no live provider is configured."],
        "limits": BULK_LIMITS,
        "operation_limits": BULK_LIMITS,
        "plan_fingerprint": fingerprint,
        "preview_fingerprint": fingerprint,
        "request_snapshot": snapshot,
    }


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
        if child.cancellation_requested:
            child.status = "cancelled"
            continue
        generation = db.get(VideoGeneration, child.generation_id) if child.generation_id else None
        if generation is None:
            continue
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation.id))
        child.output_id = (
            output.id if output and output.checksum_sha256 != "pending" else child.output_id
        )
        child.failure_code = generation.failure_code
        child.safe_error_message = generation.safe_error_message
        child.retryable = bool(
            generation.status == "retry_wait" or generation.failure_code in TRANSIENT_FAILURES
        )
        child.recovery_state = (
            "retryable"
            if child.retryable
            else ("terminal" if generation.status in {"failed", "stale"} else "none")
        )
        child.failure_category = (
            "transient"
            if child.retryable
            else ("permanent" if generation.status in {"failed", "stale"} else None)
        )
        child.status = {
            "queued": "queued",
            "generating": "generating",
            "rendering": "generating",
            "validating": "validating",
            "retry_wait": "retry_wait",
            "succeeded": "succeeded",
            "needs_review": "succeeded",
            "failed": "failed",
            "stale": "stale",
            "cancelled": "cancelled",
        }.get(generation.status, "queued")
        if child.status != "queued" and child.started_at is None:
            child.started_at = generation.created_at
        if child.status in TERMINAL_CHILD_STATES:
            child.completed_at = child.completed_at or generation.completed_at or _now()
        child.updated_at = _now()
    counts = _counts(db, operation.id)
    terminal = sum(counts.get(state, 0) for state in TERMINAL_CHILD_STATES)
    operation.requested_child_count = operation.total_children
    operation.completed_count = terminal
    operation.succeeded_count = counts.get("succeeded", 0)
    operation.retry_wait_count = counts.get("retry_wait", 0)
    operation.failed_count = counts.get("failed", 0)
    operation.stale_count = counts.get("stale", 0)
    operation.cancelled_count = counts.get("cancelled", 0)
    if terminal < operation.total_children:
        operation.status = (
            "queued" if counts.get("queued", 0) == operation.total_children else "running"
        )
    elif counts.get("cancelled", 0) == operation.total_children:
        operation.status = "cancelled"
    elif counts.get("failed", 0) or counts.get("stale", 0):
        operation.status = "partial_success" if counts.get("succeeded", 0) else "failed"
    else:
        operation.status = "succeeded"
    if operation.status != "queued" and operation.started_at is None:
        operation.started_at = _now()
    if terminal == operation.total_children and operation.completed_at is None:
        operation.completed_at = _now()
    operation.updated_at = _now()
    return counts


def _operation(db: Session, owner: User, bulk_id: uuid.UUID) -> VideoBulkOperation:
    operation = db.scalar(
        select(VideoBulkOperation).where(
            VideoBulkOperation.id == bulk_id, VideoBulkOperation.owner_id == owner.id
        )
    )
    if operation is None:
        raise HTTPException(404, "Video bulk operation was not found.")
    return operation


def _child_response(item: VideoBulkChild) -> dict[str, object]:
    return {
        "id": item.id,
        "child_id": item.id,
        "product_id": item.product_id,
        "brand_id": item.brand_id,
        "video_type": item.video_type,
        "target_channel": item.target_channel,
        "output_ordinal": item.output_ordinal,
        "script_id": item.script_id,
        "script_version": item.script_version,
        "storyboard_id": item.storyboard_id,
        "storyboard_version": item.storyboard_version,
        "style_id": item.style_id,
        "style_version": item.style_version,
        "preset_id": item.preset_id,
        "preset_version": item.preset_version,
        "source_media_ids": list(item.source_media_ids_json or []),
        "context_fingerprint": item.context_fingerprint,
        "generation_id": item.generation_id,
        "job_id": item.job_id,
        "output_id": item.output_id,
        "status": item.status,
        "retryable": item.retryable,
        "retry_count": item.retry_count,
        "failure_code": item.failure_code,
        "failure_category": item.failure_category,
        "recovery_state": item.recovery_state,
        "safe_error_message": item.safe_error_message,
        "correlation_id": item.correlation_id,
    }


def _response(
    db: Session, operation: VideoBulkOperation, counts: dict[str, int]
) -> dict[str, object]:
    children = list(
        db.scalars(
            select(VideoBulkChild)
            .where(VideoBulkChild.bulk_id == operation.id)
            .order_by(VideoBulkChild.output_ordinal, VideoBulkChild.created_at)
        )
    )
    return {
        "id": operation.id,
        "operation_id": operation.id,
        "status": operation.status,
        "total_outputs": operation.total_children,
        "child_count": operation.total_children,
        "counts": counts,
        "completed_count": operation.completed_count,
        "succeeded_count": operation.succeeded_count,
        "retry_wait_count": operation.retry_wait_count,
        "failed_count": operation.failed_count,
        "stale_count": operation.stale_count,
        "cancelled_count": operation.cancelled_count,
        "progress_percentage": round(
            100 * operation.completed_count / max(1, operation.total_children), 2
        ),
        "correlation_id": operation.correlation_id,
        "plan_fingerprint": operation.plan_fingerprint,
        "status_url": f"/api/v1/ai/video/bulk/{operation.id}",
        "children": [_child_response(item) for item in children],
    }


@router.post("/preview")
def preview(data: VideoBulkRequest, db: DB, owner: Owner) -> dict[str, object]:
    plan = _plan(db, owner, data)
    plan["ready"] = not bool(plan["blockers"])
    record_event(
        db,
        actor_id=owner.id,
        action="video_bulk_previewed",
        entity_type="video_bulk_plan",
        entity_id=uuid.uuid4(),
        metadata={
            "total_outputs": plan["total_outputs"],
            "plan_fingerprint": plan["plan_fingerprint"],
        },
    )
    db.commit()
    return plan


@router.post("", status_code=202)
def enqueue(data: VideoBulkRequest, db: DB, owner: Owner) -> dict[str, object]:
    plan = _plan(db, owner, data)
    supplied = data.preview_fingerprint or data.plan_fingerprint
    if plan["blockers"]:
        raise HTTPException(409, "Bulk Video preview contains blockers.")
    if supplied is not None and (not data.confirm or supplied != plan["plan_fingerprint"]):
        raise HTTPException(
            409, "Bulk Video preview is stale; confirm the exact current fingerprint."
        )
    if data.confirm and supplied is None:
        raise HTTPException(
            422, "Explicit Bulk Video confirmation requires the preview fingerprint."
        )
    existing = db.scalar(
        select(VideoBulkOperation).where(
            VideoBulkOperation.owner_id == owner.id,
            VideoBulkOperation.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        if supplied is not None and existing.plan_fingerprint != supplied:
            raise HTTPException(
                409, "Idempotency key is already bound to a different Bulk Video plan."
            )
        counts = _sync(db, existing)
        db.commit()
        return {
            **_response(db, existing, counts),
            "idempotent_reuse": True,
            "total_outputs": existing.total_children,
        }
    stamp = _now()
    operation = VideoBulkOperation(
        owner_id=owner.id,
        created_by=owner.id,
        idempotency_key=data.idempotency_key,
        product_ids_json=[str(value) for value in data.product_ids],
        video_types_json=list(data.video_types),
        targets_json=list(data.targets),
        total_children=int(plan["total_outputs"]),
        requested_product_count=len(data.product_ids),
        requested_child_count=int(plan["total_outputs"]),
        plan_fingerprint=str(plan["plan_fingerprint"]),
        preview_fingerprint=str(plan["preview_fingerprint"]),
        request_snapshot_json=cast(dict[str, object], plan["request_snapshot"]),
        correlation_id=uuid.uuid4().hex[:32],
        status="queued",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(operation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(VideoBulkOperation).where(
                VideoBulkOperation.owner_id == owner.id,
                VideoBulkOperation.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        if existing.plan_fingerprint != plan["plan_fingerprint"]:
            raise HTTPException(
                409, "Idempotency key is already bound to a different Bulk Video plan."
            ) from None
        counts = _sync(db, existing)
        db.commit()
        return {
            **_response(db, existing, counts),
            "idempotent_reuse": True,
            "total_outputs": existing.total_children,
        }
    for planned in cast(list[dict[str, Any]], plan["children"]):
        product_id = uuid.UUID(str(planned["product_id"]))
        ordinal = int(planned["ordinal"])
        child = VideoBulkChild(
            owner_id=owner.id,
            bulk_id=operation.id,
            product_id=product_id,
            brand_id=uuid.UUID(str(planned["brand_id"])),
            video_type=str(planned["video_type"]),
            target_channel=str(planned["target_channel"]),
            child_key=_child_key(
                owner.id,
                operation.id,
                product_id,
                str(planned["video_type"]),
                str(planned["target_channel"]),
                data,
                ordinal,
            ),
            output_ordinal=ordinal,
            script_id=data.script_id,
            script_version=cast(int | None, planned.get("script_version")),
            storyboard_id=data.storyboard_id,
            storyboard_version=cast(int | None, planned.get("storyboard_version")),
            style_id=data.style_id,
            style_version=cast(int | None, planned.get("style_version")),
            preset_id=data.preset_id,
            preset_version=data.preset_version,
            source_media_ids_json=cast(list[str], planned.get("source_media_ids") or []),
            context_fingerprint=cast(str | None, planned.get("context_fingerprint")),
            correlation_id=operation.correlation_id,
            failure_scenario=data.failure_scenarios.get(str(ordinal))
            or data.failure_scenarios.get(
                f"{planned['product_id']}:{planned['target_channel']}:{planned['video_type']}"
            )
            or data.failure_scenario,
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
                    product_id=product_id,
                    brand_id=cast(uuid.UUID, child.brand_id),
                    video_type=cast(VideoType, child.video_type),
                    target_channel=child.target_channel,
                    duration_seconds=data.duration_seconds,
                    resolution=data.resolution,
                    source_media_ids=[uuid.UUID(value) for value in child.source_media_ids_json],
                    script_id=child.script_id,
                    script_version=child.script_version,
                    storyboard_id=child.storyboard_id,
                    storyboard_version=child.storyboard_version,
                    style_id=child.style_id,
                    style_version=child.style_version,
                    preset_id=child.preset_id,
                    preset_version=child.preset_version,
                    failure_scenario=child.failure_scenario or "success",
                    idempotency_key=f"video-bulk:{operation.id}:{child.child_key}",
                ),
            )
            child.generation_id = cast(uuid.UUID, generation["id"])
            generation_row = db.get(VideoGeneration, child.generation_id)
            child.correlation_id = (
                generation_row.correlation_id if generation_row else child.correlation_id
            )
            if generation_row:
                child.context_fingerprint = generation_row.context_fingerprint
                job = db.scalar(
                    select(AIStudioJob).where(
                        AIStudioJob.owner_id == owner.id,
                        AIStudioJob.payload_json["video_generation_id"].as_string()
                        == str(generation_row.id),
                    )
                )
                if job:
                    child.job_id = job.id
        except HTTPException as error:
            child.status = "failed"
            child.retryable = False
            child.failure_category = "permanent"
            child.recovery_state = "terminal"
            child.failure_code = "video.bulk_child_invalid"
            child.safe_error_message = _safe_detail(error)
        record_event(
            db,
            actor_id=owner.id,
            action="video_bulk_child_queued",
            entity_type="video_bulk_child",
            entity_id=child.id,
            metadata={"bulk_id": str(operation.id), "ordinal": ordinal},
        )
    counts = _sync(db, operation)
    record_event(
        db,
        actor_id=owner.id,
        action="video_bulk_created",
        entity_type="video_bulk_operation",
        entity_id=operation.id,
        metadata={
            "total_children": operation.total_children,
            "correlation_id": operation.correlation_id,
        },
    )
    db.commit()
    return {
        **_response(db, operation, counts),
        "idempotent_reuse": False,
        "queued_count": counts.get("queued", 0),
        "total_outputs": operation.total_children,
    }


@router.get("/{bulk_id}")
def status(bulk_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    counts = _sync(db, operation)
    db.commit()
    return _response(db, operation, counts)


@router.post("/{bulk_id}/retry")
@router.post("/{bulk_id}/retry-failed")
def retry(
    bulk_id: uuid.UUID, data: VideoBulkRetryRequest, db: DB, owner: Owner
) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    _sync(db, operation)
    selected = set(data.child_ids)
    rows = list(
        db.scalars(
            select(VideoBulkChild)
            .where(VideoBulkChild.bulk_id == bulk_id, VideoBulkChild.owner_id == owner.id)
            .with_for_update()
        )
    )
    retried = 0
    skipped = 0
    for child in rows:
        if selected and child.id not in selected:
            continue
        if child.status != "failed" or not child.retryable:
            skipped += 1
            continue
        generation = db.get(VideoGeneration, child.generation_id)
        job = db.get(AIStudioJob, child.job_id) if child.job_id else None
        if generation is None or job is None:
            skipped += 1
            continue
        generation.status = "retry_wait"
        generation.available_at = _now()
        generation.updated_at = _now()
        job.state = "retry_wait"
        job.available_at = _now()
        job.updated_at = _now()
        job.lease_owner = None
        job.lease_expires_at = None
        child.status = "retry_wait"
        child.retry_count += 1
        child.recovery_state = "retry_scheduled"
        child.updated_at = _now()
        retried += 1
        record_event(
            db,
            actor_id=owner.id,
            action="video_bulk_child_retried",
            entity_type="video_bulk_child",
            entity_id=child.id,
            metadata={"bulk_id": str(bulk_id), "retry_count": child.retry_count},
        )
    counts = _sync(db, operation)
    db.commit()
    return {
        "bulk_id": bulk_id,
        "retried_count": retried,
        "skipped_count": skipped,
        "status": operation.status,
        "counts": counts,
        "idempotent_reuse": retried == 0 and bool(selected),
    }


@router.post("/{bulk_id}/cancel")
@router.post("/{bulk_id}/cancel-remaining")
def cancel(
    bulk_id: uuid.UUID, data: VideoBulkCancelRequest, db: DB, owner: Owner
) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    selected = set(data.child_ids)
    rows = list(
        db.scalars(
            select(VideoBulkChild)
            .where(VideoBulkChild.bulk_id == bulk_id, VideoBulkChild.owner_id == owner.id)
            .with_for_update()
        )
    )
    cancelled = 0
    for child in rows:
        if selected and child.id not in selected:
            continue
        if child.status not in {"queued", "generating", "validating", "retry_wait"}:
            continue
        generation = db.get(VideoGeneration, child.generation_id)
        job = db.get(AIStudioJob, child.job_id) if child.job_id else None
        child.status = "cancelled"
        child.cancellation_requested = True
        child.updated_at = _now()
        if generation and generation.status not in {"succeeded", "cancelled"}:
            generation.status = "cancelled"
            generation.completed_at = _now()
            generation.updated_at = _now()
        if job and job.state not in {"succeeded", "cancelled"}:
            job.state = "cancelled"
            job.lease_owner = None
            job.lease_expires_at = None
            job.completed_at = _now()
            job.updated_at = _now()
        record_event(
            db,
            actor_id=owner.id,
            action="video_bulk_child_cancelled",
            entity_type="video_bulk_child",
            entity_id=child.id,
            metadata={"bulk_id": str(bulk_id)},
        )
        cancelled += 1
    if not selected and not operation.cancellation_requested:
        operation.cancellation_requested = True
        record_event(
            db,
            actor_id=owner.id,
            action="video_bulk_cancel_remaining",
            entity_type="video_bulk_operation",
            entity_id=operation.id,
            metadata={"cancelled_count": cancelled},
        )
    counts = _sync(db, operation)
    db.commit()
    return {
        "bulk_id": bulk_id,
        "cancelled_count": cancelled,
        "status": operation.status,
        "counts": counts,
        "idempotent_reuse": cancelled == 0,
    }


@router.get("/{bulk_id}/history")
def history(bulk_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    operation = _operation(db, owner, bulk_id)
    child_ids = list(
        db.scalars(select(VideoBulkChild.id).where(VideoBulkChild.bulk_id == operation.id))
    )
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_id.in_([operation.id, *child_ids]))
        .order_by(AuditEvent.occurred_at)
    ).all()
    return [
        {
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "timestamp": event.occurred_at,
            "correlation_id": event.correlation_id,
        }
        for event in events
    ]


@router.get("/{bulk_id}/usage")
def usage(bulk_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    generation_ids = list(
        db.scalars(
            select(VideoBulkChild.generation_id).where(
                VideoBulkChild.bulk_id == operation.id, VideoBulkChild.generation_id.is_not(None)
            )
        )
    )
    rows = (
        list(db.scalars(select(VideoUsage).where(VideoUsage.generation_id.in_(generation_ids))))
        if generation_ids
        else []
    )
    return {
        "bulk_id": operation.id,
        "modality": "video",
        "child_count": operation.total_children,
        "provider_calls": sum(row.provider_calls for row in rows),
        "output_bytes": sum(row.output_bytes for row in rows),
        "retries": operation.retry_wait_count,
        "successes": operation.succeeded_count,
        "failures": operation.failed_count + operation.stale_count,
        "cost_status": "unavailable",
        "latency_ms": sum(row.latency_ms or 0 for row in rows) or None,
    }


@router.get("/{bulk_id}/diagnostics")
def diagnostics(bulk_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    counts = _sync(db, operation)
    db.commit()
    return {
        "bulk_id": operation.id,
        "parent_status": operation.status,
        "counts": counts,
        "parent_count": 1,
        "active_parents": int(operation.status in {"queued", "running"}),
        "duplicate_prevention_count": 0,
        "provider_health": {
            "provider": "deterministic_video_local",
            "status": "healthy",
            "live": False,
        },
    }


@router.get("/{bulk_id}/outputs")
def outputs(bulk_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    operation = _operation(db, owner, bulk_id)
    _sync(db, operation)
    children = list(
        db.scalars(
            select(VideoBulkChild)
            .where(VideoBulkChild.bulk_id == operation.id)
            .order_by(VideoBulkChild.output_ordinal)
        )
    )
    return [_child_response(child) for child in children if child.output_id]
