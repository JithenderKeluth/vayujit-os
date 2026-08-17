"""Harden durable Bulk Video parent and child lineage."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260908_0056"
down_revision: str | None = "20260907_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    parent_columns: list[sa.Column[Any]] = [
        sa.Column("plan_fingerprint", sa.String(64), nullable=True),
        sa.Column("request_snapshot_json", postgresql.JSONB, nullable=True),
        sa.Column("requested_product_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("requested_child_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("succeeded_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retry_wait_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stale_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cancelled_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preview_fingerprint", sa.String(64), nullable=True),
    ]
    for parent_column in parent_columns:
        op.add_column("video_bulk_operations", parent_column)
    op.create_foreign_key(
        "fk_video_bulk_created_by_users",
        "video_bulk_operations",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_video_bulk_operations_plan_fingerprint", "video_bulk_operations", ["plan_fingerprint"]
    )
    op.create_index(
        "ix_video_bulk_operations_preview_fingerprint",
        "video_bulk_operations",
        ["preview_fingerprint"],
    )

    child_columns: list[sa.Column[Any]] = [
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("output_ordinal", sa.Integer, nullable=False, server_default="0"),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("script_version", sa.Integer, nullable=True),
        sa.Column("storyboard_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storyboard_version", sa.Integer, nullable=True),
        sa.Column("style_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("style_version", sa.Integer, nullable=True),
        sa.Column("preset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("preset_version", sa.Integer, nullable=True),
        sa.Column("source_media_ids_json", postgresql.JSONB, nullable=True),
        sa.Column("context_fingerprint", sa.String(64), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("failure_category", sa.String(40), nullable=True),
        sa.Column("recovery_state", sa.String(40), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_scenario", sa.String(80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for child_column in child_columns:
        op.add_column("video_bulk_children", child_column)
    op.create_foreign_key(
        "fk_video_bulk_child_brand",
        "video_bulk_children",
        "brands",
        ["brand_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_video_bulk_child_script",
        "video_bulk_children",
        "video_scripts",
        ["script_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_video_bulk_child_storyboard",
        "video_bulk_children",
        "video_storyboards",
        ["storyboard_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_video_bulk_child_style",
        "video_bulk_children",
        "video_styles",
        ["style_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_video_bulk_child_preset",
        "video_bulk_children",
        "video_presets",
        ["preset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_video_bulk_child_job",
        "video_bulk_children",
        "ai_studio_jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for name, table, index_column in (
        (
            "ix_video_bulk_children_context_fingerprint",
            "video_bulk_children",
            "context_fingerprint",
        ),
        ("ix_video_bulk_children_job_id", "video_bulk_children", "job_id"),
        ("ix_video_bulk_children_correlation_id", "video_bulk_children", "correlation_id"),
    ):
        op.create_index(name, table, [index_column])


def downgrade() -> None:
    for name in (
        "ix_video_bulk_children_correlation_id",
        "ix_video_bulk_children_job_id",
        "ix_video_bulk_children_context_fingerprint",
    ):
        op.drop_index(name, table_name="video_bulk_children")
    for name in (
        "fk_video_bulk_child_job",
        "fk_video_bulk_child_preset",
        "fk_video_bulk_child_style",
        "fk_video_bulk_child_storyboard",
        "fk_video_bulk_child_script",
        "fk_video_bulk_child_brand",
    ):
        op.drop_constraint(name, "video_bulk_children", type_="foreignkey")
    for name in (
        "completed_at",
        "started_at",
        "failure_scenario",
        "retry_count",
        "recovery_state",
        "failure_category",
        "correlation_id",
        "job_id",
        "context_fingerprint",
        "source_media_ids_json",
        "preset_version",
        "preset_id",
        "style_version",
        "style_id",
        "storyboard_version",
        "storyboard_id",
        "script_version",
        "script_id",
        "output_ordinal",
        "brand_id",
    ):
        op.drop_column("video_bulk_children", name)
    op.drop_index(
        "ix_video_bulk_operations_preview_fingerprint", table_name="video_bulk_operations"
    )
    op.drop_index("ix_video_bulk_operations_plan_fingerprint", table_name="video_bulk_operations")
    op.drop_constraint(
        "fk_video_bulk_created_by_users", "video_bulk_operations", type_="foreignkey"
    )
    for name in (
        "preview_fingerprint",
        "completed_at",
        "started_at",
        "created_by",
        "cancelled_count",
        "stale_count",
        "failed_count",
        "retry_wait_count",
        "succeeded_count",
        "completed_count",
        "requested_child_count",
        "requested_product_count",
        "request_snapshot_json",
        "plan_fingerprint",
    ):
        op.drop_column("video_bulk_operations", name)
