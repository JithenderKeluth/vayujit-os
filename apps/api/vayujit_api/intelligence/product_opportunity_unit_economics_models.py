"""Immutable PR-5C unit-economics and capital-fit projections."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CALCULATION_VERSION = "unit-economics-capital-fit-v1"


def unit_economics_now() -> datetime:
    return datetime.now(UTC)


class ProductOpportunityUnitEconomics(Base):
    """One immutable, owner-scoped PR-5C result.

    The existing PR-5A commercial projection remains the readiness authority and
    PR-5B ``EconomicCalculation`` remains the landed-acquisition authority. This
    table only stores the derived selling-side and capital-fit result, including
    the exact immutable input snapshot used to produce it.
    """

    __tablename__ = "intelligence_product_opportunity_unit_economics"
    __table_args__ = (
        Index(
            "ix_pr5c_unit_economics_context",
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "created_at",
        ),
        Index("ix_pr5c_unit_economics_fingerprint", "owner_id", "input_fingerprint"),
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
    )
    landed_cost_calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
        index=True,
    )
    commercial_readiness_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_readiness_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    scenario_key: Mapped[str] = mapped_column(String(120), default="seller-scenario")
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    calculation_revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="READY", index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), index=True)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    readiness: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    selling_price: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    selling_price_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    selling_price_provenance: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    quantity: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    selling_cost_components: Mapped[list[object]] = mapped_column(JSONB, default=list)
    per_unit_landed_cost: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    per_unit_selling_cost: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    per_unit_total_cost: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    per_unit_contribution: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    contribution_margin: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    order_economics: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    capital_available: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    capital_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    capital_required: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    capital_headroom: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    capital_shortfall: Mapped[object | None] = mapped_column(Numeric(24, 8), nullable=True)
    capital_fit_status: Mapped[str] = mapped_column(String(24), default="NEEDS_INPUT")
    unknown_excluded: Mapped[list[object]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[object]] = mapped_column(JSONB, default=list)
    explanation: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=unit_economics_now, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
