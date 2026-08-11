"""Add durable image bulk metadata to the shared AI bulk runtime."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260829_0042"
down_revision: str | None = "20260828_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_studio_bulk_operations",
        sa.Column("modality", sa.String(16), nullable=False, server_default="text"),
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_operation", sa.String(48), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations",
        sa.Column("image_style_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_style_version", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations",
        sa.Column("image_preset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_preset_version", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_width", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_height", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_aspect_ratio", sa.String(24), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("image_output_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations", sa.Column("source_strategy", sa.String(40), nullable=True)
    )
    op.add_column(
        "ai_studio_bulk_operations",
        sa.Column(
            "source_media_by_product_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "ai_studio_bulk_operations",
        sa.Column(
            "content_artifact_by_product_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_ai_studio_bulk_operations_modality", "ai_studio_bulk_operations", ["modality"]
    )

    op.add_column(
        "ai_studio_bulk_outputs",
        sa.Column("output_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("ai_studio_bulk_outputs", sa.Column("operation", sa.String(48), nullable=True))
    op.add_column(
        "ai_studio_bulk_outputs",
        sa.Column("image_output_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ai_studio_bulk_outputs",
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ai_studio_bulk_outputs",
        sa.Column(
            "source_media_ids_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_index(
        "ix_ai_studio_bulk_outputs_image_output_id", "ai_studio_bulk_outputs", ["image_output_id"]
    )
    op.create_index("ix_ai_studio_bulk_outputs_media_id", "ai_studio_bulk_outputs", ["media_id"])
    op.drop_constraint("uq_ai_bulk_output_identity", "ai_studio_bulk_outputs", type_="unique")
    op.create_unique_constraint(
        "uq_ai_bulk_output_identity",
        "ai_studio_bulk_outputs",
        ["bulk_operation_id", "product_id", "channel", "content_type", "locale", "output_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_ai_bulk_output_identity", "ai_studio_bulk_outputs", type_="unique")
    op.create_unique_constraint(
        "uq_ai_bulk_output_identity",
        "ai_studio_bulk_outputs",
        ["bulk_operation_id", "product_id", "channel", "content_type", "locale"],
    )
    for name in ("media_id", "image_output_id"):
        op.drop_index(f"ix_ai_studio_bulk_outputs_{name}", table_name="ai_studio_bulk_outputs")
    for name in (
        "source_media_ids_json",
        "media_id",
        "image_output_id",
        "operation",
        "output_index",
    ):
        op.drop_column("ai_studio_bulk_outputs", name)
    op.drop_index("ix_ai_studio_bulk_operations_modality", table_name="ai_studio_bulk_operations")
    for name in (
        "content_artifact_by_product_json",
        "source_media_by_product_json",
        "source_strategy",
        "image_output_count",
        "image_aspect_ratio",
        "image_height",
        "image_width",
        "image_preset_version",
        "image_preset_id",
        "image_style_version",
        "image_style_id",
        "image_operation",
        "modality",
    ):
        op.drop_column("ai_studio_bulk_operations", name)
