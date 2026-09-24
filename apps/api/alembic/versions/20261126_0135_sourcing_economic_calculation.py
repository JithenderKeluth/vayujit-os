"""Add immutable deterministic landed-cost calculations for 13B."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261126_0135"
down_revision = "20261125_0134"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_economic_calculations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_economic_input_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("calculation_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(3)),
        sa.Column("target_quantity", sa.Numeric(24, 8)),
        sa.Column("total_included_cost", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("per_unit_cost", sa.Numeric(24, 8)),
        sa.Column("included_component_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("excluded_component_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("missing_inputs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("warnings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assumptions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stale_inputs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("explanation", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "calculation_fingerprint", name="uq_economic_calculation_fingerprint"
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETE','PARTIAL','INSUFFICIENT')",
            name="ck_economic_calculation_status",
        ),
        sa.CheckConstraint("total_included_cost >= 0", name="ck_economic_calculation_total"),
        sa.CheckConstraint(
            "per_unit_cost IS NULL OR per_unit_cost >= 0", name="ck_economic_calculation_per_unit"
        ),
        sa.CheckConstraint(
            "target_quantity IS NULL OR target_quantity > 0",
            name="ck_economic_calculation_quantity",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_economic_calculation_currency"
        ),
    )
    op.create_index(
        "ix_economic_calculation_owner", "intelligence_economic_calculations", ["owner_id"]
    )
    op.create_index(
        "ix_economic_calculation_context", "intelligence_economic_calculations", ["context_id"]
    )
    op.create_index(
        "ix_economic_calculation_snapshot", "intelligence_economic_calculations", ["snapshot_id"]
    )
    op.create_index(
        "ix_economic_calculation_fingerprint",
        "intelligence_economic_calculations",
        ["calculation_fingerprint"],
    )
    op.create_index(
        "ix_economic_calculation_status", "intelligence_economic_calculations", ["status"]
    )

    op.create_table(
        "intelligence_economic_calculation_breakdowns",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "calculation_id",
            UUID,
            sa.ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_id", UUID),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("original_amount", sa.Numeric(24, 8)),
        sa.Column("currency", sa.String(3)),
        sa.Column("basis", sa.String(40)),
        sa.Column("multiplier", sa.Numeric(24, 8)),
        sa.Column("included_amount", sa.Numeric(24, 8)),
        sa.Column("provenance", sa.String(16), nullable=False),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("evidence_ref", UUID),
        sa.Column("inclusion_status", sa.String(16), nullable=False),
        sa.Column("exclusion_reason", sa.String(120)),
        sa.Column("lineage", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("line_order", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("calculation_id", "line_order", name="uq_economic_calculation_line"),
        sa.CheckConstraint(
            "inclusion_status IN ('INCLUDED','EXCLUDED')", name="ck_economic_breakdown_inclusion"
        ),
    )
    op.create_index(
        "ix_economic_breakdown_owner", "intelligence_economic_calculation_breakdowns", ["owner_id"]
    )
    op.create_index(
        "ix_economic_breakdown_calculation",
        "intelligence_economic_calculation_breakdowns",
        ["calculation_id"],
    )
    op.create_index(
        "ix_economic_breakdown_source",
        "intelligence_economic_calculation_breakdowns",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_economic_calculation_breakdowns")
    op.drop_table("intelligence_economic_calculations")
