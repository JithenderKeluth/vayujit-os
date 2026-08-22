# ruff: noqa: E501, E402, I001

"""Add durable Marketing Plan revisions and channel executions."""

# mypy: ignore-errors

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260913_0062"
down_revision = "20260913_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_plan_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False, server_default="confirmed"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["marketing_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "plan_id", "version", name="uq_marketing_plan_revision"),
    )
    op.create_index("ix_marketing_plan_revisions_plan_id", "marketing_plan_revisions", ["plan_id"])
    op.create_index(
        "ix_marketing_plan_revisions_fingerprint", "marketing_plan_revisions", ["fingerprint"]
    )

    op.create_table(
        "marketing_plan_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["marketing_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_marketing_plan_execution_idempotency"
        ),
        sa.CheckConstraint(
            "state IN ('planned','blocked','queued','running','succeeded','partially_completed','failed','cancelled','stale')",
            name="ck_marketing_plan_execution_state",
        ),
    )
    op.create_index(
        "ix_marketing_plan_executions_plan_id", "marketing_plan_executions", ["plan_id"]
    )
    op.create_index("ix_marketing_plan_executions_state", "marketing_plan_executions", ["state"])
    op.create_index(
        "ix_marketing_plan_executions_correlation_id",
        "marketing_plan_executions",
        ["correlation_id"],
    )

    op.create_table(
        "marketing_channel_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32)),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("dependency_state", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True)),
        sa.Column("downstream_json", postgresql.JSONB(), nullable=False),
        sa.Column("creative_mapping_json", postgresql.JSONB(), nullable=False),
        sa.Column("failure_code", sa.String(length=80)),
        sa.Column("safe_message", sa.String(length=500)),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("lease_owner", sa.String(length=160)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["marketing_plan_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["marketing_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "execution_id", "channel", name="uq_marketing_channel_execution"
        ),
        sa.CheckConstraint(
            "state IN ('planned','blocked','queued','running','retry_wait','succeeded','failed','ambiguous','recovered','cancelled','stale')",
            name="ck_marketing_channel_execution_state",
        ),
    )
    op.create_index(
        "ix_marketing_channel_executions_execution_id",
        "marketing_channel_executions",
        ["execution_id"],
    )
    op.create_index(
        "ix_marketing_channel_executions_plan_id", "marketing_channel_executions", ["plan_id"]
    )
    op.create_index(
        "ix_marketing_channel_executions_channel", "marketing_channel_executions", ["channel"]
    )
    op.create_index(
        "ix_marketing_channel_executions_state", "marketing_channel_executions", ["state"]
    )


def downgrade() -> None:
    op.drop_table("marketing_channel_executions")
    op.drop_table("marketing_plan_executions")
    op.drop_table("marketing_plan_revisions")
