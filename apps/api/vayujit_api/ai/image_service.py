from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.image_models import (
    AIImageGeneration,
    AIImageOutput,
    AIImagePreset,
    AIImageStyle,
)
from vayujit_api.ai.image_schemas import (
    ImageAltTextRequest,
    ImageAltTextResponse,
    ImageApprovalEligibilityResponse,
    ImageCampaignHandoffRequest,
    ImageChannel,
    ImageComparisonResponse,
    ImageGenerateRequest,
    ImageGenerationResponse,
    ImageHandoffPreview,
    ImageHandoffRequest,
    ImageOperation,
    ImageOutputDetailResponse,
    ImageOutputResponse,
    ImagePresetCreate,
    ImagePresetLifecycleResponse,
    ImageReadinessResponse,
    ImageStyleCreate,
    ImageStyleResponse,
    ProductMediaItem,
)
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import AIStudioGeneration, AIStudioJob, AIStudioOutput
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.commerce.models import MarketplaceListing, MarketplaceMediaMapping
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product


def _now() -> datetime:
    return datetime.now(UTC)


def _owned(db: Session, model: Any, owner_id: uuid.UUID, value: uuid.UUID, label: str) -> Any:
    row = db.scalar(select(model).where(model.id == value, model.owner_id == owner_id))
    if row is None:
        raise HTTPException(404, f"{label} not found.")
    return row


