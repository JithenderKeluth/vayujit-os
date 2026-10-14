"""API contracts for PR-6C recommendation and human-decision workflow."""

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
RecommendationState = Literal[
    "NOT_ELIGIBLE",
    "READY_FOR_REVIEW",
    "SYSTEM_SUPPORTS_PROCEEDING",
    "SYSTEM_SUPPORTS_NOT_PROCEEDING",
]
HumanDecisionValue = Literal["PROCEED", "KEEP_UNDER_REVIEW", "DO_NOT_PROCEED"]


class RecommendationAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_target: DecisionTarget = "COMMERCIAL_ASSESSMENT"
    synthesis_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=220)


class RecommendationAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID
    owner_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    decision_evidence_snapshot_id: uuid.UUID
    synthesis_id: uuid.UUID
    decision_target: str
    recommendation_policy_version: str
    recommendation_state: RecommendationState
    supporting_reasons: list[Any] = Field(default_factory=list)
    counter_reasons: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    unknowns: list[Any] = Field(default_factory=list)
    contradictions: list[Any] = Field(default_factory=list)
    limitations: list[Any] = Field(default_factory=list)
    trust_summary: dict[str, Any] = Field(default_factory=dict)
    economics_summary: dict[str, Any] = Field(default_factory=dict)
    capital_fit_state: str
    human_review_required: bool
    input_fingerprint: str
    idempotency_key: str
    created_at: str
    explanation: str
    external_writes: list[Any] = Field(default_factory=list)
    human_decision: Any = None


class HumanDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_target: DecisionTarget = "COMMERCIAL_ASSESSMENT"
    decision: HumanDecisionValue
    recommendation_id: uuid.UUID | None = None
    synthesis_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    reason: str = Field(default="", max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=220)
    provenance: Literal["HUMAN"] = "HUMAN"


class HumanDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID
    owner_id: uuid.UUID
    actor_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    decision_evidence_snapshot_id: uuid.UUID
    synthesis_id: uuid.UUID
    recommendation_id: uuid.UUID
    supersedes_decision_id: uuid.UUID | None = None
    decision_target: str
    decision: HumanDecisionValue
    reason: str
    provenance: Literal["HUMAN"]
    context_fingerprint: str
    idempotency_key: str
    created_at: str
    external_writes: list[Any] = Field(default_factory=list)
