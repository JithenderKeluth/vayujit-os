"""Normalized AI image records backed by the shared AI Studio job runtime."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.core.database import Base


class AIImageStyle(Base):
    __tablename__ = "ai_image_styles"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "brand_id", "name", "version", name="uq_ai_image_style_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    background_preference: Mapped[str | None] = mapped_column(String(120))
    photography_style: Mapped[str | None] = mapped_column(String(240))
    lighting: Mapped[str | None] = mapped_column(String(160))
    mood: Mapped[str | None] = mapped_column(String(160))
    composition: Mapped[str | None] = mapped_column(String(240))
    colors_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    environments_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    prohibited_treatments_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    logo_guidance: Mapped[str | None] = mapped_column(String(500))
    marketplace_constraints_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    guidance: Mapped[str | None] = mapped_column(String(2000))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIImagePreset(Base):
    __tablename__ = "ai_image_presets"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", "version", name="uq_ai_image_preset_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    operation: Mapped[str] = mapped_column(String(48))
    channel: Mapped[str | None] = mapped_column(String(48))
    rules_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIImageGeneration(Base):
    __tablename__ = "ai_image_generations"
    __table_args__ = (UniqueConstraint("generation_id", name="uq_ai_image_generation_studio"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_generations.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    operation: Mapped[str] = mapped_column(String(48))
    channel: Mapped[str] = mapped_column(String(48))
    context_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_styles.id", ondelete="SET NULL")
    )
    style_version: Mapped[int | None] = mapped_column(Integer)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_presets.id", ondelete="SET NULL")
    )
    preset_version: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(100), default="deterministic_mock_v1")
    model: Mapped[str] = mapped_column(String(120), default="image-deterministic-v1")
    locale: Mapped[str] = mapped_column(String(24), default="en-IN")
    content_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL")
    )
    content_artifact_version: Mapped[int | None] = mapped_column(Integer)
    headline: Mapped[str | None] = mapped_column(String(240))
    subheadline: Mapped[str | None] = mapped_column(String(240))
    cta: Mapped[str | None] = mapped_column(String(120))
    offer_text: Mapped[str | None] = mapped_column(String(240))
    requested_width: Mapped[int] = mapped_column(Integer)
    requested_height: Mapped[int] = mapped_column(Integer)
    aspect_ratio: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIImageOutput(Base):
    __tablename__ = "ai_image_outputs"
    __table_args__ = (UniqueConstraint("job_id", name="uq_ai_image_output_job"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_generations.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_jobs.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    source_media_ids_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), index=True
    )
    parent_output_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_outputs.id", ondelete="SET NULL")
    )
    parent_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_styles.id", ondelete="SET NULL")
    )
    style_version: Mapped[int | None] = mapped_column(Integer)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_image_presets.id", ondelete="SET NULL")
    )
    preset_version: Mapped[int | None] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(24), default="en-IN")
    regeneration_reason: Mapped[str | None] = mapped_column(String(64))
    rejection_category: Mapped[str | None] = mapped_column(String(64))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_correlation_id: Mapped[str | None] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(48))
    channel: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    requested_width: Mapped[int] = mapped_column(Integer)
    requested_height: Mapped[int] = mapped_column(Integer)
    actual_width: Mapped[int | None] = mapped_column(Integer)
    actual_height: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(40))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    context_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    provider_metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    usage_metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    asset_classification: Mapped[str] = mapped_column(String(32), default="ai_generated")
    content_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL")
    )
    content_artifact_version: Mapped[int | None] = mapped_column(Integer)
    alt_text_suggestion: Mapped[str | None] = mapped_column(String(500))
    alt_text: Mapped[str | None] = mapped_column(String(500))
    alt_text_status: Mapped[str] = mapped_column(String(24), default="unreviewed")
    alt_text_version: Mapped[int] = mapped_column(Integer, default=1)
    alt_text_source: Mapped[str | None] = mapped_column(String(40))
    alt_text_provider: Mapped[str | None] = mapped_column(String(120))
    alt_text_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alt_text_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alt_text_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    approval_feedback: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# The image runtime intentionally uses the existing durable AI job table/lease worker.
AIImageJob = AIStudioJob