def style_response(row: AIImageStyle) -> ImageStyleResponse:
    return ImageStyleResponse(
        id=row.id,
        brand_id=row.brand_id,
        name=row.name,
        version=row.version,
        background_preference=row.background_preference,
        photography_style=row.photography_style,
        lighting=row.lighting,
        mood=row.mood,
        composition=row.composition,
        colors=row.colors_json,
        environments=list(row.environments_json or []),
        prohibited_treatments=list(row.prohibited_treatments_json or []),
        logo_guidance=row.logo_guidance,
        marketplace_constraints=row.marketplace_constraints_json,
        guidance=row.guidance,
        archived=row.archived,
        is_default=row.is_default,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_style(db: Session, owner: User, data: ImageStyleCreate) -> ImageStyleResponse:
    _owned(db, Brand, owner.id, data.brand_id, "Brand")
    version = (
        db.scalar(
            select(AIImageStyle.version)
            .where(
                AIImageStyle.owner_id == owner.id,
                AIImageStyle.brand_id == data.brand_id,
                AIImageStyle.name == data.name,
            )
            .order_by(AIImageStyle.version.desc())
            .limit(1)
        )
        or 0
    ) + 1
    if data.is_default:
        db.query(AIImageStyle).filter(
            AIImageStyle.owner_id == owner.id,
            AIImageStyle.brand_id == data.brand_id,
        ).update({AIImageStyle.is_default: False})
    stamp = _now()
    row = AIImageStyle(
        owner_id=owner.id,
        brand_id=data.brand_id,
        name=data.name,
        version=version,
        background_preference=data.background_preference,
        photography_style=data.photography_style,
        lighting=data.lighting,
        mood=data.mood,
        composition=data.composition,
        colors_json=data.colors,
        environments_json=data.environments,
        prohibited_treatments_json=data.prohibited_treatments,
        logo_guidance=data.logo_guidance,
        marketplace_constraints_json=data.marketplace_constraints,
        guidance=data.guidance,
        is_default=data.is_default,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.image_style_created",
        entity_type="ai_image_style",
        entity_id=row.id,
        metadata={"version": version},
    )
    db.commit()
    db.refresh(row)
    return style_response(row)


def list_presets(db: Session, owner_id: uuid.UUID) -> list[dict[str, object]]:
    defaults = [
        (
            "Amazon Main",
            "marketplace_main_image",
            "amazon",
            {"background": "white", "max_width": 2000, "max_height": 2000},
        ),
        (
            "Flipkart Main",
            "marketplace_main_image",
            "flipkart",
            {"background": "white"},
        ),
        ("Meesho Main", "marketplace_main_image", "meesho", {"background": "white"}),
        ("Marketplace Gallery", "marketplace_gallery_image", None, {"max_outputs": 8}),
        ("White Background", "white_background", None, {"background": "white"}),
        ("Premium Lifestyle", "lifestyle_scene", None, {"background": "lifestyle"}),
        ("Social Square", "promotional_creative", "social", {"aspect_ratio": "1:1"}),
        ("Story Portrait", "promotional_creative", "social", {"aspect_ratio": "9:16"}),
        ("YouTube Thumbnail", "thumbnail", "social", {"aspect_ratio": "16:9"}),
        ("Banner", "banner", None, {"aspect_ratio": "16:9"}),
    ]
    return [
        {
            "id": None,
            "name": n,
            "version": 1,
            "operation": op,
            "channel": ch,
            "rules": rules,
        }
        for n, op, ch, rules in defaults
    ]


def _output_response(row: AIImageOutput, job: AIStudioJob) -> ImageOutputResponse:
    return ImageOutputResponse(
        id=row.id,
        generation_id=row.generation_id,
        job_id=row.job_id,
        media_id=row.media_id,
        source_media_ids=[uuid.UUID(v) for v in row.source_media_ids_json],
        parent_output_id=row.parent_output_id,
        operation=row.operation,
        channel=row.channel,
        status=row.status,
        requested_width=row.requested_width,
        requested_height=row.requested_height,
        actual_width=row.actual_width,
        actual_height=row.actual_height,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        checksum_sha256=row.checksum_sha256,
        alt_text_suggestion=row.alt_text_suggestion,
        provider=job.provider,
        model=job.model,
        created_at=row.created_at,
        asset_classification=row.asset_classification,
        content_artifact_id=row.content_artifact_id,
        content_artifact_version=row.content_artifact_version,
    )


def generation_response(
    db: Session, image_generation: AIImageGeneration
) -> ImageGenerationResponse:
    generation = db.get(AIStudioGeneration, image_generation.generation_id)
    jobs = list(
        db.scalars(
            select(AIStudioJob)
            .where(AIStudioJob.generation_id == image_generation.generation_id)
            .order_by(AIStudioJob.created_at)
        )
    )
    outputs = list(
        db.scalars(
            select(AIImageOutput)
            .where(AIImageOutput.generation_id == image_generation.id)
            .order_by(AIImageOutput.created_at)
        )
    )
    return ImageGenerationResponse(
        id=image_generation.id,
        generation_id=image_generation.generation_id,
        operation=image_generation.operation,
        channel=image_generation.channel,
        status=generation.status if generation else "failed",
        total_outputs=generation.total_outputs if generation else len(outputs),
        completed_outputs=generation.completed_outputs if generation else 0,
        failed_outputs=generation.failed_outputs if generation else 0,
        outputs=(
            [
                _output_response(
                    value,
                    next((job for job in jobs if job.id == value.job_id), jobs[0]),
                )
                for value in outputs
            ]
            if jobs
            else []
        ),
        safe_error_message=generation.safe_error_message if generation else None,
    )


def queue_generation(
    db: Session, owner: User, data: ImageGenerateRequest, *, commit: bool = True
) -> ImageGenerationResponse:
    brand = _owned(db, Brand, owner.id, data.brand_id, "Brand")
    product = _owned(db, Product, owner.id, data.product_id, "Product")
    if product.brand_id != brand.id:
        raise HTTPException(422, "Product does not belong to the selected Brand.")
    source_media = []
    if data.source_media_ids:
        source_media = list(
            db.scalars(
                select(MediaAsset).where(
                    MediaAsset.owner_id == owner.id,
                    MediaAsset.id.in_(data.source_media_ids),
                    MediaAsset.status == "ready",
                )
            )
        )
        if len(source_media) != len(set(data.source_media_ids)):
            raise HTTPException(422, "One or more source Media assets are unavailable.")
    style = None
    if data.style_id:
        style = _owned(db, AIImageStyle, owner.id, data.style_id, "Image style")
        if style.brand_id != brand.id:
            raise HTTPException(422, "Image style does not belong to the selected Brand.")
        if style.archived:
            raise HTTPException(409, "Archived Image Styles cannot be selected.")
    content_artifact = None
    if data.content_artifact_id is not None:
        content_artifact = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == data.content_artifact_id,
                GeneratedArtifact.owner_id == owner.id,
            )
        )
        if content_artifact is None:
            raise HTTPException(404, "Content Artifact not found.")
        if content_artifact.product_id != product.id or content_artifact.brand_id != brand.id:
            raise HTTPException(
                422,
                "Content Artifact does not belong to the selected Product and Brand.",
            )
        if (
            content_artifact.status != "approved"
            or content_artifact.version_number != data.content_artifact_version
        ):
            raise HTTPException(
                422, "Only the exact approved Content Artifact version may be used."
            )
    if data.operation == "promotional_creative" and not any(
        (data.headline, data.subheadline, data.cta, data.offer_text, content_artifact)
    ):
        raise HTTPException(
            422,
            "Promotional creative requires explicit copy or an approved Content Artifact.",
        )
    preset = None
    if data.preset_id:
        preset = _owned(db, AIImagePreset, owner.id, data.preset_id, "Image preset")
        if preset.operation != data.operation or (
            preset.channel and preset.channel != data.channel
        ):
            raise HTTPException(
                422,
                "The selected Image preset is incompatible with this operation or channel.",
            )
    context = {
        "brand": brand.name,
        "product": product.name,
        "category": product.category,
        "short_description": product.short_description,
        "style_version": style.version if style else None,
        "content_artifact_id": str(content_artifact.id) if content_artifact else None,
        "content_artifact_version": (content_artifact.version_number if content_artifact else None),
        "headline": data.headline,
        "subheadline": data.subheadline,
        "cta": data.cta,
        "offer_text": data.offer_text,
    }
    fingerprint = hashlib.sha256(
        json.dumps(context, sort_keys=True, default=str).encode()
    ).hexdigest()
    idem = (
        data.idempotency_key
        or hashlib.sha256(
            json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()[:48]
    )
    existing = db.scalar(
        select(AIStudioGeneration).where(
            AIStudioGeneration.owner_id == owner.id,
            AIStudioGeneration.idempotency_key == idem,
        )
    )
    if existing:
        image_generation = db.scalar(
            select(AIImageGeneration).where(AIImageGeneration.generation_id == existing.id)
        )
        if image_generation:
            return generation_response(db, image_generation)
    stamp = _now()
    generation = AIStudioGeneration(
        owner_id=owner.id,
        product_ids_json=[str(product.id)],
        channels_json=[data.channel],
        content_types_json=["image"],
        locale="en-IN",
        user_instructions=data.instructions,
        provider_key=data.provider,
        model=data.model,
        context_fingerprint=fingerprint,
        idempotency_key=idem,
        status="queued",
        total_outputs=data.output_count,
        created_at=stamp,
    )
    db.add(generation)
    db.flush()
    image_generation = AIImageGeneration(
        generation_id=generation.id,
        owner_id=owner.id,
        brand_id=brand.id,
        product_id=product.id,
        operation=data.operation,
        channel=data.channel,
        context_fingerprint=fingerprint,
        style_id=style.id if style else None,
        style_version=style.version if style else None,
        preset_id=preset.id if preset else None,
        preset_version=preset.version if preset else None,
        provider=data.provider,
        model=data.model,
        locale="en-IN",
        content_artifact_id=content_artifact.id if content_artifact else None,
        content_artifact_version=(content_artifact.version_number if content_artifact else None),
        headline=data.headline,
        subheadline=data.subheadline,
        cta=data.cta,
        offer_text=data.offer_text,
        requested_width=data.width,
        requested_height=data.height,
        aspect_ratio=data.aspect_ratio,
        created_at=stamp,
    )
    db.add(image_generation)
    db.flush()
    source_ids = [str(value.id) for value in source_media]
    for index in range(data.output_count):
        job_key = f"{idem}:{index}"
        job = AIStudioJob(
            owner_id=owner.id,
            generation_id=generation.id,
            product_id=product.id,
            job_type=(
                "ai_image_generate"
                if data.operation == "generate_product_image"
                else "ai_image_edit"
            ),
            channel=data.channel,
            content_type="image",
            locale="en-IN",
            context_fingerprint=fingerprint,
            provider=data.provider,
            model=data.model,
            user_instruction_fingerprint=hashlib.sha256(
                (data.instructions or "").encode()
            ).hexdigest(),
            idempotency_key=job_key,
            correlation_id=uuid.uuid4().hex[:32],
            state="queued",
            payload_json={
                "operation": data.operation,
                "source_media_ids": source_ids,
                "style_id": str(style.id) if style else None,
                "style_version": style.version if style else None,
                "content_artifact_id": (str(content_artifact.id) if content_artifact else None),
                "content_artifact_version": (
                    content_artifact.version_number if content_artifact else None
                ),
                "headline": data.headline,
                "subheadline": data.subheadline,
                "cta": data.cta,
                "offer_text": data.offer_text,
                "width": data.width,
                "height": data.height,
                "aspect_ratio": data.aspect_ratio,
                "scenario": data.scenario,
                "brand_name": brand.name,
                "product_name": product.name,
            },
            attempt_count=0,
            max_attempts=3,
            available_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(job)
        db.flush()
        db.add(
            AIStudioOutput(
                generation_id=generation.id,
                product_id=product.id,
                channel=data.channel,
                content_type="image",
                status="queued",
                created_at=stamp,
            )
        )
        db.add(
            AIImageOutput(
                generation_id=image_generation.id,
                job_id=job.id,
                owner_id=owner.id,
                product_id=product.id,
                brand_id=brand.id,
                style_id=style.id if style else None,
                style_version=style.version if style else None,
                preset_id=preset.id if preset else None,
                preset_version=preset.version if preset else None,
                locale="en-IN",
                asset_classification="ai_generated",
                content_artifact_id=content_artifact.id if content_artifact else None,
                content_artifact_version=(
                    content_artifact.version_number if content_artifact else None
                ),
                source_media_ids_json=source_ids,
                operation=data.operation,
                channel=data.channel,
                status="queued",
                requested_width=data.width,
                requested_height=data.height,
                context_fingerprint=fingerprint,
                alt_text_suggestion=f"{product.name} product image",
                created_at=stamp,
            )
        )
    record_event(
        db,
        actor_id=owner.id,
        action="ai.image_queued",
        entity_type="ai_image_generation",
        entity_id=image_generation.id,
        metadata={"operation": data.operation, "correlation_id": "image"},
    )
    if commit:
        db.commit()
        db.refresh(image_generation)
    return generation_response(db, image_generation)


def _owned_output(
    db: Session, owner: User, output_id: uuid.UUID, *, for_update: bool = False
) -> AIImageOutput:
    statement = select(AIImageOutput).where(
        AIImageOutput.id == output_id, AIImageOutput.owner_id == owner.id
    )
    if for_update:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise HTTPException(404, "Image output not found.")
    return row


def decide_output(
    db: Session,
    owner: User,
    output_id: uuid.UUID,
    status: str,
    feedback: str | None,
    category: str | None = None,
) -> ImageOutputResponse:
    row = _owned_output(db, owner, output_id, for_update=True)
    if row.status == status:
        job = db.get(AIStudioJob, row.job_id)
        if job is None:
            raise HTTPException(409, "Image job identity is unavailable.")
        return _output_response(row, job)
    if status == "approved":
        eligibility = approval_eligibility(db, owner, output_id)
        if not eligibility.eligible:
            raise HTTPException(
                409,
                {
                    "message": "Image approval is not eligible.",
                    "eligible": False,
                    "blockers": eligibility.blockers,
                    "warnings": eligibility.warnings,
                },
            )
    if row.media_id is None or row.status not in {
        "needs_review",
        "succeeded",
        "approved",
        "rejected",
    }:
        raise HTTPException(409, "Image output is not ready for review.")
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == row.media_id,
            MediaAsset.owner_id == owner.id,
            MediaAsset.status == "ready",
        )
    )
    if media is None or media.checksum_sha256 != row.checksum_sha256:
        raise HTTPException(409, "Image validation failed; the generated file is not eligible.")
    row.status = status
    row.approval_feedback = feedback
    row.rejection_category = category
    row.decision_correlation_id = uuid.uuid4().hex[:32]
    stamp = _now()
    if status == "approved":
        row.approved_at = stamp
        row.approved_by = owner.id
        action = "ai.image_approved"
    else:
        row.rejected_at = stamp
        action = "ai.image_rejected"
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type="ai_image_output",
        entity_id=row.id,
        metadata={
            "media_id": str(row.media_id),
            "correlation_id": row.decision_correlation_id,
            "category": category,
        },
    )
    db.commit()
    job = db.get(AIStudioJob, row.job_id)
    if job is None:
        raise HTTPException(409, "Image job identity is unavailable.")
    return _output_response(row, job)


