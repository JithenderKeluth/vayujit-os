# ruff: noqa: E501
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

PROJECT_STATUSES = ("draft", "active", "paused", "completed", "archived")
RUN_STATUSES = (
    "pending",
    "claimed",
    "running",
    "checkpointed",
    "waiting",
    "completed",
    "failed",
    "retry_wait",
    "cancelled",
    "stale",
)
SOURCE_TYPES = (
    "marketplace",
    "supplier_directory",
    "manufacturer",
    "trend_source",
    "search_provider",
    "manual",
    "document",
    "offline_supplier",
    "internal_marketplace_data",
)
ACCESS_METHODS = (
    "api",
    "approved_web_fetch",
    "manual_import",
    "manual_entry",
    "internal",
    "provider_connector",
)
TRUST_CLASSIFICATIONS = (
    "trusted_internal",
    "approved_provider",
    "manual_assertion",
    "untrusted_external_data",
)
FRESHNESS_STATUSES = ("fresh", "aging", "stale", "expired", "unknown")
VERIFICATION_STATES = ("unverified", "pending", "verified", "rejected")
OPPORTUNITY_STATUSES = (
    "discovered",
    "researching",
    "review",
    "shortlisted",
    "rejected",
    "approved",
    "converted",
)
REVIEW_ACTIONS = ("shortlist", "reject", "approve")


class IntelligenceResearchProject(Base):
    __tablename__ = "intelligence_research_projects"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_intelligence_project_owner_name"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{item}'" for item in PROJECT_STATUSES) + ")",
            name="ck_intelligence_project_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    target_market: Mapped[str] = mapped_column(String(120), default="")
    target_categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    capital_budget: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    risk_profile: Mapped[str] = mapped_column(String(40), default="balanced")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntelligenceResearchRun(Base):
    __tablename__ = "intelligence_research_runs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_intelligence_run_owner_idempotency"
        ),
        CheckConstraint(
            "status IN (" + ",".join(f"'{item}'" for item in RUN_STATUSES) + ")",
            name="ck_intelligence_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_projects.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    ruleset_version: Mapped[str] = mapped_column(String(120), default="default-v1")
    source_policy_reference: Mapped[str] = mapped_column(String(120), default="internal-only")
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_classification: Mapped[str | None] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceSource(Base):
    __tablename__ = "intelligence_sources"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "provider",
            "display_name",
            name="uq_intelligence_source_owner_provider_name",
        ),
        CheckConstraint(
            "source_type IN (" + ",".join(f"'{item}'" for item in SOURCE_TYPES) + ")",
            name="ck_intelligence_source_type",
        ),
        CheckConstraint(
            "access_method IN (" + ",".join(f"'{item}'" for item in ACCESS_METHODS) + ")",
            name="ck_intelligence_source_access",
        ),
        CheckConstraint(
            "trust_classification IN ("
            + ",".join(f"'{item}'" for item in TRUST_CLASSIFICATIONS)
            + ")",
            name="ck_intelligence_source_trust",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    provider: Mapped[str] = mapped_column(String(120), default="manual")
    url_or_domain: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trust_classification: Mapped[str] = mapped_column(String(40), default="untrusted_external_data")
    access_method: Mapped[str] = mapped_column(String(32), default="manual_entry")
    configuration_status: Mapped[str] = mapped_column(String(40), default="not_configured")
    terms_policy_status: Mapped[str] = mapped_column(String(40), default="unknown")
    last_successful_retrieval: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_status: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceEvidence(Base):
    __tablename__ = "intelligence_evidence"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_intelligence_evidence_owner_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        index=True,
    )
    previous_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_evidence.id", ondelete="SET NULL"), index=True
    )
    source_reference: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_type: Mapped[str] = mapped_column(String(100))
    normalized_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    excerpt_summary: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    trust_classification: Mapped[str] = mapped_column(String(40), default="untrusted_external_data")
    verification_status: Mapped[str] = mapped_column(String(24), default="unverified")
    freshness_status: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    freshness_ttl_seconds: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IntelligenceClaim(Base):
    __tablename__ = "intelligence_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(String(80))
    normalized_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    unit: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str | None] = mapped_column(String(3))
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    verification_state: Mapped[str] = mapped_column(String(24), default="unverified")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IntelligenceClaimEvidence(Base):
    __tablename__ = "intelligence_claim_evidence"
    __table_args__ = (
        UniqueConstraint("claim_id", "evidence_id", name="uq_intelligence_claim_evidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_claims.id", ondelete="CASCADE"), index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_evidence.id", ondelete="RESTRICT"), index=True
    )


