# ruff: noqa: E501,UP017
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from vayujit_api.intelligence.autonomous_models import AUTONOMOUS_MISSION_TYPES


class AutonomousMissionCreate(BaseModel):
    mission_type: str = Field(min_length=2, max_length=40)

    @field_validator("mission_type")
    @classmethod
    def validate_mission_type(cls, value: str) -> str:
        if value not in AUTONOMOUS_MISSION_TYPES:
            raise ValueError("Unsupported autonomous mission type")
        return value

    goal: str = Field(min_length=3, max_length=4000)
    scope: dict[str, object] = Field(default_factory=dict)
    market: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=120)
    product_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    research_profile: dict[str, object] = Field(default_factory=dict)
    ruleset: dict[str, object] = Field(default_factory=dict)
    source_policy: dict[str, object] = Field(default_factory=dict)
    budget_policy: dict[str, object] = Field(default_factory=dict)
    provider_mode: Literal["DISABLED", "LOCAL_DETERMINISTIC", "EXTERNAL_AI"] = "LOCAL_DETERMINISTIC"
    required_confidence: float = Field(default=0.7, ge=0, le=1)
    max_tasks: int = Field(default=20, ge=1, le=100)
    max_provider_calls: int = Field(default=20, ge=1, le=100)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_elapsed_seconds: int = Field(default=300, ge=1, le=3600)
    idempotency_key: str = Field(min_length=2, max_length=180)
    frequency: str = Field(default="manual", max_length=32)
    timezone: str = Field(default="UTC", max_length=80)


class AutonomousMissionResponse(BaseModel):
    id: uuid.UUID
    mission_type: str
    goal: str
    scope: dict[str, object]
    market: str
    category: str
    product_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    research_profile: dict[str, object]
    ruleset: dict[str, object]
    source_policy: dict[str, object]
    budget_policy: dict[str, object]
    provider_mode: str
    correlation_id: str
    status: str
    idempotency_key: str
    confidence: float
    unknown_ratio: float
    required_confidence: float
    max_tasks: int
    max_provider_calls: int
    max_retries: int
    max_elapsed_seconds: int
    frequency: str
    timezone: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutonomousTaskResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    task_type: str
    dependency_ids: list[str]
    source_class: str
    priority: int
    status: str
    attempt_count: int
    checkpoint: dict[str, object]
    result_projection: dict[str, object]
    failure_code: str | None
    idempotency_key: str
    correlation_id: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AutonomousTaskRunRequest(BaseModel):
    confirm: bool = False
    crash_stage: Literal["before_source", "after_evidence", "after_task"] | None = None


class AutonomousEvidenceResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID
    source_class: str
    source_reference: str
    retrieval_identity: str
    content_type: str
    normalized_value: dict[str, object]
    content_hash: str
    verification_status: str
    freshness_status: str
    confidence: float
    evidence_class: str
    is_untrusted_external_data: bool
    observed_at: datetime
    retrieved_at: datetime
    created_at: datetime
    model_config = {"from_attributes": True}


class AutonomousContradictionResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    identity_key: str
    contradiction_type: str
    evidence_a_id: uuid.UUID
    evidence_b_id: uuid.UUID
    status: str
    resolution_strategy: str | None
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None
    model_config = {"from_attributes": True}


class ContradictionResolutionRequest(BaseModel):
    strategy: Literal[
        "prefer_newer_verified",
        "prefer_higher_quality",
        "require_additional_source",
        "mark_unresolved",
        "human_review",
    ]
    note: str = Field(default="", max_length=500)


class AutonomousScheduleRequest(BaseModel):
    scheduled_for: datetime
    timezone: str = Field(default="UTC", max_length=80)
    frequency: Literal["manual", "daily", "weekly", "monthly"] = "manual"
    catch_up_policy: Literal["SKIP", "RUN_LATEST", "BOUNDED_CATCH_UP"] = "SKIP"


class AutonomousRecoveryRequest(BaseModel):
    failure_code: str = Field(min_length=2, max_length=80)
    action: Literal[
        "retry",
        "reconcile",
        "refresh_source",
        "review_source",
        "review_evidence",
        "resolve_contradiction",
        "skip_optional_task",
        "cancel",
    ]
    task_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=2, max_length=180)


class AutonomousReportResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    format: str
    content: str
    provenance: dict[str, object]
    created_at: datetime
    model_config = {"from_attributes": True}


class AutonomousChangeResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    change_type: str
    identity_key: str
    previous_value: dict[str, object]
    current_value: dict[str, object]
    delta: float | None
    material: bool
    materiality: str
    reason: str
    evidence_ids: list[str]
    observed_at: datetime
    correlation_id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class AutonomousAlertResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    alert_type: str
    severity: str
    title: str
    detail: str
    acknowledged: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AutonomousRunResponse(BaseModel):
    mission: AutonomousMissionResponse
    tasks: list[AutonomousTaskResponse]
    evidence: list[AutonomousEvidenceResponse]
    contradictions: list[AutonomousContradictionResponse]
    changes: list[AutonomousChangeResponse]
    alerts: list[AutonomousAlertResponse]
    summary: dict[str, Any]


class AutonomousPolicyResponse(BaseModel):
    external_research_enabled: bool
    default_provider_mode: str
    allowed_modes: list[str]
    forbidden_capabilities: list[str]
    source_registry: list[dict[str, str]]
    prompt_injection_defense: str


class AutonomousOverviewResponse(BaseModel):
    active_missions: int
    queued_tasks: int
    completed_missions: int
    partial_missions: int
    failed_missions: int
    stale_opportunities: int
    evidence_refresh_backlog: int
    contradictions: int
    recovery: int
    external_research: str
    ai_mode: str


class AutonomousMissionHistoryResponse(BaseModel):
    mission: AutonomousMissionResponse
    tasks: list[AutonomousTaskResponse]
    evidence: list[AutonomousEvidenceResponse]
    contradictions: list[AutonomousContradictionResponse]
    changes: list[AutonomousChangeResponse]
    alerts: list[AutonomousAlertResponse]
    reports: list[AutonomousReportResponse]
    recovery: list[dict[str, object]]
    duration_ms: float | None


class AutonomousSourceCreate(BaseModel):
    source_class: str = Field(min_length=2, max_length=64)
    status: Literal["LOCAL_FIXTURE", "MANUAL_ONLY", "NOT_CONFIGURED", "NOT_IMPLEMENTED"] = (
        "LOCAL_FIXTURE"
    )
    domain: str = Field(default="", max_length=500)
    enabled: bool = False