def _lineage(db: Session, row: AIImageOutput) -> list[uuid.UUID]:
    values: list[uuid.UUID] = []
    current: AIImageOutput | None = row
    while current is not None:
        values.append(current.id)
        current = (
            db.get(AIImageOutput, current.parent_output_id) if current.parent_output_id else None
        )
    return list(reversed(values))


def output_detail(db: Session, owner: User, output_id: uuid.UUID) -> ImageOutputDetailResponse:
    row = _owned_output(db, owner, output_id)
    job = db.get(AIStudioJob, row.job_id)
    if job is None:
        raise HTTPException(409, "Image job identity is unavailable.")
    base = _output_response(row, job)
    return ImageOutputDetailResponse(
        **base.model_dump(),
        brand_id=row.brand_id,
        product_id=row.product_id,
        parent_media_id=row.parent_media_id,
        style_id=row.style_id,
        style_version=row.style_version,
        preset_id=row.preset_id,
        preset_version=row.preset_version,
        locale=row.locale,
        context_fingerprint=row.context_fingerprint,
        provider_metadata=row.provider_metadata_json or {},
        usage_metadata=row.usage_metadata_json or {},
        approval_feedback=row.approval_feedback,
        rejection_category=row.rejection_category,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        rejected_at=row.rejected_at,
        lineage=_lineage(db, row),
        readiness={
            **approval_eligibility(db, owner, row.id).model_dump(mode="json"),
            "status": row.status,
            "approved": row.status == "approved",
        },
    )


