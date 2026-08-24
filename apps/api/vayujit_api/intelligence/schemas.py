from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vayujit_api.intelligence.models import (
    ACCESS_METHODS,
    SOURCE_TYPES,
)


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ResearchProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=5000)
    target_market: str = Field(default="", max_length=120)
    target_categories: list[str] = Field(default_factory=list, max_length=100)
    excluded_categories: list[str] = Field(default_factory=list, max_length=100)
    capital_budget: float | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    risk_profile: str = Field(default="balanced", min_length=2, max_length=40)


class ResearchProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    target_market: str | None = Field(default=None, max_length=120)
    target_categories: list[str] | None = Field(default=None, max_length=100)
    excluded_categories: list[str] | None = Field(default=None, max_length=100)
    capital_budget: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    risk_profile: str | None = Field(default=None, min_length=2, max_length=40)
    status: Literal["draft", "active", "paused", "completed"] | None = None


class ResearchProjectResponse(APIModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str
    status: str
    target_market: str
    target_categories: list[str]
    excluded_categories: list[str]
    capital_budget: float | None
    currency: str
    risk_profile: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ResearchRunCreate(BaseModel):
    idempotency_key: str | None = Field(default=None, max_length=180)
    ruleset_version: str = Field(default="default-v1", max_length=120)
    source_policy_reference: str = Field(default="internal-only", max_length=120)
    source_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class ResearchRunResponse(APIModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    correlation_id: str
    ruleset_version: str
    source_policy_reference: str
    summary_json: dict[str, object]
    failure_classification: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class SourceCreate(BaseModel):
    source_type: str
    display_name: str = Field(min_length=2, max_length=160)
    provider: str = Field(default="manual", max_length=120)
    url_or_domain: str | None = Field(default=None, max_length=500)
    access_method: str = "manual_entry"
    trust_classification: str = "untrusted_external_data"
    configuration_status: str = Field(default="not_configured", max_length=40)
    terms_policy_status: str = Field(default="unknown", max_length=40)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def valid_source_type(cls, value: str) -> str:
        if value not in SOURCE_TYPES:
            raise ValueError("Unsupported source type.")
        return value

    @field_validator("access_method")
    @classmethod
    def valid_access_method(cls, value: str) -> str:
        if value not in ACCESS_METHODS:
            raise ValueError("Unsupported source access method.")
        return value


class SourceUpdate(BaseModel):
    enabled: bool | None = None
    configuration_status: str | None = Field(default=None, max_length=40)
    terms_policy_status: str | None = Field(default=None, max_length=40)
    failure_status: str | None = Field(default=None, max_length=120)
    metadata: dict[str, object] | None = None


class SourceResponse(APIModel):
    id: uuid.UUID
    source_type: str
    display_name: str
    provider: str
    url_or_domain: str | None
    enabled: bool
    trust_classification: str
    access_method: str
    configuration_status: str
    terms_policy_status: str
    last_successful_retrieval: datetime | None
    failure_status: str | None
    metadata_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class EvidenceCreate(BaseModel):
    source_id: uuid.UUID
    research_run_id: uuid.UUID | None = None
    previous_evidence_id: uuid.UUID | None = None
    source_reference: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=1000)
    observed_at: datetime
    content_type: str = Field(default="text/plain", max_length=100)
    normalized_value: dict[str, object] = Field(default_factory=dict)
    excerpt_summary: str = Field(default="", max_length=20_000)
    content_hash: str = Field(min_length=16, max_length=128)
    verification_status: Literal["unverified", "pending", "verified", "rejected"] = "unverified"
    freshness_ttl_seconds: int | None = Field(default=None, ge=1, le=31_536_000)
    metadata: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=180)


class EvidenceResponse(APIModel):
    id: uuid.UUID
    source_id: uuid.UUID
    research_run_id: uuid.UUID | None
    previous_evidence_id: uuid.UUID | None
    source_reference: str
    source_url: str | None
    observed_at: datetime
    retrieved_at: datetime
    content_type: str
    normalized_value: dict[str, object]
    excerpt_summary: str
    content_hash: str
    trust_classification: str
    verification_status: str
    freshness_status: str
    freshness_ttl_seconds: int | None
    metadata_json: dict[str, object]
    correlation_id: str
    idempotency_key: str
    created_at: datetime


