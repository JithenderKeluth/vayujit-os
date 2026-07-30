"""Complete scheduler recovery, missed-occurrence, worker, and Workflow persistence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260806_0017"
down_revision = "20260805_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "publishing_schedules",
        sa.Column(
            "missed_occurrence_policy",
            sa.String(30),
            nullable=False,
            server_default="next_occurrence",
        ),
    )
    op.add_column(
        "publishing_schedules",
        sa.Column("max_occurrences", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "publishing_schedules",
        sa.Column(
            "materialized_occurrence_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.create_check_constraint(
        "ck_schedule_missed_policy",
        "publishing_schedules",
        "missed_occurrence_policy IN ('skip_missed','next_occurrence','one_catch_up')",
    )
    op.create_check_constraint(
        "ck_schedule_max_occurrences",
        "publishing_schedules",
        "max_occurrences BETWEEN 1 AND 1000",
    )
    for name, type_ in (
        ("recovery_state", sa.String(40)),
        ("recovery_reason", sa.String(500)),
        ("maintenance_blocked_at", sa.DateTime(timezone=True)),
        ("recovered_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("publishing_jobs", sa.Column(name, type_))
    op.create_index("ix_publishing_jobs_recovery_state", "publishing_jobs", ["recovery_state"])
    for name in (
        "completed_jobs",
        "failed_jobs",
        "lease_renewal_failures",
        "stale_recoveries",
        "graceful_shutdowns",
    ):
        op.add_column(
            "publishing_worker_heartbeats",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    op.drop_constraint("ck_workflow_instance_status", "workflow_instances", type_="check")
    op.create_check_constraint(
        "ck_workflow_instance_status",
        "workflow_instances",
        "status IN ('draft','running','waiting_for_approval','waiting_for_publishing',"
        "'completed','failed','cancelled')",
    )
    op.create_table(
        "workflow_publishing_waits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_step_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_schedules.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "expected_terminal_state", sa.String(30), nullable=False, server_default="succeeded"
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workflow_step_execution_id", name="uq_workflow_publishing_wait_step"),
        sa.CheckConstraint(
            "status IN ("
            "'scheduled','waiting','running','retrying','succeeded','failed','cancelled',"
            "'dead_letter','blocked')",
            name="ck_workflow_publishing_wait_status",
        ),
    )
    for column in (
        "owner_id",
        "workflow_instance_id",
        "workflow_step_execution_id",
        "schedule_id",
        "job_id",
        "status",
    ):
        op.create_index(
            f"ix_workflow_publishing_waits_{column}", "workflow_publishing_waits", [column]
        )
    op.create_table(
        "publishing_recovery_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("worker_id", sa.String(160)),
        sa.Column(
            "publishing_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_executions.id", ondelete="SET NULL"),
        ),
        sa.Column("result", sa.String(40), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("safe_message", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("owner_id", "job_id", "result", "created_at"):
        op.create_index(
            f"ix_publishing_recovery_records_{column}", "publishing_recovery_records", [column]
        )


def downgrade() -> None:
    op.drop_table("publishing_recovery_records")
    op.drop_table("workflow_publishing_waits")
    op.drop_constraint("ck_workflow_instance_status", "workflow_instances", type_="check")
    op.create_check_constraint(
        "ck_workflow_instance_status",
        "workflow_instances",
        "status IN ('draft','running','waiting_for_approval','completed','failed','cancelled')",
    )
    for name in (
        "completed_jobs",
        "failed_jobs",
        "lease_renewal_failures",
        "stale_recoveries",
        "graceful_shutdowns",
    ):
        op.drop_column("publishing_worker_heartbeats", name)
    op.drop_index("ix_publishing_jobs_recovery_state", table_name="publishing_jobs")
    for name in ("recovered_at", "maintenance_blocked_at", "recovery_reason", "recovery_state"):
        op.drop_column("publishing_jobs", name)
    op.drop_constraint("ck_schedule_max_occurrences", "publishing_schedules", type_="check")
    op.drop_constraint("ck_schedule_missed_policy", "publishing_schedules", type_="check")
    for name in ("materialized_occurrence_count", "max_occurrences", "missed_occurrence_policy"):
        op.drop_column("publishing_schedules", name)
