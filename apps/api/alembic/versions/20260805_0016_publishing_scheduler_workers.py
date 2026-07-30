"""Add durable Publishing schedules, jobs, attempts, and worker heartbeats."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260805_0016"
down_revision = "20260804_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publishing_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("connector_key", sa.String(80), nullable=False),
        sa.Column("requested_action", sa.String(30), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("scheduled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(100), nullable=False),
        sa.Column("local_scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("recurrence_json", postgresql.JSONB()),
        sa.Column("recurrence_end_at", sa.DateTime(timezone=True)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("destination_snapshot_version", sa.String(64), nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_job_created_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at_utc", sa.DateTime(timezone=True)),
        sa.Column("last_run_at_utc", sa.DateTime(timezone=True)),
        sa.Column("last_result", sa.String(40)),
        sa.Column("cancellation_reason", sa.String(300)),
        sa.CheckConstraint("schedule_type IN ('one_time','recurring')", name="ck_schedule_type"),
        sa.CheckConstraint(
            "requested_action IN ("
            "'create_draft','publish','update','move_to_draft','update_product',"
            "'activate_product','archive_product','reconcile')",
            name="ck_schedule_action",
        ),
    )
    for column in (
        "owner_id",
        "brand_id",
        "product_id",
        "artifact_id",
        "destination_id",
        "connector_key",
        "next_run_at_utc",
    ):
        op.create_index(f"ix_publishing_schedules_{column}", "publishing_schedules", [column])

    op.create_table(
        "publishing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_schedules.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "workflow_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_instances.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "publishing_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_executions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id"),
            nullable=False,
        ),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id"),
            nullable=False,
        ),
        sa.Column("connector_key", sa.String(80), nullable=False),
        sa.Column("requested_action", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.String(160)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_execution_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_error_message", sa.String(500)),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_job_owner_idempotency"),
        sa.CheckConstraint(
            "state IN ("
            "'pending','scheduled','claimed','running','retry_wait','succeeded','failed',"
            "'cancel_requested','cancelled','paused','expired','dead_letter')",
            name="ck_publishing_job_state",
        ),
        sa.CheckConstraint("max_execution_attempts BETWEEN 1 AND 10", name="ck_job_max_attempts"),
        sa.CheckConstraint("priority BETWEEN -100 AND 100", name="ck_job_priority"),
    )
    for column in (
        "owner_id",
        "schedule_id",
        "workflow_instance_id",
        "publishing_execution_id",
        "destination_id",
        "connector_key",
        "state",
        "available_at_utc",
        "lease_owner",
        "lease_expires_at",
        "correlation_id",
    ):
        op.create_index(f"ix_publishing_jobs_{column}", "publishing_jobs", [column])
    op.create_index("ix_publishing_jobs_due", "publishing_jobs", ["state", "available_at_utc"])
    op.create_index("ix_publishing_jobs_lease", "publishing_jobs", ["state", "lease_expires_at"])
    op.create_index(
        "ix_publishing_jobs_owner_created", "publishing_jobs", ["owner_id", "created_at"]
    )
    op.create_index(
        "ix_publishing_jobs_schedule_time", "publishing_jobs", ["schedule_id", "scheduled_at_utc"]
    )
    op.create_index(
        "ix_publishing_jobs_destination_state", "publishing_jobs", ["destination_id", "state"]
    )

    op.create_table(
        "publishing_job_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(160), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("delay_seconds", sa.Integer()),
        sa.Column(
            "connector_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_executions.id", ondelete="SET NULL"),
        ),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
        sa.CheckConstraint(
            "outcome IN ('running','succeeded','failed','cancelled','lease_lost')",
            name="ck_job_attempt_outcome",
        ),
    )
    op.create_index("ix_publishing_job_attempts_job_id", "publishing_job_attempts", ["job_id"])
    op.create_index(
        "ix_publishing_job_attempts_worker_id", "publishing_job_attempts", ["worker_id"]
    )

    op.create_table(
        "publishing_worker_heartbeats",
        sa.Column("worker_id", sa.String(160), primary_key=True),
        sa.Column("process_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("active_jobs", sa.Integer(), nullable=False),
        sa.Column("draining", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shutdown_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("safe_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_publishing_worker_heartbeats_last_heartbeat_at",
        "publishing_worker_heartbeats",
        ["last_heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_table("publishing_worker_heartbeats")
    op.drop_table("publishing_job_attempts")
    op.drop_table("publishing_jobs")
    op.drop_table("publishing_schedules")