class ClaimCreate(BaseModel):
    research_run_id: uuid.UUID | None = None
    claim_type: str = Field(min_length=2, max_length=80)
    normalized_value: dict[str, object] = Field(default_factory=dict)
    unit: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    confidence: float = Field(default=0, ge=0, le=1)
    verification_state: Literal["unverified", "pending", "verified", "rejected"] = "unverified"
    evidence_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class ClaimResponse(APIModel):
    id: uuid.UUID
    research_run_id: uuid.UUID | None
    claim_type: str
    normalized_value: dict[str, object]
    unit: str | None
    currency: str | None
    confidence: float
    verification_state: str
    evidence_ids: list[uuid.UUID]
    correlation_id: str
    created_at: datetime


class RuleCategoryResponse(APIModel):
    id: uuid.UUID
    category_key: str
    display_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RuleCategoryUpdate(BaseModel):
    enabled: bool


class RuleCreate(BaseModel):
    category_id: uuid.UUID
    logical_key: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=5000)
    enabled: bool = True
    priority: int = Field(default=100, ge=-1000, le=1000)
    severity: str = Field(default="warning", max_length=24)
    hard_block: bool = False
    operator: str = Field(default="exists", max_length=32)
    conditions: dict[str, object] = Field(default_factory=dict)
    parameters: dict[str, object] = Field(default_factory=dict)
    reason_template: str = Field(default="Rule evaluated.", max_length=500)


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    severity: str | None = Field(default=None, max_length=24)
    hard_block: bool | None = None
    operator: str | None = Field(default=None, max_length=32)
    conditions: dict[str, object] | None = None
    parameters: dict[str, object] | None = None
    reason_template: str | None = Field(default=None, max_length=500)


class RuleResponse(APIModel):
    id: uuid.UUID
    category_id: uuid.UUID
    logical_key: str
    version: int
    name: str
    description: str
    enabled: bool
    priority: int
    severity: str
    hard_block: bool
    operator: str
    conditions: dict[str, object]
    parameters: dict[str, object]
    reason_template: str
    created_at: datetime
    updated_at: datetime


class OpportunityCreate(BaseModel):
    research_run_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=200)
    category: str = Field(default="", max_length=120)
    market: str = Field(default="", max_length=120)
    score: float = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0, ge=0, le=1)
    hard_blocked: bool = False
    primary_reasons: list[str] = Field(default_factory=list, max_length=50)
    risk_summary: str = Field(default="", max_length=5000)
    evidence_count: int = Field(default=0, ge=0)
    freshness_state: str = "unknown"


class OpportunityResponse(APIModel):
    id: uuid.UUID
    candidate_id: uuid.UUID | None
    research_run_id: uuid.UUID | None
    title: str
    category: str
    market: str
    status: str
    score: float
    confidence: float
    hard_blocked: bool
    primary_reasons: list[str]
    risk_summary: str
    evidence_count: int
    freshness_state: str
    created_at: datetime
    updated_at: datetime


class OpportunityReviewRequest(BaseModel):
    action: Literal["shortlist", "reject", "approve"]
    reason: str = Field(default="", max_length=500)


class RuleEvaluationResponse(BaseModel):
    opportunity_id: uuid.UUID
    score: float
    hard_blocked: bool
    evaluations: list[dict[str, Any]]


class IntelligenceOverviewResponse(BaseModel):
    active_projects: int
    recent_runs: int
    opportunities: dict[str, int]
    hard_blocked_candidates: int
    evidence_freshness: dict[str, int]
    enabled_sources: int
    source_health: dict[str, int]
    rule_counts: dict[str, int]
    recent_failures: int


