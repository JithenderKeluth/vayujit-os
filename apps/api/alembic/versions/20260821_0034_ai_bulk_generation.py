"""Add durable AI Studio bulk operations and outputs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260821_0034"
down_revision: str | None = "20260820_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_studio_bulk_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("brand_voice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_voice_version", sa.Integer(), nullable=True),
        sa.Column("preset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("preset_version", sa.Integer(), nullable=True),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
        sa.Column(
            "provider_key", sa.String(100), nullable=False, server_default="deterministic_mock_v1"
        ),
        sa.Column(
            "model", sa.String(120), nullable=False, server_default="studio-deterministic-v1"
        ),
        sa.Column("instructions_fingerprint", sa.String(64), nullable=True),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("channel_count", sa.Integer(), nullable=False),
        sa.Column("content_type_count", sa.Integer(), nullable=False),
        sa.Column("total_outputs", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column(
            "cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "completion_summary_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["brand_voice_id"], ["ai_brand_voices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["preset_id"], ["ai_generation_presets.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_bulk_operation_idempotency"),
    )
    op.create_index(
        "ix_ai_studio_bulk_operations_owner_id", "ai_studio_bulk_operations", ["owner_id"]
    )
    op.create_index("ix_ai_studio_bulk_operations_status", "ai_studio_bulk_operations", ["status"])
    op.create_index(
        "ix_ai_studio_bulk_operations_correlation_id",
        "ai_studio_bulk_operations",
        ["correlation_id"],
    )
    op.create_table(
        "ai_studio_bulk_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bulk_operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failure_category", sa.String(80), nullable=True),
        sa.Column("safe_error_message", sa.String(500), nullable=True),
        sa.Column(
            "cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("stale_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["bulk_operation_id"], ["ai_studio_bulk_operations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["ai_studio_generations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["ai_studio_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["generated_artifacts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("job_id", name="uq_ai_bulk_output_job"),
        sa.UniqueConstraint(
            "bulk_operation_id",
            "product_id",
            "channel",
            "content_type",
            "locale",
            name="uq_ai_bulk_output_identity",
        ),
    )
    for name, column in (
        ("bulk_operation_id", "bulk_operation_id"),
        ("owner_id", "owner_id"),
        ("product_id", "product_id"),
        ("generation_id", "generation_id"),
        ("artifact_id", "artifact_id"),
        ("status", "status"),
        ("failure_category", "failure_category"),
    ):
        op.create_index(f"ix_ai_studio_bulk_outputs_{name}", "ai_studio_bulk_outputs", [column])


def downgrade() -> None:
    for name in (
        "failure_category",
        "status",
        "artifact_id",
        "generation_id",
        "product_id",
        "owner_id",
        "bulk_operation_id",
    ):
        op.drop_index(f"ix_ai_studio_bulk_outputs_{name}", table_name="ai_studio_bulk_outputs")
    op.drop_table("ai_studio_bulk_outputs")
    for name in ("correlation_id", "status", "owner_id"):
        op.drop_index(
            f"ix_ai_studio_bulk_operations_{name}", table_name="ai_studio_bulk_operations"
        )
    op.drop_table("ai_studio_bulk_operations")
