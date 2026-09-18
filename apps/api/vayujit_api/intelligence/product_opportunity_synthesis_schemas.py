from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SynthesisCalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str | None = Field(default=None, max_length=220)


class SynthesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    opportunity_id: UUID
    assessment_id: UUID
    calculation_version: str
    input_fingerprint: str
    upstream_lineage: dict[str, Any]
    summary: dict[str, Any]
    risks: list[Any]
    domain_readiness: dict[str, Any]
    evidence_summary: dict[str, Any]
    research_gaps: list[Any]
    changes: dict[str, Any]
    dimensions: list[Any]
    idempotency_key: str
    created_at: datetime
    notes: str


class SynthesisHistoryItem(BaseModel):
    id: UUID
    assessment_id: UUID
    input_fingerprint: str
    summary: dict[str, Any]
    changes: dict[str, Any]
    created_at: datetime