class CandidateResponse(APIModel):
    id: uuid.UUID
    project_id: uuid.UUID
    research_run_id: uuid.UUID
    source_id: uuid.UUID
    external_reference: str
    deduplication_key: str
    title: str
    normalized_title: str
    category: str
    subcategory: str
    market: str
    observed_brand: str | None
    source_reference: str
    status: str
    observed_price: float | None
    currency: str | None
    attributes: dict[str, object]
    duplicate_of_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SignalResponse(APIModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    signal_type: str
    value: float | None
    normalized_score: float | None
    unit: str | None
    source_evidence_ids: list[str]
    observed_at: datetime
    freshness: str
    confidence: float
    calculation_method: str
    signal_version: int
    details: dict[str, object]
    created_at: datetime


class ResearchProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    market: str = Field(default="", max_length=120)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    min_selling_price: float | None = Field(default=None, ge=0)
    max_selling_price: float | None = Field(default=None, ge=0)
    max_sourcing_estimate: float | None = Field(default=None, ge=0)
    minimum_margin: float | None = Field(default=None, ge=0, le=1)
    max_weight_kg: float | None = Field(default=None, ge=0)
    max_length_cm: float | None = Field(default=None, ge=0)
    max_width_cm: float | None = Field(default=None, ge=0)
    max_height_cm: float | None = Field(default=None, ge=0)
    categories: list[str] = Field(default_factory=list, max_length=100)
    excluded_categories: list[str] = Field(default_factory=list, max_length=100)
    competition_tolerance: str = Field(default="balanced", max_length=24)
    risk_tolerance: str = Field(default="balanced", max_length=24)


class ResearchProfileResponse(APIModel):
    id: uuid.UUID
    name: str
    market: str
    currency: str
    min_selling_price: float | None
    max_selling_price: float | None
    max_sourcing_estimate: float | None
    minimum_margin: float | None
    max_weight_kg: float | None
    max_length_cm: float | None
    max_width_cm: float | None
    max_height_cm: float | None
    categories: list[str]
    excluded_categories: list[str]
    competition_tolerance: str
    risk_tolerance: str
    created_at: datetime
    updated_at: datetime


class MissionCreate(BaseModel):
    project_id: uuid.UUID
    profile_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=160)
    frequency: str = Field(default="manual", max_length=40)
    timezone: str = Field(default="UTC", max_length=80)
    market: str = Field(default="", max_length=120)
    categories: list[str] = Field(default_factory=list, max_length=100)
    ruleset_version: str = Field(default="default-v1", max_length=120)
    minimum_score_threshold: float = Field(default=45, ge=0, le=100)
    notification_threshold: float = Field(default=65, ge=0, le=100)


class MissionUpdate(BaseModel):
    enabled: bool | None = None
    frequency: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=80)
    categories: list[str] | None = Field(default=None, max_length=100)
    minimum_score_threshold: float | None = Field(default=None, ge=0, le=100)
    notification_threshold: float | None = Field(default=None, ge=0, le=100)
    status: Literal["draft", "active", "paused", "completed", "failed"] | None = None


class MissionResponse(APIModel):
    id: uuid.UUID
    project_id: uuid.UUID
    profile_id: uuid.UUID | None
    name: str
    enabled: bool
    frequency: str
    timezone: str
    market: str
    categories: list[str]
    ruleset_version: str
    minimum_score_threshold: float
    notification_threshold: float
    status: str
    last_run_id: uuid.UUID | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReportResponse(APIModel):
    id: uuid.UUID
    run_id: uuid.UUID
    format: str
    title: str
    content: str
    provenance_json: dict[str, object]
    created_at: datetime


class CompareRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)


class RuleSimulationRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    minimum_score_threshold: float = Field(default=45, ge=0, le=100)
    scoring_model_version: str = Field(default="winning-product-local-v1", max_length=120)


class RuleSimulationResponse(BaseModel):
    allowed: int
    warned: int
    review_required: int
    blocked: int
    candidates: list[dict[str, object]]


class PhysicalRuleEvaluationRequest(BaseModel):
    actual: dict[str, object] = Field(default_factory=dict)
    thresholds: dict[str, object] = Field(default_factory=dict)


class PolicySimulationRequest(BaseModel):
    rules: dict[str, list[str]] = Field(default_factory=dict)
    authorized_override: bool = False


class EconomicsEstimateRequest(BaseModel):
    inputs: dict[str, object] = Field(default_factory=dict)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class ScoreWeightRequest(BaseModel):
    weights: dict[str, float]
    known_dimensions: list[str] = Field(default_factory=list)


class ScheduleRequest(BaseModel):
    scheduled_for: datetime
    timezone: str = Field(default="UTC", max_length=80)
    frequency: str = Field(default="manual", max_length=40)


class RecoveryRequest(BaseModel):
    failure_classification: str
    action: str
    idempotency_key: str = Field(min_length=2, max_length=180)


class TrendObservationResponse(APIModel):
    id: uuid.UUID
    candidate_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    market: str
    category: str
    trend_state: str
    velocity: float
    acceleration: float
    seasonality: float
    confidence: float
    source_evidence_ids: list[str]
    observed_at: datetime
    created_at: datetime
    correlation_id: str


class HistoryResponse(BaseModel):
    mission: dict[str, object]
    run: dict[str, object]
    recovery: list[dict[str, object]]
