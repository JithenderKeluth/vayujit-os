"""Add normalized Video channel handoffs and exact Social Video lineage."""

from collections.abc import Sequence

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260905_0049"
down_revision: str | None = "20260904_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_channel_handoffs",
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
        Column("channel", String(32), nullable=False),
        Column("target_type", String(32), nullable=False),
        Column("target_id", String(200)),
        Column("target_state_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("readiness_fingerprint", String(64), nullable=False),
        Column("handoff_fingerprint", String(64), nullable=False),
        Column(
            "actor_id",
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column("correlation_id", String(64), nullable=False),
        Column("idempotency_key", String(160), nullable=False),
        Column("state", String(32), nullable=False, server_default="previewed"),
        Column(
            "social_post_id", UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="SET NULL")
        ),
        Column(
            "marketplace_mapping_id",
            UUID(as_uuid=True),
            ForeignKey("marketplace_media_mappings.id", ondelete="SET NULL"),
        ),
        Column(
            "publishing_job_id",
            UUID(as_uuid=True),
            ForeignKey("publishing_jobs.id", ondelete="SET NULL"),
        ),
        Column("remote_id", String(200)),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_video_channel_handoffs_owner_id", "video_channel_handoffs", ["owner_id"])
    op.create_index(
        "ix_video_channel_handoffs_product_id", "video_channel_handoffs", ["product_id"]
    )
    op.create_index(
        "ix_video_channel_handoffs_video_generation_id",
        "video_channel_handoffs",
        ["video_generation_id"],
    )
    op.create_index(
        "ix_video_channel_handoffs_video_output_id", "video_channel_handoffs", ["video_output_id"]
    )
    op.create_index(
        "ix_video_channel_handoffs_video_media_id", "video_channel_handoffs", ["video_media_id"]
    )
    op.create_index("ix_video_channel_handoffs_channel", "video_channel_handoffs", ["channel"])
    op.create_index(
        "ix_video_channel_handoffs_correlation_id", "video_channel_handoffs", ["correlation_id"]
    )
    op.create_index("ix_video_channel_handoffs_state", "video_channel_handoffs", ["state"])
    op.create_unique_constraint(
        "uq_video_handoff_idempotency", "video_channel_handoffs", ["owner_id", "idempotency_key"]
    )

    op.add_column(
        "social_posts",
        Column(
            "video_generation_id",
            UUID(as_uuid=True),
            ForeignKey("video_generations.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "social_posts",
        Column(
            "video_output_id",
            UUID(as_uuid=True),
            ForeignKey("video_outputs.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "social_posts",
        Column(
            "video_media_id", UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL")
        ),
    )
    op.add_column("social_posts", Column("video_version", Integer))
    op.create_index("ix_social_posts_video_generation_id", "social_posts", ["video_generation_id"])
    op.create_index("ix_social_posts_video_output_id", "social_posts", ["video_output_id"])
    op.create_index("ix_social_posts_video_media_id", "social_posts", ["video_media_id"])


def downgrade() -> None:
    op.drop_index("ix_social_posts_video_media_id", table_name="social_posts")
    op.drop_index("ix_social_posts_video_output_id", table_name="social_posts")
    op.drop_index("ix_social_posts_video_generation_id", table_name="social_posts")
    op.drop_column("social_posts", "video_version")
    op.drop_column("social_posts", "video_media_id")
    op.drop_column("social_posts", "video_output_id")
    op.drop_column("social_posts", "video_generation_id")
    op.drop_constraint("uq_video_handoff_idempotency", "video_channel_handoffs", type_="unique")
    for name in (
        "state",
        "correlation_id",
        "channel",
        "video_media_id",
        "video_output_id",
        "video_generation_id",
        "product_id",
        "owner_id",
    ):
        op.drop_index(f"ix_video_channel_handoffs_{name}", table_name="video_channel_handoffs")
    op.drop_table("video_channel_handoffs")
