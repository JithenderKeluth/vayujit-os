import uuid
from datetime import datetime
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


class RejectionRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class GenerationResponse(BaseModel):
    id: uuid.UUID
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    artifact_id: uuid.UUID | None
    error_code: str | None
    safe_error_message: str | None


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
    status: Literal["pending_review", "approved", "rejected", "superseded"]
    content: ProductContent
    validation_result: dict[str, object]
    provider_metadata: dict[str, object]
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
