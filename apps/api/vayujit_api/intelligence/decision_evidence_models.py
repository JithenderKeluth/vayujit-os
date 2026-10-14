"""Immutable target-specific decision evidence and readiness snapshots (PR-6A)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

DECISION_TARGETS = (
    "PRODUCT_SELECTION",
    "SUPPLIER_SELECTION",
    "COMMERCIAL_ASSESSMENT",
    "LAUNCH_DECISION",
)
READINESS_STATES = ("READY", "NEEDS_EVIDENCE", "BLOCKED")
DECISION_POLICY_VERSION = "decision-readiness-v1"


def decision_evidence_now() -> datetime:
    return datetime.now(UTC)


class DecisionEvidenceSnapshot(Base):
    """Historical, append-only evidence state for one decision target.

    Domain authorities remain the source of truth. JSON fields are a compact
    immutable view of their IDs and decision-relevant evidence, not a copy of
    those authorities and never a recommendation.
    """

    __tablename__ = "intelligence_decision_evidence_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "input_fingerprint", name="uq_decision_evidence_fingerprint"),
        Index(
            "ix_decision_evidence_context",
            "owner_id",
            "opportunity_id",
            "decision_target",
            "created_at",
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
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    product_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shortlist_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    due_diligence_context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    due_diligence_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_due_diligence_assessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    commercial_readiness_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_readiness_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    landed_cost_calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    unit_economics_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_unit_economics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_target: Mapped[str] = mapped_column(String(40), index=True)
    decision_version: Mapped[int] = mapped_column(Integer, default=1)
    policy_version: Mapped[str] = mapped_column(String(80))
    input_references: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    trust_environment: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    blockers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknowns: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[object]] = mapped_column(JSONB, default=list)
    freshness_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    readiness_state: Mapped[str] = mapped_column(String(24), index=True)
    safe_next_action: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=decision_evidence_now
    )
    notes: Mapped[str] = mapped_column(Text, default="")
