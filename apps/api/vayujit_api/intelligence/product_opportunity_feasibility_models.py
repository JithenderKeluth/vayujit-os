"""Immutable Product Opportunity supplier and sourcing feasibility projections."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CALCULATION_VERSION = "product-opportunity-sourcing-feasibility-v1"


def feasibility_now() -> datetime:
    return datetime.now(UTC)


class ProductOpportunitySourcingFeasibilityOutput(Base):
    """Assessment-bound projection; upstream supplier records remain authoritative."""

    __tablename__ = "intelligence_product_opportunity_sourcing_feasibility_outputs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "assessment_id", name="uq_product_opportunity_feasibility_assessment"
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_feasibility_idempotency"
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
    calculation_version: Mapped[str] = mapped_column(String(120))
    constraint_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    upstream_lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    candidates: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    dimensions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    evidence_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    research_gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=feasibility_now)
    notes: Mapped[str] = mapped_column(Text, default="")
