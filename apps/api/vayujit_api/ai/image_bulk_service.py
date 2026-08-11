"""Durable bulk image orchestration on the shared AI Studio job runtime."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.bulk_service import _sync_operation, cancel_outputs, retry_outputs
from vayujit_api.ai.image_models import (
    AIImageGeneration,
    AIImageOutput,
    AIImagePreset,
    AIImageStyle,
)
from vayujit_api.ai.image_provider import image_provider
from vayujit_api.ai.image_schemas import (
    ImageBulkOutputResponse,
    ImageBulkPreviewResponse,
    ImageBulkProductPlan,
    ImageBulkRequest,
    ImageBulkStatusResponse,
    ImageGenerateRequest,
)
from vayujit_api.ai.image_service import queue_generation
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product

IMAGE_BULK_LIMITS = {
    "max_products": 50,
    "max_channels": 6,
    "max_output_count_per_product": 8,
    "max_total_outputs": 300,
    "max_instruction_length": 2000,
    "max_dimension": 4096,
}
SOURCE_REQUIRED_OPERATIONS = {
    "remove_background",
    "replace_background",
    "enhance_image",
    "resize",
    "crop",
    "extend_canvas",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(data: ImageBulkRequest) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, default=str).encode()
    ).hexdigest()


def _product(db: Session, owner_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    value = db.scalar(select(Product).where(Product.id == product_id, Product.owner_id == owner_id))
    if value is None:
        raise HTTPException(404, "Product not found.")
    return value


def _style_preset(
    db: Session, owner: User, data: ImageBulkRequest
) -> tuple[AIImageStyle | None, AIImagePreset | None]:
    style = None
    if data.style_id:
        style = db.scalar(
            select(AIImageStyle).where(
                AIImageStyle.id == data.style_id,
                AIImageStyle.owner_id == owner.id,
                AIImageStyle.archived.is_(False),
            )
        )
        if style is None:
            raise HTTPException(404, "Image style not found.")
    preset = None
    if data.preset_id:
        preset = db.scalar(
            select(AIImagePreset).where(
                AIImagePreset.id == data.preset_id,
                AIImagePreset.owner_id == owner.id,
            )
        )
        if preset is None:
            raise HTTPException(404, "Image preset not found.")
        if preset.operation != data.operation or (
            preset.channel and preset.channel not in data.channels
        ):
            raise HTTPException(
                422,
                "The selected Image preset is incompatible with this bulk operation.",
            )
    return style, preset


def _validate_limits(data: ImageBulkRequest) -> None:
    if len(data.product_ids) > IMAGE_BULK_LIMITS["max_products"]:
        raise HTTPException(422, "Bulk image generation exceeds the Product limit.")
    if len(data.channels) > IMAGE_BULK_LIMITS["max_channels"]:
        raise HTTPException(422, "Bulk image generation exceeds the channel limit.")
    if data.output_count_per_product > IMAGE_BULK_LIMITS["max_output_count_per_product"]:
        raise HTTPException(422, "Bulk image generation exceeds the output-count limit.")
    total = len(data.product_ids) * len(data.channels) * data.output_count_per_product
    if total > IMAGE_BULK_LIMITS["max_total_outputs"]:
        raise HTTPException(422, "Bulk image generation exceeds the total output limit.")
    if data.instructions and len(data.instructions) > IMAGE_BULK_LIMITS["max_instruction_length"]:
        raise HTTPException(422, "Bulk image instructions exceed the safe size limit.")
    if max(data.width, data.height) > IMAGE_BULK_LIMITS["max_dimension"]:
        raise HTTPException(422, "Bulk image dimensions exceed the safe limit.")
    if data.provider != "deterministic_mock_v1":
        raise HTTPException(
            409,
            "Bulk Image Studio currently requires the local deterministic provider.",
        )
    try:
        image_provider.validate_operation(data.operation)
    except Exception as exc:
        raise HTTPException(
            422, "The selected image operation is not supported by the provider."
        ) from exc


def _source_ids(
    db: Session,
    owner: User,
    product_id: uuid.UUID,
    data: ImageBulkRequest,
) -> tuple[list[uuid.UUID], list[str]]:
    raw = data.source_media_by_product.get(str(product_id), [])
    ids = list(dict.fromkeys(raw))
    blockers: list[str] = []
    if (
        data.source_media_strategy == "selected"
        and data.operation in SOURCE_REQUIRED_OPERATIONS
        and not ids
    ):
        blockers.append("Select at least one source Media asset.")
    if data.operation == "replace_background" and len(ids) < 2:
        blockers.append("Background replacement requires two source Media assets.")
    if ids:
        rows = list(
            db.scalars(
                select(MediaAsset).where(
                    MediaAsset.owner_id == owner.id,
                    MediaAsset.id.in_(ids),
                    MediaAsset.status == "ready",
                )
            )
        )
        if len(rows) != len(ids):
            blockers.append("One or more selected source Media assets are unavailable.")
    return ids, blockers


def _plans(
    db: Session, owner: User, data: ImageBulkRequest, style: AIImageStyle | None
) -> tuple[list[ImageBulkProductPlan], list[str], list[str]]:
    plans: list[ImageBulkProductPlan] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for product_id in data.product_ids:
        product = _product(db, owner.id, product_id)
        source_ids, source_blockers = _source_ids(db, owner, product_id, data)
        product_blockers = list(source_blockers)
        product_warnings: list[str] = []
        if product.status != "active":
            product_warnings.append("Product is not active.")
        if style and style.brand_id != product.brand_id:
            product_blockers.append("Image Style does not belong to this Product Brand.")
        plans.append(
            ImageBulkProductPlan(
                product_id=product.id,
                product_name=product.name,
                source_media_ids=source_ids,
                source_media_count=len(source_ids),
                blockers=product_blockers,
                warnings=product_warnings,
            )
        )
        blockers.extend(f"{product.name}: {item}" for item in product_blockers)
        warnings.extend(f"{product.name}: {item}" for item in product_warnings)
    return plans, blockers, warnings


def preview_image_bulk(
    db: Session, owner: User, data: ImageBulkRequest
) -> ImageBulkPreviewResponse:
    _validate_limits(data)
    style, preset = _style_preset(db, owner, data)
    plans, blockers, warnings = _plans(db, owner, data, style)
    total = len(data.product_ids) * len(data.channels) * data.output_count_per_product
    return ImageBulkPreviewResponse(
        product_count=len(data.product_ids),
        channel_count=len(data.channels),
        operation=data.operation,
        channels=list(data.channels),
        output_count_per_product=data.output_count_per_product,
        total_outputs=total,
        products=plans,
        style_id=style.id if style else None,
        style_version=style.version if style else None,
        preset_id=preset.id if preset else None,
        preset_version=preset.version if preset else None,
        provider=data.provider,
        model=data.model,
        aspect_ratio=data.aspect_ratio,
        width=data.width,
        height=data.height,
        estimated_provider_calls=total,
        estimated_cost="unavailable",
        blockers=blockers,
        warnings=warnings,
        source_strategy=data.source_media_strategy,
    )


def create_image_bulk(db: Session, owner: User, data: ImageBulkRequest) -> AIStudioBulkOperation:
    _validate_limits(data)
    key = data.idempotency_key or f"image-bulk:{_fingerprint(data)}"
    existing = db.scalar(
        select(AIStudioBulkOperation).where(
            AIStudioBulkOperation.owner_id == owner.id,
            AIStudioBulkOperation.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing
    preview = preview_image_bulk(db, owner, data)
    if preview.blockers:
        raise HTTPException(422, "Bulk image plan has validation blockers.")
    style, preset = _style_preset(db, owner, data)
    stamp = _now()
    operation = AIStudioBulkOperation(
        owner_id=owner.id,
        created_by=owner.id,
        idempotency_key=key,
        locale="en-IN",
        provider_key=data.provider,
        model=data.model,
        instructions_fingerprint=hashlib.sha256((data.instructions or "").encode()).hexdigest(),
        product_count=preview.product_count,
        channel_count=preview.channel_count,
        content_type_count=1,
        total_outputs=preview.total_outputs,
        status="queued",
        correlation_id=uuid.uuid4().hex[:32],
        cancellation_requested=False,
        completion_summary_json={"channels": list(data.channels)},
        created_at=stamp,
        updated_at=stamp,
        modality="image",
        image_operation=data.operation,
        image_style_id=style.id if style else None,
        image_style_version=style.version if style else None,
        image_preset_id=preset.id if preset else None,
        image_preset_version=preset.version if preset else None,
        image_width=data.width,
        image_height=data.height,
        image_aspect_ratio=data.aspect_ratio,
        image_output_count=data.output_count_per_product,
        source_strategy=data.source_media_strategy,
        source_media_by_product_json={
            str(plan.product_id): [str(value) for value in plan.source_media_ids]
            for plan in preview.products
        },
        content_artifact_by_product_json=data.content_artifact_by_product,
    )
    db.add(operation)
    db.flush()
    output_index = 0
    for plan in preview.products:
        product = _product(db, owner.id, plan.product_id)
        artifact_info = data.content_artifact_by_product.get(str(plan.product_id), {})
        artifact_id = artifact_info.get("id")
        artifact_version = artifact_info.get("version")
        for channel in data.channels:
            for local_index in range(data.output_count_per_product):
                output_index += 1
                scenario = (
                    data.failure_scenarios.get(f"{plan.product_id}:{channel}:{local_index}")
                    or data.failure_scenarios.get(str(output_index))
                    or "success"
                )
                request = ImageGenerateRequest(
                    brand_id=product.brand_id,
                    product_id=product.id,
                    source_media_ids=plan.source_media_ids,
                    operation=data.operation,
                    channel=channel,
                    aspect_ratio=data.aspect_ratio,
                    width=data.width,
                    height=data.height,
                    style_id=style.id if style else None,
                    preset_id=preset.id if preset else None,
                    instructions=data.instructions,
                    provider=data.provider,
                    model=data.model,
                    output_count=1,
                    idempotency_key=f"{key}:{plan.product_id}:{channel}:{local_index}",
                    content_artifact_id=(uuid.UUID(str(artifact_id)) if artifact_id else None),
                    content_artifact_version=(
                        int(str(artifact_version)) if artifact_version is not None else None
                    ),
                    scenario=scenario,
                )
                generated = queue_generation(db, owner, request, commit=False)
                image_generation = db.get(AIImageGeneration, generated.id)
                if image_generation is None:
                    raise HTTPException(500, "Bulk image generation identity is unavailable.")
                image_output = db.scalar(
                    select(AIImageOutput).where(
                        AIImageOutput.generation_id == image_generation.id,
                        AIImageOutput.product_id == product.id,
                        AIImageOutput.channel == channel,
                    )
                )
                if image_output is None:
                    raise HTTPException(500, "Bulk image output planning was incomplete.")
                db.add(
                    AIStudioBulkOutput(
                        bulk_operation_id=operation.id,
                        owner_id=owner.id,
                        product_id=product.id,
                        generation_id=generated.generation_id,
                        job_id=image_output.job_id,
                        artifact_id=None,
                        channel=channel,
                        content_type="image",
                        locale="en-IN",
                        status="queued",
                        retryable=False,
                        cancellation_requested=False,
                        stale_reason=None,
                        output_index=output_index,
                        operation=data.operation,
                        image_output_id=image_output.id,
                        media_id=None,
                        source_media_ids_json=[str(value) for value in plan.source_media_ids],
                        created_at=stamp,
                        updated_at=stamp,
                    )
                )
                record_event(
                    db,
                    actor_id=owner.id,
                    action="ai.image_bulk_output_queued",
                    entity_type="ai_studio_bulk_output",
                    entity_id=image_output.id,
                    metadata={
                        "correlation_id": operation.correlation_id,
                        "output_index": output_index,
                    },
                )
    record_event(
        db,
        actor_id=owner.id,
        action="ai.image_bulk_started",
        entity_type="ai_studio_bulk_operation",
        entity_id=operation.id,
        metadata={
            "total_outputs": operation.total_outputs,
            "correlation_id": operation.correlation_id,
        },
    )
    db.commit()
    db.refresh(operation)
    return operation


def _bulk(db: Session, owner: User, bulk_id: uuid.UUID) -> AIStudioBulkOperation:
    row = db.scalar(
        select(AIStudioBulkOperation).where(
            AIStudioBulkOperation.id == bulk_id,
            AIStudioBulkOperation.owner_id == owner.id,
            AIStudioBulkOperation.modality == "image",
        )
    )
    if row is None:
        raise HTTPException(404, "Image bulk operation not found.")
    return row


def image_bulk_status(db: Session, owner: User, bulk_id: uuid.UUID) -> ImageBulkStatusResponse:
    operation = _bulk(db, owner, bulk_id)
    rows = _sync_operation(db, operation)
    db.commit()
    counts = cast(dict[str, int], dict(operation.completion_summary_json or {}))
    outputs: list[dict[str, object]] = []
    for row in rows:
        product = db.get(Product, row.product_id)
        job = db.get(AIStudioJob, row.job_id)
        outputs.append(
            {
                "id": row.id,
                "product_id": row.product_id,
                "product_name": product.name if product else "Unknown Product",
                "output_index": row.output_index,
                "channel": row.channel,
                "operation": row.operation or operation.image_operation or "image",
                "status": row.status,
                "source_media_ids": [uuid.UUID(value) for value in row.source_media_ids_json],
                "image_output_id": row.image_output_id,
                "media_id": row.media_id,
                "job_id": row.job_id,
                "attempt_count": job.attempt_count if job else 0,
                "retryable": row.retryable,
                "retry_eligible": row.status in {"failed", "stale"} and row.retryable,
                "failure_category": row.failure_category,
                "safe_error_message": row.safe_error_message,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
    progress = round(
        100
        * sum(
            counts.get(value, 0)
            for value in {"needs_review", "succeeded", "failed", "cancelled", "stale"}
        )
        / max(1, operation.total_outputs),
        2,
    )
    return ImageBulkStatusResponse(
        id=operation.id,
        status=operation.status,
        total_outputs=operation.total_outputs,
        counts=counts,
        progress_percentage=progress,
        product_count=operation.product_count,
        channel_count=operation.channel_count,
        operation=operation.image_operation or "image",
        channels=sorted({row.channel for row in rows}),
        output_count_per_product=operation.image_output_count or 1,
        style_id=operation.image_style_id,
        style_version=operation.image_style_version,
        preset_id=operation.image_preset_id,
        preset_version=operation.image_preset_version,
        provider=operation.provider_key,
        model=operation.model,
        width=operation.image_width or 1024,
        height=operation.image_height or 1024,
        aspect_ratio=operation.image_aspect_ratio or "1:1",
        source_strategy=operation.source_strategy or "selected",
        correlation_id=operation.correlation_id,
        created_at=operation.created_at,
        started_at=operation.started_at,
        completed_at=operation.completed_at,
        cancellation_requested=operation.cancellation_requested,
        outputs=cast(list[ImageBulkOutputResponse], outputs),
    )


def retry_image_bulk(
    db: Session, owner: User, bulk_id: uuid.UUID, output_ids: list[uuid.UUID]
) -> tuple[int, int]:
    operation = _bulk(db, owner, bulk_id)
    result = retry_outputs(db, owner, operation, output_ids)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.image_bulk_output_retried",
        entity_type="ai_studio_bulk_operation",
        entity_id=operation.id,
        metadata={
            "retried_count": result[0],
            "correlation_id": operation.correlation_id,
        },
    )
    return result


def cancel_image_bulk(
    db: Session, owner: User, bulk_id: uuid.UUID, output_ids: list[uuid.UUID]
) -> int:
    operation = _bulk(db, owner, bulk_id)
    cancelled = cancel_outputs(db, owner, operation, output_ids)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.image_bulk_output_cancelled",
        entity_type="ai_studio_bulk_operation",
        entity_id=operation.id,
        metadata={
            "cancelled_count": cancelled,
            "correlation_id": operation.correlation_id,
        },
    )
    return cancelled
