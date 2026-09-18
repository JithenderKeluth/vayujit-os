"""Schemas for supplier and sourcing feasibility projections."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeasibilityCalculateRequest(BaseModel):
    """Optional bounded references; defaults consume all owner-scoped evidence."""

    model_config = ConfigDict(extra="forbid")

    supplier_product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    idempotency_key: str | None = Field(default=None, max_length=220)


class FeasibilityHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_product_id: uuid.UUID
    confirm: bool = False


class FeasibilityOutputResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    calculation_version: str
    constraint_snapshot: dict[str, Any]
    upstream_lineage: dict[str, Any]
    summary: dict[str, Any]
    candidates: list[Any]
    dimensions: list[Any]
    evidence_summary: dict[str, Any]
    research_gaps: list[Any]
    idempotency_key: str
    created_at: datetime
    notes: str


class FeasibilityHistoryItem(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    calculation_version: str
    created_at: datetime
    summary: dict[str, Any]