def regenerate_output(
    db: Session, owner: User, output_id: uuid.UUID, data: Any
) -> ImageGenerationResponse:
    parent = _owned_output(db, owner, output_id)
    if parent.media_id is None or parent.status not in {
        "rejected",
        "approved",
        "needs_review",
        "succeeded",
    }:
        raise HTTPException(409, "This image output cannot be regenerated.")
    generation = db.get(AIImageGeneration, parent.generation_id)
    job = db.get(AIStudioJob, parent.job_id)
    if generation is None or job is None:
        raise HTTPException(409, "Image generation identity is unavailable.")
    request = ImageGenerateRequest(
        brand_id=parent.brand_id,
        product_id=parent.product_id,
        source_media_ids=[uuid.UUID(value) for value in parent.source_media_ids_json],
        operation=cast(ImageOperation, parent.operation),
        channel=cast(ImageChannel, parent.channel),
        aspect_ratio=f"{parent.requested_width}:{parent.requested_height}",
        width=parent.requested_width,
        height=parent.requested_height,
        style_id=parent.style_id,
        preset_id=parent.preset_id,
        instructions=data.instructions or data.feedback,
        provider=data.provider or job.provider,
        model=data.model or job.model,
        output_count=1,
        idempotency_key=data.idempotency_key,
        scenario=data.scenario,
    )
    result = queue_generation(db, owner, request)
    child = db.scalar(select(AIImageOutput).where(AIImageOutput.generation_id == result.id))
    if child is not None:
        child.parent_output_id = parent.id
        child.parent_media_id = parent.media_id
        child.regeneration_reason = data.reason
        child.approval_feedback = data.feedback
        db.commit()
        record_event(
            db,
            actor_id=owner.id,
            action="ai.image_regeneration_requested",
            entity_type="ai_image_output",
            entity_id=child.id,
            metadata={"parent_output_id": str(parent.id), "reason": data.reason},
        )
        db.commit()
    return result


