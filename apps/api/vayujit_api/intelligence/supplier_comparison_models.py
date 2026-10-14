"""Immutable PR-8B supplier-comparison snapshots.

The snapshot is deliberately a read-only projection of the canonical PR-8A,
PR-5A/B/C, supplier-evidence, and PR-4.2 shortlist authorities.  It is not a
new supplier-ranking or economics authority.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def comparison_now() -> datetime:
    return datetime.now(UTC)


class SupplierComparisonSnapshot(Base):
    """An immutable, owner-scoped comparison of two to five reassessments."""

    __tablename__ = "intelligence_supplier_comparison_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8b_comparison_idempotency"),
        UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr8b_comparison_fingerprint"),
        Index("ix_pr8b_comparison_context", "owner_id", "opportunity_id", "assessment_id"),
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
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="NEEDS_EVIDENCE", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    canonical_supplier_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    supplier_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    supplier_product_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    reassessment_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    quote_versions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    input_fingerprints: Mapped[list[object]] = mapped_column(JSONB, default=list)
    calculation_versions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    suppliers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    metrics: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknowns: Mapped[list[object]] = mapped_column(JSONB, default=list)
    blockers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=comparison_now, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")


@event.listens_for(SupplierComparisonSnapshot, "before_update")
def _reject_comparison_update(
    mapper: Any, connection: Any, target: SupplierComparisonSnapshot
) -> None:
    raise ValueError("Supplier comparison snapshots are immutable.")
