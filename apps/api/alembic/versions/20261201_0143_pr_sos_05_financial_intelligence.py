"""Additive PR-SOS-05 financial evidence projections."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261201_0143"
down_revision = "20261130_0142"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB()


def _common(table: str) -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "financial_events",
        *_common("financial_events"),
        sa.Column(
            "account_id",
            UUID,
            sa.ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_id", UUID, sa.ForeignKey("marketplace_orders.id", ondelete="SET NULL")),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column(
            "settlement_id", UUID, sa.ForeignKey("marketplace_settlements.id", ondelete="SET NULL")
        ),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("source_event_id", sa.String(240), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("evidence_status", sa.String(20), nullable=False, server_default="modeled"),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="synthetic_fixture"),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "calculation_version", sa.String(40), nullable=False, server_default="pr-sos-05-v1"
        ),
        sa.Column("provenance_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("payload_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint(
            "owner_id", "account_id", "source_event_id", name="uq_financial_event_source"
        ),
        sa.CheckConstraint("amount >= 0", name="ck_financial_event_amount"),
        sa.CheckConstraint(
            "event_type IN ("
            "'sale','discount','fee','shipping','fulfilment','refund','tax',"
            "'settlement','adjustment')",
            name="ck_financial_event_type",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('modeled','observed','reported','verified','unknown')",
            name="ck_financial_event_evidence",
        ),
    )
    op.create_index(
        "ix_financial_event_owner_effective", "financial_events", ["owner_id", "effective_at"]
    )
    op.create_index("ix_financial_event_owner_order", "financial_events", ["owner_id", "order_id"])
    op.create_index("ix_financial_events_owner_id", "financial_events", ["owner_id"])
    op.create_index("ix_financial_events_account_id", "financial_events", ["account_id"])
    op.create_index("ix_financial_events_product_id", "financial_events", ["product_id"])
    op.create_index("ix_financial_events_settlement_id", "financial_events", ["settlement_id"])
    op.create_index("ix_financial_events_marketplace", "financial_events", ["marketplace"])
    op.create_index("ix_financial_events_event_type", "financial_events", ["event_type"])

    op.create_table(
        "financial_cost_evidence",
        *_common("financial_cost_evidence"),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("marketplace", sa.String(30)),
        sa.Column("sku", sa.String(160)),
        sa.Column("cost_key", sa.String(220), nullable=False),
        sa.Column("cost_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("evidence_status", sa.String(20), nullable=False, server_default="modeled"),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="seller_entered"),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint(
            "owner_id", "cost_key", "effective_from", name="uq_financial_cost_version"
        ),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_financial_cost_amount"),
        sa.CheckConstraint(
            "evidence_status IN ('modeled','observed','reported','verified','unknown')",
            name="ck_financial_cost_evidence",
        ),
    )
    for col in ("owner_id", "product_id", "marketplace", "sku"):
        op.create_index(f"ix_financial_cost_evidence_{col}", "financial_cost_evidence", [col])

    op.create_table(
        "financial_fee_rules",
        *_common("financial_fee_rules"),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("category", sa.String(240)),
        sa.Column("rule_key", sa.String(220), nullable=False),
        sa.Column("fee_type", sa.String(40), nullable=False),
        sa.Column("rate_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("fixed_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="synthetic_fixture"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.String(40), nullable=False, server_default="pr-sos-05-v1"),
        sa.Column("assumptions_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint(
            "owner_id", "rule_key", "effective_from", name="uq_financial_fee_rule_version"
        ),
        sa.CheckConstraint("rate_percent >= 0", name="ck_financial_fee_rule_rate"),
        sa.CheckConstraint("fixed_amount >= 0", name="ck_financial_fee_rule_fixed"),
    )
    op.create_index("ix_financial_fee_rules_owner_id", "financial_fee_rules", ["owner_id"])
    op.create_index("ix_financial_fee_rules_marketplace", "financial_fee_rules", ["marketplace"])

    op.create_table(
        "financial_calculation_snapshots",
        *_common("financial_calculation_snapshots"),
        sa.Column("scope_key", sa.String(240), nullable=False),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("marketplace", sa.String(30)),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("order_id", UUID, sa.ForeignKey("marketplace_orders.id", ondelete="SET NULL")),
        sa.Column("calculation_version", sa.String(40), nullable=False),
        sa.Column("evidence_status", sa.String(20), nullable=False, server_default="partial"),
        sa.Column("metrics_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "missing_inputs_json", JSON, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("lineage_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint(
            "owner_id",
            "scope_key",
            "calculation_version",
            name="uq_financial_snapshot_scope_version",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('modeled','observed','reported','verified','unknown','partial')",
            name="ck_financial_snapshot_evidence",
        ),
    )
    for col in ("owner_id", "marketplace", "product_id", "order_id"):
        op.create_index(
            f"ix_financial_calculation_snapshots_{col}", "financial_calculation_snapshots", [col]
        )

    op.create_table(
        "financial_settlement_reconciliations",
        *_common("financial_settlement_reconciliations"),
        sa.Column(
            "account_id",
            UUID,
            sa.ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "settlement_id", UUID, sa.ForeignKey("marketplace_settlements.id", ondelete="SET NULL")
        ),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("settlement_key", sa.String(240), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2)),
        sa.Column("reported_amount", sa.Numeric(14, 2)),
        sa.Column("verified_amount", sa.Numeric(14, 2)),
        sa.Column("difference_amount", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("evidence_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("provenance_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "calculation_version", sa.String(40), nullable=False, server_default="pr-sos-05-v1"
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "settlement_key", name="uq_financial_settlement_reconciliation"
        ),
        sa.CheckConstraint(
            "status IN ('matched','mismatch','missing_evidence','unknown')",
            name="ck_financial_reconciliation_status",
        ),
    )
    for col in ("owner_id", "account_id", "settlement_id", "marketplace"):
        op.create_index(
            f"ix_financial_settlement_reconciliations_{col}",
            "financial_settlement_reconciliations",
            [col],
        )


def downgrade() -> None:
    op.drop_table("financial_settlement_reconciliations")
    op.drop_table("financial_calculation_snapshots")
    op.drop_table("financial_fee_rules")
    op.drop_table("financial_cost_evidence")
    op.drop_table("financial_events")
