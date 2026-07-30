"""Add mock publishing and execution history."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260728_0006"
down_revision = "20260728_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publishing_destinations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id")),
        sa.Column("connector_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("configuration_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "normalized_name", name="uq_destination_owner_name"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_destination_status"),
    )
    for column in ("owner_id", "brand_id", "connector_key", "status"):
        op.create_index(f"ix_publishing_destinations_{column}", "publishing_destinations", [column])
    op.create_table(
        "publishing_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False
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
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id"),
            nullable=False,
        ),
        sa.Column("connector_key", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("content_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("request_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("result_json", postgresql.JSONB()),
        sa.Column("external_reference", sa.String(200)),
        sa.Column("external_url", sa.String(500)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_execution_owner_idempotency"),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_execution_status",
        ),
    )
    for column in (
        "owner_id",
        "brand_id",
        "product_id",
        "artifact_id",
        "destination_id",
        "connector_key",
        "status",
    ):
        op.create_index(f"ix_publishing_executions_{column}", "publishing_executions", [column])
    op.create_table(
        "publishing_execution_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_executions.id"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("request_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("result_json", postgresql.JSONB()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("execution_id", "attempt_number", name="uq_attempt_execution_number"),
        sa.CheckConstraint("status IN ('running','succeeded','failed')", name="ck_attempt_status"),
    )
    op.create_index(
        "ix_publishing_execution_attempts_execution_id",
        "publishing_execution_attempts",
        ["execution_id"],
    )


def downgrade() -> None:
    op.drop_table("publishing_execution_attempts")
    op.drop_table("publishing_executions")
    op.drop_table("publishing_destinations")
