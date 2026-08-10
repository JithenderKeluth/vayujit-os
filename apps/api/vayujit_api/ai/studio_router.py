from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.configuration import owned_configuration
from vayujit_api.ai.models import AIGenerationRequest, GeneratedArtifact
from vayujit_api.ai.studio_models import (
    AIStudioGeneration,
    AIStudioJob,
    AIStudioJobAttempt,
    AIStudioOutput,
    BrandVoice,
    GenerationPreset,
    KeywordSet,
)
from vayujit_api.ai.studio_schemas import (
    BrandVoiceCreate,
    BrandVoicePreviewRequest,
    BrandVoicePreviewResponse,
    BrandVoiceResponse,
    ContentType,
    KeywordSetCreate,
    KeywordSetResponse,
    PresetCreate,
    PresetResponse,
    SEOAnalyzeRequest,
    SEOAnalyzeResponse,
    StudioArtifactEdit,
    StudioArtifactResponse,
    StudioComparisonResponse,
    StudioContextResponse,
    StudioGenerateRequest,
    StudioGenerationResponse,
    StudioHandoffRequest,
    StudioRejectRequest,
)
from vayujit_api.ai.studio_service import (
    _artifact_response,
    _content,
    _context,
    _quality,
    compare,
    context_response,
    create_voice,
    generate_studio,
    generation_response,
    keyword_response,
    preset_response,
    seo_analyze,
    voice_response,
)
from vayujit_api.ai.studio_worker import transition_state
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.commerce.models import MarketplaceListing
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/ai/studio", tags=["ai-studio"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


def _artifact(db: Session, owner_id: uuid.UUID, artifact_id: uuid.UUID) -> GeneratedArtifact:
    row = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == artifact_id, GeneratedArtifact.owner_id == owner_id
        )
    )
    if row is None:
        raise HTTPException(404, "AI artifact not found.")
    return row


@router.get("/providers")
def studio_providers(db: DatabaseSession, owner: CurrentUser) -> list[dict[str, object]]:
    configuration = owned_configuration(db, owner.id)
    remote_configured = configuration is not None and bool(configuration.encrypted_api_key)
    remote_health_state = "unconfigured"
    if remote_configured:
        remote_health_state = (
            "disabled" if configuration is not None and not configuration.enabled else "unknown"
        )
    return [
        {
            "id": "deterministic_mock_v1",
            "display_name": "Local deterministic provider",
            "configured": True,
            "enabled": True,
            "available": True,
            "models": ["studio-deterministic-v1"],
            "default_model": "studio-deterministic-v1",
            "structured_output": True,
            "context_capacity": None,
            "output_capacity": None,
            "last_health_state": "healthy",
            "health_state": "healthy",
            "recommended_model": "studio-deterministic-v1",
            "capabilities": ["text_generation", "structured_output", "seo_analysis"],
            "live_validation": "local",
        },
        {
            "id": "openai_compatible",
            "display_name": "OpenAI-compatible provider",
            "configured": remote_configured,
            "enabled": bool(configuration.enabled) if configuration else False,
            "available": False,
            "models": [],
            "default_model": None,
            "structured_output": True,
            "context_capacity": None,
            "output_capacity": None,
            "last_health_state": "not_validated",
            "health_state": ("unconfigured" if not remote_configured else remote_health_state),
            "recommended_model": None,
            "capabilities": ["text_generation", "structured_output"],
            "live_validation": "not_performed",
        },
    ]


@router.get("/brand-voices", response_model=list[BrandVoiceResponse])
def list_brand_voices(
    db: DatabaseSession,
    owner: CurrentUser,
    include_archived: bool = False,
    brand_id: uuid.UUID | None = None,
) -> list[BrandVoiceResponse]:
    query = select(BrandVoice).where(BrandVoice.owner_id == owner.id)
    if not include_archived:
        query = query.where(BrandVoice.archived.is_(False))
    if brand_id is not None:
        query = query.where(BrandVoice.brand_id == brand_id)
    return [
        voice_response(row)
        for row in db.scalars(query.order_by(BrandVoice.name, BrandVoice.version.desc()))
    ]


