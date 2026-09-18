"""Assessment-bound demand and competition intelligence outputs (Slice 9B)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

INTELLIGENCE_KINDS = ("demand", "competition")
CALCULATION_VERSION = "product-opportunity-intelligence-v1"


def intelligence_now() -> datetime:
    return datetime.now(UTC)


class ProductOpportunityIntelligenceOutput(Base):
    """Immutable derived intelligence tied to exactly one assessment version."""

    __tablename__ = "intelligence_product_opportunity_outputs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "assessment_id",
            "kind",
            name="uq_product_opportunity_output_assessment_kind",
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_output_idempotency"
        ),
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
    kind: Mapped[str] = mapped_column(String(24), index=True)
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    research_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=intelligence_now, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
