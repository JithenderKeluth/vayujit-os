# ruff: noqa: E501
"""Add provider-neutral marketplace runtime ledgers."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261013_0092"
down_revision = "20261012_0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("identity_key", sa.String(300), nullable=False),
        sa.Column("provider_execution_id", sa.String(180), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("checkpoint", sa.String(40), nullable=False),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("retry_after_seconds", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "owner_id", "provider", "identity_key", name="uq_marketplace_execution_identity"
        ),
    )
    op.create_index("ix_marketplace_executions_owner_id", "marketplace_executions", ["owner_id"])
    op.create_index("ix_marketplace_executions_provider", "marketplace_executions", ["provider"])
    op.create_index("ix_marketplace_executions_status", "marketplace_executions", ["status"])
    op.create_index(
        "ix_marketplace_executions_provider_execution_id",
        "marketplace_executions",
        ["provider_execution_id"],
    )
    op.create_table(
        "marketplace_rate_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("minute_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hour_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minute_used", sa.Integer(), nullable=False),
        sa.Column("hour_used", sa.Integer(), nullable=False),
        sa.UniqueConstraint("owner_id", "provider", name="uq_marketplace_rate_window_scope"),
    )
    op.create_index(
        "ix_marketplace_rate_windows_owner_id", "marketplace_rate_windows", ["owner_id"]
    )
    op.create_index(
        "ix_marketplace_rate_windows_provider", "marketplace_rate_windows", ["provider"]
    )


def downgrade() -> None:
    op.drop_index("ix_marketplace_rate_windows_provider", table_name="marketplace_rate_windows")
    op.drop_index("ix_marketplace_rate_windows_owner_id", table_name="marketplace_rate_windows")
    op.drop_table("marketplace_rate_windows")
    op.drop_index(
        "ix_marketplace_executions_provider_execution_id", table_name="marketplace_executions"
    )
    op.drop_index("ix_marketplace_executions_status", table_name="marketplace_executions")
    op.drop_index("ix_marketplace_executions_provider", table_name="marketplace_executions")
    op.drop_index("ix_marketplace_executions_owner_id", table_name="marketplace_executions")
    op.drop_table("marketplace_executions")
