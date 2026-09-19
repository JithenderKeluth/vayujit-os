"""API contracts for deterministic competitor commercial analysis (Slice 10C)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommercialAnalysisCreate(BaseModel):
    discovery_snapshot_id: uuid.UUID | None = None
    include_provisional: bool = False
    maximum_products: int = Field(default=500, ge=1, le=500)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=220)


class CohortEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_id: uuid.UUID
    context_id: uuid.UUID
    product_id: uuid.UUID
    identity_state: str
    included: bool
    exclusion_reason: str | None
    evidence_state: str
    freshness_state: str
    observation_ids: list[Any]
    explanation: dict[str, Any]


class CommercialAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    discovery_snapshot_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    analysis_version: int
    calculation_version: str
    status: str
    input_fingerprint: str
    input_snapshot: dict[str, Any]
    cohort_summary: dict[str, Any]
    pricing_analysis: dict[str, Any]
    concentration_analysis: dict[str, Any]
    rating_analysis: dict[str, Any]
    review_analysis: dict[str, Any]
    assortment_analysis: dict[str, Any]
    positioning_analysis: dict[str, Any]
    differentiation_analysis: list[dict[str, Any]]
    competitive_gaps: list[dict[str, Any]]
    evidence_coverage: dict[str, Any]
    freshness_summary: dict[str, Any]
    contradictions: list[dict[str, Any]]
    research_gaps: list[dict[str, Any]]
    explanation: dict[str, Any]
    idempotency_key: str
    created_at: datetime


class AnalysisListResponse(BaseModel):
    items: list[CommercialAnalysisResponse]
    total: int
    limit: int
    offset: int
