"""Add durable Campaign Activity rescheduling history."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260811_0021"
down_revision: str | None = "20260810_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_activity_reschedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_schedule_id", postgresql.UUID(as_uuid=True)),
        sa.Column("replacement_schedule_id", postgresql.UUID(as_uuid=True)),
        sa.Column("original_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("replacement_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("original_scheduled_for_utc", sa.DateTime(timezone=True)),
        sa.Column("requested_local_datetime", sa.DateTime(timezone=False), nullable=False),
        sa.Column("requested_timezone", sa.String(100), nullable=False),
        sa.Column("resolved_scheduled_for_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("preview_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_id"], ["campaign_activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["original_schedule_id"], ["publishing_schedules.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["replacement_schedule_id"], ["publishing_schedules.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["original_job_id"], ["publishing_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["replacement_job_id"], ["publishing_jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.UniqueConstraint(
            "owner_id", "preview_fingerprint", name="uq_reschedule_owner_fingerprint"
        ),
        sa.UniqueConstraint(
            "activity_id", "replacement_schedule_id", name="uq_reschedule_activity_schedule"
        ),
        sa.CheckConstraint(
            "status IN ('previewed','confirmed','superseded','cancelled','failed')",
            name="ck_campaign_reschedule_status",
        ),
    )
    op.create_index(
        "ix_campaign_activity_reschedules_owner_id", "campaign_activity_reschedules", ["owner_id"]
    )
    op.create_index(
        "ix_campaign_activity_reschedules_campaign_id",
        "campaign_activity_reschedules",
        ["campaign_id"],
    )
    op.create_index(
        "ix_campaign_activity_reschedules_activity_id",
        "campaign_activity_reschedules",
        ["activity_id"],
    )
    op.create_index(
        "ix_campaign_activity_reschedules_preview_fingerprint",
        "campaign_activity_reschedules",
        ["preview_fingerprint"],
    )
    op.create_index(
        "ix_campaign_activity_reschedules_status", "campaign_activity_reschedules", ["status"]
    )


def downgrade() -> None:
    op.drop_table("campaign_activity_reschedules")
