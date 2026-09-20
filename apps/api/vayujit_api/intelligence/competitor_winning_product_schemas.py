"""API schema for the 10E competitor-to-winning-product projection."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CompetitorWinningProductProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    context_id: uuid.UUID | None
    competitor_analysis_id: uuid.UUID | None
    change_comparison_id: uuid.UUID | None
    source_state: str
    contract_version: str
    nine_b_calculation_version: str
    ten_c_calculation_version: str | None
    ten_d_calculation_version: str | None
    input_fingerprint: str
    projection: dict[str, Any]
    evidence_summary: dict[str, Any]
    research_gaps: list[dict[str, Any]]
    freshness_state: str
    contradiction_state: str
    created_at: datetime
