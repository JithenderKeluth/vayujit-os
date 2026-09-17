"""Add bounded 8E.4 supplier portfolio simulations."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261028_0107"
down_revision = "20261027_0106"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete="CASCADE")


def upgrade() -> None:
    op.create_table(
        "intelligence_supplier_portfolio_simulations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("simulation_type", sa.String(48), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("assumption_hash", sa.String(64), nullable=False),
        sa.Column("assumptions", JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint(
            "owner_id",
            "portfolio_id",
            "assessment_version_id",
            "simulation_type",
            "assumption_hash",
            "idempotency_key",
            name="uq_portfolio_simulation_request",
        ),
    )
    op.create_index(
        "ix_portfolio_simulation_owner_portfolio",
        "intelligence_supplier_portfolio_simulations",
        ["owner_id", "portfolio_id"],
    )
    op.create_table(
        "intelligence_supplier_portfolio_simulation_results",
        sa.Column("id", UUID, nullable=False),
        sa.Column("simulation_id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("baseline", JSONB, nullable=False),
        sa.Column("simulated", JSONB, nullable=False),
        sa.Column("delta", JSONB, nullable=False),
        sa.Column("affected_supplier_ids", JSONB, nullable=False),
        sa.Column("affected_product_ids", JSONB, nullable=False),
        sa.Column("allocation_exposed", sa.Numeric(12, 4), nullable=True),
        sa.Column("uncovered_exposure", sa.Numeric(12, 4), nullable=True),
        sa.Column("missing_evidence", JSONB, nullable=False),
        sa.Column("limitations", JSONB, nullable=False),
        sa.Column("recommendations", JSONB, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("calculation_versions", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("simulation_id", "intelligence_supplier_portfolio_simulations.id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint("simulation_id", name="uq_portfolio_simulation_result"),
    )
    op.create_index(
        "ix_portfolio_simulation_result_owner",
        "intelligence_supplier_portfolio_simulation_results",
        ["owner_id", "portfolio_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_supplier_portfolio_simulation_results")
    op.drop_table("intelligence_supplier_portfolio_simulations")
