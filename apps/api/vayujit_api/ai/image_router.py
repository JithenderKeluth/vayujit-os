from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.image_bulk_service import (
    cancel_image_bulk,
    create_image_bulk,
    image_bulk_status,
    preview_image_bulk,
    retry_image_bulk,
)
from vayujit_api.ai.image_models import AIImageOutput, AIImageStyle
from vayujit_api.ai.image_provider import image_provider
from vayujit_api.ai.image_schemas import (
    ImageAltTextRequest,
    ImageAltTextResponse,
    ImageApprovalEligibilityResponse,
    ImageBulkCancelRequest,
    ImageBulkPreviewResponse,
    ImageBulkRequest,
    ImageBulkRetryRequest,
    ImageCampaignHandoffRequest,
    ImageComparisonResponse,
    ImageDecisionRequest,
    ImageGenerateRequest,
    ImageGenerationResponse,
    ImageHandoffPreview,
    ImageHandoffRequest,
    ImageOutputDetailResponse,
    ImageOutputResponse,
    ImagePresetCreate,
    ImagePresetLifecycleResponse,
    ImageReadinessResponse,
    ImageRegenerateRequest,
    ImageStyleCreate,
    ImageStyleResponse,
    ProductMediaItem,
)
from vayujit_api.ai.image_service import (
    approval_eligibility,
    campaign_handoff,
    compare_outputs,
    confirm_handoff,
    create_preset,
    create_style,
    decide_output,
    generation_response,
    get_alt_text,
    history,
    list_presets,
    manage_alt_text,
    marketplace_rules,
    output_detail,
    preview_handoff,
    product_media_projection,
    queue_generation,
    readiness,
    regenerate_output,
    set_style_archived,
    set_style_default,
    style_preview,
    style_response,
    update_style,
)
from vayujit_api.ai.studio_models import (
    AIStudioGeneration,
    AIStudioJob,
    AIStudioJobAttempt,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.service import storage_root

router = APIRouter(prefix="/api/v1/ai/images", tags=["ai-images"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/providers")
def image_providers() -> list[dict[str, object]]:
    return [
        {
            "id": "deterministic_mock_v1",
            "display_name": "Local deterministic image provider",
            "available": True,
            "models": ["image-deterministic-v1"],
            "capabilities": [
                "image_generation",
                "image_editing",
                "background_removal",
                "inpainting",
                "outpainting",
                "transparent_background",
                "image_variations",
            ],
            "workflow_supported": True,
            "visual_effect_simulated": True,
            "live_provider_supported": False,
        }
    ]


@router.get("/presets")
def image_presets(db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_presets(db, owner.id)


@router.get("/styles", response_model=list[ImageStyleResponse])
def styles(db: DB, owner: Owner, brand_id: uuid.UUID | None = None) -> list[ImageStyleResponse]:
    query = select(AIImageStyle).where(
        AIImageStyle.owner_id == owner.id, AIImageStyle.archived.is_(False)
    )
    if brand_id:
        query = query.where(AIImageStyle.brand_id == brand_id)
    return [
        style_response(row)
        for row in db.scalars(query.order_by(AIImageStyle.name, AIImageStyle.version.desc()))
    ]


@router.post("/styles", response_model=ImageStyleResponse, status_code=201)
def add_style(data: ImageStyleCreate, db: DB, owner: Owner) -> ImageStyleResponse:
    return create_style(db, owner, data)


@router.post("/generate", response_model=ImageGenerationResponse, status_code=202)
def generate(data: ImageGenerateRequest, db: DB, owner: Owner) -> ImageGenerationResponse:
    return queue_generation(db, owner, data)


@router.get("/generations/{generation_id}", response_model=ImageGenerationResponse)
def get_generation(generation_id: uuid.UUID, db: DB, owner: Owner) -> ImageGenerationResponse:
    generation = db.scalar(
        select(AIStudioGeneration).where(
            AIStudioGeneration.id == generation_id,
            AIStudioGeneration.owner_id == owner.id,
        )
    )
    if generation is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Image generation not found.")
    image_generation = next(
        iter(
            db.scalars(
                select(
                    __import__(
                        "vayujit_api.ai.image_models", fromlist=["AIImageGeneration"]
                    ).AIImageGeneration
                ).where(
                    __import__(
                        "vayujit_api.ai.image_models", fromlist=["AIImageGeneration"]
                    ).AIImageGeneration.generation_id
                    == generation.id
                )
            )
        ),
        None,
    )
    if image_generation is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Image generation not found.")
    return generation_response(db, image_generation)


@router.post("/outputs/{output_id}/approve")
def approve(
    output_id: uuid.UUID, data: ImageDecisionRequest, db: DB, owner: Owner
) -> ImageOutputResponse:
    return decide_output(db, owner, output_id, "approved", data.feedback, data.category)


@router.post("/outputs/{output_id}/reject")
def reject(
    output_id: uuid.UUID, data: ImageDecisionRequest, db: DB, owner: Owner
) -> ImageOutputResponse:
    return decide_output(db, owner, output_id, "rejected", data.feedback, data.category)


@router.get(
    "/outputs/{output_id}/readiness/{marketplace}",
    response_model=ImageReadinessResponse,
)
def output_readiness(
    output_id: uuid.UUID, marketplace: str, db: DB, owner: Owner
) -> ImageReadinessResponse:
    return readiness(db, owner, output_id, marketplace)


@router.get("/outputs", response_model=None)
def outputs(db: DB, owner: Owner) -> list[AIImageOutput]:
    return [
        row
        for row in db.scalars(
            select(AIImageOutput)
            .where(AIImageOutput.owner_id == owner.id)
            .order_by(AIImageOutput.created_at.desc())
        )
    ]


@router.get("/outputs/{output_id}", response_model=ImageOutputDetailResponse)
def get_output(output_id: uuid.UUID, db: DB, owner: Owner) -> ImageOutputDetailResponse:
    return output_detail(db, owner, output_id)


@router.post(
    "/outputs/{output_id}/regenerate",
    response_model=ImageGenerationResponse,
    status_code=202,
)
def regenerate(
    output_id: uuid.UUID, data: ImageRegenerateRequest, db: DB, owner: Owner
) -> ImageGenerationResponse:
    return regenerate_output(db, owner, output_id, data)


@router.post("/outputs/{output_id}/handoff/preview", response_model=ImageHandoffPreview)
def handoff_preview(
    output_id: uuid.UUID, data: ImageHandoffRequest, db: DB, owner: Owner
) -> ImageHandoffPreview:
    return preview_handoff(db, owner, output_id, data)


@router.post("/outputs/{output_id}/handoff")
def handoff(
    output_id: uuid.UUID, data: ImageHandoffRequest, db: DB, owner: Owner
) -> dict[str, object]:
    if not data.fingerprint:
        from fastapi import HTTPException

        raise HTTPException(422, "A fresh handoff preview fingerprint is required.")
    return confirm_handoff(db, owner, output_id, data, data.fingerprint)


@router.post("/outputs/{output_id}/campaign-handoff")
def campaign_image_handoff(
    output_id: uuid.UUID, data: ImageCampaignHandoffRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return campaign_handoff(db, owner, output_id, data)


@router.get("/products/{product_id}/outputs")
def product_outputs(product_id: uuid.UUID, db: DB, owner: Owner) -> list[ImageOutputDetailResponse]:
    rows = list(
        db.scalars(
            select(AIImageOutput)
            .where(
                AIImageOutput.owner_id == owner.id,
                AIImageOutput.product_id == product_id,
            )
            .order_by(AIImageOutput.created_at.desc())
        )
    )
    return [output_detail(db, owner, row.id) for row in rows]


@router.get("/marketplace-rules")
def image_marketplace_rules(marketplace: str | None = None) -> dict[str, object]:
    return marketplace_rules(marketplace)


@router.get("/outputs/{output_id}/eligibility", response_model=ImageApprovalEligibilityResponse)
def output_eligibility(
    output_id: uuid.UUID, db: DB, owner: Owner, marketplace: str | None = None
) -> ImageApprovalEligibilityResponse:
    return approval_eligibility(db, owner, output_id, marketplace)


@router.get("/outputs/{output_id}/compare", response_model=ImageComparisonResponse)
def compare_output(
    output_id: uuid.UUID,
    db: DB,
    owner: Owner,
    compare_output_id: uuid.UUID | None = None,
) -> ImageComparisonResponse:
    return compare_outputs(db, owner, output_id, compare_output_id)


@router.get("/outputs/{output_id}/history")
def output_history(output_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return history(db, owner, output_id)


@router.get("/products/{product_id}/media", response_model=list[ProductMediaItem])
def product_media(product_id: uuid.UUID, db: DB, owner: Owner) -> list[ProductMediaItem]:
    return product_media_projection(db, owner, product_id)


@router.get("/outputs/{output_id}/alt-text", response_model=ImageAltTextResponse)
def get_alt_text_route(output_id: uuid.UUID, db: DB, owner: Owner) -> ImageAltTextResponse:
    return get_alt_text(db, owner, output_id)


@router.post("/outputs/{output_id}/alt-text", response_model=ImageAltTextResponse)
def update_alt_text(
    output_id: uuid.UUID, data: ImageAltTextRequest, db: DB, owner: Owner
) -> ImageAltTextResponse:
    return manage_alt_text(db, owner, output_id, data)


@router.post("/presets", response_model=ImagePresetLifecycleResponse, status_code=201)
def add_preset(data: ImagePresetCreate, db: DB, owner: Owner) -> ImagePresetLifecycleResponse:
    return create_preset(db, owner, data)


@router.put("/styles/{style_id}", response_model=ImageStyleResponse)
def edit_style(
    style_id: uuid.UUID, data: ImageStyleCreate, db: DB, owner: Owner
) -> ImageStyleResponse:
    return update_style(db, owner, style_id, data)


@router.post("/styles/{style_id}/default", response_model=ImageStyleResponse)
def make_style_default(style_id: uuid.UUID, db: DB, owner: Owner) -> ImageStyleResponse:
    return set_style_default(db, owner, style_id)


@router.post("/styles/{style_id}/archive", response_model=ImageStyleResponse)
def archive_style(style_id: uuid.UUID, db: DB, owner: Owner) -> ImageStyleResponse:
    return set_style_archived(db, owner, style_id, True)


@router.post("/styles/{style_id}/restore", response_model=ImageStyleResponse)
def restore_style(style_id: uuid.UUID, db: DB, owner: Owner) -> ImageStyleResponse:
    return set_style_archived(db, owner, style_id, False)


@router.get("/styles/{style_id}/preview")
def preview_style(
    style_id: uuid.UUID, product_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return style_preview(db, owner, style_id, product_id)


@router.post("/bulk/preview", response_model=ImageBulkPreviewResponse)
def image_bulk_preview(data: ImageBulkRequest, db: DB, owner: Owner) -> ImageBulkPreviewResponse:
    return preview_image_bulk(db, owner, data)


@router.post("/bulk", response_model=object, status_code=202)
@router.post("/bulk/generate", response_model=object, status_code=202)
def image_bulk_generate(data: ImageBulkRequest, db: DB, owner: Owner):
    operation = create_image_bulk(db, owner, data)
    return image_bulk_status(db, owner, operation.id)


@router.get("/bulk", response_model=list[object])
def image_bulk_list(db: DB, owner: Owner):
    rows = db.scalars(
        select(AIStudioBulkOperation)
        .where(
            AIStudioBulkOperation.owner_id == owner.id,
            AIStudioBulkOperation.modality == "image",
        )
        .order_by(AIStudioBulkOperation.created_at.desc())
        .limit(100)
    ).all()
    return [image_bulk_status(db, owner, row.id) for row in rows]


@router.get("/bulk/{bulk_id}", response_model=object)
def image_bulk_get(bulk_id: uuid.UUID, db: DB, owner: Owner):
    return image_bulk_status(db, owner, bulk_id)


@router.get("/bulk/{bulk_id}/outputs")
def image_bulk_outputs(
    bulk_id: uuid.UUID,
    db: DB,
    owner: Owner,
    product_id: uuid.UUID | None = None,
    channel: str | None = None,
    state: str | None = None,
):
    status = image_bulk_status(db, owner, bulk_id)
    items = status.outputs
    if product_id:
        items = [item for item in items if item.product_id == product_id]
    if channel:
        items = [item for item in items if item.channel == channel]
    if state:
        items = [item for item in items if item.status == state]
    return {"items": items, "total": len(items), "offset": 0, "limit": len(items)}


@router.post("/bulk/{bulk_id}/retry-failed")
def image_bulk_retry(
    bulk_id: uuid.UUID, db: DB, owner: Owner, data: ImageBulkRetryRequest | None = None
):
    retried, rejected = retry_image_bulk(db, owner, bulk_id, data.output_ids if data else [])
    return {
        "status": "queued" if retried else "unchanged",
        "retried_count": retried,
        "rejected_count": rejected,
        "bulk_id": str(bulk_id),
    }


@router.post("/bulk/{bulk_id}/cancel")
def image_bulk_cancel(
    bulk_id: uuid.UUID, db: DB, owner: Owner, data: ImageBulkCancelRequest | None = None
):
    cancelled = cancel_image_bulk(db, owner, bulk_id, data.output_ids if data else [])
    return {
        "status": "cancelled",
        "cancelled_count": cancelled,
        "bulk_id": str(bulk_id),
    }


@router.post("/bulk/outputs/{output_id}/retry")
def image_bulk_output_retry(output_id: uuid.UUID, db: DB, owner: Owner):
    row = db.scalar(
        select(AIStudioBulkOutput).where(
            AIStudioBulkOutput.id == output_id,
            AIStudioBulkOutput.owner_id == owner.id,
            AIStudioBulkOutput.content_type == "image",
        )
    )
    if row is None:
        raise HTTPException(404, "Image bulk output not found.")
    retried, rejected = retry_image_bulk(db, owner, row.bulk_operation_id, [output_id])
    return {"retried_count": retried, "rejected_count": rejected}


@router.post("/bulk/outputs/{output_id}/cancel")
def image_bulk_output_cancel(output_id: uuid.UUID, db: DB, owner: Owner):
    row = db.scalar(
        select(AIStudioBulkOutput).where(
            AIStudioBulkOutput.id == output_id,
            AIStudioBulkOutput.owner_id == owner.id,
            AIStudioBulkOutput.content_type == "image",
        )
    )
    if row is None:
        raise HTTPException(404, "Image bulk output not found.")
    cancelled = cancel_image_bulk(db, owner, row.bulk_operation_id, [output_id])
    return {"cancelled_count": cancelled}


@router.get("/usage")
def image_usage(db: DB, owner: Owner):
    jobs = list(
        db.scalars(
            select(AIStudioJob).where(
                AIStudioJob.owner_id == owner.id,
                AIStudioJob.job_type.like("ai_image_%"),
            )
        )
    )
    job_ids = [job.id for job in jobs]
    attempts = (
        list(db.scalars(select(AIStudioJobAttempt).where(AIStudioJobAttempt.job_id.in_(job_ids))))
        if job_ids
        else []
    )
    outputs = (
        list(
            db.scalars(
                select(AIImageOutput).where(
                    AIImageOutput.owner_id == owner.id,
                    AIImageOutput.job_id.in_(job_ids),
                )
            )
        )
        if job_ids
        else []
    )
    latencies = sorted(int(value.latency_ms) for value in attempts if value.latency_ms is not None)
    successful = sum(value.state == "succeeded" for value in jobs)
    failed = sum(value.state in {"failed", "stale", "cancelled"} for value in jobs)
    return {
        "modality": "image",
        "total_generations": len(jobs),
        "successful": successful,
        "failed": failed,
        "retry_count": sum(max(value.attempt_count - 1, 0) for value in jobs),
        "provider_calls": len(attempts),
        "generated_images": sum(value.media_id is not None for value in outputs),
        "generated_bytes": sum(value.size_bytes or 0 for value in outputs),
        "input_image_count": sum(len(value.source_media_ids_json or []) for value in outputs),
        "median_latency_ms": latencies[len(latencies) // 2] if latencies else None,
        "latency_ms": {"median": latencies[len(latencies) // 2] if latencies else None},
        "cost_status": "unavailable",
        "cost": None,
        "token_totals": None,
        "input_tokens": None,
        "output_tokens": None,
        "providers": sorted({value.provider for value in jobs}),
        "models": sorted({value.model for value in jobs}),
        "operations": sorted({value.operation for value in outputs}),
        "channels": sorted({value.channel for value in outputs}),
        "states": {
            state: sum(value.state == state for value in jobs)
            for state in sorted({value.state for value in jobs})
        },
    }


@router.get("/diagnostics")
def image_diagnostics(db: DB, owner: Owner):
    jobs = list(
        db.scalars(
            select(AIStudioJob).where(
                AIStudioJob.owner_id == owner.id,
                AIStudioJob.job_type.like("ai_image_%"),
            )
        )
    )
    image_outputs = list(
        db.scalars(select(AIImageOutput).where(AIImageOutput.owner_id == owner.id))
    )
    storage_ok = False
    try:
        root = storage_root()
        probe = root / ".diagnostic-write-probe"
        probe.write_bytes(b"ok")
        storage_ok = probe.read_bytes() == b"ok"
        probe.unlink(missing_ok=True)
    except OSError:
        storage_ok = False
    counts = {
        state: sum(value.state == state for value in jobs)
        for state in sorted({value.state for value in jobs})
    }
    return {
        "image_studio": "healthy",
        "local_provider": {
            "key": "deterministic_mock_v1",
            "healthy": True,
            "simulated": True,
            "live": False,
        },
        "live_provider": "not_configured",
        "capabilities": sorted(image_provider.capabilities),
        "supported_operations": sorted(
            {
                "marketplace_main_image",
                "marketplace_gallery_image",
                "white_background",
                "resize",
                "crop",
                "thumbnail",
                "banner",
                "promotional_creative",
            }
        ),
        "image_jobs": counts,
        "queued_image_jobs": counts.get("queued", 0),
        "retry_wait_count": counts.get("retry_wait", 0),
        "failed_count": counts.get("failed", 0),
        "invalid_checkpoint_count": sum(
            value.last_error_code == "checkpoint_invalid" for value in jobs
        ),
        "recent_throttles": sum("thrott" in (value.failure_category or "") for value in jobs),
        "generated_media_count": sum(value.media_id is not None for value in image_outputs),
        "storage_ready": storage_ok,
        "storage_path_disclosed": False,
        "safe_message": "Image Studio diagnostics completed.",
    }