class IntelligenceRuleCategory(Base):
    __tablename__ = "intelligence_rule_categories"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "category_key", name="uq_intelligence_rule_category_owner_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_key: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceRule(Base):
    __tablename__ = "intelligence_rules"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "logical_key", "version", name="uq_intelligence_rule_owner_key_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_rule_categories.id", ondelete="CASCADE"),
        index=True,
    )
    logical_key: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    severity: Mapped[str] = mapped_column(String(24), default="warning")
    hard_block: Mapped[bool] = mapped_column(Boolean, default=False)
    operator: Mapped[str] = mapped_column(String(32), default="exists")
    conditions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    reason_template: Mapped[str] = mapped_column(String(500), default="Rule evaluated.")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceRuleEvaluation(Base):
    __tablename__ = "intelligence_rule_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "rule_id",
            "rule_version",
            "subject_type",
            "subject_id",
            name="uq_intel_rule_eval_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_rules.id", ondelete="RESTRICT"), index=True
    )
    rule_version: Mapped[int] = mapped_column(Integer)
    subject_type: Mapped[str] = mapped_column(String(80))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    input_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    result: Mapped[str] = mapped_column(String(24))
    score_impact: Mapped[float] = mapped_column(Numeric(8, 3), default=0)
    hard_block: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(500))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IntelligenceOpportunity(Base):
    __tablename__ = "intelligence_opportunities"
    __table_args__ = (
        UniqueConstraint("owner_id", "candidate_id", name="uq_intel_opportunity_owner_candidate"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{item}'" for item in OPPORTUNITY_STATUSES) + ")",
            name="ck_intelligence_opportunity_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="SET NULL"),
        index=True,
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(120), default="")
    market: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(24), default="discovered", index=True)
    score: Mapped[float] = mapped_column(Numeric(8, 3), default=0)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    hard_blocked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    primary_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risk_summary: Mapped[str] = mapped_column(Text, default="")
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    freshness_state: Mapped[str] = mapped_column(String(24), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceOpportunityReview(Base):
    __tablename__ = "intelligence_opportunity_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(500), default="")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


CANDIDATE_STATUSES = (
    "discovered",
    "normalized",
    "screening",
    "evaluated",
    "promoted",
    "rejected",
    "duplicate",
    "stale",
)
MISSION_STATUSES = ("draft", "active", "paused", "completed", "failed")
SIGNAL_TYPES = (
    "demand",
    "competition",
    "pricing",
    "trend",
    "reviews",
    "operational_complexity",
    "risk",
    "economics",
    "differentiation",
    "evidence_confidence",
)


class IntelligenceResearchProfile(Base):
    __tablename__ = "intelligence_research_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_intel_profile_owner_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    market: Mapped[str] = mapped_column(String(120), default="")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    min_selling_price: Mapped[float | None] = mapped_column(Numeric(18, 2))
    max_selling_price: Mapped[float | None] = mapped_column(Numeric(18, 2))
    max_sourcing_estimate: Mapped[float | None] = mapped_column(Numeric(18, 2))
    minimum_margin: Mapped[float | None] = mapped_column(Numeric(8, 4))
    max_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 4))
    max_length_cm: Mapped[float | None] = mapped_column(Numeric(12, 4))
    max_width_cm: Mapped[float | None] = mapped_column(Numeric(12, 4))
    max_height_cm: Mapped[float | None] = mapped_column(Numeric(12, 4))
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    competition_tolerance: Mapped[str] = mapped_column(String(24), default="balanced")
    risk_tolerance: Mapped[str] = mapped_column(String(24), default="balanced")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceResearchMission(Base):
    __tablename__ = "intelligence_research_missions"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_intel_mission_owner_name"),
        CheckConstraint(
            "status IN ('draft','active','paused','completed','failed')",
            name="ck_intel_mission_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_projects.id", ondelete="CASCADE"),
        index=True,
    )
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_research_profiles.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    frequency: Mapped[str] = mapped_column(String(40), default="manual")
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    market: Mapped[str] = mapped_column(String(120), default="")
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    ruleset_version: Mapped[str] = mapped_column(String(120), default="default-v1")
    minimum_score_threshold: Mapped[float] = mapped_column(Numeric(8, 3), default=0)
    notification_threshold: Mapped[float] = mapped_column(Numeric(8, 3), default=0)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_research_runs.id", ondelete="SET NULL")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceResearchCandidate(Base):
    __tablename__ = "intelligence_research_candidates"
    __table_args__ = (
        UniqueConstraint("owner_id", "deduplication_key", name="uq_intel_candidate_owner_dedup"),
        CheckConstraint(
            "status IN ('discovered','normalized','screening','evaluated','promoted','rejected','duplicate','stale')",
            name="ck_intel_candidate_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_projects.id", ondelete="CASCADE"),
        index=True,
    )
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    external_reference: Mapped[str] = mapped_column(String(300))
    deduplication_key: Mapped[str] = mapped_column(String(512), index=True)
    title: Mapped[str] = mapped_column(String(240))
    normalized_title: Mapped[str] = mapped_column(String(240), index=True)
    category: Mapped[str] = mapped_column(String(120), default="")
    subcategory: Mapped[str] = mapped_column(String(120), default="")
    market: Mapped[str] = mapped_column(String(120), default="")
    observed_brand: Mapped[str | None] = mapped_column(String(160))
    source_reference: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="discovered", index=True)
    observed_price: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_research_candidates.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceResearchSignal(Base):
    __tablename__ = "intelligence_research_signals"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "candidate_id",
            "signal_type",
            "signal_version",
            name="uq_intel_signal_candidate_version",
        ),
        CheckConstraint(
            "signal_type IN ('demand','competition','pricing','trend','reviews','operational_complexity','risk','economics','differentiation','evidence_confidence')",
            name="ck_intel_signal_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    normalized_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    unit: Mapped[str | None] = mapped_column(String(40))
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    freshness: Mapped[str] = mapped_column(String(24), default="unknown")
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    calculation_method: Mapped[str] = mapped_column(String(500))
    signal_version: Mapped[int] = mapped_column(Integer, default=1)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceCompetitorProduct(Base):
    __tablename__ = "intelligence_competitor_products"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "source_id",
            "external_reference",
            name="uq_intel_competitor_owner_source_ref",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    external_reference: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(240))
    brand: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceCompetitorSnapshot(Base):
    __tablename__ = "intelligence_competitor_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "competitor_id", "observed_at", name="uq_intel_competitor_snapshot_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_products.id", ondelete="CASCADE"),
        index=True,
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_evidence.id", ondelete="SET NULL")
    )
    price: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    rating: Mapped[float | None] = mapped_column(Numeric(4, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    features: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceReviewTheme(Base):
    __tablename__ = "intelligence_review_themes"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "candidate_id", "theme_type", "label", name="uq_intel_review_theme_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    theme_type: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(160))
    frequency_count: Mapped[int] = mapped_column(Integer, default=0)
    frequency_ratio: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligencePainPoint(Base):
    __tablename__ = "intelligence_pain_points"
    __table_args__ = (
        UniqueConstraint("owner_id", "candidate_id", "issue", name="uq_intel_pain_point_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    issue: Mapped[str] = mapped_column(String(240))
    frequency: Mapped[float] = mapped_column(Numeric(6, 4))
    frequency_count: Mapped[int] = mapped_column(Integer)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceDifferentiation(Base):
    __tablename__ = "intelligence_differentiations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "candidate_id", "idea", name="uq_intel_differentiation_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    idea: Mapped[str] = mapped_column(String(300))
    classification: Mapped[str] = mapped_column(String(24), default="hypothesis")
    rationale: Mapped[str] = mapped_column(String(500))
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceScoreEvaluation(Base):
    __tablename__ = "intelligence_score_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "candidate_id",
            "scoring_model_version",
            name="uq_intel_score_candidate_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    scoring_model_version: Mapped[str] = mapped_column(String(120))
    weights: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    inputs: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimension_scores: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    weighted_contributions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    score: Mapped[float] = mapped_column(Numeric(8, 3))
    confidence: Mapped[float] = mapped_column(Numeric(5, 4))
    recommendation: Mapped[str] = mapped_column(String(40))
    hard_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    critic_findings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(IntelligenceScoreEvaluation, "before_update")
def _reject_historical_score_update(mapper, connection, target) -> None:
    raise ValueError("Historical score evaluations are immutable.")


class IntelligenceResearchCheckpoint(Base):
    __tablename__ = "intelligence_research_checkpoints"
    __table_args__ = (UniqueConstraint("owner_id", "run_id", name="uq_intel_checkpoint_owner_run"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(80), default="created")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceResearchReport(Base):
    __tablename__ = "intelligence_research_reports"
    __table_args__ = (
        UniqueConstraint("owner_id", "run_id", "format", name="uq_intel_report_owner_run_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    format: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntelligenceTrendObservation(Base):
    """Append-only trend history for a candidate or opportunity."""

    __tablename__ = "intelligence_trend_observations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "candidate_id", "observed_at", name="uq_intel_trend_candidate_observed"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    market: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(120), default="")
    trend_state: Mapped[str] = mapped_column(String(40), default="unknown")
    velocity: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    acceleration: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    seasonality: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)


class IntelligenceEconomicEstimate(Base):
    """Versioned estimate-only economics; never represents supplier-confirmed cost."""

    __tablename__ = "intelligence_economic_estimates"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "candidate_id", "model_version", name="uq_intel_economics_candidate_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(120), default="economics-v1")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    inputs: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    assumption_summary: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IntelligenceResearchSchedule(Base):
    """Durable materialization cursor for recurring local research missions."""

    __tablename__ = "intelligence_research_schedules"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "scheduled_for", name="uq_intel_schedule_mission_due"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_missions.id", ondelete="CASCADE"),
        index=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    frequency: Mapped[str] = mapped_column(String(40), default="manual")
    status: Mapped[str] = mapped_column(String(24), default="materialized", index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_research_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IntelligenceRecoveryRecord(Base):
    """Append-only operator recovery history for research runs."""

    __tablename__ = "intelligence_recovery_records"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "run_id", "idempotency_key", name="uq_intel_recovery_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    failure_classification: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
