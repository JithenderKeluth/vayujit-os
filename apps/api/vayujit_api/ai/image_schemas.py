from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ImageOperation = Literal[
    "generate_product_image",
    "remove_background",
    "replace_background",
    "white_background",
    "lifestyle_scene",
    "enhance_image",
    "resize",
    "crop",
    "extend_canvas",
    "promotional_creative",
    "marketplace_main_image",
    "marketplace_gallery_image",
    "thumbnail",
    "banner",
]
ImageChannel = Literal[
    "canonical", "amazon", "flipkart", "meesho", "shopify", "wordpress", "social"
]
ImageStatus = Literal[
    "queued",
    "generating",
    "validating",
    "needs_review",
    "retry_wait",
    "succeeded",
    "failed",
    "cancelled",
    "stale",
    "approved",
    "rejected",
]


class ImageStyleCreate(BaseModel):
    brand_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    background_preference: str | None = Field(default=None, max_length=120)
    photography_style: str | None = Field(default=None, max_length=240)
    lighting: str | None = Field(default=None, max_length=160)
    mood: str | None = Field(default=None, max_length=160)
    composition: str | None = Field(default=None, max_length=240)
    colors: dict[str, object] = Field(default_factory=dict)
    environments: list[str] = Field(default_factory=list, max_length=20)
    prohibited_treatments: list[str] = Field(default_factory=list, max_length=20)
    logo_guidance: str | None = Field(default=None, max_length=500)
    marketplace_constraints: dict[str, object] = Field(default_factory=dict)
    guidance: str | None = Field(default=None, max_length=2000)
    is_default: bool = False


class ImageStyleResponse(ImageStyleCreate):
    id: uuid.UUID
    version: int
    archived: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ImagePresetResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    operation: str
    channel: str | None
    rules: dict[str, object]


class ImageGenerateRequest(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID
    source_media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=8)
    operation: ImageOperation
    channel: ImageChannel = "canonical"
    aspect_ratio: str = Field(default="1:1", pattern=r"^\d{1,4}:\d{1,4}$")
    width: int = Field(default=1024, ge=64, le=4096)
    height: int = Field(default=1024, ge=64, le=4096)
    style_id: uuid.UUID | None = None
    preset_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    provider: str = Field(default="deterministic_mock_v1", max_length=100)
    model: str = Field(default="image-deterministic-v1", max_length=120)
    output_count: int = Field(default=1, ge=1, le=8)
    idempotency_key: str | None = Field(default=None, max_length=160)
    content_artifact_id: uuid.UUID | None = None
    content_artifact_version: int | None = Field(default=None, ge=1)
    headline: str | None = Field(default=None, max_length=240)
    subheadline: str | None = Field(default=None, max_length=240)
    cta: str | None = Field(default=None, max_length=120)
    offer_text: str | None = Field(default=None, max_length=240)
    scenario: str = Field(default="success", pattern=r"^[a-z_]{1,40}$")

    @model_validator(mode="after")
    def validate_sources(self) -> ImageGenerateRequest:
        if (
            self.operation
            in {
                "remove_background",
                "replace_background",
                "enhance_image",
                "resize",
                "crop",
                "extend_canvas",
            }
            and not self.source_media_ids
        ):
            raise ValueError("This image operation requires a source Media asset.")
        if self.operation == "replace_background" and len(self.source_media_ids) < 2:
            raise ValueError(
                "Background replacement requires a source and trusted background Media asset."
            )
        return self


class ImageOutputResponse(BaseModel):
    id: uuid.UUID
    generation_id: uuid.UUID
    job_id: uuid.UUID
    media_id: uuid.UUID | None
    source_media_ids: list[uuid.UUID]
    parent_output_id: uuid.UUID | None
    operation: str
    channel: str
    status: str
    requested_width: int
    requested_height: int
    actual_width: int | None
    actual_height: int | None
    mime_type: str | None
    size_bytes: int | None
    checksum_sha256: str | None
    alt_text_suggestion: str | None
    provider: str
    model: str
    created_at: datetime
    asset_classification: str = "ai_generated"
    content_artifact_id: uuid.UUID | None = None
    content_artifact_version: int | None = None


