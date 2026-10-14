"""PR-8C procurement-readiness API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProcurementReadinessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    canonical_supplier_id: uuid.UUID
    supplier_product_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    shortlist_context_id: uuid.UUID | None = None
    shortlist_decision_id: uuid.UUID | None = None
    due_diligence_context_id: uuid.UUID | None = None
    commercial_readiness_id: uuid.UUID | None = None
    reassessment_id: uuid.UUID | None = None
    comparison_id: uuid.UUID | None = None


class ProcurementReadinessAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    decision: Literal["REVIEWED", "NEEDS_FURTHER_EVIDENCE", "KEEP_UNDER_REVIEW"]
    provenance: Literal["HUMAN"] = "HUMAN"
    reason: str = Field(default="", max_length=4000)


class ProcurementReadinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    goal_id: uuid.UUID | None
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    canonical_supplier_id: uuid.UUID
    supplier_id: uuid.UUID | None
    supplier_product_id: uuid.UUID | None
    shortlist_context_id: uuid.UUID | None
    shortlist_version_id: uuid.UUID | None
    shortlist_decision_id: uuid.UUID | None
    due_diligence_context_id: uuid.UUID | None
    commercial_readiness_id: uuid.UUID | None
    reassessment_id: uuid.UUID | None
    comparison_id: uuid.UUID | None
    snapshot_version: int
    status: str
    policy_version: str
    calculation_versions: list[object]
    dimensions: dict[str, object]
    blockers: list[object]
    unknowns: list[object]
    contradictions: list[object]
    evidence_lineage: dict[str, object]
    provenance: dict[str, object]
    input_fingerprint: str
    idempotency_key: str
    actor_id: uuid.UUID
    actor_provenance: str
    created_at: datetime
    notes: str
    acknowledgements: list[dict[str, object]] = Field(default_factory=list)
    idempotent_reuse: bool = False
