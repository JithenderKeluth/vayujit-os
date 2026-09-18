"""Add Slice 9A Product Opportunity foundation tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261030_0109"
down_revision = "20261029_0108"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "intelligence_product_opportunities",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=True),
        sa.Column("brand_id", UUID, nullable=True),
        sa.Column("research_run_id", UUID, nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("product_concept", sa.Text(), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("subcategory", sa.String(120), nullable=False),
        sa.Column("brand_strategy", sa.String(120), nullable=False),
        sa.Column("target_marketplace", sa.String(120), nullable=False),
        sa.Column("target_region", sa.String(120), nullable=False),
        sa.Column("customer_segment", sa.String(160), nullable=False),
        sa.Column("business_model", sa.String(120), nullable=False),
        sa.Column("research_objective", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(40), nullable=False),
        sa.Column("tags", JSONB, nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("research_state", sa.String(32), nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False),
        sa.Column("current_constraint_version_id", UUID, nullable=True),
        sa.Column("current_assessment_id", UUID, nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["research_run_id"], ["intelligence_research_runs.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_owner_idempotency"
        ),
    )
    op.create_index(
        "ix_product_opportunity_owner", "intelligence_product_opportunities", ["owner_id"]
    )
    op.create_index(
        "ix_product_opportunity_status", "intelligence_product_opportunities", ["lifecycle_status"]
    )
    op.create_index(
        "ix_product_opportunity_category", "intelligence_product_opportunities", ["category"]
    )
    op.create_index(
        "ix_product_opportunity_marketplace",
        "intelligence_product_opportunities",
        ["target_marketplace"],
    )
    op.create_table(
        "intelligence_product_opportunity_constraint_versions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("opportunity_id", UUID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("available_capital", sa.Numeric(18, 2)),
        sa.Column("target_selling_price_min", sa.Numeric(18, 2)),
        sa.Column("target_selling_price_max", sa.Numeric(18, 2)),
        sa.Column("target_margin", sa.Numeric(8, 4)),
        sa.Column("maximum_landed_cost", sa.Numeric(18, 2)),
        sa.Column("maximum_moq", sa.Numeric(18, 2)),
        sa.Column("maximum_lead_time_days", sa.Integer()),
        sa.Column("target_launch_window", sa.String(120)),
        sa.Column("acceptable_risk_level", sa.String(40)),
        sa.Column("marketplace", sa.String(120)),
        sa.Column("country_region", sa.String(120)),
        sa.Column("category_restrictions", JSONB, nullable=False),
        sa.Column("supplier_geography_preferences", JSONB, nullable=False),
        sa.Column("minimum_evidence_confidence", sa.Numeric(5, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "opportunity_id", "version", name="uq_product_opportunity_constraint_version"
        ),
    )
    op.create_index(
        "ix_product_opportunity_constraints_owner",
        "intelligence_product_opportunity_constraint_versions",
        ["owner_id", "opportunity_id"],
    )
    op.create_table(
        "intelligence_product_opportunity_input_snapshots",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("opportunity_id", UUID, nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_product_opportunity_snapshots_owner",
        "intelligence_product_opportunity_input_snapshots",
        ["owner_id", "opportunity_id"],
    )
    op.create_table(
        "intelligence_product_opportunity_assessments",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("opportunity_id", UUID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("constraint_version_id", UUID, nullable=False),
        sa.Column("input_snapshot_id", UUID, nullable=False),
        sa.Column("calculation_version", sa.String(120), nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["constraint_version_id"],
            ["intelligence_product_opportunity_constraint_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["input_snapshot_id"],
            ["intelligence_product_opportunity_input_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "opportunity_id", "version", name="uq_product_opportunity_assessment_version"
        ),
    )
    op.create_index(
        "ix_product_opportunity_assessments_owner",
        "intelligence_product_opportunity_assessments",
        ["owner_id", "opportunity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_opportunity_assessments_owner",
        table_name="intelligence_product_opportunity_assessments",
    )
    op.drop_table("intelligence_product_opportunity_assessments")
    op.drop_index(
        "ix_product_opportunity_snapshots_owner",
        table_name="intelligence_product_opportunity_input_snapshots",
    )
    op.drop_table("intelligence_product_opportunity_input_snapshots")
    op.drop_index(
        "ix_product_opportunity_constraints_owner",
        table_name="intelligence_product_opportunity_constraint_versions",
    )
    op.drop_table("intelligence_product_opportunity_constraint_versions")
    for index in (
        "ix_product_opportunity_marketplace",
        "ix_product_opportunity_category",
        "ix_product_opportunity_status",
        "ix_product_opportunity_owner",
    ):
        op.drop_index(index, table_name="intelligence_product_opportunities")
    op.drop_table("intelligence_product_opportunities")
