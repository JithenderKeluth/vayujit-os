"""API contracts for PR-6B explainable decision synthesis."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DecisionTarget = Literal[
    "PRODUCT_SELECTION",
    "SUPPLIER_SELECTION",
    "COMMERCIAL_ASSESSMENT",
    "LAUNCH_DECISION",
]
SynthesisPosture = Literal[
    "CONTINUE_RESEARCH",
    "HOLD",
    "READY_FOR_HUMAN_DECISION",
    "CONSTRAINT_FAILED",
]


class DecisionSynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_target: DecisionTarget = "COMMERCIAL_ASSESSMENT"
    decision_evidence_snapshot_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=220)


class DecisionSynthesisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID
    opportunity_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    decision_evidence_snapshot_id: uuid.UUID
    decision_target: str
    readiness_state: Literal["READY", "NEEDS_EVIDENCE", "BLOCKED"]
    readiness_policy_version: str
    synthesis_policy_version: str
    posture: SynthesisPosture
    primary_reason: dict[str, Any] = Field(default_factory=dict)
    reasons: list[Any] = Field(default_factory=list)
    supporting_evidence: list[Any] = Field(default_factory=list)
    blockers: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    unknowns: list[Any] = Field(default_factory=list)
    contradictions: list[Any] = Field(default_factory=list)
    limitations: list[Any] = Field(default_factory=list)
    trust_summary: dict[str, Any] = Field(default_factory=dict)
    economics_summary: dict[str, Any] = Field(default_factory=dict)
    capital_fit_state: str
    safe_next_actions: list[Any] = Field(default_factory=list)
    human_review_required: bool
    input_fingerprint: str
    idempotency_key: str
    explanation: str
    created_at: str
    external_writes: list[Any] = Field(default_factory=list)
    recommendation: Any = None