class ImageGenerationResponse(BaseModel):
    id: uuid.UUID
    generation_id: uuid.UUID
    operation: str
    channel: str
    status: str
    total_outputs: int
    completed_outputs: int
    failed_outputs: int
    outputs: list[ImageOutputResponse]
    safe_error_message: str | None = None


class ImageDecisionRequest(BaseModel):
    feedback: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=64)


class ImageReadinessResponse(BaseModel):
    media_id: uuid.UUID
    marketplace: str
    ready: bool
    certified: bool
    reasons: list[str]
    rules: dict[str, object]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rule_source: str = "fake_certified"


ImageRegenerationReason = Literal[
    "product_fidelity",
    "background",
    "lighting",
    "composition",
    "style",
    "incorrect_color",
    "logo_text_issue",
    "marketplace_readiness",
    "image_quality",
    "rejected_feedback",
    "custom",
]


class ImageApprovalEligibilityResponse(BaseModel):
    output_id: uuid.UUID
    eligible: bool
    blockers: list[str]
    warnings: list[str]


class ImageComparisonResponse(BaseModel):
    mode: Literal["source_generated", "version"]
    left: dict[str, object]
    right: dict[str, object]
    facts: dict[str, object]


class ImageHistoryEvent(BaseModel):
    action: str
    occurred_at: datetime
    correlation_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ImageRegenerateRequest(BaseModel):
    reason: ImageRegenerationReason
    feedback: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=64)
    instructions: str | None = Field(default=None, max_length=2000)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=160)
    scenario: str = Field(default="success", pattern=r"^[a-z_]{1,40}$")


class ImageOutputDetailResponse(ImageOutputResponse):
    brand_id: uuid.UUID
    product_id: uuid.UUID
    parent_media_id: uuid.UUID | None
    style_id: uuid.UUID | None
    style_version: int | None
    preset_id: uuid.UUID | None
    preset_version: int | None
    locale: str
    context_fingerprint: str
    provider_metadata: dict[str, object]
    usage_metadata: dict[str, object]
    approval_feedback: str | None
    rejection_category: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejected_at: datetime | None
    lineage: list[uuid.UUID]
    readiness: dict[str, object]


class ImageHandoffRequest(BaseModel):
    marketplace: Literal["amazon", "flipkart", "meesho"]
    listing_id: uuid.UUID
    position: int = Field(default=0, ge=0, le=99)
    role: Literal["main", "gallery"] = "gallery"
    idempotency_key: str = Field(min_length=1, max_length=160)
    fingerprint: str | None = None


class ImageHandoffPreview(BaseModel):
    output_id: uuid.UUID
    media_id: uuid.UUID
    marketplace: str
    listing_id: uuid.UUID
    position: int
    role: str
    ready: bool
    warnings: list[str]
    blockers: list[str]
    fingerprint: str
    current_media: list[dict[str, object]]
    proposed_media: dict[str, object]


class ImageCampaignHandoffRequest(BaseModel):
    campaign_id: uuid.UUID
    activity_id: uuid.UUID
    expected_row_version: int = Field(ge=1)
    confirm: bool = False


class ImageAltTextRequest(BaseModel):
    text: str | None = Field(default=None, max_length=500)
    action: Literal["suggest", "edit", "approve", "reject", "regenerate"] = "suggest"


class ImageAltTextResponse(BaseModel):
    output_id: uuid.UUID
    media_id: uuid.UUID | None
    text: str | None
    status: str
    version: int
    source: str | None
    provider: str | None
    updated_at: datetime | None
    approved_at: datetime | None


class ProductMediaItem(BaseModel):
    media_id: uuid.UUID
    image_output_id: uuid.UUID | None
    source_type: str
    operation: str | None
    status: str
    channel: str | None
    width: int
    height: int
    mime: str
    approval: str
    marketplace_usage: list[dict[str, object]] = Field(default_factory=list)
    campaign_usage: list[dict[str, object]] = Field(default_factory=list)
    lineage: list[uuid.UUID] = Field(default_factory=list)
    generated_at: datetime | None = None
    readiness: dict[str, object] = Field(default_factory=dict)


class ImagePresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    operation: ImageOperation
    channel: ImageChannel | None = None
    rules: dict[str, object] = Field(default_factory=dict)


class ImagePresetLifecycleResponse(ImagePresetResponse):
    archived: bool = False
    is_default: bool = False


ImageBulkSourceStrategy = Literal["selected", "primary_original", "first_eligible_original"]


class ImageBulkRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    channels: list[ImageChannel] = Field(min_length=1, max_length=6)
    operation: ImageOperation
    source_media_by_product: dict[str, list[uuid.UUID]] = Field(default_factory=dict, max_length=50)
    source_media_strategy: ImageBulkSourceStrategy = "selected"
    style_id: uuid.UUID | None = None
    preset_id: uuid.UUID | None = None
    aspect_ratio: str = Field(default="1:1", pattern=r"^\d{1,4}:\d{1,4}$")
    width: int = Field(default=1024, ge=64, le=4096)
    height: int = Field(default=1024, ge=64, le=4096)
    output_count_per_product: int = Field(default=1, ge=1, le=8)
    instructions: str | None = Field(default=None, max_length=2000)
    provider: Literal["deterministic_mock_v1"] = "deterministic_mock_v1"
    model: str = Field(default="image-deterministic-v1", max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=160)
    failure_scenarios: dict[str, str] = Field(default_factory=dict, max_length=300)
    content_artifact_by_product: dict[str, dict[str, object]] = Field(
        default_factory=dict, max_length=50
    )

    @model_validator(mode="after")
    def unique_targets(self) -> ImageBulkRequest:
        self.product_ids = list(dict.fromkeys(self.product_ids))
        self.channels = list(dict.fromkeys(self.channels))
        if (
            self.operation
            in {
                "remove_background",
                "replace_background",
                "enhance_image",
                "resize",
                "crop",
                "extend_canvas",
            }
            and self.source_media_strategy != "selected"
        ):
            raise ValueError("This operation requires explicitly selected source Media.")
        if self.operation == "replace_background":
            for product_id in self.product_ids:
                if len(self.source_media_by_product.get(str(product_id), [])) < 2:
                    raise ValueError(
                        "Background replacement requires two selected Media assets per Product."
                    )
        return self


class ImageBulkProductPlan(BaseModel):
    product_id: uuid.UUID
    product_name: str
    source_media_ids: list[uuid.UUID] = Field(default_factory=list)
    source_media_count: int
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImageBulkPreviewResponse(BaseModel):
    product_count: int
    channel_count: int
    operation: str
    channels: list[str]
    output_count_per_product: int
    total_outputs: int
    products: list[ImageBulkProductPlan]
    style_id: uuid.UUID | None
    style_version: int | None
    preset_id: uuid.UUID | None
    preset_version: int | None
    provider: str
    model: str
    aspect_ratio: str
    width: int
    height: int
    estimated_provider_calls: int
    estimated_cost: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_strategy: str


class ImageBulkOutputResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    output_index: int
    channel: str
    operation: str
    status: str
    source_media_ids: list[uuid.UUID] = Field(default_factory=list)
    image_output_id: uuid.UUID | None
    media_id: uuid.UUID | None
    job_id: uuid.UUID
    attempt_count: int
    retryable: bool
    retry_eligible: bool
    failure_category: str | None
    safe_error_message: str | None
    created_at: datetime
    updated_at: datetime


class ImageBulkStatusResponse(BaseModel):
    id: uuid.UUID
    modality: str = "image"
    status: str
    total_outputs: int
    counts: dict[str, int]
    progress_percentage: float
    product_count: int
    channel_count: int
    operation: str
    channels: list[str]
    output_count_per_product: int
    style_id: uuid.UUID | None
    style_version: int | None
    preset_id: uuid.UUID | None
    preset_version: int | None
    provider: str
    model: str
    width: int
    height: int
    aspect_ratio: str
    source_strategy: str
    correlation_id: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancellation_requested: bool
    outputs: list[ImageBulkOutputResponse] = Field(default_factory=list)


class ImageBulkRetryRequest(BaseModel):
    output_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class ImageBulkCancelRequest(BaseModel):
    output_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