def _handoff_fingerprint(
    db: Session,
    listing: MarketplaceListing,
    output: AIImageOutput,
    position: int,
    role: str,
) -> str:
    mappings = list(
        db.scalars(
            select(MarketplaceMediaMapping)
            .where(MarketplaceMediaMapping.listing_id == listing.id)
            .order_by(MarketplaceMediaMapping.position, MarketplaceMediaMapping.media_id)
        )
    )
    payload = {
        "listing": str(listing.id),
        "updated": listing.updated_at.isoformat(),
        "output": str(output.id),
        "media": str(output.media_id),
        "position": position,
        "role": role,
        "mappings": [(str(item.media_id), item.position, item.status) for item in mappings],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def preview_handoff(
    db: Session, owner: User, output_id: uuid.UUID, data: ImageHandoffRequest
) -> ImageHandoffPreview:
    output = _owned_output(db, owner, output_id)
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == data.listing_id,
            MarketplaceListing.owner_id == owner.id,
            MarketplaceListing.marketplace == data.marketplace,
            MarketplaceListing.product_id == output.product_id,
        )
    )
    if listing is None:
        raise HTTPException(404, "Marketplace listing not found.")
    if output.channel not in {"canonical", data.marketplace}:
        raise HTTPException(409, "This image is blocked for the selected marketplace channel.")
    if output.status != "approved" or output.media_id is None:
        raise HTTPException(409, "Only an approved image can be handed off.")
    readiness_result = readiness(db, owner, output.id, data.marketplace)
    mappings = list(
        db.scalars(
            select(MarketplaceMediaMapping)
            .where(MarketplaceMediaMapping.listing_id == listing.id)
            .order_by(MarketplaceMediaMapping.position)
        )
    )
    current = [
        {
            "media_id": str(item.media_id),
            "position": item.position,
            "status": item.status,
        }
        for item in mappings
    ]
    warnings: list[str] = []
    blockers = list(readiness_result.reasons) if not readiness_result.ready else []
    fingerprint = _handoff_fingerprint(db, listing, output, data.position, data.role)
    return ImageHandoffPreview(
        output_id=output.id,
        media_id=output.media_id,
        marketplace=data.marketplace,
        listing_id=listing.id,
        position=data.position,
        role=data.role,
        ready=not blockers,
        warnings=warnings,
        blockers=blockers,
        fingerprint=fingerprint,
        current_media=current,
        proposed_media={
            "media_id": str(output.media_id),
            "position": data.position,
            "role": data.role,
            "checksum_sha256": output.checksum_sha256,
        },
    )


