from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    CALCULATION_VERSION,
)


class IntelligenceCalculateRequest(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=220)


class IntelligenceDimension(BaseModel):
    dimension: str
    value: Any = None
    classification: str
    evidence_state: str
    explanation: str
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    calculation_version: str = CALCULATION_VERSION


class IntelligenceOutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    kind: Literal["demand", "competition"]
    calculation_version: str
    input_snapshot: dict[str, object]
    dimensions: list[IntelligenceDimension]
    evidence_summary: dict[str, object]
    research_gaps: list[dict[str, object]]
    idempotency_key: str
    created_at: datetime
    notes: str
