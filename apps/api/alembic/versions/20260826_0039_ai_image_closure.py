"""Complete image review, comparison, content and classification metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260826_0039"
down_revision: str | None = "20260825_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_image_generations", sa.Column("content_artifact_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("ai_image_generations", sa.Column("content_artifact_version", sa.Integer()))
    op.add_column("ai_image_generations", sa.Column("headline", sa.String(240)))
    op.add_column("ai_image_generations", sa.Column("subheadline", sa.String(240)))
    op.add_column("ai_image_generations", sa.Column("cta", sa.String(120)))
    op.add_column("ai_image_generations", sa.Column("offer_text", sa.String(240)))
    op.create_foreign_key(
        "fk_ai_image_generation_content_artifact",
        "ai_image_generations",
        "generated_artifacts",
        ["content_artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ai_image_outputs",
        sa.Column(
            "asset_classification", sa.String(32), nullable=False, server_default="ai_generated"
        ),
    )
    op.add_column(
        "ai_image_outputs", sa.Column("content_artifact_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("ai_image_outputs", sa.Column("content_artifact_version", sa.Integer()))
    op.create_foreign_key(
        "fk_ai_image_output_content_artifact",
        "ai_image_outputs",
        "generated_artifacts",
        ["content_artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_image_output_content_artifact", "ai_image_outputs", type_="foreignkey"
    )
    for column in ("content_artifact_version", "content_artifact_id", "asset_classification"):
        op.drop_column("ai_image_outputs", column)
    op.drop_constraint(
        "fk_ai_image_generation_content_artifact", "ai_image_generations", type_="foreignkey"
    )
    for column in (
        "offer_text",
        "cta",
        "subheadline",
        "headline",
        "content_artifact_version",
        "content_artifact_id",
    ):
        op.drop_column("ai_image_generations", column)
