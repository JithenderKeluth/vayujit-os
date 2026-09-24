"""Calculation-ready sourcing economics inputs (13A).

This module intentionally stores inputs and their provenance only.  It does
not calculate landed cost, convert currencies, or rank sourcing options.
"""

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

PROVENANCE_CLASSES = ("OBSERVED", "QUOTED", "CONFIGURED", "ASSUMED", "CALCULATED", "UNKNOWN")
FRESHNESS_STATES = ("CURRENT", "STALE", "UNKNOWN")
CONTEXT_STATUSES = ("DRAFT", "CURRENT", "ARCHIVED")
COMPLETENESS_STATES = ("COMPLETE", "PARTIAL", "INSUFFICIENT", "UNKNOWN")
COST_COMPONENT_CATEGORIES = (
    "PRODUCT_COST",
    "PACKAGING",
    "SAMPLE",
    "TOOLING",
    "INSPECTION",
    "FREIGHT",
    "INSURANCE",
    "CUSTOMS_DUTY",
    "IMPORT_TAX",
    "BROKERAGE",
    "PORT_HANDLING",
    "LOCAL_TRANSPORT",
    "WAREHOUSING",
    "FULFILMENT",
    "MARKETPLACE_FEE",
    "OTHER",
)


class EconomicContext(Base):
    __tablename__ = "intelligence_economic_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_economic_context_idempotency"),
        CheckConstraint(
            "status IN ('DRAFT','CURRENT','ARCHIVED')", name="ck_economic_context_status"
        ),
        CheckConstraint("version > 0", name="ck_economic_context_version"),
        CheckConstraint(
            "base_currency IS NULL OR base_currency ~ '^[A-Z]{3}$'",
            name="ck_economic_context_currency",
        ),
        CheckConstraint(
            "target_quantity IS NULL OR target_quantity > 0", name="ck_economic_context_quantity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_suppliers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_scenarios.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source_marketplace: Mapped[str | None] = mapped_column(String(120), nullable=True)
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_channel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_quantity: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicQuoteInput(Base):
    __tablename__ = "intelligence_economic_quote_inputs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_economic_quote_idempotency"),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_economic_quote_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_economic_quote_freshness"
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_economic_quote_currency"
        ),
        CheckConstraint(
            "unit_price IS NULL OR currency IS NOT NULL", name="ck_economic_quote_money_currency"
        ),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0", name="ck_economic_quote_unit_price"
        ),
        CheckConstraint("moq IS NULL OR moq > 0", name="ck_economic_quote_moq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_suppliers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quote_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    unit_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    moq: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    moq_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quoted_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quote_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[str] = mapped_column(String(16), default="QUOTED")
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicCostComponent(Base):
    __tablename__ = "intelligence_economic_cost_components"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "fingerprint", name="uq_economic_component_fingerprint"
        ),
        CheckConstraint(
            "category IN (" + ",".join(f"'{value}'" for value in COST_COMPONENT_CATEGORIES) + ")",
            name="ck_economic_component_category",
        ),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_economic_component_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_economic_component_freshness"
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_economic_component_currency"
        ),
        CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_economic_component_money_currency"
        ),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_economic_component_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    quote_input_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_quote_inputs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    quantity_basis: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    unit_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provenance: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicAssumption(Base):
    __tablename__ = "intelligence_economic_assumptions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "key", "version", name="uq_economic_assumption_version"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicInputSnapshot(Base):
    __tablename__ = "intelligence_economic_input_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "fingerprint", name="uq_economic_snapshot_fingerprint"
        ),
        UniqueConstraint("owner_id", "context_id", "version", name="uq_economic_snapshot_version"),
        CheckConstraint(
            "completeness IN ('COMPLETE','PARTIAL','INSUFFICIENT','UNKNOWN')",
            name="ck_economic_snapshot_completeness",
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
    version: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    completeness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    missing_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicSnapshotComponent(Base):
    __tablename__ = "intelligence_economic_snapshot_components"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "component_id", name="uq_economic_snapshot_component"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_input_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_cost_components.id", ondelete="RESTRICT"),
        index=True,
    )
