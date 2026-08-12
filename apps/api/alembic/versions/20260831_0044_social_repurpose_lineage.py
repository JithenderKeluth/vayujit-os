"""Persist Social repurposing lineage metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260831_0044"
down_revision: str | None = "20260830_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "social_posts",
        sa.Column(
            "source_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("social_posts", sa.Column("source_artifact_version", sa.Integer(), nullable=True))
    op.add_column("social_posts", sa.Column("generation_reason", sa.String(40), nullable=True))
    op.create_index("ix_social_posts_source_artifact_id", "social_posts", ["source_artifact_id"])


def downgrade() -> None:
    op.drop_index("ix_social_posts_source_artifact_id", table_name="social_posts")
    op.drop_column("social_posts", "generation_reason")
    op.drop_column("social_posts", "source_artifact_version")
    op.drop_column("social_posts", "source_artifact_id")
