import hashlib
import math
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from fnmatch import fnmatchcase
from typing import Literal, cast

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from vayujit_api.ai.configuration import owned_configuration, provider_for
from vayujit_api.ai.models import (
    AIGenerationAttempt,
    AIGenerationRequest,
    AIModelPricing,
    GeneratedArtifact,
    PromptTemplate,
)
from vayujit_api.ai.provider import (
    AIProvider,
    DeterministicMockAIProvider,
    GenerationInput,
    ProviderError,
    ProviderResult,
)
from vayujit_api.ai.schemas import (
    ArtifactDetails,
    CreateGenerationRequest,
    GenerationResponse,
    HistoryItem,
    PaginatedHistory,
    ProductContent,
)
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product, ProductStatus

provider = DeterministicMockAIProvider()


def apply_cost(
    db: Session,
    owner_id: uuid.UUID,
    attempt: AIGenerationAttempt,
) -> tuple[Decimal | None, str | None]:
    if attempt.input_tokens is None or attempt.output_tokens is None:
        return None, None
    stamp = datetime.now(UTC)
    rates = db.scalars(
        select(AIModelPricing)
        .where(
            AIModelPricing.owner_id == owner_id,
            AIModelPricing.provider_key == attempt.provider_key,
            AIModelPricing.enabled.is_(True),
            AIModelPricing.effective_from <= stamp,
            (AIModelPricing.effective_to.is_(None) | (AIModelPricing.effective_to > stamp)),
        )
        .order_by(AIModelPricing.effective_from.desc())
    )
    rate = next((item for item in rates if fnmatchcase(attempt.model, item.model_pattern)), None)
    if rate is None:
        return None, None
    million = Decimal(1_000_000)
    value = (
        Decimal(attempt.input_tokens) * rate.input_cost_per_million_tokens / million
        + Decimal(attempt.output_tokens) * rate.output_cost_per_million_tokens / million
    )
    attempt.estimated_cost = value
    attempt.cost_currency = rate.currency
    return value, rate.currency


