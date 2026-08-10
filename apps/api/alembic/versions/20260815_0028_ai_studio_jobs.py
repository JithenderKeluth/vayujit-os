"""Add durable AI Studio jobs and attempt history."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260815_0028"
down_revision: str | None = "20260814_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_brand_voices",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_brand_voices", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "ai_generation_presets",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_generation_presets", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "ai_generation_presets",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "ai_studio_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_studio_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("brand_voice_version", sa.Integer(), nullable=True),
        sa.Column("preset_version", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("user_instruction_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="queued"),
        sa.Column(
            "payload_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(80), nullable=True),
        sa.Column("safe_error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_studio_job_idempotency"),
    )
    for name, cols in {
        "owner_id": ["owner_id"],
        "generation_id": ["generation_id"],
        "product_id": ["product_id"],
        "job_type": ["job_type"],
        "context_fingerprint": ["context_fingerprint"],
        "state": ["state"],
        "available_at": ["available_at"],
        "lease_owner": ["lease_owner"],
        "lease_expires_at": ["lease_expires_at"],
        "correlation_id": ["correlation_id"],
        "artifact_id": ["artifact_id"],
    }.items():
        op.create_index(f"ix_ai_studio_jobs_{name}", "ai_studio_jobs", cols)
    op.create_table(
        "ai_studio_job_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_studio_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(160), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("safe_error_message", sa.String(500), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("provider_request_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_ai_studio_job_attempt_number"),
    )
    op.create_index("ix_ai_studio_job_attempts_job_id", "ai_studio_job_attempts", ["job_id"])


def downgrade() -> None:
    op.drop_column("ai_generation_presets", "archived_at")
    op.drop_column("ai_generation_presets", "is_default")
    op.drop_column("ai_generation_presets", "archived")
    op.drop_column("ai_brand_voices", "archived_at")
    op.drop_column("ai_brand_voices", "archived")
    op.drop_index("ix_ai_studio_job_attempts_job_id", table_name="ai_studio_job_attempts")
    op.drop_table("ai_studio_job_attempts")
    for name in (
        "artifact_id",
        "correlation_id",
        "lease_expires_at",
        "lease_owner",
        "available_at",
        "state",
        "context_fingerprint",
        "job_type",
        "product_id",
        "generation_id",
        "owner_id",
    ):
        op.drop_index(f"ix_ai_studio_jobs_{name}", table_name="ai_studio_jobs")
    op.drop_table("ai_studio_jobs")
