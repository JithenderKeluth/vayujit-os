"""Contracts for Trend 12B ingestion and bounded raw candidates."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrendRawCandidate(BaseModel):
    provider_observation_id: str | None = Field(default=None, max_length=240)
    signal_key: str = Field(min_length=1, max_length=80)
    measurement_type: str = Field(min_length=1, max_length=24)
    value_numeric: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=2000)
    value_boolean: bool | None = None
    unit: str | None = Field(default=None, max_length=40)
    scale: Decimal | None = None
    observed_at: datetime
    captured_at: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    granularity: str = Field(default="POINT_IN_TIME", max_length=24)
    geography_scope: str = Field(default="UNKNOWN", max_length=24)
    country: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    marketplace: str | None = Field(default=None, max_length=120)
    source_reference: str = Field(default="", max_length=500)
    evidence_id: uuid.UUID | None = None
    evidence_kind: str = Field(default="OBSERVED", max_length=28)
    verification_state: str = Field(default="UNKNOWN", max_length=16)
    freshness_state: str | None = Field(default=None, max_length=16)
    metadata: dict[str, object] = Field(default_factory=dict)
    canonical_metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_value(self) -> TrendRawCandidate:
        if (
            sum(
                value is not None
                for value in (self.value_numeric, self.value_text, self.value_boolean)
            )
            != 1
        ):
            raise ValueError("exactly one raw observation value is required")
        if self.value_numeric is not None and not self.value_numeric.is_finite():
            raise ValueError("numeric value must be finite")
        if self.scale is not None and (not self.scale.is_finite() or self.scale <= 0):
            raise ValueError("scale must be positive and finite")
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        return self


class TrendIngestionRequest(BaseModel):
    source_id: uuid.UUID
    mode: Literal["DISABLED", "LOCAL_FIXTURE", "LIVE_READ_ONLY"] = "LOCAL_FIXTURE"
    provider: str = Field(default="LOCAL_FIXTURE", max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=180)
    candidates: list[TrendRawCandidate] = Field(default_factory=list, max_length=500)
    adapter_version: str = Field(default="trend-adapter-v1", max_length=40)
    normalization_version: str = Field(default="trend-normalization-v1", max_length=40)


class TrendIngestionBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    source_id: uuid.UUID
    provider: str
    mode: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    requested_count: int
    received_count: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    updated_observation_count: int
    input_fingerprint: str
    adapter_version: str
    normalization_version: str
    idempotency_key: str
    summary_json: dict[str, object]
    error_code: str | None
    error_message: str | None
    created_at: datetime


class TrendIngestionCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    batch_id: uuid.UUID
    ordinal: int
    provider_observation_id: str | None
    signal_key: str
    fingerprint: str | None
    duplicate_classification: str
    quality_state: str
    accepted: bool
    rejection_code: str | None
    normalized_payload: dict[str, object]
    observation_id: uuid.UUID | None
    created_at: datetime


class TrendIngestionSummary(BaseModel):
    batch: TrendIngestionBatchResponse
    coverage: dict[str, Any]
    quality_distribution: dict[str, int]
    freshness_distribution: dict[str, int]
    rejection_distribution: dict[str, int]
    gaps: list[str]
