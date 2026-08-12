"""Add owner-scoped social accounts, posts, and metrics."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260830_0043"
down_revision: str | None = "20260829_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(24), nullable=False),
        sa.Column("identity_type", sa.String(32), nullable=False, server_default="account"),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("remote_account_id", sa.String(200), nullable=False),
        sa.Column("environment", sa.String(24), nullable=False, server_default="local"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("capabilities_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("credential_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "owner_id", "platform", "remote_account_id", name="uq_social_account_remote"
        ),
        sa.CheckConstraint(
            "platform IN ('instagram','facebook','youtube')", name="ck_social_platform"
        ),
        sa.CheckConstraint(
            "validation_status IN ('unknown','valid','invalid')", name="ck_social_validation"
        ),
    )
    op.create_index("ix_social_accounts_owner_id", "social_accounts", ["owner_id"])
    op.create_index("ix_social_accounts_platform", "social_accounts", ["platform"])
    op.create_index("ix_social_accounts_enabled", "social_accounts", ["enabled"])
    op.create_index(
        "ix_social_accounts_validation_status", "social_accounts", ["validation_status"]
    )
    op.create_table(
        "social_posts",
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
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("social_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(24), nullable=False),
        sa.Column("content_type", sa.String(48), nullable=False),
        sa.Column(
            "content_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content_artifact_version", sa.Integer(), nullable=False),
        sa.Column("media_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hashtags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("cta_json", postgresql.JSONB(), nullable=True),
        sa.Column("destination_url", sa.String(2048), nullable=True),
        sa.Column("scheduled_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone_name", sa.String(100), nullable=True),
        sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("remote_publication_id", sa.String(200), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("preview_fingerprint", sa.String(64), nullable=True),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("safe_failure_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_social_post_idempotency"),
        sa.CheckConstraint(
            "platform IN ('instagram','facebook','youtube')", name="ck_social_post_platform"
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ("
            "'draft','pending_review','approved','scheduled','publishing','published','failed','cancelled')",
            name="ck_social_post_status",
        ),
    )
    for column in (
        "owner_id",
        "brand_id",
        "product_id",
        "account_id",
        "platform",
        "content_artifact_id",
        "scheduled_at_utc",
        "lifecycle_status",
        "remote_publication_id",
        "correlation_id",
    ):
        op.create_index(f"ix_social_posts_{column}", "social_posts", [column])
    op.create_table(
        "social_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("social_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(40), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("availability", sa.String(20), nullable=False, server_default="not_synced"),
        sa.Column("source", sa.String(30), nullable=False, server_default="synthetic_test_data"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("post_id", "metric_key", name="uq_social_metric_key"),
    )
    op.create_index("ix_social_metrics_owner_id", "social_metrics", ["owner_id"])
    op.create_index("ix_social_metrics_post_id", "social_metrics", ["post_id"])


def downgrade() -> None:
    op.drop_table("social_metrics")
    op.drop_table("social_posts")
    op.drop_table("social_accounts")
