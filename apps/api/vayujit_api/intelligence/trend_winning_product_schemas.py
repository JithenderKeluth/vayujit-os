"""API contracts for the 12F Trend-to-Winning-Product adapter."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TrendWinningProductProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    context_id: uuid.UUID | None
    snapshot_id: uuid.UUID | None
    analysis_id: uuid.UUID | None
    comparison_id: uuid.UUID | None
    validation_id: uuid.UUID | None
    projection_version: int
    contract_version: str
    calculation_version: str
    input_fingerprint: str
    readiness: str
    source_state: str
    validated_hypotheses: list[dict[str, Any]]
    signal_summaries: list[dict[str, Any]]
    momentum_summaries: list[dict[str, Any]]
    evidence_confidence: dict[str, Any]
    freshness: dict[str, Any]
    contradictions: list[dict[str, Any]]
    research_gaps: list[dict[str, Any]]
    evidence_lineage: dict[str, Any]
    limitations: list[str]
    projection: dict[str, Any]
    created_at: datetime


class TrendWinningProductProjectionPage(BaseModel):
    items: list[TrendWinningProductProjectionResponse]
    total: int
    limit: int
    offset: int
