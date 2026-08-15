"""Add normalized marketplace Video mappings and durable jobs."""

from collections.abc import Sequence

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260906_0054"
down_revision: str | None = "20260905_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketplace_video_mappings",
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column(
            "owner_id",
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column(
            "product_id",
            UUID(as_uuid=True),
            ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "account_id",
            UUID(as_uuid=True),
            ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "listing_id",
            UUID(as_uuid=True),
            ForeignKey("marketplace_listings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column("marketplace", String(30), nullable=False),
        Column(
            "video_generation_id",
            UUID(as_uuid=True),
            ForeignKey("video_generations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "video_output_id",
            UUID(as_uuid=True),
            ForeignKey("video_outputs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "video_media_id",
            UUID(as_uuid=True),
            ForeignKey("media_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column("video_version", Integer, nullable=False),
        Column("remote_video_id", String(200)),
        Column("attachment_state", String(40), nullable=False, server_default="pending"),
        Column("reconciliation_state", String(40), nullable=False, server_default="unknown"),
        Column("drift_state", String(40), nullable=False, server_default="none"),
        Column("readiness_fingerprint", String(64), nullable=False),
        Column("mutation_fingerprint", String(64), nullable=False),
        Column(
            "actor_id",
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column("correlation_id", String(64), nullable=False),
        Column("operation", String(30), nullable=False, server_default="attach"),
        Column("remote_state_json", JSONB, nullable=False, server_default="{}"),
        Column("last_reconciled_at", DateTime(timezone=True)),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint(
            "owner_id",
            "account_id",
            "listing_id",
            "video_output_id",
            name="uq_marketplace_video_mapping_exact",
        ),
        UniqueConstraint(
            "owner_id", "account_id", "remote_video_id", name="uq_marketplace_video_mapping_remote"
        ),
    )
    for name, column in (
        ("owner_id", "owner_id"),
        ("product_id", "product_id"),
        ("account_id", "account_id"),
        ("listing_id", "listing_id"),
        ("marketplace", "marketplace"),
        ("video_generation_id", "video_generation_id"),
        ("video_output_id", "video_output_id"),
        ("video_media_id", "video_media_id"),
        ("remote_video_id", "remote_video_id"),
        ("attachment_state", "attachment_state"),
        ("reconciliation_state", "reconciliation_state"),
        ("drift_state", "drift_state"),
        ("correlation_id", "correlation_id"),
    ):
        op.create_index(
            f"ix_marketplace_video_mappings_{name}", "marketplace_video_mappings", [column]
        )
    op.create_table(
        "marketplace_video_jobs",
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column(
            "owner_id",
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column(
            "mapping_id",
            UUID(as_uuid=True),
            ForeignKey("marketplace_video_mappings.id", ondelete="SET NULL"),
        ),
        Column(
            "product_id",
            UUID(as_uuid=True),
            ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "account_id",
            UUID(as_uuid=True),
            ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "listing_id",
            UUID(as_uuid=True),
            ForeignKey("marketplace_listings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column("marketplace", String(30), nullable=False),
        Column("operation", String(30), nullable=False),
        Column("idempotency_key", String(200), nullable=False),
        Column("state", String(30), nullable=False, server_default="pending"),
        Column("attempt_count", Integer, nullable=False, server_default="0"),
        Column("payload_json", JSONB, nullable=False, server_default="{}"),
        Column("correlation_id", String(64), nullable=False),
        Column("last_error_code", String(100)),
        Column("safe_error_message", String(500)),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("started_at", DateTime(timezone=True)),
        Column("completed_at", DateTime(timezone=True)),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_marketplace_video_job_idempotency"
        ),
    )
    for name, column in (
        ("owner_id", "owner_id"),
        ("mapping_id", "mapping_id"),
        ("product_id", "product_id"),
        ("account_id", "account_id"),
        ("listing_id", "listing_id"),
        ("marketplace", "marketplace"),
        ("state", "state"),
        ("correlation_id", "correlation_id"),
    ):
        op.create_index(f"ix_marketplace_video_jobs_{name}", "marketplace_video_jobs", [column])


def downgrade() -> None:
    for name in (
        "correlation_id",
        "state",
        "marketplace",
        "listing_id",
        "account_id",
        "product_id",
        "mapping_id",
        "owner_id",
    ):
        op.drop_index(f"ix_marketplace_video_jobs_{name}", table_name="marketplace_video_jobs")
    op.drop_table("marketplace_video_jobs")
    for name in (
        "correlation_id",
        "drift_state",
        "reconciliation_state",
        "attachment_state",
        "remote_video_id",
        "video_media_id",
        "video_output_id",
        "video_generation_id",
        "marketplace",
        "listing_id",
        "account_id",
        "product_id",
        "owner_id",
    ):
        op.drop_index(
            f"ix_marketplace_video_mappings_{name}", table_name="marketplace_video_mappings"
        )
    op.drop_table("marketplace_video_mappings")