def confirm_handoff(
    db: Session,
    owner: User,
    output_id: uuid.UUID,
    data: ImageHandoffRequest,
    fingerprint: str,
) -> dict[str, object]:
    preview = preview_handoff(db, owner, output_id, data)
    if preview.fingerprint != fingerprint:
        raise HTTPException(409, "Marketplace state changed; request a fresh handoff preview.")
    existing = db.scalar(
        select(MarketplaceMediaMapping).where(
            MarketplaceMediaMapping.owner_id == owner.id,
            MarketplaceMediaMapping.listing_id == data.listing_id,
            MarketplaceMediaMapping.position == data.position,
        )
    )
    listing = db.get(MarketplaceListing, data.listing_id)
    if listing is None:
        raise HTTPException(404, "Marketplace listing not found.")
    reused = existing is not None
    if existing is None:
        existing = MarketplaceMediaMapping(
            owner_id=owner.id,
            listing_id=listing.id,
            media_id=preview.media_id,
            image_output_id=output_id,
            position=data.position,
            alt_text=None,
            remote_media_id=None,
            remote_url=None,
            status="accepted",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(existing)
    else:
        reused = existing.media_id == preview.media_id
        existing.media_id = preview.media_id
        existing.image_output_id = output_id
        existing.position = data.position
        existing.status = "accepted"
        existing.updated_at = _now()
    if not reused:
        record_event(
            db,
            actor_id=owner.id,
            action="ai.image_marketplace_handoff_completed",
            entity_type="marketplace_listing",
            entity_id=listing.id,
            metadata={
                "output_id": str(output_id),
                "media_id": str(preview.media_id),
                "marketplace": data.marketplace,
            },
        )
    db.commit()
    return {
        "status": "succeeded",
        "idempotent_reuse": reused,
        "media_id": str(preview.media_id),
        "listing_id": str(listing.id),
        "position": data.position,
    }


def campaign_handoff(
    db: Session, owner: User, output_id: uuid.UUID, data: ImageCampaignHandoffRequest
) -> dict[str, object]:
    output = _owned_output(db, owner, output_id)
    if output.status != "approved" or output.media_id is None:
        raise HTTPException(409, "Only an approved image can be used in a Campaign.")
    activity = db.scalar(
        select(CampaignActivity).where(
            CampaignActivity.id == data.activity_id,
            CampaignActivity.campaign_id == data.campaign_id,
            CampaignActivity.owner_id == owner.id,
        )
    )
    if activity is None:
        raise HTTPException(404, "Campaign activity not found.")
    if activity.row_version != data.expected_row_version:
        raise HTTPException(409, "Campaign activity changed; reload before attaching the image.")
    if data.confirm:
        activity.image_output_id = output.id
        activity.image_media_id = output.media_id
        activity.row_version += 1
        activity.updated_at = _now()
        record_event(
            db,
            actor_id=owner.id,
            action="ai.image_campaign_handoff_completed",
            entity_type="campaign_activity",
            entity_id=activity.id,
            metadata={"output_id": str(output.id), "media_id": str(output.media_id)},
        )
        db.commit()
    return {
        "status": "succeeded" if data.confirm else "preview",
        "output_id": str(output.id),
        "media_id": str(output.media_id),
        "activity_id": str(activity.id),
        "row_version": activity.row_version,
    }


def readiness(
    db: Session, owner: User, output_id: uuid.UUID, marketplace: str
) -> ImageReadinessResponse:
    row = db.scalar(
        select(AIImageOutput).where(
            AIImageOutput.id == output_id, AIImageOutput.owner_id == owner.id
        )
    )
    if row is None or row.media_id is None:
        raise HTTPException(404, "Approved image output not found.")
    reasons: list[str] = []
    ready = row.status == "approved"
    if not ready:
        reasons.append("Image approval is required.")
    if row.mime_type not in {None, "image/png", "image/jpeg", "image/webp"}:
        reasons.append("Unsupported image MIME type.")
    configured = MARKETPLACE_IMAGE_RULES.get(marketplace, {})
    if (
        row.mime_type
        and configured
        and row.mime_type not in cast(list[str], configured.get("allowed_mime", []))
    ):
        reasons.append("Unsupported MIME for marketplace.")
    if (
        configured
        and row.actual_width
        and row.actual_width < int(cast(int, configured.get("min_width", 0)))
    ):
        reasons.append("Image width is below marketplace minimum.")
    rules: dict[str, object] = {
        "marketplace": marketplace,
        "certification": "deterministic_local_rules_only",
        **configured,
    }
    return ImageReadinessResponse(
        media_id=row.media_id,
        marketplace=marketplace,
        ready=ready and not reasons,
        certified=False,
        reasons=reasons,
        rules=rules,
        blockers=reasons,
        warnings=[],
        rule_source=(
            str(configured.get("rule_source", "configured")) if configured else "configured"
        ),
    )


MARKETPLACE_IMAGE_RULES: dict[str, dict[str, object]] = {
    "amazon": {
        "allowed_mime": ["image/jpeg", "image/png"],
        "min_width": 64,
        "min_height": 64,
        "max_size_bytes": 10_000_000,
        "rule_source": "fake_certified",
    },
    "flipkart": {
        "allowed_mime": ["image/jpeg", "image/png"],
        "min_width": 300,
        "min_height": 300,
        "max_size_bytes": 10_000_000,
        "rule_source": "fake_certified",
    },
    "meesho": {
        "allowed_mime": ["image/jpeg", "image/png"],
        "min_width": 300,
        "min_height": 300,
        "max_size_bytes": 10_000_000,
        "rule_source": "fake_certified",
    },
    "shopify": {
        "allowed_mime": ["image/jpeg", "image/png", "image/webp"],
        "min_width": 100,
        "min_height": 100,
        "max_size_bytes": 20_000_000,
        "rule_source": "configured",
    },
    "wordpress": {
        "allowed_mime": ["image/jpeg", "image/png", "image/webp"],
        "min_width": 100,
        "min_height": 100,
        "max_size_bytes": 20_000_000,
        "rule_source": "configured",
    },
}


def approval_eligibility(
    db: Session, owner: User, output_id: uuid.UUID, marketplace: str | None = None
) -> ImageApprovalEligibilityResponse:
    row = _owned_output(db, owner, output_id)
    blockers: list[str] = []
    warnings: list[str] = []
    if row.status not in {"succeeded", "needs_review"}:
        blockers.append("output_not_reviewable")
    media = (
        db.scalar(
            select(MediaAsset).where(MediaAsset.id == row.media_id, MediaAsset.owner_id == owner.id)
        )
        if row.media_id
        else None
    )
    if media is None:
        blockers.append("generated_media_missing")
    else:
        if media.status != "ready":
            blockers.append("media_not_ready")
        if media.checksum_sha256 != row.checksum_sha256:
            blockers.append("checksum_mismatch")
        if media.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            blockers.append("unsupported_mime")
        if media.width <= 0 or media.height <= 0:
            blockers.append("invalid_dimensions")
        if media.size_bytes <= 0 or media.size_bytes > 20_000_000:
            blockers.append("invalid_file_size")
        if marketplace:
            rules = MARKETPLACE_IMAGE_RULES.get(marketplace, {})
            if rules:
                if media.mime_type not in cast(list[str], rules["allowed_mime"]):
                    blockers.append("marketplace_mime_blocker")
                if media.width < int(cast(int, rules["min_width"])) or media.height < int(
                    cast(int, rules["min_height"])
                ):
                    blockers.append("marketplace_dimensions_blocker")
                if media.size_bytes > int(cast(int, rules["max_size_bytes"])):
                    blockers.append("marketplace_size_blocker")
    return ImageApprovalEligibilityResponse(
        output_id=row.id, eligible=not blockers, blockers=blockers, warnings=warnings
    )


def compare_outputs(
    db: Session,
    owner: User,
    output_id: uuid.UUID,
    compare_output_id: uuid.UUID | None = None,
) -> ImageComparisonResponse:
    row = _owned_output(db, owner, output_id)
    other = _owned_output(db, owner, compare_output_id) if compare_output_id else None
    if other is None and row.parent_output_id:
        other = _owned_output(db, owner, row.parent_output_id)

    def facts(value: AIImageOutput) -> dict[str, object]:
        return {
            "output_id": str(value.id),
            "media_id": str(value.media_id) if value.media_id else None,
            "operation": value.operation,
            "channel": value.channel,
            "status": value.status,
            "dimensions": {
                "width": value.actual_width or value.requested_width,
                "height": value.actual_height or value.requested_height,
            },
            "mime": value.mime_type,
            "size_bytes": value.size_bytes,
            "checksum": value.checksum_sha256,
            "classification": value.asset_classification,
            "created_at": value.created_at.isoformat(),
        }

    left: dict[str, object] = (
        facts(other) if other else {"source_media_ids": row.source_media_ids_json}
    )
    right = facts(row)
    return ImageComparisonResponse(
        mode="version" if other else "source_generated",
        left=left,
        right=right,
        facts={
            "deterministic": True,
            "readiness": (
                readiness(db, owner, row.id, row.channel).model_dump(mode="json")
                if row.media_id
                else {}
            ),
        },
    )


def history(db: Session, owner: User, output_id: uuid.UUID) -> list[dict[str, object]]:
    row = _owned_output(db, owner, output_id)
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == row.id).order_by(AuditEvent.occurred_at)
    )
    return [
        {
            "action": event.action,
            "occurred_at": event.occurred_at.isoformat(),
            "correlation_id": event.correlation_id,
            "metadata": event.metadata_json or {},
        }
        for event in events
    ]


