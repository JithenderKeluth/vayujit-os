"""Normalized owner-scoped AI Video Studio records."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

VIDEO_TYPES = (
    "product_showcase",
    "slideshow",
    "marketplace_product_video",
    "instagram_reel",
    "facebook_reel",
    "instagram_story",
    "facebook_story",
    "youtube_video",
    "youtube_short",
    "promotional_video",
    "explainer_video",
    "product_demo",
    "testimonial_style",
    "generic_social_video",
)
VIDEO_STATUSES = (
    "queued",
    "generating",
    "rendering",
    "validating",
    "needs_review",
    "retry_wait",
    "succeeded",
    "failed",
    "cancelled",
    "stale",
)


class VideoProject(Base):
    __tablename__ = "video_projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    script_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT")
    )
    script_artifact_version: Mapped[int | None] = mapped_column(Integer)
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_scripts.id", ondelete="RESTRICT")
    )
    script_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoScript(Base):
    __tablename__ = "video_scripts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "product_id", "name", "version", name="uq_video_script_version"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    hook: Mapped[str] = mapped_column(Text)
    introduction: Mapped[str] = mapped_column(Text)
    scenes: Mapped[list[object]] = mapped_column(JSONB, default=list)
    narration: Mapped[str] = mapped_column(Text)
    on_screen_text: Mapped[str] = mapped_column(Text)
    cta: Mapped[str] = mapped_column(Text)
    outro: Mapped[str] = mapped_column(Text)
    target_duration_seconds: Mapped[int] = mapped_column(Integer, default=30)
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoPreset(Base):
    __tablename__ = "video_presets"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", "version", name="uq_video_preset_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    video_type: Mapped[str] = mapped_column(String(50))
    target_channel: Mapped[str] = mapped_column(String(40))
    aspect_ratio: Mapped[str] = mapped_column(String(20))
    resolution: Mapped[str] = mapped_column(String(20))
    target_duration_seconds: Mapped[int] = mapped_column(Integer, default=10)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, default=60)
    scene_limit: Mapped[int] = mapped_column(Integer, default=12)
    caption_defaults: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    audio_defaults: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    thumbnail_required: Mapped[bool] = mapped_column(Boolean, default=False)
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_styles.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(80), default="deterministic_video_local")
    model: Mapped[str] = mapped_column(String(80), default="local-slideshow-v1")
    guidance: Mapped[str | None] = mapped_column(String(2000))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoStoryboard(Base):
    __tablename__ = "video_storyboards"
    __table_args__ = (
        UniqueConstraint("owner_id", "product_id", "version", name="uq_video_storyboard_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT")
    )
    source_artifact_version: Mapped[int | None] = mapped_column(Integer)
    video_type: Mapped[str] = mapped_column(String(50), default="product_showcase")
    target_channel: Mapped[str] = mapped_column(String(40), default="youtube")
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9")
    resolution: Mapped[str] = mapped_column(String(20), default="1280x720")
    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    context_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoStyle(Base):
    __tablename__ = "video_styles"
    __table_args__ = (
        UniqueConstraint("owner_id", "brand_id", "name", "version", name="uq_video_style_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    config_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoGeneration(Base):
    __tablename__ = "video_generations"
    __table_args__ = (
        CheckConstraint(
            "video_type IN (" + ",".join(f"'{value}'" for value in VIDEO_TYPES) + ")",
            name="ck_video_type",
        ),
        CheckConstraint(
            "status IN (" + ",".join(f"'{value}'" for value in VIDEO_STATUSES) + ")",
            name="ck_video_status",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_video_generation_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_projects.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT")
    )
    source_artifact_version: Mapped[int | None] = mapped_column(Integer)
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_scripts.id", ondelete="RESTRICT")
    )
    script_version: Mapped[int | None] = mapped_column(Integer)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_presets.id", ondelete="RESTRICT")
    )
    preset_version: Mapped[int | None] = mapped_column(Integer)
    storyboard_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_storyboards.id", ondelete="RESTRICT")
    )
    storyboard_version: Mapped[int | None] = mapped_column(Integer)
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_styles.id", ondelete="RESTRICT")
    )
    style_version: Mapped[int | None] = mapped_column(Integer)
    video_type: Mapped[str] = mapped_column(String(50))
    target_channel: Mapped[str] = mapped_column(String(40))
    aspect_ratio: Mapped[str] = mapped_column(String(20))
    resolution: Mapped[str] = mapped_column(String(20))
    frame_rate: Mapped[int] = mapped_column(Integer, default=24)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=10)
    provider_key: Mapped[str] = mapped_column(String(80), default="deterministic_video_local")
    model: Mapped[str] = mapped_column(String(80), default="local-slideshow-v1")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    source_media_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    storyboard_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    context_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_generation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="SET NULL")
    )
    regeneration_reason: Mapped[str | None] = mapped_column(String(80))
    rejection_feedback: Mapped[str | None] = mapped_column(Text)
    checkpoint_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audio_mode: Mapped[str] = mapped_column(String(40), default="none")
    audio_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    audio_checksum: Mapped[str | None] = mapped_column(String(64))
    audio_mime_type: Mapped[str | None] = mapped_column(String(80))
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float)
    audio_source_type: Mapped[str | None] = mapped_column(String(40))
    audio_lineage_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    thumbnail_image_output_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_outputs.id", ondelete="RESTRICT")
    )
    thumbnail_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    thumbnail_version: Mapped[int | None] = mapped_column(Integer)
    thumbnail_attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VideoOutput(Base):
    __tablename__ = "video_outputs"
    __table_args__ = (UniqueConstraint("generation_id", name="uq_video_output_generation"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), unique=True
    )
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(40), default="video/mp4")
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    container: Mapped[str] = mapped_column(String(24), default="mp4")
    video_stream_count: Mapped[int] = mapped_column(Integer, default=1)
    audio_stream_count: Mapped[int] = mapped_column(Integer, default=0)
    frame_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9")
    status: Mapped[str] = mapped_column(String(24), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoScene(Base):
    __tablename__ = "video_scenes"
    __table_args__ = (
        UniqueConstraint("generation_id", "scene_order", name="uq_video_scene_order"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="CASCADE"), index=True
    )
    storyboard_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_storyboards.id", ondelete="CASCADE"), index=True
    )
    stable_key: Mapped[str] = mapped_column(String(80), default="scene")
    scene_order: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=3)
    source_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    scene_text: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    transition: Mapped[str] = mapped_column(String(40), default="cut")
    visual_guidance: Mapped[str | None] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(String(240))
    cta: Mapped[str | None] = mapped_column(String(240))
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft")


class VideoCaptionTrack(Base):
    __tablename__ = "video_caption_tracks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="CASCADE"), index=True
    )
    locale: Mapped[str] = mapped_column(String(16))
    caption_text: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(12), default="webvtt")
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT")
    )
    source_artifact_version: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    timing_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    approval_state: Mapped[str] = mapped_column(String(24), default="pending_review")


class VideoApproval(Base):
    __tablename__ = "video_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="CASCADE"), unique=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(String(24), default="pending_review")
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoAudioAttachment(Base):
    __tablename__ = "video_audio_attachments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="CASCADE"), unique=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(40))
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    mime_type: Mapped[str | None] = mapped_column(String(80))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String(40))
    lineage_reference: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoUsage(Base):
    __tablename__ = "video_usage"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="CASCADE"), unique=True
    )
    modality: Mapped[str] = mapped_column(String(20), default="video")
    provider_calls: Mapped[int] = mapped_column(Integer, default=0)
    output_bytes: Mapped[int] = mapped_column(Integer, default=0)
    cost_status: Mapped[str] = mapped_column(String(32), default="unavailable")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
