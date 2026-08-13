"""Create normalized AI Video Studio foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260903_0047"
down_revision: str | None = "20260902_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_projects",
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
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "video_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("video_type", sa.String(50), nullable=False),
        sa.Column("target_channel", sa.String(40), nullable=False),
        sa.Column("aspect_ratio", sa.String(20), nullable=False),
        sa.Column("resolution", sa.String(20), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("scene_limit", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", "version", name="uq_video_preset_version"),
    )
    op.create_table(
        "video_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_projects.id", ondelete="CASCADE"),
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
        sa.Column(
            "source_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("source_artifact_version", sa.Integer(), nullable=True),
        sa.Column(
            "preset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_presets.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("preset_version", sa.Integer(), nullable=True),
        sa.Column("video_type", sa.String(50), nullable=False),
        sa.Column("target_channel", sa.String(40), nullable=False),
        sa.Column("aspect_ratio", sa.String(20), nullable=False),
        sa.Column("resolution", sa.String(20), nullable=False),
        sa.Column("frame_rate", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("source_media_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("storyboard_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("checkpoint_json", postgresql.JSONB(), nullable=True),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("safe_error_message", sa.String(500), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_video_generation_idempotency"),
    )
    op.create_table(
        "video_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("generation_id", name="uq_video_output_generation"),
    )
    op.create_table(
        "video_scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scene_order", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "source_media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("scene_text", sa.Text(), nullable=True),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("transition", sa.String(40), nullable=False, server_default="cut"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.UniqueConstraint("generation_id", "scene_order", name="uq_video_scene_order"),
    )
    op.create_table(
        "video_caption_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("caption_text", sa.Text(), nullable=False),
        sa.Column("timing_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("approval_state", sa.String(24), nullable=False, server_default="pending_review"),
    )
    op.create_table(
        "video_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_generations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "video_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_generations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("modality", sa.String(20), nullable=False, server_default="video"),
        sa.Column("provider_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_status", sa.String(32), nullable=False, server_default="unavailable"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table, col in [
        ("video_projects", "owner_id"),
        ("video_projects", "product_id"),
        ("video_presets", "owner_id"),
        ("video_generations", "owner_id"),
        ("video_generations", "product_id"),
        ("video_generations", "status"),
        ("video_generations", "available_at"),
        ("video_outputs", "owner_id"),
        ("video_outputs", "generation_id"),
    ]:
        op.create_index(f"ix_{table}_{col}", table, [col])


def downgrade() -> None:
    for table in (
        "video_usage",
        "video_approvals",
        "video_caption_tracks",
        "video_scenes",
        "video_outputs",
        "video_generations",
        "video_presets",
        "video_projects",
    ):
        op.drop_table(table)
