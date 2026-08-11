"""Complete AI image review, lineage, and exact handoff metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260825_0038"
down_revision: str | None = "20260824_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_image_generations", sa.Column("preset_id", postgresql.UUID(as_uuid=True)))
    op.add_column("ai_image_generations", sa.Column("preset_version", sa.Integer()))
    op.add_column(
        "ai_image_generations",
        sa.Column(
            "provider", sa.String(100), nullable=False, server_default="deterministic_mock_v1"
        ),
    )
    op.add_column(
        "ai_image_generations",
        sa.Column("model", sa.String(120), nullable=False, server_default="image-deterministic-v1"),
    )
    op.add_column(
        "ai_image_generations",
        sa.Column("locale", sa.String(24), nullable=False, server_default="en-IN"),
    )
    op.create_foreign_key(
        "fk_ai_image_generation_preset",
        "ai_image_generations",
        "ai_image_presets",
        ["preset_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("ai_image_outputs", sa.Column("parent_media_id", postgresql.UUID(as_uuid=True)))
    op.add_column("ai_image_outputs", sa.Column("brand_id", postgresql.UUID(as_uuid=True)))
    op.add_column("ai_image_outputs", sa.Column("style_id", postgresql.UUID(as_uuid=True)))
    op.add_column("ai_image_outputs", sa.Column("style_version", sa.Integer()))
    op.add_column("ai_image_outputs", sa.Column("preset_id", postgresql.UUID(as_uuid=True)))
    op.add_column("ai_image_outputs", sa.Column("preset_version", sa.Integer()))
    op.add_column(
        "ai_image_outputs",
        sa.Column("locale", sa.String(24), nullable=False, server_default="en-IN"),
    )
    op.add_column("ai_image_outputs", sa.Column("regeneration_reason", sa.String(64)))
    op.add_column("ai_image_outputs", sa.Column("rejection_category", sa.String(64)))
    op.add_column("ai_image_outputs", sa.Column("approved_by", postgresql.UUID(as_uuid=True)))
    op.add_column("ai_image_outputs", sa.Column("decision_correlation_id", sa.String(64)))
    op.create_foreign_key(
        "fk_ai_image_output_parent_media",
        "ai_image_outputs",
        "media_assets",
        ["parent_media_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_image_output_brand",
        "ai_image_outputs",
        "brands",
        ["brand_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ai_image_output_style",
        "ai_image_outputs",
        "ai_image_styles",
        ["style_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_image_output_preset",
        "ai_image_outputs",
        "ai_image_presets",
        ["preset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_image_output_approver",
        "ai_image_outputs",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE ai_image_outputs o SET brand_id = g.brand_id "
        "FROM ai_image_generations g WHERE o.generation_id = g.id"
    )
    op.alter_column("ai_image_outputs", "brand_id", nullable=False)

    op.add_column(
        "campaign_activities", sa.Column("image_output_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("campaign_activities", sa.Column("image_media_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_campaign_activity_image_output",
        "campaign_activities",
        "ai_image_outputs",
        ["image_output_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_campaign_activity_image_media",
        "campaign_activities",
        "media_assets",
        ["image_media_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_campaign_activity_image_media", "campaign_activities", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_campaign_activity_image_output", "campaign_activities", type_="foreignkey"
    )
    op.drop_column("campaign_activities", "image_media_id")
    op.drop_column("campaign_activities", "image_output_id")
    op.drop_constraint("fk_ai_image_output_approver", "ai_image_outputs", type_="foreignkey")
    op.drop_constraint("fk_ai_image_output_preset", "ai_image_outputs", type_="foreignkey")
    op.drop_constraint("fk_ai_image_output_style", "ai_image_outputs", type_="foreignkey")
    op.drop_constraint("fk_ai_image_output_brand", "ai_image_outputs", type_="foreignkey")
    op.drop_constraint("fk_ai_image_output_parent_media", "ai_image_outputs", type_="foreignkey")
    for column in (
        "decision_correlation_id",
        "approved_by",
        "rejection_category",
        "regeneration_reason",
        "locale",
        "preset_version",
        "preset_id",
        "style_version",
        "style_id",
        "brand_id",
        "parent_media_id",
    ):
        op.drop_column("ai_image_outputs", column)
    op.drop_constraint("fk_ai_image_generation_preset", "ai_image_generations", type_="foreignkey")
    for column in ("locale", "model", "provider", "preset_version", "preset_id"):
        op.drop_column("ai_image_generations", column)
