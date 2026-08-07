"""Add durable standalone Campaign catch-up identity fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260812_0022"
down_revision: str | None = "20260811_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaign_missed_activity_resolutions",
        sa.Column("original_schedule_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "campaign_missed_activity_resolutions",
        sa.Column("original_job_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "campaign_missed_activity_resolutions",
        sa.Column("preview_fingerprint", sa.String(128)),
    )
    op.add_column(
        "campaign_missed_activity_resolutions",
        sa.Column("requested_local_datetime", sa.DateTime(timezone=False)),
    )
    op.add_column(
        "campaign_missed_activity_resolutions",
        sa.Column("requested_timezone", sa.String(100)),
    )
    op.add_column(
        "campaign_missed_activity_resolutions",
        sa.Column("resolved_scheduled_for_utc", sa.DateTime(timezone=True)),
    )
    op.add_column("campaign_missed_activity_resolutions", sa.Column("fold", sa.Integer()))
    op.create_foreign_key(
        "fk_missed_resolution_original_schedule",
        "campaign_missed_activity_resolutions",
        "publishing_schedules",
        ["original_schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_missed_resolution_original_job",
        "campaign_missed_activity_resolutions",
        "publishing_jobs",
        ["original_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_missed_resolution_owner_fingerprint",
        "campaign_missed_activity_resolutions",
        ["owner_id", "preview_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_missed_resolution_owner_fingerprint",
        "campaign_missed_activity_resolutions",
        type_="unique",
    )
    op.drop_constraint(
        "fk_missed_resolution_original_job",
        "campaign_missed_activity_resolutions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_missed_resolution_original_schedule",
        "campaign_missed_activity_resolutions",
        type_="foreignkey",
    )
    for name in (
        "fold",
        "resolved_scheduled_for_utc",
        "requested_timezone",
        "requested_local_datetime",
        "preview_fingerprint",
        "original_job_id",
        "original_schedule_id",
    ):
        op.drop_column("campaign_missed_activity_resolutions", name)
