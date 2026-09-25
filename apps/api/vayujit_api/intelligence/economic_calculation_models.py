"""Immutable deterministic landed-cost calculation persistence (13B)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CALCULATION_STATUSES = ("COMPLETE", "PARTIAL", "INSUFFICIENT")
INCLUSION_STATUSES = ("INCLUDED", "EXCLUDED")


class EconomicCalculation(Base):
    __tablename__ = "intelligence_economic_calculations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "calculation_fingerprint", name="uq_economic_calculation_fingerprint"
        ),
        CheckConstraint(
            "status IN ('COMPLETE','PARTIAL','INSUFFICIENT')",
            name="ck_economic_calculation_status",
        ),
        CheckConstraint("total_included_cost >= 0", name="ck_economic_calculation_total"),
        CheckConstraint(
            "per_unit_cost IS NULL OR per_unit_cost >= 0", name="ck_economic_calculation_per_unit"
        ),
        CheckConstraint(
            "target_quantity IS NULL OR target_quantity > 0",
            name="ck_economic_calculation_quantity",
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_economic_calculation_currency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_input_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    fx_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_fx_rate_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    freight_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_freight_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    customs_tax_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_customs_tax_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    calculation_version: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(64))
    calculation_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reporting_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    target_quantity: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    total_included_cost: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    per_unit_cost: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    included_component_count: Mapped[int] = mapped_column(Integer, default=0)
    excluded_component_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    assumptions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    stale_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    explanation: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicCalculationBreakdown(Base):
    __tablename__ = "intelligence_economic_calculation_breakdowns"
    __table_args__ = (
        UniqueConstraint("calculation_id", "line_order", name="uq_economic_calculation_line"),
        CheckConstraint(
            "inclusion_status IN ('INCLUDED','EXCLUDED')", name="ck_economic_breakdown_inclusion"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    category: Mapped[str] = mapped_column(String(32))
    original_amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    multiplier: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    included_amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    converted_amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    fx_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    fx_pair: Mapped[str | None] = mapped_column(String(7), nullable=True)
    fx_rate: Mapped[float | None] = mapped_column(Numeric(30, 16), nullable=True)
    fx_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fx_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fx_freshness: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fx_inverted: Mapped[bool | None] = mapped_column(nullable=True)
    freight_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    customs_tax_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    provenance: Mapped[str] = mapped_column(String(16))
    freshness: Mapped[str] = mapped_column(String(16))
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inclusion_status: Mapped[str] = mapped_column(String(16))
    exclusion_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    line_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