def marketplace_rules(marketplace: str | None = None) -> dict[str, object]:
    if marketplace:
        return dict(MARKETPLACE_IMAGE_RULES.get(marketplace, {}))
    return dict(MARKETPLACE_IMAGE_RULES)


def _alt_text_response(row: AIImageOutput) -> ImageAltTextResponse:
    return ImageAltTextResponse(
        output_id=row.id,
        media_id=row.media_id,
        text=row.alt_text,
        status=row.alt_text_status,
        version=row.alt_text_version,
        source=row.alt_text_source,
        provider=row.alt_text_provider,
        updated_at=row.alt_text_updated_at,
        approved_at=row.alt_text_approved_at,
    )


def get_alt_text(db: Session, owner: User, output_id: uuid.UUID) -> ImageAltTextResponse:
    row = _owned_output(db, owner, output_id)
    return _alt_text_response(row)


def manage_alt_text(
    db: Session, owner: User, output_id: uuid.UUID, data: ImageAltTextRequest
) -> ImageAltTextResponse:
    row = _owned_output(db, owner, output_id, for_update=True)
    product = db.get(Product, row.product_id)
    if product is None or row.media_id is None:
        raise HTTPException(409, "Image output has no persisted Media asset.")
    if data.action in {"edit", "approve"} and not (data.text or row.alt_text):
        raise HTTPException(422, "Alt text is required.")
    text = (data.text if data.text is not None else row.alt_text or "").strip()
    if len(text) > 500 or "<" in text or ">" in text:
        raise HTTPException(422, "Alt text contains unsupported markup or exceeds the safe limit.")
    if data.action in {"suggest", "regenerate"}:
        row.alt_text = text or f"{product.name} product image"
        row.alt_text_status = "suggested"
        row.alt_text_source = "ai_suggested"
        row.alt_text_provider = "deterministic_mock_v1"
    elif data.action == "edit":
        row.alt_text = text
        row.alt_text_status = "draft"
        row.alt_text_source = "manual"
    elif data.action == "approve":
        row.alt_text = text
        row.alt_text_status = "approved"
        row.alt_text_source = row.alt_text_source or "manual"
        row.alt_text_approved_at = _now()
        row.alt_text_approved_by = owner.id
    else:
        row.alt_text = text or row.alt_text
        row.alt_text_status = "rejected"
        row.alt_text_approved_at = None
        row.alt_text_approved_by = None
    row.alt_text_version = (row.alt_text_version or 0) + 1
    row.alt_text_updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action=f"ai.image_alt_text_{data.action}",
        entity_type="ai_image_output",
        entity_id=row.id,
        metadata={"media_id": str(row.media_id), "version": row.alt_text_version},
    )
    db.commit()
    return _alt_text_response(row)


