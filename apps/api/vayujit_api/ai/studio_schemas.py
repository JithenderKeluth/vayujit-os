from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

SECRET_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|bearer\s+[A-Za-z0-9._-]{12,}|password\s*[:=])", re.I
)

Channel = Literal["amazon", "flipkart", "meesho", "shopify", "wordpress", "canonical"]
ContentType = Literal[
    "marketplace_listing",
    "product_description",
    "product_title",
    "bullet_points",
    "highlights",
    "search_terms",
    "tags",
    "seo_metadata",
    "blog_content",
    "social_caption",
    "ad_copy",
    "video_script",
    "email_copy",
    "faq",
    "product_comparison",
    "landing_page_copy",
]


def normalized_terms(value: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        term = " ".join(item.strip().split())
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            result.append(term)
    return result[:100]


class BrandVoiceCreate(BaseModel):
    brand_id: uuid.UUID | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    description: Annotated[str | None, StringConstraints(max_length=500)] = None
    tone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] = (
        "professional"
    )
    personality: Annotated[str | None, StringConstraints(max_length=500)] = None
    terminology: dict[str, object] = Field(default_factory=dict, max_length=50)
    target_audience: Annotated[str | None, StringConstraints(max_length=500)] = None
    preferred_phrases: list[Annotated[str, StringConstraints(max_length=160)]] = Field(
        default_factory=list, max_length=50
    )
    prohibited_phrases: list[Annotated[str, StringConstraints(max_length=160)]] = Field(
        default_factory=list, max_length=50
    )
    spelling_conventions: Annotated[str | None, StringConstraints(max_length=200)] = None
    language: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}$")] = "en"
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    formatting_preferences: dict[str, object] = Field(default_factory=dict, max_length=50)
    compliance_notes: Annotated[str | None, StringConstraints(max_length=1000)] = None
    custom_instructions: Annotated[str | None, StringConstraints(max_length=2000)] = None
    is_default: bool = False

    @model_validator(mode="after")
    def validate_voice(self) -> BrandVoiceCreate:
        self.preferred_phrases = normalized_terms(self.preferred_phrases)
        self.prohibited_phrases = normalized_terms(self.prohibited_phrases)
        preferred = {value.casefold() for value in self.preferred_phrases}
        prohibited = {value.casefold() for value in self.prohibited_phrases}
        if preferred & prohibited:
            raise ValueError("preferred_phrases and prohibited_phrases must not overlap")
        combined = " ".join(filter(None, [self.custom_instructions, self.compliance_notes]))
        if SECRET_PATTERN.search(combined):
            raise ValueError("secret-like content is not allowed")
        return self


class BrandVoiceResponse(BrandVoiceCreate):
    id: uuid.UUID
    version: int
    archived: bool = False
    created_at: datetime
    updated_at: datetime


class PresetCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    description: Annotated[str | None, StringConstraints(max_length=500)] = None
    brand_voice_id: uuid.UUID | None = None
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    guidance: Annotated[str | None, StringConstraints(max_length=2000)] = None
    preferred_provider: Annotated[str | None, StringConstraints(max_length=100)] = None
    preferred_model: Annotated[str | None, StringConstraints(max_length=120)] = None
    output_types: list[str] = Field(default_factory=lambda: ["marketplace_listing"], max_length=20)
    channels: list[str] = Field(
        default_factory=lambda: ["amazon", "flipkart", "meesho"], max_length=6
    )
    tone: Annotated[str | None, StringConstraints(max_length=80)] = None
    length: Annotated[str | None, StringConstraints(max_length=40)] = None
    required_context: list[str] = Field(default_factory=list, max_length=30)
    validation_rules: dict[str, object] = Field(default_factory=dict, max_length=50)


class PresetResponse(PresetCreate):
    id: uuid.UUID
    is_system: bool
    archived: bool = False
    is_default: bool = False
    version: int = 1
    created_at: datetime
    updated_at: datetime


