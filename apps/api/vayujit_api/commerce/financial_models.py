"""Owner-scoped financial evidence and deterministic calculation snapshots.

These tables are an additive projection over the canonical marketplace order,
fee, refund and settlement authorities.  Financial events are immutable input
facts; calculations are versioned snapshots and never overwrite the source
lineage.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class FinancialEvent(Base):
    __tablename__ = "financial_events"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "account_id", "source_event_id", name="uq_financial_event_source"
        ),
        CheckConstraint(
            "event_type IN ("
            "'sale','discount','fee','shipping','fulfilment','refund','tax','settlement','adjustment')",
            name="ck_financial_event_type",
        ),
        CheckConstraint(
            "evidence_status IN ('modeled','observed','reported','verified','unknown')",
            name="ck_financial_event_evidence",
        ),
        CheckConstraint("amount >= 0", name="ck_financial_event_amount"),
        Index("ix_financial_event_owner_effective", "owner_id", "effective_at"),
        Index("ix_financial_event_owner_order", "owner_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_settlements.id", ondelete="SET NULL"),
        index=True,
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    source_event_id: Mapped[str] = mapped_column(String(240))
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    evidence_status: Mapped[str] = mapped_column(String(20), default="modeled")
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic_fixture")
    source_reference: Mapped[str | None] = mapped_column(String(500))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    calculation_version: Mapped[str] = mapped_column(String(40), default="pr-sos-05-v1")
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinancialCostEvidence(Base):
    __tablename__ = "financial_cost_evidence"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "cost_key", "effective_from", name="uq_financial_cost_version"
        ),
        CheckConstraint("amount >= 0", name="ck_financial_cost_amount"),
        CheckConstraint(
            "evidence_status IN ('modeled','observed','reported','verified','unknown')",
            name="ck_financial_cost_evidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    marketplace: Mapped[str | None] = mapped_column(String(30), index=True)
    sku: Mapped[str | None] = mapped_column(String(160), index=True)
    cost_key: Mapped[str] = mapped_column(String(220))
    cost_type: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    evidence_status: Mapped[str] = mapped_column(String(20), default="modeled")
    source_type: Mapped[str] = mapped_column(String(40), default="seller_entered")
    source_reference: Mapped[str | None] = mapped_column(String(500))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinancialFeeRule(Base):
    __tablename__ = "financial_fee_rules"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "rule_key", "effective_from", name="uq_financial_fee_rule_version"
        ),
        CheckConstraint("rate_percent >= 0", name="ck_financial_fee_rule_rate"),
        CheckConstraint("fixed_amount >= 0", name="ck_financial_fee_rule_fixed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    category: Mapped[str | None] = mapped_column(String(240))
    rule_key: Mapped[str] = mapped_column(String(220))
    fee_type: Mapped[str] = mapped_column(String(40))
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"))
    fixed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic_fixture")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[str] = mapped_column(String(40), default="pr-sos-05-v1")
    assumptions_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinancialCalculationSnapshot(Base):
    __tablename__ = "financial_calculation_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "scope_key",
            "calculation_version",
            name="uq_financial_snapshot_scope_version",
        ),
        CheckConstraint(
            "evidence_status IN ('modeled','observed','reported','verified','unknown','partial')",
            name="ck_financial_snapshot_evidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope_key: Mapped[str] = mapped_column(String(240))
    scope_type: Mapped[str] = mapped_column(String(40))
    marketplace: Mapped[str | None] = mapped_column(String(30), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="SET NULL"), index=True
    )
    calculation_version: Mapped[str] = mapped_column(String(40))
    evidence_status: Mapped[str] = mapped_column(String(20), default="partial")
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    missing_inputs_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    lineage_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinancialSettlementReconciliation(Base):
    __tablename__ = "financial_settlement_reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "settlement_key", name="uq_financial_settlement_reconciliation"
        ),
        CheckConstraint(
            "status IN ('matched','mismatch','missing_evidence','unknown')",
            name="ck_financial_reconciliation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_settlements.id", ondelete="SET NULL"),
        index=True,
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    settlement_key: Mapped[str] = mapped_column(String(240))
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reported_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    verified_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    difference_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(24), default="unknown")
    evidence_status: Mapped[str] = mapped_column(String(20), default="unknown")
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    calculation_version: Mapped[str] = mapped_column(String(40), default="pr-sos-05-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
