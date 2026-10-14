"""Durable, owner-scoped PR-9A source approval and certification artifacts.

The existing :class:`ExternalSourceProfile` remains the canonical domain
approval authority.  These records add the missing *scoped* approval and
certification evidence needed to prove a single, read-only supplier-source
check for a goal/opportunity without widening that authority.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LiveSupplierSourceApproval(Base):
    """HUMAN, versioned scope layered on the canonical source profile."""

    __tablename__ = "intelligence_live_supplier_source_approvals"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_approval_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_external_source_profiles.id", ondelete="RESTRICT"),
        index=True,
    )
    source_url: Mapped[str] = mapped_column(Text)
    normalized_host: Mapped[str] = mapped_column(String(255), index=True)
    path_scope: Mapped[str] = mapped_column(Text, default="/")
    candidate_category: Mapped[str] = mapped_column(String(64), default="supplier_website")
    operation: Mapped[str] = mapped_column(String(32), default="LIVE_READ_ONLY")
    purpose: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(24), default="APPROVED", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LiveSupplierCertificationRun(Base):
    """Durable certification run and gate ledger (never a supplier contact)."""

    __tablename__ = "intelligence_live_supplier_certification_runs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "fingerprint", name="uq_live_supplier_certification_fingerprint"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_source_approvals.id", ondelete="RESTRICT"),
        index=True,
    )
    source_url: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(64), default="approved_web_fetch")
    mode: Mapped[str] = mapped_column(String(32), default="LIVE_READ_ONLY")
    policy_version: Mapped[str] = mapped_column(String(80), default="pr9a-live-supplier-v1")
    requested_checks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    executed_checks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    gate_outcomes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, default=list)
    blockers: Mapped[list[str]] = mapped_column(JSONB, default=list)
    external_read_count: Mapped[int] = mapped_column(Integer, default=0)
    external_write_count: Mapped[int] = mapped_column(Integer, default=0)
    fetch_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="NOT_EXECUTED", index=True)
    trust_classification: Mapped[str] = mapped_column(String(48), default="UNKNOWN")
    supplier_correlation: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    product_classification: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(120), index=True)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LiveSupplierCertificationExecution(Base):
    """Immutable fetch attempt metadata and evidence lineage."""

    __tablename__ = "intelligence_live_supplier_certification_executions"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_execution_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_certification_runs.id", ondelete="CASCADE"),
        index=True,
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_source_approvals.id", ondelete="RESTRICT"),
        index=True,
    )
    external_fetch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_external_fetches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    redirect_chain: Mapped[list[str]] = mapped_column(JSONB, default=list)
    provider: Mapped[str] = mapped_column(String(64), default="approved_web_fetch")
    mode: Mapped[str] = mapped_column(String(32), default="LIVE_READ_ONLY")
    status: Mapped[str] = mapped_column(String(24), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extracted: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    trust_classification: Mapped[str] = mapped_column(String(48), default="FETCHED_SOURCE")
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LiveSupplierExecutionAuthorization(Base):
    """Separate, durable HUMAN authorization for one live read.

    Source approval and execution authorization are intentionally different
    records.  The row is consumed under a database lock, making the
    single-use boundary survive retries and concurrent requests.
    """

    __tablename__ = "intelligence_live_supplier_execution_authorizations"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_exec_auth_fingerprint"),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_live_supplier_exec_auth_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_source_approvals.id", ondelete="RESTRICT"),
        index=True,
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(Text)
    normalized_host: Mapped[str] = mapped_column(String(255), index=True)
    path_scope: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(64), default="approved_web_fetch")
    mode: Mapped[str] = mapped_column(String(32), default="LIVE_READ_ONLY")
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_provenance: Mapped[str] = mapped_column(String(16), default="HUMAN")
    approval_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    max_requests: Mapped[int] = mapped_column(Integer, default=1)
    used_requests: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_certification_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LiveSupplierEvidenceReview(Base):
    """Append-only HUMAN review events for one immutable evidence snapshot."""

    __tablename__ = "intelligence_live_supplier_evidence_reviews"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "fingerprint", name="uq_live_supplier_evidence_review_fingerprint"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_certification_executions.id", ondelete="CASCADE"),
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_live_supplier_certification_runs.id", ondelete="CASCADE"),
        index=True,
    )
    evidence_hash: Mapped[str] = mapped_column(String(128), default="")
    evidence_version: Mapped[int] = mapped_column(Integer, default=1)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_provenance: Mapped[str] = mapped_column(String(16), default="HUMAN")
    rationale: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
