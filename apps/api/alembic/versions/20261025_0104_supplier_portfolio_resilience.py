"""Supplier portfolio context and immutable assessment foundation (8E.1)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261025_0104"
down_revision = "20261024_0103"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "intelligence_supplier_portfolio_contexts",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_reference", sa.String(240), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("current_assessment_version_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_portfolio_owner_idempotency"
        ),
    )
    op.create_index(
        "ix_intelligence_supplier_portfolio_contexts_owner_id",
        "intelligence_supplier_portfolio_contexts",
        ["owner_id"],
    )
    op.create_index(
        "ix_intelligence_supplier_portfolio_contexts_status",
        "intelligence_supplier_portfolio_contexts",
        ["status"],
    )
    op.create_index(
        "ix_portfolio_context_current_assessment",
        "intelligence_supplier_portfolio_contexts",
        ["current_assessment_version_id"],
    )

    op.create_table(
        "intelligence_supplier_portfolio_memberships",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("supplier_id", UUID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("associated_products", JSONB, nullable=False),
        sa.Column("associated_opportunities", JSONB, nullable=False),
        sa.Column("shortlist_lineage_id", UUID, nullable=True),
        sa.Column("due_diligence_lineage_id", UUID, nullable=True),
        sa.Column("sourcing_scenario_lineage_id", UUID, nullable=True),
        sa.Column("allocation_percent", sa.Numeric(9, 6), nullable=True),
        sa.Column("evidence_freshness", sa.String(24), nullable=False),
        sa.Column("confidence", sa.Numeric(9, 6), nullable=True),
        sa.Column("risk", sa.String(32), nullable=True),
        sa.Column("country_region", sa.String(120), nullable=True),
        sa.Column("capabilities", JSONB, nullable=False),
        sa.Column("alternate_source_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["intelligence_supplier_portfolio_contexts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["intelligence_cross_marketplace_suppliers.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "portfolio_id",
            "supplier_id",
            "version",
            name="uq_supplier_portfolio_membership_version",
        ),
    )
    for column in ("owner_id", "portfolio_id", "supplier_id"):
        op.create_index(
            f"ix_intelligence_supplier_portfolio_memberships_{column}",
            "intelligence_supplier_portfolio_memberships",
            [column],
        )

    op.create_table(
        "intelligence_supplier_portfolio_assessment_versions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("input_snapshot", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["intelligence_supplier_portfolio_contexts.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "portfolio_id", "version", name="uq_supplier_portfolio_assessment_version"
        ),
        sa.UniqueConstraint(
            "portfolio_id", "idempotency_key", name="uq_supplier_portfolio_assessment_idempotency"
        ),
    )
    for column in ("owner_id", "portfolio_id"):
        op.create_index(
            f"ix_spav_{column}",
            "intelligence_supplier_portfolio_assessment_versions",
            [column],
        )

    op.create_table(
        "intelligence_supplier_portfolio_input_snapshots",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["intelligence_supplier_portfolio_contexts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["intelligence_supplier_portfolio_assessment_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("assessment_version_id", name="uq_supplier_portfolio_snapshot"),
    )
    for column in ("owner_id", "portfolio_id", "assessment_version_id"):
        op.create_index(
            f"ix_spis_{column}",
            "intelligence_supplier_portfolio_input_snapshots",
            [column],
        )
    op.create_foreign_key(
        "fk_supplier_portfolio_current_assessment",
        "intelligence_supplier_portfolio_contexts",
        "intelligence_supplier_portfolio_assessment_versions",
        ["current_assessment_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_supplier_portfolio_current_assessment",
        "intelligence_supplier_portfolio_contexts",
        type_="foreignkey",
    )
    op.drop_table("intelligence_supplier_portfolio_input_snapshots")
    op.drop_table("intelligence_supplier_portfolio_assessment_versions")
    op.drop_table("intelligence_supplier_portfolio_memberships")
    op.drop_table("intelligence_supplier_portfolio_contexts")
