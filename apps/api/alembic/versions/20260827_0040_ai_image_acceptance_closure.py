"""Add image acceptance lifecycle metadata."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260827_0040"
down_revision = "20260826_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_image_outputs", sa.Column("alt_text", sa.String(length=500), nullable=True))
    op.add_column(
        "ai_image_outputs",
        sa.Column(
            "alt_text_status", sa.String(length=24), nullable=False, server_default="unreviewed"
        ),
    )
    op.add_column(
        "ai_image_outputs",
        sa.Column("alt_text_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "ai_image_outputs", sa.Column("alt_text_source", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "ai_image_outputs", sa.Column("alt_text_provider", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "ai_image_outputs",
        sa.Column("alt_text_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_image_outputs",
        sa.Column("alt_text_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_image_outputs",
        sa.Column("alt_text_approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_image_outputs_alt_text_approved_by",
        "ai_image_outputs",
        "users",
        ["alt_text_approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    bind = op.get_bind()
    mapping_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("marketplace_media_mappings")
    }
    if "image_output_id" not in mapping_columns:
        op.add_column(
            "marketplace_media_mappings",
            sa.Column("image_output_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    op.create_index(
        "ix_marketplace_media_mappings_image_output_id",
        "marketplace_media_mappings",
        ["image_output_id"],
    )
    op.create_foreign_key(
        "fk_marketplace_media_mappings_image_output_id",
        "marketplace_media_mappings",
        "ai_image_outputs",
        ["image_output_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("ai_studio_jobs", sa.Column("checkpoint_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "ai_studio_job_attempts", sa.Column("checkpoint_size_bytes", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ai_studio_job_attempts", "checkpoint_size_bytes")
    op.drop_column("ai_studio_jobs", "checkpoint_size_bytes")
    op.drop_constraint(
        "fk_marketplace_media_mappings_image_output_id",
        "marketplace_media_mappings",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_marketplace_media_mappings_image_output_id", table_name="marketplace_media_mappings"
    )
    op.drop_constraint(
        "fk_ai_image_outputs_alt_text_approved_by", "ai_image_outputs", type_="foreignkey"
    )
    for name in (
        "alt_text_approved_by",
        "alt_text_approved_at",
        "alt_text_updated_at",
        "alt_text_provider",
        "alt_text_source",
        "alt_text_version",
        "alt_text_status",
        "alt_text",
    ):
        op.drop_column("ai_image_outputs", name)
