"""API contracts for the provider-independent Trend Intelligence foundation."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrendAPIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TrendContextCreate(BaseModel):
    name: str = Field(default="Trend context", min_length=1, max_length=180)
    subject_type: str = "CUSTOM"
    subject_key: str = Field(default="", max_length=240)
    product_id: uuid.UUID | None = None
    product_opportunity_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    marketplace: str | None = Field(default=None, max_length=120)
    market: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, max_length=3)
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=180)
    input_fingerprint: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def subject_is_described(self) -> TrendContextCreate:
        if not self.subject_key and not any(
            (self.product_id, self.product_opportunity_id, self.brand_id)
        ):
            raise ValueError("subject_key or a canonical subject link is required")
        return self


class TrendContextUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    marketplace: str | None = Field(default=None, max_length=120)
    market: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, max_length=3)
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] | None = None


class TrendContextResponse(TrendAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    subject_type: str
    subject_key: str
    name: str
    product_id: uuid.UUID | None
    product_opportunity_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    marketplace: str | None
    market: str | None
    country: str | None
    region: str | None
    language: str | None
    currency: str | None
    status: str
    version: int
    idempotency_key: str
    input_fingerprint: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class TrendSignalDefinitionCreate(BaseModel):
    signal_type: str = Field(min_length=1, max_length=80)
    measurement_type: str
    unit: str | None = Field(default=None, max_length=40)
    scale: Decimal | None = None
    aggregation_semantics: str = Field(default="source_reported", max_length=80)
    compatible_source_types: list[str] = Field(default_factory=list, max_length=30)
    version: str = Field(default="v1", min_length=1, max_length=40)
    description: str = Field(default="", max_length=2000)


class TrendSignalDefinitionResponse(TrendAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    signal_type: str
    measurement_type: str
    unit: str | None
    scale: Decimal | None
    aggregation_semantics: str
    compatible_source_types: list[str]
    version: str
    description: str
    created_at: datetime
    updated_at: datetime


class TrendObservationCreate(BaseModel):
    source_id: uuid.UUID
    signal_definition_id: uuid.UUID | None = None
    signal_type: str | None = Field(default=None, max_length=80)
    provider_observation_id: str | None = Field(default=None, max_length=240)
    observed_at: datetime
    captured_at: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    granularity: str = "POINT_IN_TIME"
    measurement_type: str | None = None
    value_numeric: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=2000)
    value_boolean: bool | None = None
    unit: str | None = Field(default=None, max_length=40)
    scale: Decimal | None = None
    geography_scope: str = "UNKNOWN"
    country: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    marketplace: str | None = Field(default=None, max_length=120)
    source_reference: str = Field(default="", max_length=500)
    evidence_id: uuid.UUID | None = None
    evidence_kind: str = "OBSERVED"
    verification_state: str = "UNKNOWN"
    freshness_state: str | None = None
    quality_state: str | None = None
    raw_metadata: dict[str, object] = Field(default_factory=dict)
    canonical_metadata: dict[str, object] = Field(default_factory=dict)
    provenance_note: str = Field(default="", max_length=4000)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def validate_measurement(self) -> TrendObservationCreate:
        values = [
            self.value_numeric is not None,
            self.value_text is not None,
            self.value_boolean is not None,
        ]
        if sum(values) != 1:
            raise ValueError("exactly one observation value is required")
        if self.value_numeric is not None and not self.value_numeric.is_finite():
            raise ValueError("numeric observation must be finite")
        if self.scale is not None and (not self.scale.is_finite() or self.scale <= 0):
            raise ValueError("scale must be finite and positive")
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        return self


class TrendObservationResponse(TrendAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    source_id: uuid.UUID
    evidence_id: uuid.UUID | None
    signal_definition_id: uuid.UUID
    provider_observation_id: str | None
    observed_at: datetime
    captured_at: datetime
    period_start: datetime | None
    period_end: datetime | None
    granularity: str
    measurement_type: str
    value_numeric: Decimal | None
    value_text: str | None
    value_boolean: bool | None
    unit: str | None
    scale: Decimal | None
    geography_scope: str
    country: str | None
    region: str | None
    city: str | None
    marketplace: str | None
    source_reference: str
    evidence_kind: str
    verification_state: str
    freshness_state: str
    quality_state: str
    raw_metadata: dict[str, object]
    canonical_metadata: dict[str, object]
    provenance_note: str
    fingerprint: str
    created_at: datetime


class TrendSnapshotCreate(BaseModel):
    observation_ids: list[uuid.UUID] | None = Field(default=None, max_length=10000)
    calculation_version: str = Field(default="trend-snapshot-v1", max_length=80)
    captured_at: datetime | None = None


class TrendSnapshotResponse(TrendAPIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    previous_snapshot_id: uuid.UUID | None
    snapshot_version: int
    captured_at: datetime
    observation_ids: list[str]
    source_inventory: dict[str, object]
    signal_inventory: dict[str, object]
    geographic_inventory: dict[str, object]
    granularity_inventory: dict[str, object]
    evidence_summary: dict[str, object]
    freshness_summary: dict[str, object]
    observation_count: int
    input_fingerprint: str
    calculation_version: str
    created_at: datetime


class TrendPage(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class TrendCoverageResponse(BaseModel):
    context_id: uuid.UUID
    observation_count: int
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    sources: list[dict[str, object]]
    signals: list[dict[str, object]]
    geographies: list[str]
    granularities: list[str]


class TrendDoctorResponse(BaseModel):
    status: Literal["PASS", "FAIL"]
    checks: dict[str, int]
    external_write_exposure: int


class TrendOperationsResponse(BaseModel):
    contexts: int
    observations: int
    snapshots: int
    sources: int
    last_observation_at: datetime | None
    analysis_count: int = 0
    current_analyses: int = 0
    insufficient_evidence_analyses: int = 0
    not_comparable_analyses: int = 0
    stale_analyses: int = 0
    series_count: int = 0
    evidence_gap_count: int = 0
    latest_analysis_activity: datetime | None = None
