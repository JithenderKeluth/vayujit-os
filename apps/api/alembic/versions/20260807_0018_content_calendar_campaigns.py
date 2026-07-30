"""Add normalized Content Calendar and Campaign orchestration.

Revision ID: 20260807_0018
Revises: 20260806_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260807_0018"
down_revision: str | None = "20260806_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
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
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("objective", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timezone_name", sa.String(100), nullable=False),
        sa.Column("start_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_start_at", sa.DateTime(), nullable=False),
        sa.Column("local_end_at", sa.DateTime(), nullable=False),
        sa.Column(
            "campaign_manager_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("approval_policy", sa.String(40), nullable=False),
        sa.Column("scheduling_policy", sa.String(40), nullable=False),
        sa.Column("conflict_policy", sa.String(40), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("launched_at", sa.DateTime(timezone=True)),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.String(500)),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_campaign_owner_slug"),
        sa.CheckConstraint(
            "status IN ('draft','planning','ready','scheduled','running','paused',"
            "'partially_completed','completed','failed','cancelled','archived')",
            name="ck_campaign_status",
        ),
        sa.CheckConstraint("priority BETWEEN -100 AND 100", name="ck_campaign_priority"),
    )
    op.create_index("ix_campaigns_owner_created", "campaigns", ["owner_id", "created_at"])
    op.create_index("ix_campaigns_brand_status", "campaigns", ["brand_id", "status"])
    op.create_index("ix_campaigns_status_start", "campaigns", ["status", "start_at_utc"])

    op.create_table(
        "campaign_default_destinations",
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
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "campaign_id", "destination_id", name="uq_campaign_default_destination"
        ),
    )
    op.create_index(
        "ix_campaign_default_destinations_owner",
        "campaign_default_destinations",
        ["owner_id"],
    )
    op.create_index(
        "ix_campaign_default_destinations_campaign",
        "campaign_default_destinations",
        ["campaign_id"],
    )

    op.create_table(
        "campaign_activities",
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
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="RESTRICT"),
        ),
        sa.Column("artifact_version", sa.Integer()),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="RESTRICT"),
        ),
        sa.Column("connector_key", sa.String(80)),
        sa.Column("requested_action", sa.String(30)),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "dependency_policy",
            sa.String(30),
            nullable=False,
            server_default="success_required",
        ),
        sa.Column("scheduled_local_date", sa.Date(), nullable=False),
        sa.Column("scheduled_local_time", sa.Time(), nullable=False),
        sa.Column("timezone_name", sa.String(100), nullable=False),
        sa.Column("scheduled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("readiness_status", sa.String(20), nullable=False),
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
            "publishing_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_executions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "workflow_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_instances.id", ondelete="SET NULL"),
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_failure_message", sa.String(500)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("campaign_id", "sequence", name="uq_campaign_activity_sequence"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_campaign_activity_identity"),
        sa.CheckConstraint(
            "readiness_status IN ('ready','incomplete','blocked','warning','invalid')",
            name="ck_campaign_activity_readiness",
        ),
        sa.CheckConstraint(
            "status IN ('draft','blocked','ready','scheduled','waiting_dependency','queued',"
            "'running','retrying','succeeded','failed','dead_letter','cancel_requested',"
            "'cancelled','paused','maintenance_blocked','reconciliation_required',"
            "'completed_with_warning','archived')",
            name="ck_campaign_activity_status",
        ),
    )
    op.create_index(
        "ix_campaign_activities_campaign_sequence",
        "campaign_activities",
        ["campaign_id", "sequence"],
    )
    op.create_index(
        "ix_campaign_activities_campaign_time",
        "campaign_activities",
        ["campaign_id", "scheduled_at_utc"],
    )
    op.create_index(
        "ix_campaign_activities_destination_time",
        "campaign_activities",
        ["destination_id", "scheduled_at_utc"],
    )
    op.create_index(
        "ix_campaign_activities_product_time",
        "campaign_activities",
        ["product_id", "scheduled_at_utc"],
    )
    op.create_index(
        "ix_campaign_activities_owner_status",
        "campaign_activities",
        ["owner_id", "status"],
    )

    op.create_table(
        "campaign_activity_dependencies",
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
            "predecessor_activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "successor_activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dependency_type", sa.String(30), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "predecessor_activity_id",
            "successor_activity_id",
            name="uq_campaign_activity_dependency_edge",
        ),
        sa.CheckConstraint(
            "dependency_type IN "
            "('finish_to_start','success_required','completion_required','manual_release')",
            name="ck_campaign_dependency_type",
        ),
    )
    op.create_index(
        "ix_campaign_dependencies_campaign",
        "campaign_activity_dependencies",
        ["campaign_id"],
    )
    op.create_index(
        "ix_campaign_dependencies_owner",
        "campaign_activity_dependencies",
        ["owner_id"],
    )

    op.create_table(
        "campaign_schedule_links",
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
            sa.ForeignKey("campaign_activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_schedules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column("occurrence_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("activity_id", "schedule_id", name="uq_campaign_activity_schedule"),
    )
    op.create_index(
        "ix_campaign_schedule_links_activity_schedule",
        "campaign_schedule_links",
        ["activity_id", "schedule_id"],
    )
    op.create_index(
        "ix_campaign_schedule_links_campaign",
        "campaign_schedule_links",
        ["campaign_id"],
    )
    op.create_index("ix_campaign_schedule_links_owner", "campaign_schedule_links", ["owner_id"])


def downgrade() -> None:
    op.drop_table("campaign_schedule_links")
    op.drop_table("campaign_activity_dependencies")
    op.drop_table("campaign_activities")
    op.drop_table("campaign_default_destinations")
    op.drop_table("campaigns")
