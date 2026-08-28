# ruff: noqa: E501
"""Add durable external budget, execution, and recovery ledgers."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261005_0084"
down_revision = "20261004_0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_external_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *[
            sa.Column(name, sa.Integer, nullable=False, server_default=str(default))
            for name, default in {
                "max_searches": 10,
                "max_fetches": 10,
                "max_domains": 10,
                "max_results": 100,
                "max_response_bytes": 1_000_000,
                "max_total_bytes": 10_000_000,
                "max_elapsed_seconds": 300,
                "max_retries": 3,
                "max_provider_requests": 20,
                "searches_used": 0,
                "fetches_used": 0,
                "domains_used": 0,
                "results_used": 0,
                "bytes_used": 0,
                "retries_used": 0,
                "provider_requests_used": 0,
            }.items()
        ],
        sa.Column("domains_seen", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("elapsed_seconds", sa.Float, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_external_budget_mission", "intelligence_external_budgets", ["owner_id", "mission_id"]
    )
    op.create_table(
        "intelligence_external_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("identity_key", sa.String(300), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("checkpoint", sa.String(40), nullable=False, server_default="CLAIMED"),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("result_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("domains_seen", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_external_execution_identity",
        "intelligence_external_executions",
        ["owner_id", "identity_key"],
    )
    op.create_table(
        "intelligence_external_recovery",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        ),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("failure_code", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("safe_reason_code", sa.String(120), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("identity_key", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_external_recovery_identity",
        "intelligence_external_recovery",
        ["owner_id", "identity_key"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_external_recovery")
    op.drop_table("intelligence_external_executions")
    op.drop_table("intelligence_external_budgets")
