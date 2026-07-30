import csv
import io
import math
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.configuration import (
    PROVIDER_KEY,
    discover_models,
    owned_configuration,
    remove_credential,
    response_for_configuration,
    save_configuration,
    set_enabled,
)
from vayujit_api.ai.credentials import CredentialError
from vayujit_api.ai.models import (
    AIGenerationAttempt,
    AIGenerationRequest,
    AIModelPricing,
    PromptTemplate,
)
from vayujit_api.ai.provider import DeterministicMockAIProvider, ProviderError
from vayujit_api.ai.schemas import (
    ArtifactDetails,
    CancellationResponse,
    CreateGenerationRequest,
    GenerationAttemptResponse,
    GenerationResponse,
    ModelSummary,
    PaginatedHistory,
    PricingCreate,
    PricingSummary,
    ProviderConfigurationResponse,
    ProviderConfigurationUpdate,
    ProviderSummary,
    ProviderValidationResult,
    RejectionRequest,
    TemplateSummary,
    UsageHistoryItem,
    UsageHistoryPage,
    UsageSummary,
)
from vayujit_api.ai.service import (
    artifact_details,
    decide,
    generate,
    history,
    response_for,
)
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import get_session
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product

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
        ),
        ProviderSummary(
            key=PROVIDER_KEY,
            name="OpenAI-compatible",
            provider_type="remote",
            available=False,
            deterministic=False,
            local=False,
        ),
    ]


def provider_http_error(error: Exception) -> HTTPException:
    if isinstance(error, ProviderError):
        return HTTPException(
            503 if error.retryable else 409,
            {"code": error.code, "message": error.safe_message},
        )
    return HTTPException(409, {"code": "provider_configuration_invalid", "message": str(error)})


@router.get(
    "/providers/{provider_key}/configuration",
    response_model=ProviderConfigurationResponse,
)
def provider_configuration(
    provider_key: str, db: DatabaseSession, owner: CurrentUser
) -> ProviderConfigurationResponse:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    try:
        return response_for_configuration(owned_configuration(db, owner.id))
    except CredentialError as error:
        raise provider_http_error(error) from None


@router.put(
    "/providers/{provider_key}",
    response_model=ProviderConfigurationResponse,
)
def configure_provider(
    provider_key: str,
    data: ProviderConfigurationUpdate,
    db: DatabaseSession,
    owner: CurrentUser,
) -> ProviderConfigurationResponse:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    try:
        return save_configuration(db, owner, data)
    except (CredentialError, ProviderError, ValueError) as error:
        raise provider_http_error(error) from None


@router.post(
    "/providers/{provider_key}/validate",
    response_model=ProviderValidationResult,
)
def validate_provider(
    provider_key: str, db: DatabaseSession, owner: CurrentUser
) -> ProviderValidationResult:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    configuration = owned_configuration(db, owner.id, required=True)
    assert configuration is not None
    started = time.perf_counter()
    try:
        models = discover_models(db, owner.id, refresh=True)
        if not configuration.manual_model_allowed and not any(
            item.identifier == configuration.default_model for item in models
        ):
            raise ProviderError("unsupported_model", "The configured model was not discovered.")
        configuration.validation_status = "valid"
        configuration.safe_validation_message = "Provider configuration is valid."
        valid = True
    except (CredentialError, ProviderError, ValueError) as error:
        configuration.validation_status = "invalid"
        configuration.safe_validation_message = (
            error.safe_message if isinstance(error, ProviderError) else str(error)
        )
        valid = False
    latency = round((time.perf_counter() - started) * 1000)
    configuration.last_validated_at = datetime.now().astimezone()
    configuration.last_validation_latency_ms = latency
    record_event(
        db,
        actor_id=owner.id,
        action="ai.provider_validated" if valid else "ai.provider_validation_failed",
        entity_type="ai_provider_configuration",
        entity_id=configuration.id,
        metadata={
            "provider": PROVIDER_KEY,
            "model": configuration.default_model,
            "valid": valid,
            "latency_ms": latency,
        },
    )
    db.commit()
    return ProviderValidationResult(
        valid=valid,
        status=configuration.validation_status,
        safe_message=configuration.safe_validation_message or "Validation completed.",
        correlation_id=correlation_id(),
        latency_ms=latency,
        validated_model=configuration.default_model if valid else None,
    )


@router.post(
    "/providers/{provider_key}/enable",
    response_model=ProviderConfigurationResponse,
)
def enable_provider(
    provider_key: str, db: DatabaseSession, owner: CurrentUser
) -> ProviderConfigurationResponse:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    try:
        return set_enabled(db, owner, True)
    except (CredentialError, ProviderError) as error:
        raise provider_http_error(error) from None