class KeywordSetCreate(BaseModel):
    description: Annotated[str | None, StringConstraints(max_length=500)] = None
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    primary_keywords: list[str] = Field(default_factory=list, max_length=100)
    secondary_keywords: list[str] = Field(default_factory=list, max_length=100)
    marketplace_keywords: list[str] = Field(default_factory=list, max_length=100)
    website_keywords: list[str] = Field(default_factory=list, max_length=100)
    campaign_keywords: list[str] = Field(default_factory=list, max_length=100)
    negative_keywords: list[str] = Field(default_factory=list, max_length=100)
    excluded_keywords: list[str] = Field(default_factory=list, max_length=100)
    competitor_references: list[str] = Field(default_factory=list, max_length=100)
    source: Annotated[str, StringConstraints(max_length=80)] = "manual"
    notes: Annotated[str | None, StringConstraints(max_length=1000)] = None

    @field_validator(
        "primary_keywords",
        "secondary_keywords",
        "marketplace_keywords",
        "website_keywords",
        "campaign_keywords",
        "negative_keywords",
    )
    @classmethod
    def normalize(cls, value: list[str]) -> list[str]:
        return normalized_terms(value)


class KeywordSetResponse(KeywordSetCreate):
    version: int = 1
    archived: bool = False
    is_default: bool = False
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class StudioGenerateRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    channels: list[str] = Field(min_length=1, max_length=6)
    content_types: list[ContentType] = Field(min_length=1, max_length=8)
    brand_voice_id: uuid.UUID | None = None
    preset_id: uuid.UUID | None = None
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    user_instructions: Annotated[str | None, StringConstraints(max_length=2000)] = None
    provider_key: Literal["deterministic_mock_v1", "openai_compatible"] = "deterministic_mock_v1"
    model: Annotated[str | None, StringConstraints(max_length=120)] = None
    idempotency_key: Annotated[str | None, StringConstraints(max_length=160)] = None
    generation_reason: Literal[
        "studio",
        "regeneration",
        "bulk",
        "seo",
        "localization",
        "localized_generation",
        "translation",
    ] = "studio"
    source_artifact_id: uuid.UUID | None = None
    source_artifact_version: int | None = Field(default=None, ge=1)
    operation: Literal["localized_generation", "translation"] | None = None
    failure_scenario: str | None = None

    @field_validator("channels", "content_types")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class StudioBulkRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    channels: list[Channel] = Field(min_length=1, max_length=6)
    content_types: list[ContentType] = Field(min_length=1, max_length=12)
    brand_voice_id: uuid.UUID | None = None
    preset_id: uuid.UUID | None = None
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    user_instructions: Annotated[str | None, StringConstraints(max_length=2000)] = None
    provider_key: Literal["deterministic_mock_v1", "openai_compatible"] = "deterministic_mock_v1"
    model: Annotated[str | None, StringConstraints(max_length=120)] = None
    idempotency_key: Annotated[str | None, StringConstraints(max_length=160)] = None
    failure_scenarios: dict[str, str] = Field(default_factory=dict, max_length=100)

    @field_validator("product_ids", "channels", "content_types")
    @classmethod
    def unique_values_bulk(cls, value: list[object]) -> list[object]:
        return list(dict.fromkeys(value))


class StudioBulkPreviewResponse(BaseModel):
    product_ids: list[uuid.UUID]
    channels: list[str]
    content_types: list[str]
    product_count: int
    channel_count: int
    content_type_count: int
    total_outputs: int
    brand_voice_id: uuid.UUID | None
    brand_voice_version: int | None
    preset_id: uuid.UUID | None
    preset_version: int | None
    locale: str
    provider_key: str
    model: str
    estimated_provider_calls: int
    estimated_cost: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    operation_limits: dict[str, int]


class StudioBulkOutputResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    channel: str
    content_type: str
    locale: str
    status: str
    artifact_id: uuid.UUID | None
    artifact_version: int | None
    job_id: uuid.UUID | None
    generation_id: uuid.UUID | None
    attempt_count: int
    failure_category: str | None
    safe_error_message: str | None
    retryable: bool
    retry_eligible: bool
    updated_at: datetime


class StudioBulkStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    total_outputs: int
    counts: dict[str, int]
    progress_percentage: float
    product_count: int
    channel_count: int
    content_type_count: int
    locale: str
    provider_key: str
    model: str
    brand_voice_id: uuid.UUID | None
    brand_voice_version: int | None
    preset_id: uuid.UUID | None
    preset_version: int | None
    correlation_id: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    completion_summary: dict[str, object]
    cancellation_requested: bool
    outputs: list[StudioBulkOutputResponse] = Field(default_factory=list)


class StudioBulkRetryRequest(BaseModel):
    output_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class StudioBulkCancelRequest(BaseModel):
    output_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class BrandVoicePreviewRequest(BaseModel):
    product_id: uuid.UUID
    channel: Channel = "canonical"
    content_type: ContentType = "product_description"


