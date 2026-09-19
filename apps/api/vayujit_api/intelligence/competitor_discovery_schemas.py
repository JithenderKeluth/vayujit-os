"""API contracts for deterministic competitor discovery (10B)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DiscoveryProviderMode = Literal["DISABLED", "LOCAL_FIXTURE", "LIVE_READ_ONLY"]
ResolutionState = Literal[
    "UNRESOLVED", "CANDIDATE", "PROBABLE", "CONFIRMED", "REJECTED", "AMBIGUOUS"
]


class DiscoveryRequestCreate(BaseModel):
    marketplace: str = Field(default="", max_length=120)
    market: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=120)
    query_inputs: dict[str, object] = Field(default_factory=dict)
    filters: dict[str, object] = Field(default_factory=dict)
    source_selection: list[object] = Field(default_factory=list, max_length=20)
    maximum_candidates: int = Field(default=50, ge=1, le=500)
    provider_mode: DiscoveryProviderMode = "LOCAL_FIXTURE"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)

    @field_validator("marketplace", "market", "category")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class DiscoveryRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    marketplace: str
    market: str
    category: str
    query_inputs: dict[str, object]
    filters: dict[str, object]
    source_selection: list[object]
    maximum_candidates: int
    provider_mode: str
    input_fingerprint: str
    status: str
    version: int
    created_by: uuid.UUID
    started_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    request_id: uuid.UUID
    context_id: uuid.UUID
    source_mode: str
    source_identifier: str
    listing_identifier: str | None
    canonical_url: str | None
    raw_title: str
    normalized_title: str
    brand_claim: str | None
    seller_claim: str | None
    category: str | None
    marketplace: str
    price_amount: Decimal | None
    currency: str | None
    rating: Decimal | None
    review_count: int | None
    availability_state: str
    structured_attributes: dict[str, object]
    identity_state: str
    match_level: str
    match_score: Decimal | None
    supporting_signals: list[object]
    conflicting_signals: list[object]
    missing_signals: list[object]
    rule_version: str
    input_fingerprint: str
    evidence_state: str
    freshness_state: str
    source_id: uuid.UUID | None
    evidence_id: uuid.UUID | None
    competitor_product_id: uuid.UUID | None
    discovered_at: datetime
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class CandidateResolutionRequest(BaseModel):
    reason: str = Field(default="", max_length=500)
    confirm: bool = False


class DiscoverySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    request_id: uuid.UUID
    context_id: uuid.UUID
    snapshot_version: int
    candidate_count: int
    accepted_candidate_count: int
    ambiguous_count: int
    rejected_count: int
    source_counts: dict[str, object]
    source_diversity: int
    evidence_coverage: Decimal
    competitor_product_references: list[object]
    input_fingerprint: str
    previous_snapshot_id: uuid.UUID | None
    source_freshness: dict[str, object]
    captured_at: datetime
    idempotency_key: str
    created_at: datetime


class DiscoveryExecutionResponse(BaseModel):
    request: DiscoveryRequestResponse
    candidates: list[CandidateResponse]
    snapshot: DiscoverySnapshotResponse | None


class DiscoverySystemDoctorResponse(BaseModel):
    status: str
    counts: dict[str, int]
    duplicate_counts: dict[str, int]
    provider_modes: dict[str, str]
