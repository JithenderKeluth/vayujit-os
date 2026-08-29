# ruff: noqa: E501,UP017
"""Durable, owner-scoped models for autonomous research orchestration."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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

AUTONOMOUS_MISSION_TYPES = (
    "PRODUCT_DISCOVERY",
    "PRODUCT_VALIDATION",
    "TREND_RESEARCH",
    "COMPETITOR_RESEARCH",
    "REVIEW_RESEARCH",
    "SUPPLIER_DISCOVERY",
    "SUPPLIER_VERIFICATION",
    "PRICING_RESEARCH",
    "ECONOMICS_RESEARCH",
    "RISK_RESEARCH",
    "SOURCE_REFRESH",
    "FULL_OPPORTUNITY_RESEARCH",
    "MANUFACTURER_RESEARCH",
    "SUPPLIER_WEBSITE_RESEARCH",
)
AUTONOMOUS_MISSION_STATUSES = (
    "DRAFT",
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "COMPLETED_WITH_WARNINGS",
    "PARTIAL",
    "FAILED",
    "PAUSED",
    "CANCELLED",
    "REQUIRES_REVIEW",
    "STALE",
)
AUTONOMOUS_TASK_STATUSES = (
    "QUEUED",
    "WAITING_DEPENDENCY",
    "RUNNING",
    "CHECKPOINTED",
    "COMPLETED",
    "FAILED",
    "RETRY_WAIT",
    "CANCELLED",
    "STALE",
    "SKIPPED",
)
EVIDENCE_VERIFICATION_STATUSES = (
    "VERIFIED",
    "SUPPORTED",
    "PARTIAL",
    "CONFLICTING",
    "STALE",
    "UNVERIFIED",
    "REJECTED",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutonomousResearchMission(Base):
    __tablename__ = "intelligence_autonomous_missions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_autonomous_mission_owner_idempotency"
        ),
        CheckConstraint(
            "mission_type IN (" + ",".join(repr(v) for v in AUTONOMOUS_MISSION_TYPES) + ")",
            name="ck_autonomous_mission_type",
        ),
        CheckConstraint(
            "status IN (" + ",".join(repr(v) for v in AUTONOMOUS_MISSION_STATUSES) + ")",
            name="ck_autonomous_mission_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_type: Mapped[str] = mapped_column(String(40), index=True)
    goal: Mapped[str] = mapped_column(Text)
    scope: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    market: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(120), default="")
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    research_profile: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    ruleset: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_policy: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    budget_policy: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provider_mode: Mapped[str] = mapped_column(String(32), default="LOCAL_DETERMINISTIC")
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    unknown_ratio: Mapped[float] = mapped_column(Numeric(6, 4), default=1)
    required_confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0.7)
    max_tasks: Mapped[int] = mapped_column(Integer, default=20)
    max_provider_calls: Mapped[int] = mapped_column(Integer, default=20)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    max_elapsed_seconds: Mapped[int] = mapped_column(Integer, default=300)
    frequency: Mapped[str] = mapped_column(String(32), default="manual")
    catch_up_policy: Mapped[str] = mapped_column(String(24), default="SKIP")
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AutonomousResearchTask(Base):
    __tablename__ = "intelligence_autonomous_tasks"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "idempotency_key", name="uq_autonomous_task_identity"
        ),
        CheckConstraint(
            "status IN (" + ",".join(repr(v) for v in AUTONOMOUS_TASK_STATUSES) + ")",
            name="ck_autonomous_task_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    dependency_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_class: Mapped[str] = mapped_column(String(64), default="INTERNAL")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_projection: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AutonomousResearchAttempt(Base):
    __tablename__ = "intelligence_autonomous_attempts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "task_id", "attempt_number", name="uq_autonomous_attempt_identity"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    checkpoint: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutonomousResearchEvidence(Base):
    __tablename__ = "intelligence_autonomous_evidence"
    __table_args__ = (
        UniqueConstraint("owner_id", "retrieval_identity", name="uq_autonomous_evidence_retrieval"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    source_class: Mapped[str] = mapped_column(String(64), index=True)
    source_reference: Mapped[str] = mapped_column(String(500))
    retrieval_identity: Mapped[str] = mapped_column(String(500), index=True)
    content_type: Mapped[str] = mapped_column(String(120), default="application/json")
    normalized_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED", index=True)
    freshness_status: Mapped[str] = mapped_column(String(32), default="FRESH", index=True)
    fresh_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_at_verification: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    evidence_class: Mapped[str] = mapped_column(String(64), default="GENERAL")
    is_untrusted_external_data: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class AutonomousResearchClaim(Base):
    __tablename__ = "intelligence_autonomous_claims"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AutonomousResearchContradiction(Base):
    __tablename__ = "intelligence_autonomous_contradictions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "identity_key", name="uq_autonomous_contradiction_identity"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    identity_key: Mapped[str] = mapped_column(String(300))
    contradiction_type: Mapped[str] = mapped_column(String(64), index=True)
    evidence_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_autonomous_evidence.id", ondelete="CASCADE")
    )
    evidence_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_autonomous_evidence.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32), default="UNRESOLVED", index=True)
    resolution_strategy: Mapped[str | None] = mapped_column(String(64))
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    claim_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence_a_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_b_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_a: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_b: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    freshness_a: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_b: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_a: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_b: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_a: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    confidence_b: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutonomousResearchChange(Base):
    __tablename__ = "intelligence_autonomous_changes"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "identity_key", name="uq_autonomous_change_identity"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), default="external_claim", index=True)
    entity_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    field_key: Mapped[str] = mapped_column(String(120), default="")
    identity_key: Mapped[str] = mapped_column(String(300), index=True)
    previous_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    current_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    delta: Mapped[float | None] = mapped_column(Numeric(12, 4))
    material: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    materiality: Mapped[str] = mapped_column(String(24), default="NON_MATERIAL", index=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    correlation_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AutonomousResearchSchedule(Base):
    __tablename__ = "intelligence_autonomous_schedules"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "scheduled_for", name="uq_autonomous_schedule_identity"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    frequency: Mapped[str] = mapped_column(String(32), default="manual")
    catch_up_policy: Mapped[str] = mapped_column(String(24), default="SKIP")
    status: Mapped[str] = mapped_column(String(32), default="SCHEDULED", index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    materialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutonomousResearchRecovery(Base):
    __tablename__ = "intelligence_autonomous_recovery"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "idempotency_key", name="uq_autonomous_recovery_identity"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    failure_code: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    safe_reason_code: Mapped[str] = mapped_column(String(120), default="AUTONOMOUS_RECOVERY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AutonomousResearchAlert(Base):
    __tablename__ = "intelligence_autonomous_alerts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "mission_id", "identity_key", name="uq_autonomous_alert_identity"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(24), default="REQUIRES_REVIEW")
    title: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str] = mapped_column(String(500), default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    identity_key: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class AutonomousResearchReport(Base):
    __tablename__ = "intelligence_autonomous_reports"
    __table_args__ = (
        UniqueConstraint("owner_id", "mission_id", "format", name="uq_autonomous_report_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    format: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
