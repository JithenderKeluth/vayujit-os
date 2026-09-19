"""Schemas for the bounded Competitor Intelligence foundation."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContextCreate(BaseModel):
    subject_type: Literal["PRODUCT_OPPORTUNITY", "PRODUCT", "BRAND"]
    subject_reference: uuid.UUID
    marketplace: str = Field(default="", max_length=120)
    market: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: Literal["DRAFT", "ACTIVE", "WATCHING"] = "DRAFT"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    subject_type: str
    subject_reference: uuid.UUID
    product_opportunity_id: uuid.UUID | None
    product_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    marketplace: str
    market: str
    category: str
    currency: str | None
    status: str
    version: int
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class EntityCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=240)
    entity_type: Literal["BRAND", "SELLER", "MANUFACTURER", "MERCHANT", "OPERATOR", "UNKNOWN"] = (
        "UNKNOWN"
    )
    canonical_name: str = Field(min_length=1, max_length=240)
    marketplace_identifiers: dict[str, object] = Field(default_factory=dict)
    country_region: str | None = Field(default=None, max_length=120)
    website_domain: str | None = Field(default=None, max_length=255)
    evidence_state: Literal["UNKNOWN", "PARTIAL", "INSUFFICIENT_EVIDENCE", "AVAILABLE"] = "UNKNOWN"
    source_lineage: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    display_name: str
    entity_type: str
    canonical_name: str
    marketplace_identifiers: dict[str, object]
    country_region: str | None
    website_domain: str | None
    evidence_state: str
    source_lineage: dict[str, object]
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class CompetitorProductCreate(BaseModel):
    entity_id: uuid.UUID | None = None
    canonical_product_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    brand_reference: str | None = Field(default=None, max_length=240)
    seller_reference: str | None = Field(default=None, max_length=240)
    marketplace: str = Field(default="", max_length=120)
    external_identifier: str = Field(min_length=1, max_length=240)
    canonical_url: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=120)
    availability_state: Literal[
        "UNKNOWN", "AVAILABLE", "UNAVAILABLE", "OUT_OF_STOCK", "DISCONTINUED"
    ] = "UNKNOWN"
    identity_state: Literal[
        "UNRESOLVED", "CANDIDATE", "PROBABLE", "CONFIRMED", "REJECTED", "AMBIGUOUS"
    ] = "UNRESOLVED"
    evidence_state: Literal["UNKNOWN", "PARTIAL", "INSUFFICIENT_EVIDENCE", "AVAILABLE"] = "UNKNOWN"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)


class CompetitorProductIdentityUpdate(BaseModel):
    identity_state: Literal[
        "UNRESOLVED", "CANDIDATE", "PROBABLE", "CONFIRMED", "REJECTED", "AMBIGUOUS"
    ]


class CompetitorProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    entity_id: uuid.UUID | None
    canonical_product_id: uuid.UUID | None
    title: str
    brand_reference: str | None
    seller_reference: str | None
    marketplace: str
    external_identifier: str
    canonical_url: str | None
    category: str | None
    availability_state: str
    identity_state: str
    evidence_state: str
    first_observed: datetime
    last_observed: datetime
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class ObservationCreate(BaseModel):
    observation_type: str = Field(min_length=1, max_length=80)
    observed_value: dict[str, object] = Field(default_factory=dict)
    numeric_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    source_id: uuid.UUID | None = None
    source_reference: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=1000)
    observed_at: datetime
    retrieved_at: datetime
    evidence_id: uuid.UUID | None = None
    freshness_state: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    verification_state: str = Field(default="UNVERIFIED", min_length=1, max_length=24)
    observation_key: str = Field(min_length=1, max_length=240)

    @field_validator("numeric_value")
    @classmethod
    def non_negative_numeric(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("numeric_value must be non-negative")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_observation_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    competitor_product_id: uuid.UUID
    observation_type: str
    observed_value: dict[str, object]
    numeric_value: Decimal | None
    unit: str | None
    currency: str | None
    source_id: uuid.UUID | None
    source_reference: str
    source_url: str | None
    observed_at: datetime
    retrieved_at: datetime
    evidence_id: uuid.UUID | None
    freshness_state: str
    verification_state: str
    observation_key: str
    created_at: datetime


class SnapshotCreate(BaseModel):
    product_id: uuid.UUID | None = None
    snapshot_version: int = Field(ge=1)
    input_fingerprint: str = Field(min_length=1, max_length=128)
    source_references: list[str] = Field(default_factory=list, max_length=100)
    observation_references: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    payload: dict[str, object] = Field(default_factory=dict)
    schema_version: str = Field(default="competitor-snapshot-v1", max_length=80)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    product_id: uuid.UUID | None
    snapshot_version: int
    captured_at: datetime
    input_fingerprint: str
    source_references: list[str]
    observation_references: list[str]
    payload: dict[str, object]
    schema_version: str
    idempotency_key: str
    created_at: datetime


class CompetitorProductDetailResponse(BaseModel):
    product: CompetitorProductResponse
    observations: list[ObservationResponse]
    snapshots: list[SnapshotResponse]


class CompetitorIntegrityResponse(BaseModel):
    status: str
    counts: dict[str, int]
    duplicate_counts: dict[str, int]