def product_media_projection(
    db: Session, owner: User, product_id: uuid.UUID
) -> list[ProductMediaItem]:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    outputs = list(
        db.scalars(
            select(AIImageOutput)
            .where(
                AIImageOutput.owner_id == owner.id,
                AIImageOutput.product_id == product_id,
            )
            .order_by(AIImageOutput.created_at.desc())
        )
    )
    output_media_ids = {row.media_id for row in outputs if row.media_id is not None}
    source_ids = {sid for row in outputs for sid in row.source_media_ids_json}
    media_ids = {value for value in output_media_ids | {uuid.UUID(value) for value in source_ids}}
    media_rows = (
        {
            row.id: row
            for row in db.scalars(
                select(MediaAsset).where(
                    MediaAsset.owner_id == owner.id, MediaAsset.id.in_(media_ids)
                )
            )
        }
        if media_ids
        else {}
    )
    result: list[ProductMediaItem] = []
    for media in media_rows.values():
        row = next((item for item in outputs if item.media_id == media.id), None)
        marketplace: list[dict[str, object]] = [
            {
                "listing_id": str(mapping.listing_id),
                "position": mapping.position,
                "status": mapping.status,
            }
            for mapping in db.scalars(
                select(MarketplaceMediaMapping).where(
                    MarketplaceMediaMapping.owner_id == owner.id,
                    MarketplaceMediaMapping.media_id == media.id,
                )
            )
        ]
        campaign: list[dict[str, object]] = [
            {
                "activity_id": str(activity.id),
                "campaign_id": str(activity.campaign_id),
                "status": activity.status,
            }
            for activity in db.scalars(
                select(CampaignActivity).where(
                    CampaignActivity.owner_id == owner.id,
                    CampaignActivity.image_media_id == media.id,
                )
            )
        ]
        lineage = _lineage(db, row) if row else []
        result.append(
            ProductMediaItem(
                media_id=media.id,
                image_output_id=row.id if row else None,
                source_type=row.asset_classification if row else "original_uploaded",
                operation=row.operation if row else None,
                status=row.status if row else "ready",
                channel=row.channel if row else None,
                width=media.width,
                height=media.height,
                mime=media.mime_type,
                approval=row.status if row else "original",
                marketplace_usage=marketplace,
                campaign_usage=campaign,
                lineage=lineage,
                generated_at=row.created_at if row else None,
                readiness=(
                    readiness(db, owner, row.id, row.channel).model_dump()
                    if row and row.channel
                    else {}
                ),
            )
        )
    return result


def _preset_response(row: AIImagePreset) -> ImagePresetLifecycleResponse:
    rules = dict(row.rules_json or {})
    return ImagePresetLifecycleResponse(
        id=row.id,
        name=row.name,
        version=row.version,
        operation=row.operation,
        channel=row.channel,
        rules=rules,
        archived=bool(rules.get("archived")),
        is_default=bool(rules.get("is_default")),
    )


def create_preset(
    db: Session, owner: User, data: ImagePresetCreate
) -> ImagePresetLifecycleResponse:
    stamp = _now()
    row = AIImagePreset(
        owner_id=owner.id,
        name=data.name,
        version=1,
        operation=data.operation,
        channel=data.channel,
        rules_json=data.rules,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _preset_response(row)


def update_style(
    db: Session, owner: User, style_id: uuid.UUID, data: ImageStyleCreate
) -> ImageStyleResponse:
    current = db.scalar(
        select(AIImageStyle).where(AIImageStyle.id == style_id, AIImageStyle.owner_id == owner.id)
    )
    if current is None:
        raise HTTPException(404, "Image Style not found.")
    data = data.model_copy(update={"is_default": current.is_default})
    current.archived = True
    db.flush()
    return create_style(db, owner, data)


def set_style_archived(
    db: Session, owner: User, style_id: uuid.UUID, archived: bool
) -> ImageStyleResponse:
    row = db.scalar(
        select(AIImageStyle).where(AIImageStyle.id == style_id, AIImageStyle.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Image Style not found.")
    row.archived = archived
    if archived:
        row.is_default = False
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return style_response(row)


def style_preview(
    db: Session, owner: User, style_id: uuid.UUID, product_id: uuid.UUID
) -> dict[str, object]:
    row = db.scalar(
        select(AIImageStyle).where(AIImageStyle.id == style_id, AIImageStyle.owner_id == owner.id)
    )
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if row is None or product is None:
        raise HTTPException(404, "Image Style or Product not found.")
    return {
        "status": "preview",
        "style_id": str(row.id),
        "style_version": row.version,
        "product_id": str(product.id),
        "operation": "deterministic_style_preview",
        "approved": False,
    }


def set_style_default(db: Session, owner: User, style_id: uuid.UUID) -> ImageStyleResponse:
    row = db.scalar(
        select(AIImageStyle).where(AIImageStyle.id == style_id, AIImageStyle.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Image Style not found.")
    if row.archived:
        raise HTTPException(409, "Archived Image Styles cannot be default.")
    db.query(AIImageStyle).filter(
        AIImageStyle.owner_id == owner.id,
        AIImageStyle.brand_id == row.brand_id,
    ).update({AIImageStyle.is_default: False})
    row.is_default = True
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return style_response(row)
