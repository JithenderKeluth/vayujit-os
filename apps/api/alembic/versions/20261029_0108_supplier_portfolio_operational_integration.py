"""Add bounded 8E.5 supplier portfolio human-action ledger."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261029_0108"
down_revision = "20261028_0107"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "intelligence_supplier_portfolio_human_actions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=True),
        sa.Column("recommendation_id", UUID, nullable=True),
        sa.Column("supplier_id", UUID, nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["intelligence_supplier_portfolio_contexts.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "portfolio_id",
            "action",
            "idempotency_key",
            name="uq_supplier_portfolio_human_action",
        ),
    )
    op.create_index(
        "ix_supplier_portfolio_human_action_owner",
        "intelligence_supplier_portfolio_human_actions",
        ["owner_id", "portfolio_id"],
    )
    op.create_index(
        "ix_supplier_portfolio_human_action_type",
        "intelligence_supplier_portfolio_human_actions",
        ["action"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_portfolio_human_action_type",
        table_name="intelligence_supplier_portfolio_human_actions",
    )
    op.drop_index(
        "ix_supplier_portfolio_human_action_owner",
        table_name="intelligence_supplier_portfolio_human_actions",
    )
    op.drop_table("intelligence_supplier_portfolio_human_actions")
