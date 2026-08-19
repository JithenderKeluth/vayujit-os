from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Provider = Literal["meta", "google"]


class AdsAccountCreate(BaseModel):
    provider: Provider
    external_account_id: str = Field(min_length=1, max_length=180)
    display_name: str = Field(min_length=1, max_length=160)
    environment: Literal["local", "sandbox", "production"] = "local"
    timezone_name: str = "Asia/Kolkata"
    currency: str = Field(default="INR", min_length=3, max_length=3)
    budget_type: Literal["daily", "lifetime"] | None = None
    credentials: dict[str, Any] = Field(default_factory=dict)


class AdsAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    external_account_id: str
    display_name: str
    environment: str
    status: str
    enabled: bool
    validated: bool
    validation_status: str
    credential_version: int
    credential_metadata: dict[str, object]
    timezone_name: str
    currency: str
    capabilities: dict[str, object]
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdsAudienceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    geography: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=list, max_length=20)
    age_min: int = Field(default=18, ge=0, le=120)
    age_max: int = Field(default=65, ge=0, le=120)
    gender: str | None = None
    interests: list[str] = Field(default_factory=list, max_length=100)
    demographics: list[str] = Field(default_factory=list, max_length=100)
    custom_segment_id: str | None = Field(default=None, max_length=160)
    remarketing_segment_id: str | None = Field(default=None, max_length=160)
    keyword_intent: dict[str, object] = Field(default_factory=dict)
    exclusions: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("geography")
    @classmethod
    def valid_geography(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value]
        if any(len(item) != 2 or not item.isalpha() for item in normalized):
            raise ValueError("geography must contain ISO 3166-1 alpha-2 country codes")
        return normalized

    @field_validator("languages")
    @classmethod
    def valid_languages(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        for item in normalized:
            parts = item.split("-")
            if len(parts) not in {1, 2} or len(parts[0]) != 2 or not parts[0].isalpha():
                raise ValueError("languages must contain valid BCP-47 locale tags")
            if len(parts) == 2 and (len(parts[1]) != 2 or not parts[1].isalpha()):
                raise ValueError("languages must contain valid BCP-47 locale tags")
        return normalized

    @field_validator("custom_segment_id", "remarketing_segment_id")
    @classmethod
    def abstract_segment_reference(cls, value: str | None) -> str | None:
        if value is not None and any(token in value for token in ("@", "http://", "https://")):
            raise ValueError("segment references must remain abstract and PII-free")
        return value

    @model_validator(mode="after")
    def valid_age(self) -> AdsAudienceCreate:
        if self.age_min > self.age_max:
            raise ValueError("age_min must not exceed age_max")
        if set(self.interests) & set(self.exclusions):
            raise ValueError("audience exclusions conflict with included interests")
        return self


class AdsBudgetCreate(BaseModel):
    daily_amount: Decimal | None = Field(default=None, ge=0)
    lifetime_amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    budget_type: Literal["daily", "lifetime"] | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def has_budget(self) -> AdsBudgetCreate:
        if self.daily_amount is None and self.lifetime_amount is None:
            raise ValueError("daily_amount or lifetime_amount is required")
        return self


class AdsCampaignCreate(BaseModel):
    provider: Provider
    account_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(default="awareness", max_length=40)
    timezone_name: str = "Asia/Kolkata"
    bidding_strategy: str | None = None
    targeting_summary: dict[str, object] = Field(default_factory=dict)
    keyword_set_id: uuid.UUID | None = None
    budget: AdsBudgetCreate
    start_at: datetime | None = None
    end_at: datetime | None = None
    idempotency_key: str = Field(min_length=1, max_length=180)


class AdsCreativeCreate(BaseModel):
    campaign_id: uuid.UUID
    product_id: uuid.UUID | None = None
    creative_type: Literal["content", "image", "video", "manual"] = "content"
    artifact_id: uuid.UUID | None = None
    artifact_version: int | None = Field(default=None, ge=1)
    image_output_id: uuid.UUID | None = None
    image_media_id: uuid.UUID | None = None
    image_version: int | None = Field(default=None, ge=1)
    video_generation_id: uuid.UUID | None = None
    video_output_id: uuid.UUID | None = None
    video_media_id: uuid.UUID | None = None
    video_version: int | None = Field(default=None, ge=1)
    locale: str = "en-IN"
    headline: str | None = Field(default=None, max_length=500)
    primary_text: str | None = None
    description: str | None = None
    cta: str | None = Field(default=None, max_length=60)
    destination_url: str | None = Field(default=None, max_length=2048)
    placements: list[str] = Field(default_factory=list, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=180)


class AdsCampaignConfirm(BaseModel):
    preview_fingerprint: str = Field(min_length=32, max_length=64)
    confirm: bool = False


class AdsBudgetPreview(BaseModel):
    proposed: AdsBudgetCreate
    expected_version: int = Field(default=1, ge=1)


class AdsRecoveryRequest(BaseModel):
    action: Literal[
        "retry",
        "reconcile",
        "pause",
        "resume",
        "replace_creative",
        "change_budget",
        "review_failure",
        "review_policy",
        "cancel",
        "change_account",
    ]
    entity_type: Literal["campaign", "group", "creative", "ad"]
    entity_id: uuid.UUID
    confirm: bool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=180)
    failure_code: str | None = Field(default=None, min_length=1, max_length=120)


class AdsBudgetConfirm(BaseModel):
    proposed: AdsBudgetCreate
    expected_version: int = Field(default=1, ge=1)
    preview_fingerprint: str = Field(min_length=32, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=180)
    confirm: bool = False


class AdsAccountUpdate(BaseModel):
    display_name: str | None = None
    credentials: dict[str, Any] | None = None
    currency: str | None = None


class AdsConversionCreate(BaseModel):
    provider_event_id: str = Field(min_length=1, max_length=180)
    conversion_type: str = Field(min_length=1, max_length=60)
    occurred_at: datetime
    value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    attribution_type: Literal["click_through", "view_through", "direct", "unknown"] = "unknown"
    attribution_window: str | None = Field(default=None, max_length=40)
    source: str = Field(default="fake_connector", max_length=40)


class AdsMetricResponse(BaseModel):
    metric_key: str
    value: float | None
    availability: str
    source: str
    observed_at: datetime
