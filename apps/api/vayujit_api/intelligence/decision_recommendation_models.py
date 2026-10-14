"""PR-6C immutable recommendation assessments and human decisions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

RECOMMENDATION_POLICY_VERSION = "decision-recommendation-v1"
RECOMMENDATION_STATES = (
    "NOT_ELIGIBLE",
    "READY_FOR_REVIEW",
    "SYSTEM_SUPPORTS_PROCEEDING",
    "SYSTEM_SUPPORTS_NOT_PROCEEDING",
)
HUMAN_DECISIONS = ("PROCEED", "KEEP_UNDER_REVIEW", "DO_NOT_PROCEED")


def recommendation_now() -> datetime:
    return datetime.now(UTC)


class RecommendationAssessment(Base):
    """Append-only, advisory assessment derived from one PR-6B snapshot."""

    __tablename__ = "intelligence_recommendation_assessments"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "input_fingerprint", name="uq_recommendation_assessment_fingerprint"
        ),
        Index(
            "ix_recommendation_assessment_context",
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
    synthesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_decision_synthesis_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    decision_target: Mapped[str] = mapped_column(String(40), index=True)
    recommendation_policy_version: Mapped[str] = mapped_column(String(80))
    recommendation_state: Mapped[str] = mapped_column(String(48), index=True)
    supporting_reasons: Mapped[list[object]] = mapped_column(JSONB, default=list)
    counter_reasons: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknowns: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[object]] = mapped_column(JSONB, default=list)
    trust_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    economics_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    capital_fit_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    human_review_required: Mapped[bool] = mapped_column(default=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=recommendation_now
    )
    explanation: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class HumanDecision(Base):
    """Append-only explicit human decision with recommendation context."""

    __tablename__ = "intelligence_human_decisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_human_decision_idempotency"),
        Index(
            "ix_human_decision_context",
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
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
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
    synthesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_decision_synthesis_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_recommendation_assessments.id", ondelete="RESTRICT"),
        index=True,
    )
    supersedes_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_human_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_target: Mapped[str] = mapped_column(String(40), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[str] = mapped_column(String(24), default="HUMAN")
    context_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=recommendation_now
    )
    external_writes: Mapped[list[object]] = mapped_column(JSONB, default=list)