class BrandVoicePreviewResponse(BaseModel):
    voice_id: uuid.UUID
    voice_version: int
    channel: str
    content_type: str
    sample: dict[str, object]


class StudioOutputResponse(BaseModel):
    id: uuid.UUID
    generation_id: uuid.UUID
    product_id: uuid.UUID
    artifact_id: uuid.UUID | None
    channel: str
    content_type: str
    status: str
    error_code: str | None = None
    safe_error_message: str | None = None

    job_id: uuid.UUID | None = None
    correlation_id: str | None = None
    failure_category: str | None = None
    retryable: bool = False
    recovery_actions: list[str] = Field(default_factory=list)
    context_refresh_required: bool = False


class StudioGenerationResponse(BaseModel):
    id: uuid.UUID
    status: str
    product_ids: list[str]
    channels: list[str]
    content_types: list[str]
    context_fingerprint: str
    total_outputs: int
    completed_outputs: int
    failed_outputs: int
    outputs: list[StudioOutputResponse]
    created_at: datetime
    completed_at: datetime | None
    failure_category: str | None = None
    retryable: bool = False
    recovery_actions: list[str] = Field(default_factory=list)
    correlation_ids: list[str] = Field(default_factory=list)


class StudioContextResponse(BaseModel):
    product_id: uuid.UUID
    brand_id: uuid.UUID
    context_fingerprint: str
    context: dict[str, object]
    sources: list[str]
    warnings: list[str]


class StudioArtifactResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    brand_id: uuid.UUID
    brand_name: str
    channel: str
    content_type: str
    locale: str
    version_number: int
    status: str
    source: str
    content: dict[str, object]
    validation_result: dict[str, object]
    context_fingerprint: str | None
    parent_artifact_id: uuid.UUID | None
    generation_reason: str
    source_artifact_version: int | None = None
    source_locale: str | None = None
    source_product_context: dict[str, object] | None = None
    provider_key: str
    model: str | None
    created_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    rejection_category: str | None = None
    rejection_feedback: str | None = None
    rejection_field_notes: dict[str, object] | None = None
    rejection_regeneration_guidance: str | None = None
    parent_artifact_version: int | None = None
    brand_voice_version: int | None = None
    preset_version: str | None = None
    edited_at: datetime | None = None
    edited_by: uuid.UUID | None = None


class StudioArtifactEdit(BaseModel):
    content: dict[str, object] = Field(min_length=1, max_length=50)
    expected_source_version: int | None = Field(default=None, ge=1)


class StudioRejectRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    category: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=80)] = None
    feedback: Annotated[str | None, StringConstraints(max_length=2000)] = None
    field_notes: dict[str, object] | None = Field(default=None, max_length=50)
    regeneration_guidance: Annotated[str | None, StringConstraints(max_length=1000)] = None


class StudioHandoffRequest(BaseModel):
    destination_id: uuid.UUID | None = None
    listing_id: uuid.UUID | None = None
    activity_id: uuid.UUID | None = None
    marketplace: str | None = None
    confirm: bool = False
    expected_artifact_version: int | None = Field(default=None, ge=1)
    expected_current_artifact_version: int | None = Field(default=None, ge=1)


class StudioFieldDiff(BaseModel):
    status: Literal["unchanged", "changed", "added", "removed"]
    left: object = None
    right: object = None
    added: list[object] = Field(default_factory=list)
    removed: list[object] = Field(default_factory=list)
    changed: list[dict[str, object]] = Field(default_factory=list)


class StudioComparisonResponse(BaseModel):
    left: StudioArtifactResponse
    right: StudioArtifactResponse
    fields: dict[str, StudioFieldDiff] = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list)
    additions: list[str] = Field(default_factory=list)
    removals: list[str] = Field(default_factory=list)
    different_locale: bool = False
    locale_warning: str | None = None


class SEOAnalyzeRequest(BaseModel):
    product_id: uuid.UUID
    channel: Channel = "canonical"
    primary_keyword: Annotated[str | None, StringConstraints(max_length=160)] = None
    secondary_keywords: list[str] = Field(default_factory=list, max_length=50)
    artifact_id: uuid.UUID | None = None


class SEOAnalyzeResponse(BaseModel):
    product_id: uuid.UUID
    channel: str
    score: int
    dimensions: dict[str, int]
    recommendations: list[str]
    keyword_coverage: dict[str, object]
    fact_warnings: list[str]
    generated_at: datetime