@router.post(
    "/providers/{provider_key}/disable",
    response_model=ProviderConfigurationResponse,
)
def disable_provider(
    provider_key: str, db: DatabaseSession, owner: CurrentUser
) -> ProviderConfigurationResponse:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    return set_enabled(db, owner, False)


@router.delete(
    "/providers/{provider_key}/credential",
    response_model=ProviderConfigurationResponse,
)
def delete_provider_credential(
    provider_key: str, db: DatabaseSession, owner: CurrentUser
) -> ProviderConfigurationResponse:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    return remove_credential(db, owner)


@router.get("/providers/{provider_key}/models", response_model=list[ModelSummary])
def provider_models(
    provider_key: str, db: DatabaseSession, owner: CurrentUser
) -> list[ModelSummary]:
    if provider_key != PROVIDER_KEY:
        raise HTTPException(404, "AI provider not found.")
    try:
        return [
            ModelSummary(
                identifier=item.identifier,
                provider_key=PROVIDER_KEY,
                structured_output=item.structured_output,
            )
            for item in discover_models(db, owner.id)
        ]
    except (CredentialError, ProviderError, ValueError) as error:
        raise provider_http_error(error) from None


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


@router.get(
    "/generations/{generation_id}/attempts",
    response_model=list[GenerationAttemptResponse],
)
def generation_attempts(
    generation_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> list[AIGenerationAttempt]:
    owned = db.scalar(
        select(AIGenerationRequest.id).where(
            AIGenerationRequest.id == generation_id,
            AIGenerationRequest.owner_id == owner.id,
        )
    )
    if owned is None:
        raise HTTPException(404, "AI generation not found.")
    return list(
        db.scalars(
            select(AIGenerationAttempt)
            .where(AIGenerationAttempt.generation_request_id == generation_id)
            .order_by(AIGenerationAttempt.attempt_number)
        )
    )


@router.post(
    "/generations/{generation_id}/cancel",
    response_model=CancellationResponse,
)
def cancel_generation(
    generation_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> CancellationResponse:
    request = db.scalar(
        select(AIGenerationRequest).where(
            AIGenerationRequest.id == generation_id,
            AIGenerationRequest.owner_id == owner.id,
        )
    )
    if request is None:
        raise HTTPException(404, "AI generation not found.")
    if request.status in {"completed", "failed"}:
        raise HTTPException(409, "Completed generations cannot be cancelled.")
    stamp = request.cancellation_requested_at or datetime.now().astimezone()
    request.cancellation_requested_at = stamp
    request.cancelled_at = stamp
    request.status = "cancelled"
    record_event(
        db,
        actor_id=owner.id,
        action="ai.generation_cancelled",
        entity_type="ai_generation_request",
        entity_id=request.id,
        metadata={"provider": request.provider_key, "remote_cancellation": False},
    )
    db.commit()
    return CancellationResponse(
        id=request.id,
        status=request.status,
        cancellation_requested_at=stamp,
    )


@router.get("/usage/summary", response_model=UsageSummary)
def usage_summary(db: DatabaseSession, owner: CurrentUser) -> UsageSummary:
    requests = (
        db.scalar(
            select(func.count(AIGenerationRequest.id)).where(
                AIGenerationRequest.owner_id == owner.id
            )
        )
        or 0
    )
    succeeded = (
        db.scalar(
            select(func.count(AIGenerationRequest.id)).where(
                AIGenerationRequest.owner_id == owner.id,
                AIGenerationRequest.status == "completed",
            )
        )
        or 0
    )
    failed = (
        db.scalar(
            select(func.count(AIGenerationRequest.id)).where(
                AIGenerationRequest.owner_id == owner.id,
                AIGenerationRequest.status == "failed",
            )
        )
        or 0
    )
    totals = db.execute(
        select(
            func.coalesce(func.sum(AIGenerationRequest.input_tokens), 0),
            func.coalesce(func.sum(AIGenerationRequest.output_tokens), 0),
            func.coalesce(func.sum(AIGenerationRequest.total_tokens), 0),
            func.coalesce(func.sum(AIGenerationRequest.final_attempt_count), 0),
            func.sum(AIGenerationRequest.estimated_total_cost),
        ).where(AIGenerationRequest.owner_id == owner.id)
    ).one()
    return UsageSummary(
        requests=requests,
        successful_generations=succeeded,
        failed_generations=failed,
        retries=max(int(totals[3]) - requests, 0),
        input_tokens=int(totals[0]),
        output_tokens=int(totals[1]),
        total_tokens=int(totals[2]),
        estimated_cost=str(totals[4]) if totals[4] is not None else None,
        cost_currency="USD" if totals[4] is not None else None,
    )


def usage_query(
    owner_id: uuid.UUID,
    *,
    provider_key: str | None = None,
    model: str | None = None,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Any:
    filters = [AIGenerationRequest.owner_id == owner_id]
    if provider_key:
        filters.append(AIGenerationRequest.final_provider_key == provider_key)
    if model:
        filters.append(AIGenerationRequest.selected_model == model)
    if brand_id:
        filters.append(AIGenerationRequest.brand_id == brand_id)
    if product_id:
        filters.append(AIGenerationRequest.product_id == product_id)
    if date_from:
        filters.append(AIGenerationRequest.created_at >= date_from)
    if date_to:
        filters.append(AIGenerationRequest.created_at <= date_to)
    return (
        select(AIGenerationRequest, Brand, Product)
        .join(Brand, Brand.id == AIGenerationRequest.brand_id)
        .join(Product, Product.id == AIGenerationRequest.product_id)
        .where(*filters)
    )


def usage_item(request: AIGenerationRequest, brand: Brand, product: Product) -> UsageHistoryItem:
    return UsageHistoryItem(
        generation_id=request.id,
        created_at=request.created_at,
        provider_key=request.final_provider_key or request.provider_key,
        model=request.selected_model,
        status=request.status,
        attempts=request.final_attempt_count,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
        total_tokens=request.total_tokens,
        estimated_cost=(
            str(request.estimated_total_cost) if request.estimated_total_cost is not None else None
        ),
        cost_currency=request.cost_currency,
        brand_id=brand.id,
        brand_name=brand.name,
        product_id=product.id,
        product_name=product.name,
    )


@router.get("/usage/history", response_model=UsageHistoryPage)
def usage_history(
    db: DatabaseSession,
    owner: CurrentUser,
    provider_key: str | None = None,
    model: str | None = None,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> UsageHistoryPage:
    if date_from and date_to and date_to - date_from > timedelta(days=366):
        raise HTTPException(422, "Usage date range cannot exceed 366 days.")
    query = usage_query(
        owner.id,
        provider_key=provider_key,
        model=model,
        brand_id=brand_id,
        product_id=product_id,
        date_from=date_from,
        date_to=date_to,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(AIGenerationRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return UsageHistoryPage(
        items=[usage_item(*row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


def csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/usage/export")
def usage_export(db: DatabaseSession, owner: CurrentUser) -> Response:
    since = datetime.now(UTC) - timedelta(days=31)
    rows = db.execute(
        usage_query(owner.id, date_from=since)
        .order_by(AIGenerationRequest.created_at.desc())
        .limit(5000)
    ).all()
    target = io.StringIO()
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(
        [
            "generation_id",
            "created_at",
            "provider",
            "model",
            "status",
            "attempts",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost",
            "currency",
            "brand",
            "product",
        ]
    )
    for row in rows:
        item = usage_item(*row)
        writer.writerow(
            [
                csv_safe(item.generation_id),
                csv_safe(item.created_at),
                csv_safe(item.provider_key),
                csv_safe(item.model),
                csv_safe(item.status),
                item.attempts,
                item.input_tokens,
                item.output_tokens,
                item.total_tokens,
                item.estimated_cost,
                item.cost_currency,
                csv_safe(item.brand_name),
                csv_safe(item.product_name),
            ]
        )
    return Response(
        target.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ai-usage.csv"'},
    )


@router.get("/pricing", response_model=list[PricingSummary])
def pricing(db: DatabaseSession, owner: CurrentUser) -> list[AIModelPricing]:
    return list(
        db.scalars(
            select(AIModelPricing)
            .where(AIModelPricing.owner_id == owner.id)
            .order_by(AIModelPricing.effective_from.desc())
            .limit(100)
        )
    )


@router.post("/pricing", response_model=PricingSummary, status_code=201)
def create_pricing(data: PricingCreate, db: DatabaseSession, owner: CurrentUser) -> AIModelPricing:
    if data.effective_to and data.effective_to <= data.effective_from:
        raise HTTPException(422, "Pricing end time must follow its start time.")
    value = AIModelPricing(owner_id=owner.id, **data.model_dump())
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.pricing_configured",
        entity_type="ai_model_pricing",
        entity_id=value.id,
        metadata={
            "provider": value.provider_key,
            "model_pattern": value.model_pattern,
            "currency": value.currency,
        },
    )
    db.commit()
    return value


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
