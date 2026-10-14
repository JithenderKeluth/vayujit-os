"""PR-8A immutable, owner-scoped commercial reassessments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def reassessment_now() -> datetime:
    return datetime.now(UTC)


class CommercialReassessment(Base):
    """One immutable comparison between a historical scenario and a reviewed quote."""

    __tablename__ = "intelligence_commercial_reassessments"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8a_reassessment_idempotency"),
        UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr8a_reassessment_fingerprint"),
        Index("ix_pr8a_reassessment_context", "owner_id", "opportunity_id", "assessment_id"),
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
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="RESTRICT"), index=True
    )
    supplier_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_products.id", ondelete="RESTRICT"),
        index=True,
    )
    promotion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_response_promotions.id", ondelete="RESTRICT"),
        index=True,
    )
    commercial_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_commercial_terms.id", ondelete="RESTRICT"),
        index=True,
    )
    baseline_landed_cost_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="SET NULL"),
        nullable=True,
    )
    baseline_unit_economics_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_unit_economics.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_readiness_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_readiness_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_landed_cost_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_unit_economics_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_unit_economics.id", ondelete="SET NULL"),
        nullable=True,
    )
    scenario_key: Mapped[str] = mapped_column(String(120), default="reviewed-quote-reassessment")
    status: Mapped[str] = mapped_column(String(32), default="BLOCKED", index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="NEEDS_HUMAN_REVIEW")
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    quote_version: Mapped[int] = mapped_column()
    quote_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    assumptions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    baseline: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    current: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    comparison: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    blockers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=reassessment_now, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")


class CommercialReassessmentReview(Base):
    """Explicit HUMAN acknowledgement/retention of a reassessment."""

    __tablename__ = "intelligence_commercial_reassessment_reviews"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8a_review_idempotency"),
        Index("ix_pr8a_review_reassessment", "owner_id", "reassessment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reassessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_reassessments.id", ondelete="CASCADE"),
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(32))
    provenance: Mapped[str] = mapped_column(String(16), default="HUMAN")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=reassessment_now)
    idempotency_key: Mapped[str] = mapped_column(String(220))
