import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class ProductContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    short_description: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    long_description: Annotated[str, StringConstraints(min_length=1, max_length=5000)]
    key_features: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=200)]],
        Field(min_length=1, max_length=10),
    ]
    seo_title: Annotated[str, StringConstraints(min_length=1, max_length=70)]
    seo_description: Annotated[str, StringConstraints(min_length=1, max_length=170)]
    social_caption: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    keywords: Annotated[
        list[Annotated[str, StringConstraints(pattern=r"^[\w -]{1,50}$")]],
        Field(min_length=1, max_length=20),
    ]
    generation_summary: Annotated[str, StringConstraints(min_length=1, max_length=500)]

    @field_validator("*")
    @classmethod
    def reject_markup(cls, value: object) -> object:
        values = value if isinstance(value, list) else [value]
        if any("<" in item or ">" in item for item in values if isinstance(item, str)):
            raise ValueError("HTML and markup are not allowed.")
        return value


class ProviderSummary(BaseModel):
    key: str
    name: str
    provider_type: str
    available: bool
    deterministic: bool
    local: bool
    configured: bool = False
    enabled: bool = True
    health_state: str = "unknown"
    models: list[dict[str, object]] = []
    default_model: str | None = None
    recommended_model: str | None = None
    capabilities: list[str] = []
    structured_output: bool = False
    live_validation: str = "not_performed"


class TemplateSummary(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    version: int
    template_type: str
    is_default: bool


class CreateGenerationRequest(BaseModel):
    product_id: uuid.UUID
    prompt_template_id: uuid.UUID | None = None
    additional_instructions: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    provider_key: Literal["deterministic_mock_v1", "openai_compatible"] | None = None
    model: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    allow_fallback: bool = False


class RejectionRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class GenerationResponse(BaseModel):
    id: uuid.UUID
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    artifact_id: uuid.UUID | None
    error_code: str | None
    safe_error_message: str | None
    provider_key: str | None = None
    model: str | None = None
    attempt_count: int = 0
    fallback_used: bool = False
    correlation_id: str | None = None


class ProviderConfigurationUpdate(BaseModel):
    api_key: Annotated[str, StringConstraints(min_length=1, max_length=4096)] | None = None
    base_url: Annotated[str, StringConstraints(min_length=8, max_length=500)]
    default_model: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    manual_model_allowed: bool = False
    enabled: bool = False
    fallback_provider_key: Literal["deterministic_mock_v1"] | None = None
    request_timeout_seconds: int = Field(default=45, ge=10, le=120)
    max_retry_attempts: int = Field(default=3, ge=1, le=5)


class ProviderConfigurationResponse(BaseModel):
    provider_key: str
    display_name: str
    configured: bool
    credential_source: Literal["application", "deployment", "not_configured"]
    masked_credential: str | None
    base_url: str
    default_model: str
    manual_model_allowed: bool
    enabled: bool
    fallback_provider_key: str | None
    request_timeout_seconds: int
    max_retry_attempts: int
    validation_status: str
    safe_validation_message: str | None
    last_validated_at: datetime | None
    last_validation_latency_ms: int | None


class ProviderValidationResult(BaseModel):
    valid: bool
    status: str
    safe_message: str
    correlation_id: str | None
    latency_ms: int
    validated_model: str | None


class ModelSummary(BaseModel):
    identifier: str
    provider_key: str
    structured_output: bool | None
    display_name: str | None = None
    enabled: bool = True
    available: bool = True
    recommended: bool = False
    capabilities: list[str] = []
    max_context: int | None = None
    max_output: int | None = None
    usage_reporting: bool = False
    pricing_metadata_available: bool = False


class GenerationAttemptResponse(BaseModel):
    id: uuid.UUID
    attempt_number: int
    provider_key: str
    model: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    usage_source: str
    estimated_cost: str | None
    cost_currency: str | None
    retryable: bool
    fallback: bool
    error_code: str | None
    safe_error_message: str | None
    correlation_id: str | None


class CancellationResponse(BaseModel):
    id: uuid.UUID
    status: str
    cancellation_requested_at: datetime
    remote_cancellation: bool = False


class UsageSummary(BaseModel):
    requests: int
    successful_generations: int
    failed_generations: int
    retries: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: str | None
    cost_currency: str | None


class UsageHistoryItem(BaseModel):
    generation_id: uuid.UUID
    created_at: datetime
    provider_key: str
    model: str | None
    status: str
    attempts: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: str | None
    cost_currency: str | None
    brand_id: uuid.UUID
    brand_name: str
    product_id: uuid.UUID
    product_name: str


class UsageHistoryPage(BaseModel):
    items: list[UsageHistoryItem]
    page: int
    page_size: int
    total: int
    pages: int


class PricingCreate(BaseModel):
    provider_key: Literal["openai_compatible"]
    model_pattern: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "USD"
    input_cost_per_million_tokens: Decimal = Field(ge=0)
    output_cost_per_million_tokens: Decimal = Field(ge=0)
    effective_from: datetime
    effective_to: datetime | None = None
    source_note: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    enabled: bool = True


class PricingSummary(PricingCreate):
    id: uuid.UUID


class HistoryItem(BaseModel):
    generation_id: uuid.UUID
    artifact_id: uuid.UUID | None
    product_id: uuid.UUID
    product_name: str
    brand_id: uuid.UUID
    brand_name: str
    template_name: str
    template_version: int
    provider_key: str
    request_status: str
    artifact_status: str | None
    version_number: int | None
    created_at: datetime


class PaginatedHistory(BaseModel):
    items: list[HistoryItem]
    page: int
    page_size: int
    total: int
    pages: int


class ArtifactDetails(BaseModel):
    id: uuid.UUID
    generation_request_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    brand_id: uuid.UUID
    brand_name: str
    template_id: uuid.UUID
    template_name: str
    template_version: int
    provider_key: str
    version_number: int
    channel: str
    content_type: str
    locale: str
    status: Literal["pending_review", "approved", "rejected", "superseded"]
    content: ProductContent
    validation_result: dict[str, object]
    provider_metadata: dict[str, object]
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    source_artifact_version: int | None = None
    source_locale: str | None = None
    source_product_context: dict[str, object] | None = None
    created_at: datetime
