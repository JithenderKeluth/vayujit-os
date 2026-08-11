"""Add normalized AI Image Studio records backed by AI Studio jobs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260824_0037"
down_revision: str | None = "20260823_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.Column:
    return sa.Column(postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"))


def upgrade() -> None:
    op.create_table(
        "ai_image_styles",
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
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("background_preference", sa.String(120)),
        sa.Column("photography_style", sa.String(240)),
        sa.Column("lighting", sa.String(160)),
        sa.Column("mood", sa.String(160)),
        sa.Column("composition", sa.String(240)),
        sa.Column(
            "colors_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "environments_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "prohibited_treatments_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("logo_guidance", sa.String(500)),
        sa.Column(
            "marketplace_constraints_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("guidance", sa.String(2000)),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "brand_id", "name", "version", name="uq_ai_image_style_version"
        ),
    )
    op.create_table(
        "ai_image_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("operation", sa.String(48), nullable=False),
        sa.Column("channel", sa.String(48)),
        sa.Column(
            "rules_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", "version", name="uq_ai_image_preset_version"),
    )
    op.create_table(
        "ai_image_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_studio_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
            nullable=False,
        ),
        sa.Column("operation", sa.String(48), nullable=False),
        sa.Column("channel", sa.String(48), nullable=False),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "style_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_image_styles.id", ondelete="SET NULL"),
        ),
        sa.Column("style_version", sa.Integer()),
        sa.Column("requested_width", sa.Integer(), nullable=False),
        sa.Column("requested_height", sa.Integer(), nullable=False),
        sa.Column("aspect_ratio", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("generation_id", name="uq_ai_image_generation_studio"),
    )
    op.create_table(
        "ai_image_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_image_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_studio_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_media_ids_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "parent_output_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_image_outputs.id", ondelete="SET NULL"),
        ),
        sa.Column("operation", sa.String(48), nullable=False),
        sa.Column("channel", sa.String(48), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("requested_width", sa.Integer(), nullable=False),
        sa.Column("requested_height", sa.Integer(), nullable=False),
        sa.Column("actual_width", sa.Integer()),
        sa.Column("actual_height", sa.Integer()),
        sa.Column("mime_type", sa.String(40)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "provider_metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "usage_metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("alt_text_suggestion", sa.String(500)),
        sa.Column("approval_feedback", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("job_id", name="uq_ai_image_output_job"),
    )


def downgrade() -> None:
    op.drop_table("ai_image_outputs")
    op.drop_table("ai_image_generations")
    op.drop_table("ai_image_presets")
    op.drop_table("ai_image_styles")
