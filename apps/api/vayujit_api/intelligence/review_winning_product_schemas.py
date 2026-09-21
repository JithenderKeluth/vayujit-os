"""API schemas for the 11F Review-to-Winning-Product projection."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReviewWinningProductProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    context_id: uuid.UUID | None
    snapshot_id: uuid.UUID | None
    analysis_id: uuid.UUID | None
    gap_analysis_id: uuid.UUID | None
    change_comparison_id: uuid.UUID | None
    contract_version: str
    calculation_version: str
    input_fingerprint: str
    readiness: str
    source_state: str
    cohort: dict[str, Any]
    rating_evidence: dict[str, Any]
    feedback_evidence: dict[str, Any]
    gap_evidence: list[dict[str, Any]]
    change_evidence: dict[str, Any]
    research_gaps: list[dict[str, Any]]
    freshness: dict[str, Any]
    contradictions: list[dict[str, Any]]
    evidence_lineage: dict[str, Any]
    limitations: list[str]
    projection: dict[str, Any]
    created_at: datetime
