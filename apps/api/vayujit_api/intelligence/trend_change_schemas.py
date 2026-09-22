"""API contracts for Trend 12D change and momentum intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrendChangeComparisonCreate(BaseModel):
    baseline_analysis_id: uuid.UUID
    current_analysis_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)


class TrendChangeComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    baseline_analysis_id: uuid.UUID
    current_analysis_id: uuid.UUID
    baseline_snapshot_id: uuid.UUID
    current_snapshot_id: uuid.UUID
    comparison_version: int
    calculation_version: str
    materiality_policy_version: str
    input_fingerprint: str
    status: str
    summary: dict[str, Any]
    limitations: list[str]
    created_at: datetime


class TrendChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    comparison_id: uuid.UUID
    signal_definition_id: uuid.UUID | None
    source_id: uuid.UUID | None
    event_type: str
    change_semantics: str
    old_value: Any
    new_value: Any
    absolute_delta: Decimal | None
    relative_delta: Decimal | None
    relative_reason: str | None
    momentum: str
    materiality: str
    materiality_policy_version: str
    status: str
    alert_eligibility: str
    alert_reason: str
    baseline_reference: dict[str, Any]
    current_reference: dict[str, Any]
    evidence_references: dict[str, Any]
    freshness_state: str
    limitations: list[str]
    event_fingerprint: str
    previous_event_id: uuid.UUID | None
    created_at: datetime


class TrendChangeComparisonResult(BaseModel):
    comparison: TrendChangeComparisonResponse
    events: list[TrendChangeEventResponse]


class TrendChangeComparisonPage(BaseModel):
    items: list[TrendChangeComparisonResponse]
    total: int
    limit: int
    offset: int


class TrendChangeEventPage(BaseModel):
    items: list[TrendChangeEventResponse]
    total: int
    limit: int
    offset: int
