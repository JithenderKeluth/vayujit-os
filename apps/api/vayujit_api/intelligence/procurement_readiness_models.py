"""Immutable PR-8C procurement-readiness assessment snapshots.

PR-8C is a read-only synthesis boundary.  It references the existing supplier,
shortlist, due-diligence, commercial, economics, reassessment, and comparison
authorities; it does not replace any of them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def procurement_now() -> datetime:
    return datetime.now(UTC)


class SupplierProcurementReadinessAssessment(Base):
    """Append-only, owner-scoped evidence synthesis for one supplier context."""

    __tablename__ = "intelligence_supplier_procurement_readiness_assessments"
    __table_args__ = (
        UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr8c_assessment_fingerprint"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8c_assessment_idempotency"),
        Index("ix_pr8c_assessment_context", "owner_id", "opportunity_id", "assessment_id"),
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
    canonical_supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="RESTRICT"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shortlist_context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shortlist_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_versions.id", ondelete="SET NULL"),
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
    commercial_readiness_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_readiness_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reassessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_reassessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_comparison_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="NEEDS_EVIDENCE", index=True)
    policy_version: Mapped[str] = mapped_column(String(80), default="pr8c-readiness-v1")
    calculation_versions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    blockers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknowns: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    evidence_lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_provenance: Mapped[str] = mapped_column(String(16), default="HUMAN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=procurement_now)
    notes: Mapped[str] = mapped_column(Text, default="")


@event.listens_for(SupplierProcurementReadinessAssessment, "before_update")
def _reject_assessment_update(mapper: Any, connection: Any, target: Any) -> None:
    raise ValueError("Procurement-readiness assessments are immutable.")


class SupplierProcurementReadinessAcknowledgement(Base):
    """Append-only HUMAN review acknowledgement; never an approval or offer acceptance."""

    __tablename__ = "intelligence_supplier_procurement_readiness_acknowledgements"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8c_ack_idempotency"),
        Index("ix_pr8c_ack_assessment", "owner_id", "assessment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "intelligence_supplier_procurement_readiness_assessments.id", ondelete="CASCADE"
        ),
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(32))
    provenance: Mapped[str] = mapped_column(String(16), default="HUMAN")
    reason: Mapped[str] = mapped_column(Text, default="")
    assessment_fingerprint: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=procurement_now)
    idempotency_key: Mapped[str] = mapped_column(String(220))
