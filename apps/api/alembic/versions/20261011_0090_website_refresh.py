"""Add durable website refresh scheduling state."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261011_0090"
down_revision = "20261010_0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_website_source_profiles", sa.Column("timezone", sa.String(80), nullable=True)
    )
    op.add_column(
        "intelligence_website_source_profiles",
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_website_source_profiles",
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_website_source_profiles",
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_website_source_profiles",
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_website_source_profiles",
        sa.Column("refresh_failure_code", sa.String(80), nullable=True),
    )
    op.add_column(
        "intelligence_website_source_profiles",
        sa.Column("refresh_target_type", sa.String(64), nullable=True),
    )
    op.execute(
        "UPDATE intelligence_website_source_profiles SET timezone = 'UTC' WHERE timezone IS NULL"
    )
    op.execute(
        "UPDATE intelligence_website_source_profiles SET refresh_target_type = 'WEBSITE_SOURCE'"
        " WHERE refresh_target_type IS NULL"
    )
    op.create_index(
        "ix_website_profile_next_refresh",
        "intelligence_website_source_profiles",
        ["next_refresh_at"],
    )
    op.create_table(
        "intelligence_website_refresh_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_website_source_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "owner_id", "source_profile_id", "scheduled_for", name="uq_website_refresh_job_identity"
        ),
    )
    op.create_index(
        "ix_website_refresh_jobs_owner_id", "intelligence_website_refresh_jobs", ["owner_id"]
    )
    op.create_index(
        "ix_website_refresh_jobs_source_profile_id",
        "intelligence_website_refresh_jobs",
        ["source_profile_id"],
    )
    op.create_index(
        "ix_website_refresh_jobs_scheduled_for",
        "intelligence_website_refresh_jobs",
        ["scheduled_for"],
    )
    op.create_index(
        "ix_website_refresh_jobs_status", "intelligence_website_refresh_jobs", ["status"]
    )

    op.create_table(
        "intelligence_website_refresh_recovery",
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
            sa.ForeignKey("intelligence_website_refresh_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("failure_code", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("safe_reason_code", sa.String(120), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "job_id", "idempotency_key", name="uq_website_refresh_recovery_identity"
        ),
    )
    op.create_index(
        "ix_website_refresh_recovery_owner_id",
        "intelligence_website_refresh_recovery",
        ["owner_id"],
    )
    op.create_index(
        "ix_website_refresh_recovery_job_id", "intelligence_website_refresh_recovery", ["job_id"]
    )


def downgrade() -> None:
    op.drop_table("intelligence_website_refresh_recovery")
    op.drop_table("intelligence_website_refresh_jobs")
    op.drop_index(
        "ix_website_profile_next_refresh", table_name="intelligence_website_source_profiles"
    )
    for column in (
        "refresh_failure_code",
        "last_failure_at",
        "last_success_at",
        "last_refresh_at",
        "next_refresh_at",
        "refresh_target_type",
        "timezone",
    ):
        op.drop_column("intelligence_website_source_profiles", column)
