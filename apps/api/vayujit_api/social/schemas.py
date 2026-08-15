from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from vayujit_api.social.models import CONTENT_TYPES, SOCIAL_PLATFORMS

Platform = Literal["instagram", "facebook", "youtube"]


class SocialAccountCreate(BaseModel):
    platform: Platform
    display_name: str = Field(min_length=1, max_length=160)
    remote_account_id: str = Field(min_length=1, max_length=200)
    identity_type: str = Field(default="account", max_length=32)
    environment: str = Field(default="local", max_length=24)
    credentials: dict[str, str] = Field(default_factory=dict)
    capabilities: dict[str, object] = Field(default_factory=dict)


class SocialAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    credentials: dict[str, str] | None = None
    capabilities: dict[str, object] | None = None


class SocialAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    platform: str
    identity_type: str
    display_name: str
    remote_account_id: str
    environment: str
    enabled: bool
    validation_status: str
    capabilities: dict[str, object]
    credential_configured: bool
    credential_version: int
    created_at: datetime
    updated_at: datetime
    last_validated_at: datetime | None


class SocialPostCreate(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID | None = None
    account_id: uuid.UUID
    platform: Platform
    content_type: str
    content_artifact_id: uuid.UUID
    content_artifact_version: int = Field(gt=0)
    source_artifact_id: uuid.UUID | None = None
    source_artifact_version: int | None = Field(default=None, gt=0)
    generation_reason: str | None = Field(default=None, max_length=40)
    media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    locale: str = Field(default="en-IN", max_length=16)
    caption: str | None = Field(default=None, max_length=20_000)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    hashtags: list[str] = Field(default_factory=list, max_length=50)
    cta: dict[str, object] | None = None
    destination_url: HttpUrl | None = None
    campaign_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_format(self) -> SocialPostCreate:
        if self.content_type not in CONTENT_TYPES:
            raise ValueError("Unsupported social content type.")
        expected = self.content_type.split("_", 1)[0]
        if expected in SOCIAL_PLATFORMS and expected != self.platform:
            raise ValueError("Content format does not match the selected platform.")
        return self


class SocialPostUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=20_000)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    hashtags: list[str] | None = Field(default=None, max_length=50)
    cta: dict[str, object] | None = None
    destination_url: HttpUrl | None = None


class SocialScheduleRequest(BaseModel):
    preview_fingerprint: str = Field(min_length=64, max_length=64)
    local_scheduled_at: datetime
    timezone_name: str = Field(min_length=1, max_length=100)
    fold: Literal[0, 1] = 0


class SocialPreviewResponse(BaseModel):
    post_id: uuid.UUID
    platform: str
    account: SocialAccountResponse
    format: str
    caption: str | None
    title: str | None
    description: str | None
    media_ids: list[uuid.UUID]
    hashtags: list[str]
    cta: dict[str, object] | None
    schedule: dict[str, object]
    readiness: dict[str, object]
    fingerprint: str


class SocialPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    brand_id: uuid.UUID
    product_id: uuid.UUID | None
    account_id: uuid.UUID
    platform: str
    content_type: str
    content_artifact_id: uuid.UUID
    content_artifact_version: int
    source_artifact_id: uuid.UUID | None
    source_artifact_version: int | None
    generation_reason: str | None
    media_ids: list[str]
    video_generation_id: uuid.UUID | None
    video_output_id: uuid.UUID | None
    video_media_id: uuid.UUID | None
    video_version: int | None
    metadata_artifact_id: uuid.UUID | None
    metadata_artifact_version: int | None
    title_artifact_id: uuid.UUID | None
    title_artifact_version: int | None
    description_artifact_id: uuid.UUID | None
    description_artifact_version: int | None
    copy_artifact_id: uuid.UUID | None
    copy_artifact_version: int | None
    cta_artifact_id: uuid.UUID | None
    cta_artifact_version: int | None
    tags_artifact_id: uuid.UUID | None
    tags_artifact_version: int | None
    thumbnail_output_id: uuid.UUID | None
    thumbnail_media_id: uuid.UUID | None
    thumbnail_version: int | None
    caption_track_id: uuid.UUID | None
    caption_version: int | None
    locale: str
    caption: str | None
    title: str | None
    description: str | None
    hashtags: list[str]
    cta_json: dict[str, object] | None
    destination_url: str | None
    scheduled_at_utc: datetime | None
    timezone_name: str | None
    lifecycle_status: str
    remote_publication_id: str | None
    correlation_id: str
    campaign_id: uuid.UUID | None
    schedule_id: uuid.UUID | None
    idempotency_key: str
    preview_fingerprint: str | None
    failure_code: str | None
    safe_failure_message: str | None
    remote_checkpoint_json: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


class SocialMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metric_key: str
    value: float | None
    availability: str
    source: str
    product_id: uuid.UUID | None
    platform: str | None
    content_type: str | None
    video_output_id: uuid.UUID | None
    video_media_id: uuid.UUID | None
    observed_at: datetime | None


class SocialRecoveryActionRequest(BaseModel):
    action: Literal["retry", "reconcile", "cancel", "reschedule", "review_failure"]
    post_id: uuid.UUID
    confirm: bool = False
    idempotency_key: str | None = Field(default=None, max_length=160)


class SocialRecoveryActionResult(BaseModel):
    post_id: uuid.UUID
    action: str
    status: str
    idempotent_reuse: bool = False
    safe_message: str
    remote_publication_id: str | None = None
    failure_code: str | None = None
    correlation_id: str | None = None
    video_output_id: uuid.UUID | None = None
    schedule_id: uuid.UUID | None = None
    retryable: bool = False


class SocialRecoveryProjection(BaseModel):
    post_id: uuid.UUID
    platform: str
    content_type: str
    lifecycle_status: str
    failure_code: str | None = None
    safe_failure_message: str | None = None
    remote_publication_id: str | None
    correlation_id: str | None = None
    video_output_id: uuid.UUID | None = None
    schedule_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    retryable: bool = False
    available_actions: list[str]


class SocialRepurposeRequest(BaseModel):
    account_id: uuid.UUID
    content_type: str
    idempotency_key: str = Field(min_length=1, max_length=160)


class SocialBulkRequest(BaseModel):
    post_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    action: Literal["approve", "schedule", "publish_now"] = "approve"
    idempotency_key: str = Field(min_length=1, max_length=160)


class SocialHistoryItem(BaseModel):
    id: uuid.UUID
    action: str
    occurred_at: datetime
    metadata: dict[str, object]


class SocialBulkScheduleItem(BaseModel):
    post_id: uuid.UUID
    preview_fingerprint: str = Field(min_length=64, max_length=64)
    local_scheduled_at: datetime
    timezone_name: str = Field(min_length=1, max_length=100)
    fold: Literal[0, 1] = 0


class SocialBulkScheduleRequest(BaseModel):
    items: list[SocialBulkScheduleItem] = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=160)
