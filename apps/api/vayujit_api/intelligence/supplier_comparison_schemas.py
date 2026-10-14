"""PR-8B comparison and HUMAN-shortlist API contracts."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vayujit_api.intelligence.shortlisting_schemas import Decision


class SupplierComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    reassessment_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)
    goal_id: uuid.UUID | None = None


class SupplierComparisonShortlistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_supplier_id: uuid.UUID
    decision: Decision
    reason: str = Field(default="", max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    decision_key: str = Field(min_length=3, max_length=180)


class SupplierComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    goal_id: uuid.UUID | None
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    snapshot_version: int
    status: str
    idempotency_key: str
    input_fingerprint: str
    canonical_supplier_ids: list[object]
    supplier_ids: list[object]
    supplier_product_ids: list[object]
    reassessment_ids: list[object]
    quote_versions: list[object]
    input_fingerprints: list[object]
    calculation_versions: list[object]
    suppliers: list[object]
    metrics: list[object]
    unknowns: list[object]
    blockers: list[object]
    contradictions: list[object]
    provenance: dict[str, object]
    lineage: dict[str, object]
    shortlist_context_id: uuid.UUID | None
    shortlist_version_id: uuid.UUID | None
    human_decisions: list[object] = Field(default_factory=list)
    created_at: object
    notes: str
    idempotent_reuse: bool = False


class SupplierComparisonShortlistResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID
    decision: str
    idempotent_reuse: bool = False
    comparison_id: uuid.UUID
    canonical_supplier_id: uuid.UUID
    human_provenance: Literal["HUMAN"] = "HUMAN"
