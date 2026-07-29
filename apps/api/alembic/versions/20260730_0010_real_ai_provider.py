"""Add real AI provider configuration, attempts, and usage."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260730_0010"
down_revision = "20260729_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_generation_requests", sa.Column("selected_model", sa.String(120)))
    op.add_column("ai_generation_requests", sa.Column("final_provider_key", sa.String(100)))
    op.add_column(
        "ai_generation_requests",
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_generation_requests", sa.Column("cancellation_requested_at", sa.DateTime(timezone=True))
    )
    op.add_column("ai_generation_requests", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ai_generation_requests",
        sa.Column("final_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("ai_generation_requests", sa.Column("total_latency_ms", sa.Integer()))
    op.add_column("ai_generation_requests", sa.Column("input_tokens", sa.Integer()))
    op.add_column("ai_generation_requests", sa.Column("output_tokens", sa.Integer()))
    op.add_column("ai_generation_requests", sa.Column("total_tokens", sa.Integer()))
    op.add_column("ai_generation_requests", sa.Column("estimated_total_cost", sa.Numeric(18, 8)))
    op.add_column("ai_generation_requests", sa.Column("cost_currency", sa.String(3)))
    op.create_table(
        "ai_provider_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("encrypted_api_key", sa.Text()),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("default_model", sa.String(120), nullable=False),
        sa.Column("manual_model_allowed", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("fallback_provider_key", sa.String(100)),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retry_attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("safe_validation_message", sa.String(500)),
        sa.Column("last_validation_latency_ms", sa.Integer()),
        sa.Column("last_successful_request_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "request_timeout_seconds BETWEEN 10 AND 120", name="ck_ai_provider_timeout"
        ),
        sa.CheckConstraint("max_retry_attempts BETWEEN 1 AND 5", name="ck_ai_provider_retries"),
        sa.UniqueConstraint("owner_id", "provider_key", name="uq_ai_provider_owner_key"),
    )
    op.create_index(
        "ix_ai_provider_configurations_owner_id", "ai_provider_configurations", ["owner_id"]
    )
    op.create_table(
        "ai_generation_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_generation_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("provider_request_id", sa.String(160)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("usage_source", sa.String(20), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(18, 8)),
        sa.Column("cost_currency", sa.String(3)),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("fallback", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("correlation_id", sa.String(64)),
        sa.UniqueConstraint(
            "generation_request_id", "attempt_number", name="uq_ai_generation_attempt_number"
        ),
    )
    op.create_index(
        "ix_ai_generation_attempts_generation_request_id",
        "ai_generation_attempts",
        ["generation_request_id"],
    )
    op.create_table(
        "ai_model_pricing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("model_pattern", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("input_cost_per_million_tokens", sa.Numeric(18, 8), nullable=False),
        sa.Column("output_cost_per_million_tokens", sa.Numeric(18, 8), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("source_note", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "provider_key",
            "model_pattern",
            "effective_from",
            name="uq_ai_model_pricing_effective",
        ),
    )
    op.create_index("ix_ai_model_pricing_owner_id", "ai_model_pricing", ["owner_id"])


def downgrade() -> None:
    op.drop_table("ai_model_pricing")
    op.drop_table("ai_generation_attempts")
    op.drop_table("ai_provider_configurations")
    for column in [
        "cost_currency",
        "estimated_total_cost",
        "total_tokens",
        "output_tokens",
        "input_tokens",
        "total_latency_ms",
        "final_attempt_count",
        "cancelled_at",
        "cancellation_requested_at",
        "fallback_used",
        "final_provider_key",
        "selected_model",
    ]:
        op.drop_column("ai_generation_requests", column)
