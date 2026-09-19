"""API contracts for deterministic competitive change intelligence (10D)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChangeComparisonCreate(BaseModel):
    baseline_analysis_id: uuid.UUID | None = None
    current_analysis_id: uuid.UUID | None = None
    baseline_snapshot_id: uuid.UUID | None = None
    current_snapshot_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=220)


class ChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    comparison_id: uuid.UUID
    product_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    change_type: str
    observed_or_derived: str
    old_value: Any
    new_value: Any
    unit: str | None
    currency: str | None
    absolute_delta: Any
    percentage_delta: Any
    baseline_reference: str | None
    current_reference: str | None
    evidence_references: dict[str, Any]
    first_observed: datetime | None
    last_observed: datetime | None
    freshness_state: str
    evidence_state: str
    verification_state: str
    materiality: str
    materiality_policy_version: str
    status: str
    confidence: Any
    alert_eligibility: str
    alert_reason: str
    persistence_count: int
    previous_event_id: uuid.UUID | None
    resolution_reference: str | None
    calculation_version: str
    event_fingerprint: str
    created_at: datetime
    reviewed_at: datetime | None


class ChangeComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    baseline_analysis_id: uuid.UUID
    current_analysis_id: uuid.UUID
    baseline_snapshot_id: uuid.UUID | None
    current_snapshot_id: uuid.UUID | None
    comparison_version: int
    calculation_version: str
    status: str
    input_fingerprint: str
    input_snapshot: dict[str, Any]
    summary: dict[str, Any]
    idempotency_key: str
    created_at: datetime


class ChangeComparisonResult(BaseModel):
    comparison: ChangeComparisonResponse
    events: list[ChangeEventResponse]


class ChangeListResponse(BaseModel):
    items: list[ChangeEventResponse]
    total: int
    limit: int
    offset: int


class ChangeReviewRequest(BaseModel):
    status: str = Field(
        pattern="^(NEW|ONGOING|RESOLVED|REVERTED|SUPERSEDED|UNRESOLVED|POSSIBLY_REMOVED)$"
    )
    note: str = Field(default="", max_length=500)
