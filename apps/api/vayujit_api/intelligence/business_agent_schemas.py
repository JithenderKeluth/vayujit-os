# ruff: noqa
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class BusinessGoalCreate(BaseModel):
    raw_goal: str = Field(min_length=5, max_length=4000)
    structured_goal: dict[str, object] | None = None
    provenance: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=2, max_length=180)


class RunCreate(BaseModel):
    idempotency_key: str = Field(min_length=2, max_length=180)
    max_steps: int = Field(default=20, ge=1, le=50)
    max_provider_calls: int = Field(default=20, ge=0, le=100)
    max_elapsed_seconds: int = Field(default=300, ge=1, le=3600)


class DecisionRequest(BaseModel):
    note: str = Field(default="", max_length=500)


class GoalResponse(BaseModel):
    id: uuid.UUID
    raw_goal: str
    structured_goal: dict[str, object]
    provenance: dict[str, object]
    assumptions: list[str]
    unresolved_questions: list[str]
    extraction_version: str
    status: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PlanResponse(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    version: int
    status: str
    planner: str
    plan_hash: str
    steps: list[dict[str, Any]]
    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    idempotency_key: str
    correlation_id: str
    budget: dict[str, object]
    usage: dict[str, object]
    result: dict[str, object]
    failure: dict[str, object]
    checkpoint: dict[str, object]
    approvals: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []
    tool_invocations: list[dict[str, object]] = []
    model_config = {"from_attributes": True}


class CapabilityResponse(BaseModel):
    id: str
    version: str
    input_schema: str
    output_schema: str
    execution_class: str
    side_effect_class: str
    approval_required: bool
    provider_required: bool
    availability: str
    health: str


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None
    status: str
    reason: str
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None
    model_config = {"from_attributes": True}
