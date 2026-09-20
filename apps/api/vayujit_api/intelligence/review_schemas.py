"""Review Intelligence 11A API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewAPIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ReviewContextCreate(BaseModel):
    name: str = Field(default="Review context", min_length=1, max_length=180)
    product_id: uuid.UUID | None = None
    product_opportunity_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    competitor_context_id: uuid.UUID | None = None
    marketplace: str = Field(default="", max_length=120)
    market: str = Field(default="", max_length=120)
    locale: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)
    input_fingerprint: str | None = Field(default=None, max_length=128)


class ReviewContextUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    marketplace: str | None = Field(default=None, max_length=120)
    market: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    status: Literal["DRAFT", "ACTIVE", "STALE"] | None = None


class ReviewContextResponse(ReviewAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    product_id: uuid.UUID | None
    product_opportunity_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    competitor_context_id: uuid.UUID | None
    marketplace: str
    market: str
    locale: str | None
    language: str | None
    status: str
    version: int
    idempotency_key: str
    input_fingerprint: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ReviewSourceCreate(BaseModel):
    source_type: str = Field(default="manual", min_length=1, max_length=40)
    provider: str = Field(default="manual", min_length=1, max_length=120)
    source_key: str | None = Field(default=None, max_length=240)
    marketplace: str | None = Field(default=None, max_length=120)
    external_product_identifier: str | None = Field(default=None, max_length=240)
    source_reference: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=1000)
    observed_at: datetime | None = None
    verification_status: Literal["UNVERIFIED", "VERIFIED", "REJECTED", "UNKNOWN"] = "UNVERIFIED"
    freshness_status: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    metadata: dict[str, object] = Field(default_factory=dict)
    intelligence_source_id: uuid.UUID | None = None


class ReviewSourceResponse(ReviewAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    intelligence_source_id: uuid.UUID | None
    source_type: str
    provider: str
    source_key: str
    marketplace: str | None
    external_product_identifier: str | None
    source_reference: str
    source_url: str | None
    captured_at: datetime
    observed_at: datetime | None
    verification_status: str
    freshness_status: str
    metadata_json: dict[str, object]
    created_at: datetime


class ReviewRecordCreate(BaseModel):
    provider: str = Field(default="manual", min_length=1, max_length=120)
    provider_review_id: str | None = Field(default=None, max_length=240)
    external_product_id: str | None = Field(default=None, max_length=240)
    source_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None
    source: ReviewSourceCreate | None = None
    rating: Decimal | None = None
    rating_scale: Decimal | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, max_length=1000)
    body: str | None = Field(default=None, max_length=100_000)
    reviewer_display_id: str | None = Field(default=None, max_length=240)
    verified_purchase: Literal["TRUE", "FALSE", "UNKNOWN"] = "UNKNOWN"
    review_date: datetime | None = None
    observed_at: datetime | None = None
    language: str | None = Field(default=None, max_length=40)
    locale: str | None = Field(default=None, max_length=40)
    helpful_count: int | None = Field(default=None, ge=0)
    variant_info: dict[str, object] = Field(default_factory=dict)
    source_reference: str | None = Field(default=None, max_length=500)
    verification_status: Literal["UNVERIFIED", "VERIFIED", "REJECTED", "UNKNOWN"] = "UNVERIFIED"
    freshness_status: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    evidence_state: Literal["AVAILABLE", "PARTIAL", "MISSING", "UNKNOWN", "UNVERIFIED"] = "UNKNOWN"
    raw_metadata: dict[str, object] = Field(default_factory=dict)
    canonical_metadata: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def validate_rating(self) -> ReviewRecordCreate:
        if self.rating is not None:
            if self.rating_scale is None:
                raise ValueError("rating_scale is required when rating is supplied")
            if self.rating < 0 or self.rating > self.rating_scale:
                raise ValueError("rating must be within rating_scale")
        return self


class ReviewRecordResponse(ReviewAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    source_id: uuid.UUID | None
    evidence_id: uuid.UUID | None
    provider: str
    provider_review_id: str | None
    external_product_id: str | None
    rating: Decimal | None
    rating_scale: Decimal | None
    title: str | None
    body: str | None
    reviewer_display_id: str | None
    verified_purchase: str
    review_date: datetime | None
    observed_at: datetime
    captured_at: datetime
    language: str | None
    locale: str | None
    helpful_count: int | None
    variant_info: dict[str, object]
    source_reference: str | None
    verification_status: str
    freshness_status: str
    evidence_state: str
    raw_metadata: dict[str, object]
    canonical_metadata: dict[str, object]
    fingerprint: str
    fingerprint_version: str
    idempotency_key: str
    created_at: datetime


class ReviewSnapshotCreate(BaseModel):
    review_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10_000)
    source_inventory: dict[str, int] | None = None
    calculation_version: str = Field(default="review-foundation-v1", max_length=80)
    input_fingerprint: str | None = Field(default=None, max_length=128)


class ReviewSnapshotResponse(ReviewAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    previous_snapshot_id: uuid.UUID | None
    snapshot_version: int
    captured_at: datetime
    review_count: int
    rated_review_count: int
    review_ids: list[str]
    source_inventory: dict[str, int]
    evidence_coverage: dict[str, int]
    freshness_summary: dict[str, int]
    statistics_json: dict[str, object]
    input_fingerprint: str
    calculation_version: str
    created_at: datetime


class ReviewStatisticsResponse(BaseModel):
    review_count: int
    rated_review_count: int
    unrated_review_count: int
    rating_scales: dict[str, int]
    verified_purchase_count: int
    unknown_verified_purchase_count: int
    source_counts: dict[str, int]
    freshness_counts: dict[str, int]
    evidence_counts: dict[str, int]
    review_date_min: datetime | None
    review_date_max: datetime | None


class ReviewIntegrityResponse(BaseModel):
    status: str
    counts: dict[str, int]


class ReviewPage(BaseModel):
    items: list[ReviewRecordResponse]
    total: int
    limit: int
    offset: int
