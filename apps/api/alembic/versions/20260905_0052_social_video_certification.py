"""Complete Social Video field lineage, checkpoints, and metric identity."""

from collections.abc import Sequence

from sqlalchemy import JSON, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20260905_0052"
down_revision: str | None = "20260905_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("title", "description", "copy", "cta", "tags"):
        op.add_column(
            "social_posts",
            Column(
                f"{name}_artifact_id",
                UUID(as_uuid=True),
                ForeignKey("generated_artifacts.id", ondelete="SET NULL"),
            ),
        )
        op.add_column("social_posts", Column(f"{name}_artifact_version", Integer))
        op.create_index(
            f"ix_social_posts_{name}_artifact_id", "social_posts", [f"{name}_artifact_id"]
        )
    op.add_column("social_posts", Column("remote_checkpoint_json", JSON))
    for name, column_type in (
        ("product_id", UUID(as_uuid=True)),
        ("platform", String(24)),
        ("content_type", String(48)),
        ("video_output_id", UUID(as_uuid=True)),
        ("video_media_id", UUID(as_uuid=True)),
    ):
        op.add_column("social_metrics", Column(name, column_type))
        op.create_index(f"ix_social_metrics_{name}", "social_metrics", [name])


def downgrade() -> None:
    for name in ("video_media_id", "video_output_id", "content_type", "platform", "product_id"):
        op.drop_index(f"ix_social_metrics_{name}", table_name="social_metrics")
        op.drop_column("social_metrics", name)
    op.drop_column("social_posts", "remote_checkpoint_json")
    for name in ("tags", "cta", "copy", "description", "title"):
        op.drop_index(f"ix_social_posts_{name}_artifact_id", table_name="social_posts")
        op.drop_column("social_posts", f"{name}_artifact_version")
        op.drop_column("social_posts", f"{name}_artifact_id")
