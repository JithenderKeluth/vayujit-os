"""Add calculation-free sourcing economic inputs for 13A."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import TextClause

from alembic import op

revision = "20261125_0134"
down_revision = "20261124_0133"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def _json(value: str) -> TextClause:
    return sa.text(f"'{value}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "intelligence_economic_contexts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="RESTRICT")),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_opportunities.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "supplier_id", UUID, sa.ForeignKey("intelligence_suppliers.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "scenario_id", UUID, sa.ForeignKey("intelligence_scenarios.id", ondelete="RESTRICT")
        ),
        sa.Column("source_marketplace", sa.String(120)),
        sa.Column("origin_country", sa.String(80)),
        sa.Column("destination_country", sa.String(80)),
        sa.Column("target_channel", sa.String(120)),
        sa.Column("target_quantity", sa.Numeric(24, 8)),
        sa.Column("quantity_unit", sa.String(40)),
        sa.Column("base_currency", sa.String(3)),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_economic_context_idempotency"),
        sa.CheckConstraint(
            "status IN ('DRAFT','CURRENT','ARCHIVED')", name="ck_economic_context_status"
        ),
        sa.CheckConstraint("version > 0", name="ck_economic_context_version"),
        sa.CheckConstraint(
            "base_currency IS NULL OR base_currency ~ '^[A-Z]{3}$'",
            name="ck_economic_context_currency",
        ),
        sa.CheckConstraint(
            "target_quantity IS NULL OR target_quantity > 0", name="ck_economic_context_quantity"
        ),
    )
    op.create_index("ix_economic_context_owner", "intelligence_economic_contexts", ["owner_id"])
    op.create_index("ix_economic_context_product", "intelligence_economic_contexts", ["product_id"])
    op.create_index(
        "ix_economic_context_supplier", "intelligence_economic_contexts", ["supplier_id"]
    )
    op.create_index(
        "ix_economic_context_scenario", "intelligence_economic_contexts", ["scenario_id"]
    )

    op.create_table(
        "intelligence_economic_quote_inputs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id", UUID, sa.ForeignKey("intelligence_suppliers.id", ondelete="RESTRICT")
        ),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="RESTRICT")),
        sa.Column(
            "supplier_quote_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_quotes.id", ondelete="SET NULL"),
        ),
        sa.Column("quote_reference", sa.String(180)),
        sa.Column("unit_price", sa.Numeric(24, 8)),
        sa.Column("currency", sa.String(3)),
        sa.Column("unit_basis", sa.String(40)),
        sa.Column("moq", sa.Numeric(24, 8)),
        sa.Column("moq_unit", sa.String(40)),
        sa.Column("quoted_lead_time_days", sa.Integer),
        sa.Column("incoterm", sa.String(8)),
        sa.Column("quote_date", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("provenance", sa.String(16), nullable=False, server_default="QUOTED"),
        sa.Column("freshness", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "evidence_ref",
            UUID,
            sa.ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        ),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_economic_quote_idempotency"),
        sa.CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_economic_quote_provenance",
        ),
        sa.CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_economic_quote_freshness"
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_economic_quote_currency"
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR currency IS NOT NULL", name="ck_economic_quote_money_currency"
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0", name="ck_economic_quote_unit_price"
        ),
        sa.CheckConstraint("moq IS NULL OR moq > 0", name="ck_economic_quote_moq"),
    )
    op.create_index("ix_economic_quote_owner", "intelligence_economic_quote_inputs", ["owner_id"])
    op.create_index(
        "ix_economic_quote_context", "intelligence_economic_quote_inputs", ["context_id"]
    )
    op.create_index(
        "ix_economic_quote_supplier", "intelligence_economic_quote_inputs", ["supplier_id"]
    )
    op.create_index(
        "ix_economic_quote_evidence", "intelligence_economic_quote_inputs", ["evidence_ref"]
    )

    op.create_table(
        "intelligence_economic_cost_components",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quote_input_id",
            UUID,
            sa.ForeignKey("intelligence_economic_quote_inputs.id", ondelete="SET NULL"),
        ),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8)),
        sa.Column("currency", sa.String(3)),
        sa.Column("quantity_basis", sa.Numeric(24, 8)),
        sa.Column("unit_basis", sa.String(40)),
        sa.Column("provenance", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("freshness", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column(
            "evidence_ref",
            UUID,
            sa.ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        ),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "fingerprint", name="uq_economic_component_fingerprint"
        ),
        sa.CheckConstraint(
            "category IN ("
            "'PRODUCT_COST','PACKAGING','SAMPLE','TOOLING','INSPECTION','FREIGHT',"
            "'INSURANCE','CUSTOMS_DUTY','IMPORT_TAX','BROKERAGE','PORT_HANDLING',"
            "'LOCAL_TRANSPORT','WAREHOUSING','FULFILMENT','MARKETPLACE_FEE','OTHER')",
            name="ck_economic_component_category",
        ),
        sa.CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_economic_component_provenance",
        ),
        sa.CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_economic_component_freshness"
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_economic_component_currency"
        ),
        sa.CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_economic_component_money_currency"
        ),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_economic_component_amount"),
    )
    op.create_index(
        "ix_economic_component_owner", "intelligence_economic_cost_components", ["owner_id"]
    )
    op.create_index(
        "ix_economic_component_context", "intelligence_economic_cost_components", ["context_id"]
    )
    op.create_index(
        "ix_economic_component_fingerprint",
        "intelligence_economic_cost_components",
        ["fingerprint"],
    )

    op.create_table(
        "intelligence_economic_assumptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("freshness", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "key", "version", name="uq_economic_assumption_version"
        ),
    )
    op.create_index(
        "ix_economic_assumption_owner", "intelligence_economic_assumptions", ["owner_id"]
    )
    op.create_index(
        "ix_economic_assumption_context", "intelligence_economic_assumptions", ["context_id"]
    )

    op.create_table(
        "intelligence_economic_input_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("completeness", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("missing_inputs", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("payload", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "fingerprint", name="uq_economic_snapshot_fingerprint"
        ),
        sa.UniqueConstraint(
            "owner_id", "context_id", "version", name="uq_economic_snapshot_version"
        ),
        sa.CheckConstraint(
            "completeness IN ('COMPLETE','PARTIAL','INSUFFICIENT','UNKNOWN')",
            name="ck_economic_snapshot_completeness",
        ),
    )
    op.create_index(
        "ix_economic_snapshot_owner", "intelligence_economic_input_snapshots", ["owner_id"]
    )
    op.create_index(
        "ix_economic_snapshot_context", "intelligence_economic_input_snapshots", ["context_id"]
    )
    op.create_index(
        "ix_economic_snapshot_fingerprint", "intelligence_economic_input_snapshots", ["fingerprint"]
    )

    op.create_table(
        "intelligence_economic_snapshot_components",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_economic_input_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "component_id",
            UUID,
            sa.ForeignKey("intelligence_economic_cost_components.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("snapshot_id", "component_id", name="uq_economic_snapshot_component"),
    )
    op.create_index(
        "ix_economic_snapshot_component_owner",
        "intelligence_economic_snapshot_components",
        ["owner_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_economic_snapshot_components")
    op.drop_table("intelligence_economic_input_snapshots")
    op.drop_table("intelligence_economic_assumptions")
    op.drop_table("intelligence_economic_cost_components")
    op.drop_table("intelligence_economic_quote_inputs")
    op.drop_table("intelligence_economic_contexts")
