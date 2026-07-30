"""Add durable Campaign waits and missed-activity resolutions.

Revision ID: 20260808_0019
Revises: 20260807_0018
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0019"
down_revision: str | None = "20260807_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_campaign_activity_status", "campaign_activities", type_="check")
    op.create_check_constraint(
        "ck_campaign_activity_status",
        "campaign_activities",
        "status IN ('draft','blocked','ready','scheduled','waiting_dependency','queued',"
        "'running','retrying','succeeded','failed','dead_letter','cancel_requested','cancelled',"
        "'paused','maintenance_blocked','reconciliation_required','completed_with_warning',"
        "'missed','skipped','archived')",
    )
    op.create_table(
        "campaign_workflow_waits",
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
            "workflow_step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_step_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expected_state", sa.String(30), nullable=False),
        sa.Column("current_state", sa.String(30), nullable=False),
        sa.Column("terminal_success_states", sa.String(160), nullable=False),
        sa.Column("terminal_failure_states", sa.String(160), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_failure_message", sa.String(500)),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("workflow_step_id", name="uq_campaign_workflow_wait_step"),
        sa.CheckConstraint(
            "current_state IN ('planning','scheduled','running','partially_completed','completed','failed','cancelled','blocked')",
            name="ck_campaign_workflow_wait_state",
        ),
    )
    op.create_index(
        "ix_campaign_wait_owner_state", "campaign_workflow_waits", ["owner_id", "current_state"]
    )
    op.create_index("ix_campaign_wait_campaign", "campaign_workflow_waits", ["campaign_id"])
    op.create_table(
        "campaign_missed_activity_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_activities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy", sa.String(30), nullable=False),
        sa.Column("original_scheduled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_status", sa.String(30), nullable=False),
        sa.Column(
            "replacement_activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_activities.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "replacement_schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_schedules.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "replacement_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column(
            "resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("activity_id", "policy", name="uq_campaign_missed_resolution"),
        sa.CheckConstraint(
            "policy IN ('skip_missed','run_next','one_catch_up','reschedule_manually')",
            name="ck_campaign_missed_policy",
        ),
    )
    op.create_index(
        "ix_campaign_missed_owner_status",
        "campaign_missed_activity_resolutions",
        ["owner_id", "resolution_status"],
    )
    op.create_index(
        "ix_campaign_missed_campaign", "campaign_missed_activity_resolutions", ["campaign_id"]
    )


def downgrade() -> None:
    op.drop_table("campaign_missed_activity_resolutions")
    op.drop_table("campaign_workflow_waits")
    op.drop_constraint("ck_campaign_activity_status", "campaign_activities", type_="check")
    op.create_check_constraint(
        "ck_campaign_activity_status",
        "campaign_activities",
        "status IN ('draft','blocked','ready','scheduled','waiting_dependency','queued',"
        "'running','retrying','succeeded','failed','dead_letter','cancel_requested','cancelled',"
        "'paused','maintenance_blocked','reconciliation_required','completed_with_warning','archived')",
    )
