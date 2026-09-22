"""API contracts for descriptive Trend Signal and Time-Series Intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TrendAnalysisAPIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TrendAnalysisCreate(BaseModel):
    snapshot_id: uuid.UUID
    calculation_version: str = Field(default="trend-analysis-v1", min_length=1, max_length=80)
    signal: str | None = Field(default=None, max_length=80)
    source_id: uuid.UUID | None = None
    geography: str | None = Field(default=None, max_length=24)
    granularity: str | None = Field(default=None, max_length=24)


class TrendAnalysisResponse(TrendAnalysisAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    snapshot_id: uuid.UUID
    analysis_version: int
    calculation_version: str
    input_fingerprint: str
    status: str
    readiness: str
    included_observation_count: int
    excluded_observation_count: int
    included_reasons: dict[str, object]
    excluded_reasons: dict[str, object]
    time_coverage: dict[str, object]
    source_coverage: dict[str, object]
    signal_coverage: dict[str, object]
    summary: dict[str, object]
    limitations: list[str]
    freshness_state: str
    created_at: datetime


class TrendAnalysisSeriesResponse(TrendAnalysisAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    analysis_id: uuid.UUID
    context_id: uuid.UUID
    signal_definition_id: uuid.UUID
    source_id: uuid.UUID
    cohort_fingerprint: str
    measurement_type: str
    unit: str | None
    scale: Decimal | None
    geography_scope: str
    country: str | None
    region: str | None
    city: str | None
    marketplace: str | None
    granularity: str
    readiness: str
    direction: str
    persistence: str
    variability_state: str
    freshness_state: str
    sample_size: int
    included_observation_count: int
    excluded_observation_count: int
    time_start: datetime | None
    time_end: datetime | None
    expected_period_count: int | None
    observed_period_count: int | None
    missing_period_count: int
    coverage_ratio: Decimal | None
    statistics: dict[str, object]
    change: dict[str, object]
    movement: dict[str, object]
    missing_periods: list[object]
    limitations: list[str]
    observation_ids: list[str]
    evidence_ids: list[str]
    created_at: datetime


class TrendAnalysisGapResponse(TrendAnalysisAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    analysis_id: uuid.UUID
    series_id: uuid.UUID | None
    gap_type: str
    detail: dict[str, object]
    created_at: datetime


class TrendAnalysisPage(BaseModel):
    items: list[TrendAnalysisResponse]
    total: int
    limit: int
    offset: int


class TrendAnalysisSeriesPage(BaseModel):
    items: list[TrendAnalysisSeriesResponse]
    total: int
    limit: int
    offset: int
