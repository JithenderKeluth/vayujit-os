"""Assessment-bound commercial viability projections (Slice 9C)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CALCULATION_VERSION = "product-opportunity-commercial-v1"


def commercial_now() -> datetime:
    return datetime.now(UTC)


class ProductOpportunityCommercialOutput(Base):
    """Immutable commercial projection tied to one Product Opportunity assessment."""

    __tablename__ = "intelligence_product_opportunity_commercial_outputs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "assessment_id",
            name="uq_product_opportunity_commercial_assessment",
        ),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_product_opportunity_commercial_idempotency",
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
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    constraint_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    economics: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    sensitivity: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    research_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=commercial_now, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
