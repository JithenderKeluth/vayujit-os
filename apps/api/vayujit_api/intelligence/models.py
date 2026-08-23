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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

PROJECT_STATUSES = ("draft", "active", "paused", "completed", "archived")
RUN_STATUSES = ("pending", "running", "waiting", "completed", "failed", "cancelled", "stale")
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
        CheckConstraint(
            "status IN (" + ",".join(f"'{item}'" for item in OPPORTUNITY_STATUSES) + ")",
            name="ck_intelligence_opportunity_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
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
