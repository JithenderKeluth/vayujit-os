"""Add durable PR-5B ProductOpportunity scope to canonical calculations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261002_0143"
down_revision = "20261130_0142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column("product_opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column(
            "commercial_readiness_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column("scenario_key", sa.String(length=120), nullable=True),
    )
    op.create_foreign_key(
        "fk_economic_calc_product_opportunity",
        "intelligence_economic_calculations",
        "intelligence_product_opportunities",
        ["product_opportunity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_economic_calc_assessment",
        "intelligence_economic_calculations",
        "intelligence_product_opportunity_assessments",
        ["assessment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_economic_calc_readiness",
        "intelligence_economic_calculations",
        "intelligence_commercial_readiness_snapshots",
        ["commercial_readiness_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_economic_calc_supplier",
        "intelligence_economic_calculations",
        "intelligence_suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_economic_calculation_product_opportunity",
        "intelligence_economic_calculations",
        ["product_opportunity_id"],
    )
    op.create_index(
        "ix_economic_calculation_assessment",
        "intelligence_economic_calculations",
        ["assessment_id"],
    )
    op.create_index(
        "ix_economic_calculation_readiness",
        "intelligence_economic_calculations",
        ["commercial_readiness_snapshot_id"],
    )
    op.create_index(
        "ix_economic_calculation_supplier",
        "intelligence_economic_calculations",
        ["supplier_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_economic_calculation_supplier", table_name="intelligence_economic_calculations"
    )
    op.drop_index(
        "ix_economic_calculation_readiness", table_name="intelligence_economic_calculations"
    )
    op.drop_index(
        "ix_economic_calculation_assessment", table_name="intelligence_economic_calculations"
    )
    op.drop_index(
        "ix_economic_calculation_product_opportunity",
        table_name="intelligence_economic_calculations",
    )
    op.drop_constraint(
        "fk_economic_calc_supplier", "intelligence_economic_calculations", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_economic_calc_readiness", "intelligence_economic_calculations", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_economic_calc_assessment", "intelligence_economic_calculations", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_economic_calc_product_opportunity",
        "intelligence_economic_calculations",
        type_="foreignkey",
    )
    for name in (
        "scenario_key",
        "supplier_id",
        "commercial_readiness_snapshot_id",
        "assessment_id",
        "product_opportunity_id",
    ):
        op.drop_column("intelligence_economic_calculations", name)