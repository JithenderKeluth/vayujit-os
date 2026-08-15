"""Persist exact Social video metadata, thumbnail, and caption lineage."""

from collections.abc import Sequence

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20260905_0051"
down_revision: str | None = "20260905_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "social_posts",
        Column(
            "metadata_artifact_id",
            UUID(as_uuid=True),
            ForeignKey("generated_artifacts.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("social_posts", Column("metadata_artifact_version", Integer))
    op.add_column(
        "social_posts",
        Column(
            "thumbnail_output_id",
            UUID(as_uuid=True),
            ForeignKey("ai_image_outputs.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "social_posts",
        Column(
            "thumbnail_media_id",
            UUID(as_uuid=True),
            ForeignKey("media_assets.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("social_posts", Column("thumbnail_version", Integer))
    op.add_column(
        "social_posts",
        Column(
            "caption_track_id",
            UUID(as_uuid=True),
            ForeignKey("video_caption_tracks.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("social_posts", Column("caption_version", Integer))
    for column in (
        "metadata_artifact_id",
        "thumbnail_output_id",
        "thumbnail_media_id",
        "caption_track_id",
    ):
        op.create_index(f"ix_social_posts_{column}", "social_posts", [column])


def downgrade() -> None:
    for column in (
        "caption_track_id",
        "thumbnail_media_id",
        "thumbnail_output_id",
        "metadata_artifact_id",
    ):
        op.drop_index(f"ix_social_posts_{column}", table_name="social_posts")
    for column in (
        "caption_version",
        "caption_track_id",
        "thumbnail_version",
        "thumbnail_media_id",
        "thumbnail_output_id",
        "metadata_artifact_version",
        "metadata_artifact_id",
    ):
        op.drop_column("social_posts", column)
