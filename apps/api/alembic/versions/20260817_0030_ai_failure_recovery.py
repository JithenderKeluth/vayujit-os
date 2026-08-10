"""Add durable AI failure, retry, and recovery metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260817_0030"
down_revision: str | None = "20260816_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_studio_generations", sa.Column("failure_category", sa.String(80)))
    op.add_column(
        "ai_studio_generations",
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_studio_generations",
        sa.Column(
            "recovery_actions_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "ai_studio_generations",
        sa.Column(
            "context_refresh_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_ai_studio_generations_failure_category", "ai_studio_generations", ["failure_category"]
    )
    for name, column in (
        ("failure_category", sa.String(80)),
        (
            "retryable",
            sa.Boolean(),
        ),
        ("recovery_actions_json", sa.JSON()),
        ("context_refresh_required", sa.Boolean()),
        ("retry_after_seconds", sa.Integer()),
        ("calculated_delay_seconds", sa.Integer()),
        ("applied_delay_seconds", sa.Integer()),
        ("next_retry_at", sa.DateTime(timezone=True)),
        ("checkpoint_fingerprint", sa.String(64)),
    ):
        op.add_column(
            "ai_studio_jobs",
            sa.Column(
                name,
                column,
                nullable=False if name == "retryable" else None,
                server_default=sa.false() if name == "retryable" else None,
            ),
        )
    op.create_index("ix_ai_studio_jobs_failure_category", "ai_studio_jobs", ["failure_category"])
    for name, column in (
        ("failure_category", sa.String(80)),
        ("calculated_delay_seconds", sa.Integer()),
        ("applied_delay_seconds", sa.Integer()),
        ("retry_after_seconds", sa.Integer()),
        ("checkpoint_fingerprint", sa.String(64)),
        ("correlation_id", sa.String(64)),
    ):
        op.add_column("ai_studio_job_attempts", sa.Column(name, column))


def downgrade() -> None:
    for name in (
        "correlation_id",
        "checkpoint_fingerprint",
        "retry_after_seconds",
        "applied_delay_seconds",
        "calculated_delay_seconds",
        "failure_category",
    ):
        op.drop_column("ai_studio_job_attempts", name)
    op.drop_index("ix_ai_studio_jobs_failure_category", table_name="ai_studio_jobs")
    for name in (
        "checkpoint_fingerprint",
        "next_retry_at",
        "applied_delay_seconds",
        "calculated_delay_seconds",
        "retry_after_seconds",
        "context_refresh_required",
        "recovery_actions_json",
        "retryable",
        "failure_category",
    ):
        op.drop_column("ai_studio_jobs", name)
    op.drop_index("ix_ai_studio_generations_failure_category", table_name="ai_studio_generations")
    for name in (
        "context_refresh_required",
        "recovery_actions_json",
        "retryable",
        "failure_category",
    ):
        op.drop_column("ai_studio_generations", name)
