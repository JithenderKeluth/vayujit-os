"""API contracts for Trend 12E validation and confidence."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrendValidationCreate(BaseModel):
    analysis_id: uuid.UUID
    comparison_id: uuid.UUID | None = None
    calculation_version: str = Field(default="trend-validation-v1", min_length=1, max_length=80)


class TrendValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    analysis_id: uuid.UUID
    snapshot_id: uuid.UUID
    comparison_id: uuid.UUID | None
    validation_version: int
    calculation_version: str
    input_fingerprint: str
    status: str
    evidence_coverage: dict[str, object]
    source_coverage: dict[str, object]
    time_coverage: dict[str, object]
    freshness_summary: dict[str, object]
    agreement_summary: dict[str, object]
    contradiction_summary: dict[str, object]
    confidence: str
    downstream_readiness: str
    materiality_summary: dict[str, object]
    alert_summary: dict[str, object]
    limitations: list[str]
    research_gaps: list[str]
    created_at: datetime


class TrendValidationHypothesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    validation_id: uuid.UUID
    context_id: uuid.UUID
    signal_definition_id: uuid.UUID | None
    hypothesis_type: str
    signal_semantics: str
    source_scope: dict[str, object]
    time_window: dict[str, object]
    geography: str
    granularity: str
    supporting_source_ids: list[str]
    opposing_source_ids: list[str]
    supporting_signal_ids: list[str]
    supporting_analysis_ids: list[str]
    supporting_series_ids: list[str]
    supporting_change_event_ids: list[str]
    supporting_observation_ids: list[str]
    supporting_evidence_ids: list[str]
    support_count: int
    opposition_count: int
    unknown_count: int
    agreement: str
    confidence: str
    readiness: str
    materiality: str
    momentum: str
    limitations: list[str]
    hypothesis_fingerprint: str
    created_at: datetime


class TrendValidationContradictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    validation_id: uuid.UUID
    context_id: uuid.UUID
    contradiction_type: str
    severity: str
    supporting_source_ids: list[str]
    opposing_source_ids: list[str]
    series_ids: list[str]
    evidence_ids: list[str]
    time_windows: list[object]
    reason: str
    limitations: list[str]
    contradiction_fingerprint: str
    created_at: datetime


class TrendValidationGapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    validation_id: uuid.UUID
    context_id: uuid.UUID
    gap_type: str
    priority: str
    detail: dict[str, object]
    recommendation: str
    created_at: datetime


class TrendValidationPage(BaseModel):
    items: list[TrendValidationResponse]
    total: int
    limit: int
    offset: int