@router.get("/brand-voices/{voice_id}", response_model=BrandVoiceResponse)
def get_brand_voice(
    voice_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    row = db.scalar(
        select(BrandVoice).where(BrandVoice.id == voice_id, BrandVoice.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Brand Voice not found.")
    return voice_response(row)


@router.post("/brand-voices", response_model=BrandVoiceResponse, status_code=201)
def add_brand_voice(
    data: BrandVoiceCreate, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    return create_voice(db, owner, data)


@router.patch("/brand-voices/{voice_id}", response_model=BrandVoiceResponse)
def update_brand_voice(
    voice_id: uuid.UUID, data: BrandVoiceCreate, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    current = db.scalar(
        select(BrandVoice).where(BrandVoice.id == voice_id, BrandVoice.owner_id == owner.id)
    )
    if current is None:
        raise HTTPException(404, "Brand Voice not found.")
    if (
        data.brand_id
        and db.scalar(select(Brand).where(Brand.id == data.brand_id, Brand.owner_id == owner.id))
        is None
    ):
        raise HTTPException(404, "Brand not found.")
    if data.is_default:
        db.query(BrandVoice).filter(
            BrandVoice.owner_id == owner.id, BrandVoice.brand_id == data.brand_id
        ).update({BrandVoice.is_default: False})
    stamp = datetime.now(UTC)
    row = BrandVoice(
        owner_id=owner.id,
        brand_id=data.brand_id,
        name=data.name,
        description=data.description,
        tone=data.tone,
        personality=data.personality,
        terminology_json=data.terminology,
        target_audience=data.target_audience,
        preferred_phrases_json=data.preferred_phrases,
        prohibited_phrases_json=data.prohibited_phrases,
        spelling_conventions=data.spelling_conventions,
        language=data.language,
        locale=data.locale,
        formatting_preferences_json=data.formatting_preferences,
        compliance_notes=data.compliance_notes,
        custom_instructions=data.custom_instructions,
        version=current.version + 1,
        is_default=data.is_default,
        archived=False,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.brand_voice_updated",
        entity_type="ai_brand_voice",
        entity_id=row.id,
        metadata={
            "previous_id": str(current.id),
            "version": row.version,
            "previous_version": current.version,
        },
    )
    db.commit()
    db.refresh(row)
    return voice_response(row)


@router.get("/presets", response_model=list[PresetResponse])
def list_presets(
    db: DatabaseSession,
    owner: CurrentUser,
    include_archived: bool = False,
    channel: str | None = None,
    content_type: str | None = None,
    default_only: bool = False,
) -> list[PresetResponse]:
    query = select(GenerationPreset).where(
        (GenerationPreset.owner_id == owner.id) | (GenerationPreset.is_system.is_(True))
    )
    if not include_archived:
        query = query.where(GenerationPreset.archived.is_(False))
    if channel:
        query = query.where(GenerationPreset.channels_json.contains([channel]))
    if content_type:
        query = query.where(GenerationPreset.output_types_json.contains([content_type]))
    if default_only:
        query = query.where(GenerationPreset.is_default.is_(True))
    return [
        preset_response(row)
        for row in db.scalars(
            query.order_by(GenerationPreset.name, GenerationPreset.version.desc())
        )
    ]


@router.get("/presets/{preset_id}", response_model=PresetResponse)
def get_preset(preset_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> PresetResponse:
    row = db.scalar(
        select(GenerationPreset).where(
            GenerationPreset.id == preset_id,
            (GenerationPreset.owner_id == owner.id) | (GenerationPreset.is_system.is_(True)),
        )
    )
    if row is None:
        raise HTTPException(404, "Preset not found.")
    return preset_response(row)


@router.post("/presets", response_model=PresetResponse, status_code=201)
def add_preset(data: PresetCreate, db: DatabaseSession, owner: CurrentUser) -> PresetResponse:
    if data.brand_voice_id:
        voice = db.scalar(
            select(BrandVoice).where(
                BrandVoice.id == data.brand_voice_id,
                BrandVoice.owner_id == owner.id,
                BrandVoice.archived.is_(False),
            )
        )
        if voice is None:
            raise HTTPException(409, "Brand Voice not found or archived.")
    stamp = datetime.now(UTC)
    row = GenerationPreset(
        owner_id=owner.id,
        name=data.name,
        description=data.description,
        brand_voice_id=data.brand_voice_id,
        locale=data.locale,
        guidance=data.guidance,
        preferred_provider=data.preferred_provider,
        preferred_model=data.preferred_model,
        output_types_json=data.output_types,
        channels_json=data.channels,
        tone=data.tone,
        length=data.length,
        required_context_json=data.required_context,
        validation_rules_json=data.validation_rules,
        is_system=False,
        is_default=False,
        version=1,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.preset_created",
        entity_type="ai_generation_preset",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return preset_response(row)


@router.post("/brand-voices/{voice_id}/preview", response_model=BrandVoicePreviewResponse)
def preview_brand_voice(
    voice_id: uuid.UUID, data: BrandVoicePreviewRequest, db: DatabaseSession, owner: CurrentUser
) -> BrandVoicePreviewResponse:
    voice = db.scalar(
        select(BrandVoice).where(
            BrandVoice.id == voice_id,
            BrandVoice.owner_id == owner.id,
            BrandVoice.archived.is_(False),
        )
    )
    if voice is None:
        raise HTTPException(404, "Brand Voice not found.")
    context, _, _ = _context(db, owner.id, data.product_id, voice.id)
    sample = _content(context, data.channel, data.content_type, None, voice, [])
    record_event(
        db,
        actor_id=owner.id,
        action="ai.brand_voice_previewed",
        entity_type="ai_brand_voice",
        entity_id=voice.id,
        metadata={
            "version": voice.version,
            "product_id": str(data.product_id),
            "channel": data.channel,
            "content_type": data.content_type,
        },
    )
    db.commit()
    return BrandVoicePreviewResponse(
        voice_id=voice.id,
        voice_version=voice.version,
        channel=data.channel,
        content_type=data.content_type,
        sample=sample,
    )


@router.get("/keywords", response_model=list[KeywordSetResponse])
def list_keywords(db: DatabaseSession, owner: CurrentUser) -> list[KeywordSetResponse]:
    return [
        keyword_response(row)
        for row in db.scalars(
            select(KeywordSet).where(KeywordSet.owner_id == owner.id).order_by(KeywordSet.name)
        )
    ]


@router.post("/keywords", response_model=KeywordSetResponse, status_code=201)
def add_keywords(
    data: KeywordSetCreate, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetResponse:
    row = KeywordSet(
        owner_id=owner.id,
        name=data.name,
        brand_id=data.brand_id,
        product_id=data.product_id,
        primary_keywords_json=data.primary_keywords,
        secondary_keywords_json=data.secondary_keywords,
        marketplace_keywords_json=data.marketplace_keywords,
        website_keywords_json=data.website_keywords,
        campaign_keywords_json=data.campaign_keywords,
        negative_keywords_json=data.negative_keywords,
        source=data.source,
        notes=data.notes,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return keyword_response(row)


@router.get("/context/{product_id}", response_model=StudioContextResponse)
def get_context(
    product_id: uuid.UUID,
    db: DatabaseSession,
    owner: CurrentUser,
    voice_id: uuid.UUID | None = None,
    locale: str = "en-IN",
) -> StudioContextResponse:
    return context_response(db, owner.id, product_id, voice_id, locale)


@router.post("/generate", response_model=StudioGenerationResponse, status_code=202)
def generate(
    data: StudioGenerateRequest, db: DatabaseSession, owner: CurrentUser
) -> StudioGenerationResponse:
    return generate_studio(db, owner, data)


@router.get("/generations/{generation_id}", response_model=StudioGenerationResponse)
def get_generation(
    generation_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> StudioGenerationResponse:
    row = db.scalar(
        select(AIStudioGeneration).where(
            AIStudioGeneration.id == generation_id, AIStudioGeneration.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "AI Studio generation not found.")
    return generation_response(db, row)


@router.get("/artifacts", response_model=list[StudioArtifactResponse])
def list_artifacts(
    db: DatabaseSession,
    owner: CurrentUser,
    product_id: uuid.UUID | None = None,
    channel: str | None = None,
    content_type: str | None = None,
    status: str | None = None,
) -> list[StudioArtifactResponse]:
    query = select(GeneratedArtifact).where(GeneratedArtifact.owner_id == owner.id)
    if product_id:
        query = query.where(GeneratedArtifact.product_id == product_id)
    if channel:
        query = query.where(GeneratedArtifact.channel == channel)
    if content_type:
        query = query.where(GeneratedArtifact.content_type == content_type)
    if status:
        query = query.where(GeneratedArtifact.status == status)
    return [
        _artifact_response(db, row)
        for row in db.scalars(query.order_by(GeneratedArtifact.created_at.desc()))
    ]


@router.get("/artifacts/{artifact_id}/history")
def artifact_history(
    artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> list[dict[str, object]]:
    source = _artifact(db, owner.id, artifact_id)
    ids: set[uuid.UUID] = {source.id}
    frontier = [source.id]
    while frontier and len(ids) < 100:
        children = list(
            db.scalars(
                select(GeneratedArtifact.id).where(
                    GeneratedArtifact.owner_id == owner.id,
                    GeneratedArtifact.parent_artifact_id.in_(frontier),
                )
            )
        )
        frontier = [item for item in children if item not in ids]
        ids.update(frontier)
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_id == owner.id, AuditEvent.entity_id.in_(ids))
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
    )
    return [
        {
            "id": event.id,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "metadata": event.metadata_json,
            "correlation_id": event.correlation_id,
            "occurred_at": event.occurred_at,
        }
        for event in events
    ]


@router.get("/artifacts/{artifact_id}/lineage")
def artifact_lineage(
    artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> list[StudioArtifactResponse]:
    row = _artifact(db, owner.id, artifact_id)
    lineage: list[GeneratedArtifact] = []
    seen: set[uuid.UUID] = set()
    while row.id not in seen and len(lineage) < 100:
        lineage.append(row)
        seen.add(row.id)
        if row.parent_artifact_id is None:
            break
        parent = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == row.parent_artifact_id,
                GeneratedArtifact.owner_id == owner.id,
            )
        )
        if parent is None:
            break
        row = parent
    return [_artifact_response(db, item) for item in reversed(lineage)]


@router.get("/artifacts/{artifact_id}", response_model=StudioArtifactResponse)
def get_artifact(
    artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> StudioArtifactResponse:
    return _artifact_response(db, _artifact(db, owner.id, artifact_id))


@router.get("/artifacts/{artifact_id}/compare", response_model=StudioComparisonResponse)
def compare_artifacts(
    artifact_id: uuid.UUID,
    db: DatabaseSession,
    owner: CurrentUser,
    against_id: uuid.UUID,
) -> StudioComparisonResponse:
    assert db is not None and owner is not None
    result = compare(db, owner.id, artifact_id, against_id)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.artifact_compared",
        entity_type="generated_artifact",
        entity_id=artifact_id,
        metadata={"against_artifact_id": str(against_id)},
    )
    db.commit()
    return result


@router.patch("/artifacts/{artifact_id}", response_model=StudioArtifactResponse)
def edit_artifact(
    artifact_id: uuid.UUID, data: StudioArtifactEdit, db: DatabaseSession, owner: CurrentUser
) -> StudioArtifactResponse:
    row = _artifact(db, owner.id, artifact_id)
    if (
        data.expected_source_version is not None
        and data.expected_source_version != row.version_number
    ):
        raise HTTPException(409, "Artifact version is stale; refresh before editing.")
    existing_edit = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.parent_artifact_id == row.id,
            GeneratedArtifact.source == "ai_human_edited",
        )
    )
    if existing_edit is not None:
        raise HTTPException(
            409, "This Artifact version already has a human edit. Refresh before editing."
        )
    if row.status == "approved":
        raise HTTPException(409, "Approved artifacts cannot be edited; regenerate a new version.")
    product = db.get(Product, row.product_id)
    if product is None:
        raise HTTPException(404, "Product not found.")
    source_request = db.get(AIGenerationRequest, row.generation_request_id)
    if source_request is None:
        raise HTTPException(409, "Artifact generation lineage is unavailable.")
    stamp = datetime.now(UTC)
    next_version = (
        db.scalar(
            select(func.max(GeneratedArtifact.version_number)).where(
                GeneratedArtifact.owner_id == owner.id,
                GeneratedArtifact.product_id == row.product_id,
            )
        )
        or 0
    ) + 1
    context = row.input_context_json or {}
    quality = _quality(data.content, row.channel, context, [])
    request = AIGenerationRequest(
        owner_id=owner.id,
        brand_id=row.brand_id,
        product_id=row.product_id,
        prompt_template_id=row.prompt_template_id,
        provider_key=source_request.provider_key,
        status="completed",
        additional_instructions="Human-edited Artifact version.",
        normalized_input_hash=None,
        started_at=stamp,
        completed_at=stamp,
        failed_at=None,
        error_code=None,
        safe_error_message=None,
        created_at=stamp,
        updated_at=stamp,
        selected_model=source_request.selected_model,
        final_provider_key=source_request.final_provider_key or source_request.provider_key,
        fallback_used=source_request.fallback_used,
        final_attempt_count=source_request.final_attempt_count,
        total_latency_ms=source_request.total_latency_ms,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        estimated_total_cost=None,
        cost_currency=None,
        channel=row.channel,
        content_type=row.content_type,
        locale=row.locale,
        context_fingerprint=row.context_fingerprint,
        brand_voice_id=row.brand_voice_id,
        preset_id=source_request.preset_id,
        generation_reason="human_edit",
        user_instruction_fingerprint=None,
    )
    db.add(request)
    db.flush()
    edited = GeneratedArtifact(
        owner_id=owner.id,
        brand_id=row.brand_id,
        product_id=row.product_id,
        generation_request_id=request.id,
        prompt_template_id=row.prompt_template_id,
        artifact_type=row.artifact_type,
        version_number=next_version,
        status="pending_review",
        content_json=data.content,
        validation_result=quality,
        provider_metadata={**(row.provider_metadata or {}), "origin": "ai_human_edited"},
        channel=row.channel,
        content_type=row.content_type,
        locale=row.locale,
        context_fingerprint=row.context_fingerprint,
        brand_voice_id=row.brand_voice_id,
        parent_artifact_id=row.id,
        generation_reason="human_edit",
        source="ai_human_edited",
        user_instructions=row.user_instructions,
        input_context_json=context,
        edited_at=stamp,
        edited_by=owner.id,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(edited)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.artifact_edited",
        entity_type="generated_artifact",
        entity_id=edited.id,
        metadata={
            "source_artifact_id": str(row.id),
            "source_artifact_version": row.version_number,
            "artifact_version": edited.version_number,
        },
    )
    db.commit()
    db.refresh(edited)
    return _artifact_response(db, edited)


@router.post("/artifacts/{artifact_id}/approve", response_model=StudioArtifactResponse)
def approve_artifact(
    artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> StudioArtifactResponse:
    row = _artifact(db, owner.id, artifact_id)
    if row.status == "rejected":
        raise HTTPException(409, "Rejected artifacts cannot be approved.")
    if row.status == "approved":
        return _artifact_response(db, row)
    validation = row.validation_result or {}
    blockers = validation.get("blockers", [])
    if validation.get("valid") is False or (isinstance(blockers, list) and blockers):
        raise HTTPException(409, "Artifact has unresolved quality blockers.")
    row.status = "approved"
    row.approved_by = owner.id
    row.approved_at = datetime.now(UTC)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.artifact_approved",
        entity_type="generated_artifact",
        entity_id=row.id,
        metadata={"artifact_version": row.version_number},
    )
    db.commit()
    db.refresh(row)
    return _artifact_response(db, row)


@router.post("/artifacts/{artifact_id}/reject", response_model=StudioArtifactResponse)
def reject_artifact(
    artifact_id: uuid.UUID, data: StudioRejectRequest, db: DatabaseSession, owner: CurrentUser
) -> StudioArtifactResponse:
    row = _artifact(db, owner.id, artifact_id)
    if row.status == "approved":
        raise HTTPException(409, "Approved artifacts cannot be rejected.")
    if row.status == "rejected":
        return _artifact_response(db, row)
    row.status = "rejected"
    row.rejection_reason = data.reason
    row.rejection_category = data.category
    row.rejection_feedback = data.feedback
    row.rejection_field_notes = data.field_notes
    row.rejection_regeneration_guidance = data.regeneration_guidance
    row.rejected_by = owner.id
    row.rejected_at = datetime.now(UTC)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.artifact_rejected",
        entity_type="generated_artifact",
        entity_id=row.id,
        metadata={"artifact_version": row.version_number, "category": data.category},
    )
    db.commit()
    db.refresh(row)
    return _artifact_response(db, row)


@router.post(
    "/artifacts/{artifact_id}/regenerate", response_model=StudioGenerationResponse, status_code=201
)
def regenerate_artifact(
    artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> StudioGenerationResponse:
    source = _artifact(db, owner.id, artifact_id)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.artifact_regeneration_requested",
        entity_type="generated_artifact",
        entity_id=source.id,
        metadata={"source_artifact_version": source.version_number, "reason": "regeneration"},
    )
    request = StudioGenerateRequest(
        product_ids=[source.product_id],
        channels=[source.channel],
        content_types=[cast(ContentType, source.content_type)],
        brand_voice_id=source.brand_voice_id,
        locale=source.locale,
        provider_key="deterministic_mock_v1",
        generation_reason="regeneration",
        source_artifact_id=source.id,
        idempotency_key=f"regenerate:{source.id}:{source.version_number}",
    )
    result = generate_studio(db, owner, request)
    output = next((item for item in result.outputs if item.artifact_id), None)
    if output and output.artifact_id:
        replacement = _artifact(db, owner.id, output.artifact_id)
        replacement.parent_artifact_id = source.id
        replacement.generation_reason = "regeneration"
        db.commit()
    return result


@router.post("/artifacts/{artifact_id}/listing-handoff")
def listing_handoff(
    artifact_id: uuid.UUID, data: StudioHandoffRequest, db: DatabaseSession, owner: CurrentUser
) -> dict[str, object]:
    row = _artifact(db, owner.id, artifact_id)
    if row.status != "approved":
        raise HTTPException(409, "Artifact approval is required before listing handoff.")
    if (
        data.expected_artifact_version is not None
        and data.expected_artifact_version != row.version_number
    ):
        raise HTTPException(409, "Artifact preview is stale; refresh before handoff.")
    if data.marketplace and data.marketplace != row.channel:
        raise HTTPException(409, "Artifact channel does not match the requested marketplace.")
    if data.listing_id:
        listing = db.scalar(
            select(MarketplaceListing).where(
                MarketplaceListing.id == data.listing_id,
                MarketplaceListing.owner_id == owner.id,
            )
        )
        if listing is None:
            raise HTTPException(404, "Listing not found.")
        if listing.product_id != row.product_id or listing.marketplace != row.channel:
            raise HTTPException(409, "Listing does not match the Artifact Product or channel.")
        if (
            listing.content_artifact_id == row.id
            and listing.content_artifact_version == row.version_number
        ):
            return {
                "status": "completed",
                "artifact_id": str(row.id),
                "artifact_version": row.version_number,
                "listing_id": str(listing.id),
                "idempotent_reuse": True,
            }
        if (
            listing.content_artifact_id is not None
            and data.expected_current_artifact_version is None
        ):
            raise HTTPException(409, "Listing changed; request a fresh handoff preview.")
        if (
            data.expected_current_artifact_version is not None
            and data.expected_current_artifact_version != listing.content_artifact_version
        ):
            raise HTTPException(409, "Listing preview is stale; refresh before handoff.")
        if not data.confirm:
            record_event(
                db,
                actor_id=owner.id,
                action="ai.artifact_listing_handoff_previewed",
                entity_type="marketplace_listing",
                entity_id=listing.id,
                metadata={"artifact_id": str(row.id), "artifact_version": row.version_number},
            )
            db.commit()
            return {
                "status": "confirmation_required",
                "artifact_id": str(row.id),
                "artifact_version": row.version_number,
                "listing_id": str(listing.id),
                "current_artifact_version": listing.content_artifact_version,
            }
        listing.content_artifact_id = row.id
        listing.content_artifact_version = row.version_number
        listing.description_source = "artifact"
        listing.updated_at = datetime.now(UTC)
        record_event(
            db,
            actor_id=owner.id,
            action="ai.artifact_listing_handoff_completed",
            entity_type="marketplace_listing",
            entity_id=listing.id,
            metadata={"artifact_id": str(row.id), "artifact_version": row.version_number},
        )
        db.commit()
        return {
            "status": "completed",
            "artifact_id": str(row.id),
            "artifact_version": row.version_number,
            "listing_id": str(listing.id),
        }
    return {
        "status": "ready_for_listing",
        "artifact_id": str(row.id),
        "artifact_version": row.version_number,
        "channel": row.channel,
        "content_type": row.content_type,
        "destination_id": str(data.destination_id) if data.destination_id else None,
    }


@router.post("/artifacts/{artifact_id}/campaign-handoff")
def campaign_handoff(
    artifact_id: uuid.UUID, data: StudioHandoffRequest, db: DatabaseSession, owner: CurrentUser
) -> dict[str, object]:
    row = _artifact(db, owner.id, artifact_id)
    if row.status != "approved":
        raise HTTPException(409, "Artifact approval is required before campaign handoff.")
    if (
        data.expected_artifact_version is not None
        and data.expected_artifact_version != row.version_number
    ):
        raise HTTPException(409, "Artifact preview is stale; refresh before handoff.")
    if data.activity_id:
        activity = db.scalar(
            select(CampaignActivity).where(
                CampaignActivity.id == data.activity_id, CampaignActivity.owner_id == owner.id
            )
        )
        if activity is None:
            raise HTTPException(404, "Campaign Activity not found.")
        if activity.product_id != row.product_id or (
            activity.status in {"completed", "succeeded", "cancelled"}
        ):
            raise HTTPException(409, "Campaign Activity is not eligible for this Artifact handoff.")
        if activity.artifact_id == row.id and activity.artifact_version == row.version_number:
            return {
                "status": "completed",
                "artifact_id": str(row.id),
                "artifact_version": row.version_number,
                "activity_id": str(activity.id),
                "idempotent_reuse": True,
            }
        if activity.artifact_id is not None and data.expected_current_artifact_version is None:
            raise HTTPException(409, "Campaign Activity changed; request a fresh handoff preview.")
        if (
            data.expected_current_artifact_version is not None
            and data.expected_current_artifact_version != activity.artifact_version
        ):
            raise HTTPException(409, "Campaign preview is stale; refresh before handoff.")
        if not data.confirm:
            record_event(
                db,
                actor_id=owner.id,
                action="ai.artifact_campaign_handoff_previewed",
                entity_type="campaign_activity",
                entity_id=activity.id,
                metadata={"artifact_id": str(row.id), "artifact_version": row.version_number},
            )
            db.commit()
            return {
                "status": "confirmation_required",
                "artifact_id": str(row.id),
                "artifact_version": row.version_number,
                "activity_id": str(activity.id),
                "current_artifact_version": activity.artifact_version,
            }
        activity.artifact_id = row.id
        activity.artifact_version = row.version_number
        activity.updated_at = datetime.now(UTC)
        activity.row_version += 1
        record_event(
            db,
            actor_id=owner.id,
            action="ai.artifact_campaign_handoff_completed",
            entity_type="campaign_activity",
            entity_id=activity.id,
            metadata={"artifact_id": str(row.id), "artifact_version": row.version_number},
        )
        db.commit()
        return {
            "status": "completed",
            "artifact_id": str(row.id),
            "artifact_version": row.version_number,
            "activity_id": str(activity.id),
        }
    return {
        "status": "ready_for_campaign",
        "artifact_id": str(row.id),
        "artifact_version": row.version_number,
        "channel": row.channel,
        "content_type": row.content_type,
        "destination_id": str(data.destination_id) if data.destination_id else None,
    }


@router.post("/seo/analyze", response_model=SEOAnalyzeResponse)
def analyze_seo(
    data: SEOAnalyzeRequest, db: DatabaseSession, owner: CurrentUser
) -> SEOAnalyzeResponse:
    return seo_analyze(db, owner.id, data)


@router.post(
    "/brand-voices/{voice_id}/duplicate", response_model=BrandVoiceResponse, status_code=201
)
def duplicate_brand_voice(
    voice_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    source = db.scalar(
        select(BrandVoice).where(BrandVoice.id == voice_id, BrandVoice.owner_id == owner.id)
    )
    if source is None:
        raise HTTPException(404, "Brand Voice not found.")
    stamp = datetime.now(UTC)
    row = BrandVoice(
        owner_id=owner.id,
        brand_id=source.brand_id,
        name=f"{source.name} copy",
        tone=source.tone,
        personality=source.personality,
        terminology_json=source.terminology_json,
        target_audience=source.target_audience,
        preferred_phrases_json=source.preferred_phrases_json,
        prohibited_phrases_json=source.prohibited_phrases_json,
        spelling_conventions=source.spelling_conventions,
        language=source.language,
        locale=source.locale,
        formatting_preferences_json=source.formatting_preferences_json,
        compliance_notes=source.compliance_notes,
        custom_instructions=source.custom_instructions,
        version=1,
        is_default=False,
        archived=False,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.brand_voice_duplicated",
        entity_type="ai_brand_voice",
        entity_id=row.id,
        metadata={"duplicated_from": str(source.id), "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return voice_response(row)


@router.post("/brand-voices/{voice_id}/default", response_model=BrandVoiceResponse)
def set_default_brand_voice(
    voice_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    row = db.scalar(
        select(BrandVoice).where(BrandVoice.id == voice_id, BrandVoice.owner_id == owner.id)
    )
    if row is None or row.archived:
        raise HTTPException(404, "Brand Voice not found.")
    db.query(BrandVoice).filter(
        BrandVoice.owner_id == owner.id, BrandVoice.brand_id == row.brand_id
    ).update({BrandVoice.is_default: False})
    row.is_default = True
    row.updated_at = datetime.now(UTC)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.brand_voice_default_changed",
        entity_type="ai_brand_voice",
        entity_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return voice_response(row)


@router.post("/brand-voices/{voice_id}/archive", response_model=BrandVoiceResponse)
def archive_brand_voice(
    voice_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    row = db.scalar(
        select(BrandVoice).where(BrandVoice.id == voice_id, BrandVoice.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Brand Voice not found.")
    row.archived = True
    row.is_default = False
    row.archived_at = datetime.now(UTC)
    row.updated_at = row.archived_at
    record_event(
        db,
        actor_id=owner.id,
        action="ai.brand_voice_archived",
        entity_type="ai_brand_voice",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return voice_response(row)


@router.post("/brand-voices/{voice_id}/restore", response_model=BrandVoiceResponse)
def restore_brand_voice(
    voice_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> BrandVoiceResponse:
    row = db.scalar(
        select(BrandVoice).where(BrandVoice.id == voice_id, BrandVoice.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Brand Voice not found.")
    row.archived = False
    row.archived_at = None
    row.updated_at = datetime.now(UTC)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.brand_voice_restored",
        entity_type="ai_brand_voice",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return voice_response(row)


@router.post("/presets/{preset_id}/duplicate", response_model=PresetResponse, status_code=201)
def duplicate_preset(
    preset_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> PresetResponse:
    source = db.scalar(
        select(GenerationPreset).where(
            GenerationPreset.id == preset_id,
            (GenerationPreset.owner_id == owner.id) | (GenerationPreset.is_system.is_(True)),
        )
    )
    if source is None:
        raise HTTPException(404, "Preset not found.")
    stamp = datetime.now(UTC)
    row = GenerationPreset(
        owner_id=owner.id,
        name=f"{source.name} copy",
        description=source.description,
        brand_voice_id=source.brand_voice_id,
        locale=source.locale,
        guidance=source.guidance,
        preferred_provider=source.preferred_provider,
        preferred_model=source.preferred_model,
        version=1,
        output_types_json=list(source.output_types_json or []),
        channels_json=list(source.channels_json or []),
        tone=source.tone,
        length=source.length,
        required_context_json=list(source.required_context_json or []),
        validation_rules_json=dict(source.validation_rules_json or {}),
        is_system=False,
        is_default=False,
        archived=False,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.preset_duplicated",
        entity_type="ai_generation_preset",
        entity_id=row.id,
        metadata={"duplicated_from": str(source.id), "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return preset_response(row)


@router.patch("/presets/{preset_id}", response_model=PresetResponse)
def update_preset(
    preset_id: uuid.UUID, data: PresetCreate, db: DatabaseSession, owner: CurrentUser
) -> PresetResponse:
    current = db.scalar(
        select(GenerationPreset).where(
            GenerationPreset.id == preset_id, GenerationPreset.owner_id == owner.id
        )
    )
    if current is None or current.archived:
        raise HTTPException(404, "Preset not found.")
    if (
        data.brand_voice_id
        and db.scalar(
            select(BrandVoice).where(
                BrandVoice.id == data.brand_voice_id,
                BrandVoice.owner_id == owner.id,
                BrandVoice.archived.is_(False),
            )
        )
        is None
    ):
        raise HTTPException(409, "Brand Voice not found or archived.")
    stamp = datetime.now(UTC)
    row = GenerationPreset(
        owner_id=owner.id,
        name=data.name,
        description=data.description,
        brand_voice_id=data.brand_voice_id,
        locale=data.locale,
        guidance=data.guidance,
        preferred_provider=data.preferred_provider,
        preferred_model=data.preferred_model,
        version=current.version + 1,
        output_types_json=data.output_types,
        channels_json=data.channels,
        tone=data.tone,
        length=data.length,
        required_context_json=data.required_context,
        validation_rules_json=data.validation_rules,
        is_system=False,
        is_default=current.is_default,
        archived=False,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.preset_updated",
        entity_type="ai_generation_preset",
        entity_id=row.id,
        metadata={
            "previous_id": str(current.id),
            "version": row.version,
            "previous_version": current.version,
        },
    )
    db.commit()
    db.refresh(row)
    return preset_response(row)


@router.post("/presets/{preset_id}/default", response_model=PresetResponse)
def set_default_preset(
    preset_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> PresetResponse:
    row = db.scalar(
        select(GenerationPreset).where(
            GenerationPreset.id == preset_id, GenerationPreset.owner_id == owner.id
        )
    )
    if row is None or row.archived:
        raise HTTPException(404, "Preset not found.")
    db.query(GenerationPreset).filter(GenerationPreset.owner_id == owner.id).update(
        {GenerationPreset.is_default: False}
    )
    row.is_default = True
    row.updated_at = datetime.now(UTC)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.preset_default_changed",
        entity_type="ai_generation_preset",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return preset_response(row)


@router.post("/presets/{preset_id}/archive", response_model=PresetResponse)
def archive_preset(preset_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> PresetResponse:
    row = db.scalar(
        select(GenerationPreset).where(
            GenerationPreset.id == preset_id, GenerationPreset.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Preset not found.")
    row.archived = True
    row.is_default = False
    row.archived_at = datetime.now(UTC)
    row.updated_at = row.archived_at
    record_event(
        db,
        actor_id=owner.id,
        action="ai.preset_archived",
        entity_type="ai_generation_preset",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return preset_response(row)


@router.post("/presets/{preset_id}/restore", response_model=PresetResponse)
def restore_preset(preset_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> PresetResponse:
    row = db.scalar(
        select(GenerationPreset).where(
            GenerationPreset.id == preset_id, GenerationPreset.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Preset not found.")
    row.archived = False
    row.archived_at = None
    row.updated_at = datetime.now(UTC)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.preset_restored",
        entity_type="ai_generation_preset",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return preset_response(row)


@router.get("/jobs")
def list_studio_jobs(
    db: DatabaseSession, owner: CurrentUser, state: str | None = None
) -> list[dict[str, object]]:
    query = select(AIStudioJob).where(AIStudioJob.owner_id == owner.id)
    if state:
        query = query.where(AIStudioJob.state == state)
    rows = db.scalars(query.order_by(AIStudioJob.created_at.desc())).all()
    return [
        {
            "id": str(row.id),
            "generation_id": str(row.generation_id),
            "product_id": str(row.product_id),
            "job_type": row.job_type,
            "channel": row.channel,
            "content_type": row.content_type,
            "locale": row.locale,
            "context_fingerprint": row.context_fingerprint,
            "provider": row.provider,
            "model": row.model,
            "state": row.state,
            "attempt_count": row.attempt_count,
            "artifact_id": str(row.artifact_id) if row.artifact_id else None,
            "correlation_id": row.correlation_id,
            "last_error_code": row.last_error_code,
            "safe_error_message": row.safe_error_message,
        }
        for row in rows
    ]


@router.post("/jobs/{job_id}/cancel")
def cancel_studio_job(
    job_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> dict[str, object]:
    row = db.scalar(
        select(AIStudioJob).where(AIStudioJob.id == job_id, AIStudioJob.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "AI Studio job not found.")
    if row.state in {"succeeded", "failed", "cancelled", "stale"}:
        return {"status": row.state, "cancelled": False}
    if row.state not in {"queued", "generating", "validating", "retry_wait", "needs_review"}:
        raise HTTPException(409, "This AI job cannot be cancelled safely.")
    row.state = transition_state(row.state, "cancelled")
    row.completed_at = datetime.now(UTC)
    row.updated_at = row.completed_at
    row.lease_owner = None
    row.lease_expires_at = None
    output = db.scalar(
        select(AIStudioOutput).where(
            AIStudioOutput.generation_id == row.generation_id,
            AIStudioOutput.product_id == row.product_id,
            AIStudioOutput.channel == row.channel,
            AIStudioOutput.content_type == row.content_type,
        )
    )
    if output and output.artifact_id is None:
        output.status = "cancelled"
        output.error_code = "cancelled"
        output.safe_error_message = "AI generation was cancelled before provider execution."
    record_event(
        db,
        actor_id=owner.id,
        action="ai.content_cancelled",
        entity_type="ai_studio_job",
        entity_id=row.id,
        metadata={"correlation_id": row.correlation_id},
    )
    db.commit()
    return {"status": "cancelled", "cancelled": True}


@router.post("/recovery/actions")
def recover_studio_action(
    data: dict[str, object], db: DatabaseSession, owner: CurrentUser
) -> dict[str, object]:
    """Execute a safe, idempotent recovery action for one AI Studio job."""
    action = str(data.get("action") or "")
    if action not in {"retry_generation", "refresh_context", "review_failure"}:
        raise HTTPException(422, "Unsupported AI recovery action.")
    raw_job_id = data.get("job_id") or data.get("generation_id")
    try:
        identifier = uuid.UUID(str(raw_job_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "A valid AI job or generation identifier is required.") from exc
    row = db.scalar(
        select(AIStudioJob).where(
            (AIStudioJob.id == identifier) | (AIStudioJob.generation_id == identifier),
            AIStudioJob.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "AI Studio job not found.")
    if action == "review_failure":
        return {
            "status": row.state,
            "action": action,
            "job_id": str(row.id),
            "generation_id": str(row.generation_id),
            "idempotent_reuse": True,
            "failure_category": row.failure_category,
            "retryable": row.retryable,
            "recovery_actions": list(row.recovery_actions_json or []),
            "safe_error_message": row.safe_error_message,
            "correlation_id": row.correlation_id,
        }
    if row.state in {"queued", "retry_wait", "generating", "validating"}:
        return {
            "status": row.state,
            "action": action,
            "job_id": str(row.id),
            "generation_id": str(row.generation_id),
            "idempotent_reuse": True,
            "failure_category": row.failure_category,
            "retryable": row.retryable,
            "recovery_actions": list(row.recovery_actions_json or []),
            "safe_error_message": row.safe_error_message,
            "correlation_id": row.correlation_id,
        }
    if row.state != "failed":
        raise HTTPException(409, "This AI generation cannot be recovered safely.")
    row.state = transition_state(row.state, "retry_wait")
    row.available_at = datetime.now(UTC)
    row.next_retry_at = row.available_at
    row.completed_at = None
    row.lease_owner = None
    row.lease_expires_at = None
    row.provider_result_json = None
    row.provider_result_fingerprint = None
    row.provider_request_id = None
    row.failure_category = None
    row.last_error_code = None
    row.safe_error_message = None
    row.retryable = True
    row.recovery_actions_json = []
    generation = db.get(AIStudioGeneration, row.generation_id)
    if generation:
        generation.status = "queued"
        generation.completed_at = None
        generation.error_code = None
        generation.safe_error_message = None
        generation.failure_category = None
        generation.retryable = False
        generation.recovery_actions_json = []
        generation.context_refresh_required = action == "refresh_context"
        if generation.failed_outputs:
            generation.failed_outputs -= 1
    output = db.scalar(
        select(AIStudioOutput).where(
            AIStudioOutput.generation_id == row.generation_id,
            AIStudioOutput.product_id == row.product_id,
            AIStudioOutput.channel == row.channel,
            AIStudioOutput.content_type == row.content_type,
        )
    )
    if output and output.artifact_id is None:
        output.status = "queued"
        output.error_code = None
        output.safe_error_message = None
    record_event(
        db,
        actor_id=owner.id,
        action="ai.content_recovery_requested",
        entity_type="ai_studio_job",
        entity_id=row.id,
        metadata={"action": action, "correlation_id": row.correlation_id},
    )
    db.commit()
    return {
        "status": row.state,
        "action": action,
        "job_id": str(row.id),
        "generation_id": str(row.generation_id),
        "idempotent_reuse": False,
        "failure_category": None,
        "retryable": True,
        "recovery_actions": ["review_failure"],
        "safe_error_message": "AI generation queued for a safe retry.",
        "correlation_id": row.correlation_id,
    }


@router.get("/usage")
def usage_dashboard(
    db: DatabaseSession,
    owner: CurrentUser,
    provider: str | None = None,
    model: str | None = None,
    channel: str | None = None,
    content_type: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, object]:
    query = select(AIStudioJob).where(AIStudioJob.owner_id == owner.id)
    if provider:
        query = query.where(AIStudioJob.provider == provider)
    if model:
        query = query.where(AIStudioJob.model == model)
    if channel:
        query = query.where(AIStudioJob.channel == channel)
    if content_type:
        query = query.where(AIStudioJob.content_type == content_type)
    if status:
        query = query.where(AIStudioJob.state == status)
    if date_from:
        query = query.where(AIStudioJob.created_at >= date_from)
    if date_to:
        query = query.where(AIStudioJob.created_at <= date_to)
    jobs = list(db.scalars(query))
    attempts = list(
        db.scalars(
            select(AIStudioJobAttempt)
            .join(AIStudioJob, AIStudioJobAttempt.job_id == AIStudioJob.id)
            .where(AIStudioJob.owner_id == owner.id)
        )
    )
    latencies = sorted([int(item.latency_ms) for item in attempts if item.latency_ms is not None])
    median = latencies[len(latencies) // 2] if latencies else None
    total = len(jobs)
    successful = sum(item.state == "succeeded" for item in jobs)
    failed = sum(item.state in {"failed", "stale", "cancelled"} for item in jobs)
    retries = sum(max(item.attempt_count - 1, 0) for item in jobs)
    states: dict[str, int] = {}
    channels: dict[str, int] = {}
    content_types: dict[str, int] = {}
    providers: dict[str, int] = {}
    for item in jobs:
        states[item.state] = states.get(item.state, 0) + 1
        channels[item.channel] = channels.get(item.channel, 0) + 1
        content_types[item.content_type] = content_types.get(item.content_type, 0) + 1
        providers[item.provider] = providers.get(item.provider, 0) + 1
    categories = {
        "throttled": 0,
        "transient": 0,
        "permanent": 0,
        "repair_attempts": 0,
        "repair_successes": 0,
        "retry_exhausted": 0,
    }
    for attempt in attempts:
        category = (attempt.failure_category or "").casefold()
        if "thrott" in category:
            categories["throttled"] += 1
        elif "transient" in category:
            categories["transient"] += 1
        elif category:
            categories["permanent"] += 1
    bulk_jobs = sum(item.job_type == "ai_bulk_generate" for item in jobs)
    single_jobs = max(0, total - bulk_jobs)
    return {
        "total_generations": total,
        "generations": total,
        "successful": successful,
        "failed": failed,
        "success_rate": round(successful / total * 100, 2) if total else None,
        "retry_count": retries,
        "retries": retries,
        "provider_calls": len(attempts),
        "latency_ms": {
            "average": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "median": median,
        },
        "median_latency_ms": median,
        "channels": channels,
        "content_types": content_types,
        "providers": providers,
        "states": states,
        "token_totals": None,
        "input_tokens": None,
        "output_tokens": None,
        "unknown_cost_count": total,
        "cost_status": "unavailable",
        "cost": None,
        "failure_metrics": categories,
        "bulk_generations": bulk_jobs,
        "single_generations": single_jobs,
    }


@router.get("/diagnostics")
def diagnostics(db: DatabaseSession, owner: CurrentUser) -> dict[str, object]:
    total = (
        db.scalar(
            select(func.count(AIStudioGeneration.id)).where(AIStudioGeneration.owner_id == owner.id)
        )
        or 0
    )
    completed = (
        db.scalar(
            select(func.count(AIStudioGeneration.id)).where(
                AIStudioGeneration.owner_id == owner.id, AIStudioGeneration.status == "completed"
            )
        )
        or 0
    )
    return {
        "provider": "deterministic_mock_v1",
        "available": True,
        "remote_calls_enabled": False,
        "generations": {"total": total, "completed": completed},
        "safe_message": "AI Studio diagnostics completed.",
    }
