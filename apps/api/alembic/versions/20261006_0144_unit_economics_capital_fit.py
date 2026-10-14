"""Add immutable PR-5C unit economics and capital-fit results."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261006_0144"
down_revision = "20261002_0143"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_product_opportunity_unit_economics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("landed_cost_calculation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commercial_readiness_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scenario_key", sa.String(length=120), nullable=False, server_default="seller-scenario"),
        sa.Column("calculation_version", sa.String(length=120), nullable=False),
        sa.Column("calculation_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="READY"),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("readiness", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("selling_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("selling_price_currency", sa.String(length=3), nullable=True),
        sa.Column("selling_price_provenance", sa.String(length=40), nullable=False, server_default="UNKNOWN"),
        sa.Column("base_currency", sa.String(length=3), nullable=True),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("selling_cost_components", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("per_unit_landed_cost", sa.Numeric(24, 8), nullable=True),
        sa.Column("per_unit_selling_cost", sa.Numeric(24, 8), nullable=True),
        sa.Column("per_unit_total_cost", sa.Numeric(24, 8), nullable=True),
        sa.Column("per_unit_contribution", sa.Numeric(24, 8), nullable=True),
        sa.Column("contribution_margin", sa.Numeric(24, 8), nullable=True),
        sa.Column("order_economics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("capital_available", sa.Numeric(24, 8), nullable=True),
        sa.Column("capital_currency", sa.String(length=3), nullable=True),
        sa.Column("capital_required", sa.Numeric(24, 8), nullable=True),
        sa.Column("capital_headroom", sa.Numeric(24, 8), nullable=True),
        sa.Column("capital_shortfall", sa.Numeric(24, 8), nullable=True),
        sa.Column("capital_fit_status", sa.String(length=24), nullable=False, server_default="NEEDS_INPUT"),
        sa.Column("unknown_excluded", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("contradictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("explanation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["intelligence_product_opportunity_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["landed_cost_calculation_id"], ["intelligence_economic_calculations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commercial_readiness_snapshot_id"], ["intelligence_commercial_readiness_snapshots.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr5c_unit_economics_fingerprint"),
    )
    op.create_index(
        "ix_pr5c_unit_economics_owner_context",
        "intelligence_product_opportunity_unit_economics",
        ["owner_id", "opportunity_id", "assessment_id", "created_at"],
    )
    op.create_index(
        "ix_pr5c_unit_economics_landed_cost",
        "intelligence_product_opportunity_unit_economics",
        ["landed_cost_calculation_id"],
    )
    op.create_index(
        "ix_pr5c_unit_economics_idempotency",
        "intelligence_product_opportunity_unit_economics",
        ["owner_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_pr5c_unit_economics_idempotency", table_name="intelligence_product_opportunity_unit_economics")
    op.drop_index("ix_pr5c_unit_economics_landed_cost", table_name="intelligence_product_opportunity_unit_economics")
    op.drop_index("ix_pr5c_unit_economics_owner_context", table_name="intelligence_product_opportunity_unit_economics")
    op.drop_table("intelligence_product_opportunity_unit_economics")
