from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class VideoBulkOperation(Base):
    __tablename__ = "video_bulk_operations"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_video_bulk_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160))
    product_ids_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    video_types_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    targets_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    total_children: Mapped[int] = mapped_column(Integer)
    plan_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    request_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    requested_product_count: Mapped[int] = mapped_column(Integer, default=0)
    requested_child_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_wait_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    stale_count: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preview_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoBulkChild(Base):
    __tablename__ = "video_bulk_children"
    __table_args__ = (UniqueConstraint("bulk_id", "child_key", name="uq_video_bulk_child_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bulk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_bulk_operations.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), index=True
    )
    video_type: Mapped[str] = mapped_column(String(50))
    target_channel: Mapped[str] = mapped_column(String(40))
    child_key: Mapped[str] = mapped_column(String(220))
    output_ordinal: Mapped[int] = mapped_column(Integer, default=0)
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_scripts.id", ondelete="SET NULL")
    )
    script_version: Mapped[int | None] = mapped_column(Integer)
    storyboard_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_storyboards.id", ondelete="SET NULL")
    )
    storyboard_version: Mapped[int | None] = mapped_column(Integer)
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_styles.id", ondelete="SET NULL")
    )
    style_version: Mapped[int | None] = mapped_column(Integer)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_presets.id", ondelete="SET NULL")
    )
    preset_version: Mapped[int | None] = mapped_column(Integer)
    source_media_ids_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    context_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_jobs.id", ondelete="SET NULL"), index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    failure_category: Mapped[str | None] = mapped_column(String(40))
    recovery_state: Mapped[str | None] = mapped_column(String(40))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_scenario: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="SET NULL")
    )
    output_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_outputs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