def owned_product_context(
    db: Session, owner_id: uuid.UUID, product_id: uuid.UUID, *, writable: bool = False
) -> tuple[Product, Brand]:
    row = db.execute(
        select(Product, Brand)
        .join(Brand, Brand.id == Product.brand_id)
        .where(Product.id == product_id, Product.owner_id == owner_id, Brand.owner_id == owner_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Product not found.")
    product, brand = row
    if writable:
        if product.status == ProductStatus.ARCHIVED.value:
            raise HTTPException(409, "Archived products cannot start generation.")
        if brand.status == BrandStatus.ARCHIVED.value:
            raise HTTPException(409, "Products in archived brands cannot start generation.")
    return product, brand


def resolve_template(db: Session, template_id: uuid.UUID | None) -> PromptTemplate:
    query = select(PromptTemplate).where(PromptTemplate.status == "enabled")
    query = (
        query.where(PromptTemplate.id == template_id)
        if template_id
        else query.where(PromptTemplate.is_default.is_(True)).order_by(
            PromptTemplate.version.desc()
        )
    )
    template = db.scalar(query.limit(1))
    if template is None:
        raise HTTPException(404, "AI template not found.")
    return template


def response_for(db: Session, request: AIGenerationRequest) -> GenerationResponse:
    artifact_id = db.scalar(
        select(GeneratedArtifact.id).where(GeneratedArtifact.generation_request_id == request.id)
    )
    return GenerationResponse(
        id=request.id,
        status=cast(
            "Literal['pending', 'running', 'completed', 'failed', 'cancelled']",
            request.status,
        ),
        artifact_id=artifact_id,
        error_code=request.error_code,
        safe_error_message=request.safe_error_message,
        provider_key=request.final_provider_key or request.provider_key,
        model=request.selected_model,
        attempt_count=request.final_attempt_count,
        fallback_used=request.fallback_used,
        correlation_id=correlation_id(),
    )


def resolve_provider(
    db: Session, owner_id: uuid.UUID, data: CreateGenerationRequest
) -> tuple[AIProvider, str, bool]:
    configuration = owned_configuration(db, owner_id)
    selected = data.provider_key
    if selected is None and configuration and configuration.enabled:
        selected = "openai_compatible"
    if selected in {None, provider.key}:
        return provider, data.model or "mock-product-content-v1", False
    if selected != "openai_compatible" or configuration is None or not configuration.enabled:
        raise HTTPException(409, "The selected AI provider is not enabled.")
    selected_provider = provider_for(configuration)
    model = data.model or configuration.default_model
    selected_provider.validate_model(model)
    fallback = bool(data.allow_fallback and configuration.fallback_provider_key == provider.key)
    return selected_provider, model, fallback


def run_attempt(
    db: Session,
    request: AIGenerationRequest,
    selected_provider: AIProvider,
    model: str,
    value: GenerationInput,
    *,
    fallback: bool = False,
) -> tuple[ProviderResult, AIGenerationAttempt]:
    number = request.final_attempt_count + 1
    attempt = AIGenerationAttempt(
        generation_request_id=request.id,
        attempt_number=number,
        provider_key=selected_provider.key,
        model=model,
        status="running",
        started_at=now(),
        usage_source="unavailable",
        retryable=False,
        fallback=fallback,
        correlation_id=correlation_id(),
    )
    db.add(attempt)
    db.flush()
    record_event(
        db,
        actor_id=request.owner_id,
        action="ai.generation_attempt_started",
        entity_type="ai_generation_attempt",
        entity_id=attempt.id,
        metadata={
            "generation_id": str(request.id),
            "provider": selected_provider.key,
            "model": model,
            "attempt": number,
            "fallback": fallback,
        },
    )
    before = time.perf_counter()
    try:
        result = selected_provider.generate(value, model)
        attempt.status = "succeeded"
        attempt.input_tokens = result.input_tokens
        attempt.output_tokens = result.output_tokens
        attempt.total_tokens = result.total_tokens
        attempt.usage_source = "provider" if result.total_tokens is not None else "unavailable"
        attempt.provider_request_id = result.provider_request_id
        record_event(
            db,
            actor_id=request.owner_id,
            action="ai.generation_attempt_succeeded",
            entity_type="ai_generation_attempt",
            entity_id=attempt.id,
            metadata={
                "generation_id": str(request.id),
                "provider": selected_provider.key,
                "model": model,
                "attempt": number,
                "total_tokens": result.total_tokens,
            },
        )
        return result, attempt
    except ProviderError as error:
        attempt.status = "failed"
        attempt.retryable = error.retryable
        attempt.error_code = error.code
        attempt.safe_error_message = error.safe_message
        record_event(
            db,
            actor_id=request.owner_id,
            action="ai.generation_attempt_failed",
            entity_type="ai_generation_attempt",
            entity_id=attempt.id,
            metadata={
                "generation_id": str(request.id),
                "provider": selected_provider.key,
                "model": model,
                "attempt": number,
                "error_code": error.code,
                "retryable": error.retryable,
            },
        )
        raise
    finally:
        attempt.completed_at = now()
        attempt.latency_ms = round((time.perf_counter() - before) * 1000)
        request.final_attempt_count = number
        request.total_latency_ms = (request.total_latency_ms or 0) + attempt.latency_ms
        db.flush()


def generate(db: Session, owner: User, data: CreateGenerationRequest) -> GenerationResponse:
    product, brand = owned_product_context(db, owner.id, data.product_id, writable=True)
    template = resolve_template(db, data.prompt_template_id)
    stamp = now()
    selected_provider, selected_model, fallback_allowed = resolve_provider(db, owner.id, data)
    request = AIGenerationRequest(
        owner_id=owner.id,
        brand_id=brand.id,
        product_id=product.id,
        prompt_template_id=template.id,
        provider_key=selected_provider.key,
        selected_model=selected_model,
        fallback_used=False,
        final_attempt_count=0,
        status="pending",
        additional_instructions=data.additional_instructions,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(request)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.generation_requested",
        entity_type="ai_generation_request",
        entity_id=request.id,
        metadata={
            "product_id": str(product.id),
            "brand_id": str(brand.id),
            "template_key": template.key,
            "template_version": template.version,
            "provider_key": selected_provider.key,
            "model": selected_model,
        },
    )
    request.status = "running"
    request.started_at = request.updated_at = now()
    value = GenerationInput(
        brand_name=brand.name,
        product_name=product.name,
        product_type=product.product_type,
        short_description=product.short_description,
        description=product.description,
        category=product.category,
        tags=product.tags,
        additional_instructions=data.additional_instructions,
        template_key=template.key,
        template_version=template.version,
        system_instructions=template.system_instructions,
        template_instructions=template.user_template,
    )
    request.normalized_input_hash = hashlib.sha256(value.normalized().encode()).hexdigest()
    try:
        try:
            result, attempt = run_attempt(db, request, selected_provider, selected_model, value)
        except ProviderError as initial_error:
            if (
                selected_provider.key == "openai_compatible"
                and initial_error.code == "invalid_structured_output"
            ):
                result, attempt = run_attempt(db, request, selected_provider, selected_model, value)
            elif fallback_allowed and initial_error.retryable:
                request.fallback_used = True
                record_event(
                    db,
                    actor_id=owner.id,
                    action="ai.generation_fallback_used",
                    entity_type="ai_generation_request",
                    entity_id=request.id,
                    metadata={
                        "provider": selected_provider.key,
                        "fallback_provider": provider.key,
                        "error_code": initial_error.code,
                    },
                )
                selected_provider = provider
                selected_model = "mock-product-content-v1"
                result, attempt = run_attempt(
                    db,
                    request,
                    selected_provider,
                    selected_model,
                    value,
                    fallback=True,
                )
            else:
                raise
        db.refresh(request)
        if request.cancellation_requested_at is not None:
            request.status = "cancelled"
            request.cancelled_at = request.cancelled_at or now()
            request.updated_at = now()
            db.commit()
            return response_for(db, request)
        try:
            content = ProductContent.model_validate(result.content)
        except ValidationError:
            if selected_provider.key != "openai_compatible":
                raise
            result, attempt = run_attempt(db, request, selected_provider, selected_model, value)
            content = ProductContent.model_validate(result.content)
        version = (
            db.scalar(
                select(func.max(GeneratedArtifact.version_number)).where(
                    GeneratedArtifact.product_id == product.id
                )
            )
            or 0
        ) + 1
        db.execute(
            update(GeneratedArtifact)
            .where(
                GeneratedArtifact.product_id == product.id,
                GeneratedArtifact.status == "pending_review",
            )
            .values(status="superseded", updated_at=now())
        )
        artifact = GeneratedArtifact(
            owner_id=owner.id,
            brand_id=brand.id,
            product_id=product.id,
            generation_request_id=request.id,
            prompt_template_id=template.id,
            artifact_type="product_content",
            version_number=version,
            status="pending_review",
            content_json=content.model_dump(mode="json"),
            validation_result={"valid": True, "schema": "product_content_v1"},
            provider_metadata=result.metadata,
            created_at=now(),
            updated_at=now(),
        )
        db.add(artifact)
        request.status = "completed"
        request.final_provider_key = selected_provider.key
        request.selected_model = selected_model
        request.input_tokens = attempt.input_tokens
        request.output_tokens = attempt.output_tokens
        request.total_tokens = attempt.total_tokens
        request.estimated_total_cost, request.cost_currency = apply_cost(db, owner.id, attempt)
        request.completed_at = request.updated_at = now()
        db.flush()
        record_event(
            db,
            actor_id=owner.id,
            action="ai.generation_completed",
            entity_type="generated_artifact",
            entity_id=artifact.id,
            metadata={
                "product_id": str(product.id),
                "brand_id": str(brand.id),
                "artifact_version": version,
                "validation_success": True,
                "provider_key": selected_provider.key,
                "model": selected_model,
                "attempts": request.final_attempt_count,
                "fallback_used": request.fallback_used,
            },
        )
        if request.total_tokens is not None:
            record_event(
                db,
                actor_id=owner.id,
                action="ai.usage_recorded",
                entity_type="ai_generation_request",
                entity_id=request.id,
                metadata={
                    "provider": selected_provider.key,
                    "model": selected_model,
                    "total_tokens": request.total_tokens,
                    "estimated_cost": (
                        str(request.estimated_total_cost)
                        if request.estimated_total_cost is not None
                        else None
                    ),
                    "currency": request.cost_currency,
                },
            )
        db.commit()
    except (ProviderError, ValidationError) as error:
        request.status = "failed"
        request.failed_at = request.updated_at = now()
        request.error_code = (
            error.code if isinstance(error, ProviderError) else "invalid_provider_output"
        )
        request.safe_error_message = (
            error.safe_message
            if isinstance(error, ProviderError)
            else "The AI provider returned invalid structured content."
        )
        record_event(
            db,
            actor_id=owner.id,
            action="ai.generation_failed",
            entity_type="ai_generation_request",
            entity_id=request.id,
            metadata={
                "product_id": str(product.id),
                "brand_id": str(brand.id),
                "error_code": request.error_code,
                "provider_key": request.provider_key,
            },
        )
        db.commit()
    return response_for(db, request)


def artifact_details(db: Session, owner_id: uuid.UUID, artifact_id: uuid.UUID) -> ArtifactDetails:
    row = db.execute(
        select(GeneratedArtifact, AIGenerationRequest, PromptTemplate, Product, Brand)
        .join(
            AIGenerationRequest, AIGenerationRequest.id == GeneratedArtifact.generation_request_id
        )
        .join(PromptTemplate, PromptTemplate.id == GeneratedArtifact.prompt_template_id)
        .join(Product, Product.id == GeneratedArtifact.product_id)
        .join(Brand, Brand.id == GeneratedArtifact.brand_id)
        .where(GeneratedArtifact.id == artifact_id, GeneratedArtifact.owner_id == owner_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "AI artifact not found.")
    artifact, request, template, product, brand = row
    return ArtifactDetails(
        id=artifact.id,
        generation_request_id=request.id,
        product_id=product.id,
        product_name=product.name,
        brand_id=brand.id,
        brand_name=brand.name,
        template_id=template.id,
        template_name=template.name,
        template_version=template.version,
        provider_key=request.provider_key,
        version_number=artifact.version_number,
        status=artifact.status,
        content=ProductContent.model_validate(artifact.content_json),
        validation_result=artifact.validation_result,
        provider_metadata=artifact.provider_metadata,
        approved_at=artifact.approved_at,
        rejected_at=artifact.rejected_at,
        rejection_reason=artifact.rejection_reason,
        created_at=artifact.created_at,
    )


def decide(
    db: Session,
    owner: User,
    artifact_id: uuid.UUID,
    *,
    approve: bool,
    reason: str | None = None,
) -> ArtifactDetails:
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == artifact_id, GeneratedArtifact.owner_id == owner.id
        )
    )
    if artifact is None:
        raise HTTPException(404, "AI artifact not found.")
    target = "approved" if approve else "rejected"
    if artifact.status == target:
        return artifact_details(db, owner.id, artifact.id)
    if artifact.status != "pending_review":
        raise HTTPException(409, f"Only pending-review artifacts may be {target}.")
    stamp = now()
    artifact.status = target
    artifact.updated_at = stamp
    if approve:
        artifact.approved_at = stamp
        artifact.approved_by = owner.id
    else:
        artifact.rejected_at = stamp
        artifact.rejected_by = owner.id
        artifact.rejection_reason = reason
    record_event(
        db,
        actor_id=owner.id,
        action=f"ai.artifact_{target}",
        entity_type="generated_artifact",
        entity_id=artifact.id,
        metadata={
            "product_id": str(artifact.product_id),
            "brand_id": str(artifact.brand_id),
            "artifact_version": artifact.version_number,
            "new_status": target,
        },
    )
    db.commit()
    return artifact_details(db, owner.id, artifact.id)


def history(
    db: Session,
    owner_id: uuid.UUID,
    *,
    product_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    request_status: str | None = None,
    artifact_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedHistory:
    filters = [AIGenerationRequest.owner_id == owner_id]
    if product_id:
        filters.append(AIGenerationRequest.product_id == product_id)
    if brand_id:
        filters.append(AIGenerationRequest.brand_id == brand_id)
    if request_status:
        filters.append(AIGenerationRequest.status == request_status)
    if artifact_status:
        filters.append(GeneratedArtifact.status == artifact_status)
    if date_from:
        filters.append(AIGenerationRequest.created_at >= date_from)
    if date_to:
        filters.append(AIGenerationRequest.created_at <= date_to)
    base = (
        select(AIGenerationRequest, GeneratedArtifact, PromptTemplate, Product, Brand)
        .outerjoin(
            GeneratedArtifact, GeneratedArtifact.generation_request_id == AIGenerationRequest.id
        )
        .join(PromptTemplate, PromptTemplate.id == AIGenerationRequest.prompt_template_id)
        .join(Product, Product.id == AIGenerationRequest.product_id)
        .join(Brand, Brand.id == AIGenerationRequest.brand_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    rows = db.execute(
        base.order_by(AIGenerationRequest.created_at.desc(), AIGenerationRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedHistory(
        items=[
            HistoryItem(
                generation_id=request.id,
                artifact_id=artifact.id if artifact else None,
                product_id=product.id,
                product_name=product.name,
                brand_id=brand.id,
                brand_name=brand.name,
                template_name=template.name,
                template_version=template.version,
                provider_key=request.provider_key,
                request_status=request.status,
                artifact_status=artifact.status if artifact else None,
                version_number=artifact.version_number if artifact else None,
                created_at=request.created_at,
            )
            for request, artifact, template, product, brand in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )
