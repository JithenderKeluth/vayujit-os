"""Durable PR-5A commercial evidence/readiness projections.

This is a read-model over the existing supplier evidence and term authorities.
It deliberately stores no calculated landed cost, margin, or profitability.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def readiness_now() -> datetime:
    return datetime.now(UTC)


class CommercialReadinessSnapshot(Base):
    __tablename__ = "intelligence_commercial_readiness_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_commercial_readiness_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
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
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scenario_key: Mapped[str] = mapped_column(String(120), default="source-evidence")
    readiness: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    known_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    claims: Mapped[list[object]] = mapped_column(JSONB, default=list)
    assumptions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknown_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    missing_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    optional_gaps: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=readiness_now)
