"""API contracts for PR-6A decision evidence/readiness snapshots."""

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


class DecisionReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_target: DecisionTarget = "COMMERCIAL_ASSESSMENT"
    assessment_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=220)


class DecisionReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID | None = None
    decision_target: str
    readiness_state: Literal["READY", "NEEDS_EVIDENCE", "BLOCKED"]
    policy_version: str
    decision_version: int | None = None
    input_fingerprint: str
    input_references: dict[str, Any] = Field(default_factory=dict)
    trust_environment: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    blockers: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    unknowns: list[Any] = Field(default_factory=list)
    contradictions: list[Any] = Field(default_factory=list)
    limitations: list[Any] = Field(default_factory=list)
    freshness_summary: dict[str, Any] = Field(default_factory=dict)
    safe_next_action: dict[str, Any] = Field(default_factory=dict)
    external_writes: list[Any] = Field(default_factory=list)
    recommendation: Any = None
