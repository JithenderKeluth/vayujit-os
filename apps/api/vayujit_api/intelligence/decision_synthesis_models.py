"""Immutable PR-6B explainable decision synthesis snapshots."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

SYNTHESIS_POSTURES = (
    "CONTINUE_RESEARCH",
    "HOLD",
    "READY_FOR_HUMAN_DECISION",
    "CONSTRAINT_FAILED",
)
SYNTHESIS_POLICY_VERSION = "decision-synthesis-v1"


def decision_synthesis_now() -> datetime:
    return datetime.now(UTC)


class DecisionSynthesisSnapshot(Base):
    """Append-only explainable synthesis of one immutable PR-6A snapshot.

    This table stores a deterministic projection. PR-6A remains the authority
    for readiness, blockers, trust, and evidence; no recommendation is stored.
    """

    __tablename__ = "intelligence_decision_synthesis_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "input_fingerprint", name="uq_decision_synthesis_fingerprint"),
        Index(
            "ix_decision_synthesis_context",
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
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_evidence_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_decision_evidence_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    decision_target: Mapped[str] = mapped_column(String(40), index=True)
    readiness_state: Mapped[str] = mapped_column(String(24), index=True)
    readiness_policy_version: Mapped[str] = mapped_column(String(80))
    synthesis_policy_version: Mapped[str] = mapped_column(String(80))
    posture: Mapped[str] = mapped_column(String(40), index=True)
    primary_reason: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    reasons: Mapped[list[object]] = mapped_column(JSONB, default=list)
    supporting_evidence: Mapped[list[object]] = mapped_column(JSONB, default=list)
    blockers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknowns: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[object]] = mapped_column(JSONB, default=list)
    trust_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    economics_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    capital_fit_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    safe_next_actions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    human_review_required: Mapped[bool] = mapped_column(default=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=decision_synthesis_now
    )
    explanation: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
