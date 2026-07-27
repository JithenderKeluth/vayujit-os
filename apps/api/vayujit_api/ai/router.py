import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import AIGenerationRequest, PromptTemplate
from vayujit_api.ai.provider import DeterministicMockAIProvider
from vayujit_api.ai.schemas import (
    ArtifactDetails,
    CreateGenerationRequest,
    GenerationResponse,
    PaginatedHistory,
    ProviderSummary,
    RejectionRequest,
    TemplateSummary,
)
from vayujit_api.ai.service import (
    artifact_details,
    decide,
    generate,
    history,
    response_for,
)
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("/providers", response_model=list[ProviderSummary])
def providers(owner: CurrentUser) -> list[ProviderSummary]:
    provider = DeterministicMockAIProvider()
    return [
        ProviderSummary(
            key=provider.key,
            name=provider.name,
            provider_type=provider.provider_type,
            available=provider.available(),
            deterministic=True,
            local=True,
        )
    ]


@router.get("/templates", response_model=list[TemplateSummary])
def templates(db: DatabaseSession, owner: CurrentUser) -> list[TemplateSummary]:
    values = db.scalars(
        select(PromptTemplate)
        .where(PromptTemplate.status == "enabled")
        .order_by(
            PromptTemplate.is_default.desc(), PromptTemplate.key, PromptTemplate.version.desc()
        )
    )
    return [
        TemplateSummary(
            id=value.id,
            key=value.key,
            name=value.name,
            description=value.description,
            version=value.version,
            template_type=value.template_type,
            is_default=value.is_default,
        )
        for value in values
    ]


@router.post("/generations", response_model=GenerationResponse, status_code=201)
def create_generation(
    data: CreateGenerationRequest, db: DatabaseSession, owner: CurrentUser
) -> GenerationResponse:
    return generate(db, owner, data)


@router.get("/generations", response_model=PaginatedHistory)
@router.get("/artifacts", response_model=PaginatedHistory)
def generation_history(
    db: DatabaseSession,
    owner: CurrentUser,
    product_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    request_status: Literal["pending", "running", "completed", "failed", "cancelled"] | None = None,
    artifact_status: Literal["pending_review", "approved", "rejected", "superseded"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedHistory:
    return history(
        db,
        owner.id,
        product_id=product_id,
        brand_id=brand_id,
        request_status=request_status,
        artifact_status=artifact_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/generations/{generation_id}", response_model=GenerationResponse)
def generation(
    generation_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> GenerationResponse:
    request = db.scalar(
        select(AIGenerationRequest).where(
            AIGenerationRequest.id == generation_id,
            AIGenerationRequest.owner_id == owner.id,
        )
    )
    if request is None:
        raise HTTPException(404, "AI generation not found.")
    return response_for(db, request)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetails)
def artifact(artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> ArtifactDetails:
    return artifact_details(db, owner.id, artifact_id)


@router.post("/artifacts/{artifact_id}/approve", response_model=ArtifactDetails)
def approve(artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> ArtifactDetails:
    return decide(db, owner, artifact_id, approve=True)


@router.post("/artifacts/{artifact_id}/reject", response_model=ArtifactDetails)
def reject(
    artifact_id: uuid.UUID,
    data: RejectionRequest,
    db: DatabaseSession,
    owner: CurrentUser,
) -> ArtifactDetails:
    return decide(db, owner, artifact_id, approve=False, reason=data.reason)


@router.post(
    "/artifacts/{artifact_id}/regenerate", response_model=GenerationResponse, status_code=201
)
def regenerate(
    artifact_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> GenerationResponse:
    existing = artifact_details(db, owner.id, artifact_id)
    result = generate(
        db,
        owner,
        CreateGenerationRequest(
            product_id=existing.product_id,
            prompt_template_id=existing.template_id,
        ),
    )
    record_event(
        db,
        actor_id=owner.id,
        action="ai.artifact_regenerated",
        entity_type="generated_artifact",
        entity_id=artifact_id,
        metadata={
            "product_id": str(existing.product_id),
            "changed_artifact_id": str(result.artifact_id),
        },
    )
    db.commit()
    return result
