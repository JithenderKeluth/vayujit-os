"""Complete AI Video Studio Slice 2 lifecycle fields."""

from collections.abc import Sequence
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260904_0048"
down_revision: str | None = "20260903_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_scripts",
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
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=False),
        sa.Column("scenes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("on_screen_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("cta", sa.Text(), nullable=False, server_default=""),
        sa.Column("outro", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(1000), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "product_id", "name", "version", name="uq_video_script_version"
        ),
    )

    op.add_column(
        "video_projects",
        sa.Column("script_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "video_projects", sa.Column("script_artifact_version", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_video_project_script_artifact",
        "video_projects",
        "generated_artifacts",
        ["script_artifact_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "video_projects", sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("video_projects", sa.Column("script_version", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_video_project_script",
        "video_projects",
        "video_scripts",
        ["script_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "video_styles",
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
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("config_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "brand_id", "name", "version", name="uq_video_style_version"
        ),
    )
    op.create_table(
        "video_storyboards",
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
        sa.Column(
            "source_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("source_artifact_version", sa.Integer(), nullable=True),
        sa.Column("video_type", sa.String(50), nullable=False, server_default="product_showcase"),
        sa.Column("target_channel", sa.String(40), nullable=False, server_default="youtube"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
        sa.Column("aspect_ratio", sa.String(20), nullable=False, server_default="16:9"),
        sa.Column("resolution", sa.String(20), nullable=False, server_default="1280x720"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "product_id", "version", name="uq_video_storyboard_version"
        ),
    )

    for name, column in (
        (
            "target_duration_seconds",
            sa.Integer(),
        ),
        (
            "caption_defaults",
            postgresql.JSONB(),
        ),
        (
            "audio_defaults",
            postgresql.JSONB(),
        ),
        (
            "thumbnail_required",
            sa.Boolean(),
        ),
        (
            "style_id",
            postgresql.UUID(as_uuid=True),
        ),
        (
            "provider",
            sa.String(80),
        ),
        (
            "model",
            sa.String(80),
        ),
        (
            "guidance",
            sa.String(2000),
        ),
    ):
        defaults = {
            "target_duration_seconds": "10",
            "caption_defaults": "{}",
            "audio_defaults": "{}",
            "thumbnail_required": sa.false(),
            "provider": "deterministic_video_local",
            "model": "local-slideshow-v1",
        }
        op.add_column(
            "video_presets",
            sa.Column(
                name,
                column,
                nullable=name in {"guidance", "style_id"},
                server_default=cast(Any, defaults.get(name)),
            ),
        )
    op.create_foreign_key(
        "fk_video_preset_style",
        "video_presets",
        "video_styles",
        ["style_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "video_generations", sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("video_generations", sa.Column("script_version", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_video_generation_script",
        "video_generations",
        "video_scripts",
        ["script_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for name, target in (("storyboard_id", "video_storyboards"), ("style_id", "video_styles")):
        op.add_column(
            "video_generations", sa.Column(name, postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.add_column(
            "video_generations", sa.Column(f"{name[:-3]}version", sa.Integer(), nullable=True)
        )
        op.create_foreign_key(
            f"fk_video_generation_{name}",
            "video_generations",
            target,
            [name],
            ["id"],
            ondelete="RESTRICT",
        )
    for name, column in (
        ("context_fingerprint", sa.String(64)),
        ("parent_generation_id", postgresql.UUID(as_uuid=True)),
        ("regeneration_reason", sa.String(80)),
        ("rejection_feedback", sa.Text()),
    ):
        op.add_column("video_generations", sa.Column(name, cast(Any, column), nullable=True))
    op.create_foreign_key(
        "fk_video_generation_parent",
        "video_generations",
        "video_generations",
        ["parent_generation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for name, column in (
        ("storyboard_id", postgresql.UUID(as_uuid=True)),
        ("stable_key", sa.String(80)),
        ("visual_guidance", sa.Text()),
        ("background", sa.String(240)),
        ("cta", sa.String(240)),
        ("locale", sa.String(16)),
        ("version", sa.Integer()),
    ):
        op.add_column(
            "video_scenes",
            sa.Column(
                name,
                column,
                nullable=name in {"storyboard_id", "visual_guidance", "background", "cta"},
                server_default={"stable_key": "scene", "locale": "en-IN", "version": "1"}.get(name),
            ),
        )
    op.create_foreign_key(
        "fk_video_scene_storyboard",
        "video_scenes",
        "video_storyboards",
        ["storyboard_id"],
        ["id"],
        ondelete="CASCADE",
    )

    output_columns: tuple[tuple[str, Any], ...] = (
        ("container", sa.String(24)),
        ("video_stream_count", sa.Integer()),
        ("audio_stream_count", sa.Integer()),
        ("frame_rate", sa.Float()),
        ("aspect_ratio", sa.String(20)),
    )
    for name, column in output_columns:
        op.add_column("video_outputs", sa.Column(name, cast(Any, column), nullable=True))
    op.execute(
        "UPDATE video_outputs SET container='mp4', video_stream_count=1, "
        "audio_stream_count=0, aspect_ratio='16:9' WHERE container IS NULL"
    )
    for name in ("container", "video_stream_count", "audio_stream_count", "aspect_ratio"):
        op.alter_column("video_outputs", name, nullable=False)

    for name, column in (
        ("format", sa.String(12)),
        ("source_artifact_id", postgresql.UUID(as_uuid=True)),
        ("source_artifact_version", sa.Integer()),
        ("version", sa.Integer()),
    ):
        op.add_column(
            "video_caption_tracks",
            sa.Column(
                name,
                column,
                nullable=name in {"source_artifact_id", "source_artifact_version"},
                server_default={"format": "webvtt", "version": "1"}.get(name),
            ),
        )
    op.create_foreign_key(
        "fk_video_caption_artifact",
        "video_caption_tracks",
        "generated_artifacts",
        ["source_artifact_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    audio_columns: tuple[tuple[str, Any], ...] = (
        ("audio_mode", sa.String(40)),
        ("audio_media_id", postgresql.UUID(as_uuid=True)),
        ("audio_checksum", sa.String(64)),
        ("audio_mime_type", sa.String(80)),
        ("audio_duration_seconds", sa.Float()),
        ("audio_source_type", sa.String(40)),
        ("audio_lineage_created_at", sa.DateTime(timezone=True)),
        ("thumbnail_image_output_id", postgresql.UUID(as_uuid=True)),
        ("thumbnail_media_id", postgresql.UUID(as_uuid=True)),
        ("thumbnail_version", sa.Integer()),
        ("thumbnail_attached_at", sa.DateTime(timezone=True)),
    )
    for name, column in audio_columns:
        op.add_column("video_generations", sa.Column(name, cast(Any, column), nullable=True))
    op.create_table(
        "video_audio_attachments",
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
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
        ),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("mime_type", sa.String(80)),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("lineage_reference", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("video_audio_attachments")
    for name in (
        "thumbnail_attached_at",
        "thumbnail_version",
        "thumbnail_media_id",
        "thumbnail_image_output_id",
        "audio_lineage_created_at",
        "audio_source_type",
        "audio_duration_seconds",
        "audio_mime_type",
        "audio_checksum",
        "audio_media_id",
        "audio_mode",
    ):
        op.drop_column("video_generations", name)
    op.drop_constraint("fk_video_caption_artifact", "video_caption_tracks", type_="foreignkey")
    for name in ("version", "source_artifact_version", "source_artifact_id", "format"):
        op.drop_column("video_caption_tracks", name)
    for name in (
        "aspect_ratio",
        "frame_rate",
        "audio_stream_count",
        "video_stream_count",
        "container",
    ):
        op.drop_column("video_outputs", name)
    op.drop_constraint("fk_video_scene_storyboard", "video_scenes", type_="foreignkey")
    for name in (
        "version",
        "locale",
        "cta",
        "background",
        "visual_guidance",
        "stable_key",
        "storyboard_id",
    ):
        op.drop_column("video_scenes", name)
    op.drop_constraint("fk_video_generation_parent", "video_generations", type_="foreignkey")
    for name in (
        "rejection_feedback",
        "regeneration_reason",
        "parent_generation_id",
        "context_fingerprint",
    ):
        op.drop_column("video_generations", name)
    op.drop_constraint("fk_video_generation_script", "video_generations", type_="foreignkey")
    op.drop_column("video_generations", "script_version")
    op.drop_column("video_generations", "script_id")
    for name in ("style_id", "storyboard_id"):
        op.drop_constraint(f"fk_video_generation_{name}", "video_generations", type_="foreignkey")
        op.drop_column("video_generations", f"{name[:-3]}version")
        op.drop_column("video_generations", name)
    op.drop_constraint("fk_video_preset_style", "video_presets", type_="foreignkey")
    for name in (
        "guidance",
        "model",
        "provider",
        "style_id",
        "thumbnail_required",
        "audio_defaults",
        "caption_defaults",
        "target_duration_seconds",
    ):
        op.drop_column("video_presets", name)
    op.drop_constraint("fk_video_project_script", "video_projects", type_="foreignkey")
    op.drop_column("video_projects", "script_version")
    op.drop_column("video_projects", "script_id")
    op.drop_constraint("fk_video_project_script_artifact", "video_projects", type_="foreignkey")
    op.drop_column("video_projects", "script_artifact_version")
    op.drop_column("video_projects", "script_artifact_id")
    op.drop_table("video_storyboards")
    op.drop_table("video_scripts")
    op.drop_table("video_styles")
