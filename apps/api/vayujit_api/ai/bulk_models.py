"""Durable bulk AI generation parent and logical output records."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class AIStudioBulkOperation(Base):
    __tablename__ = "ai_studio_bulk_operations"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_bulk_operation_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(160))
    brand_voice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_brand_voices.id", ondelete="SET NULL")
    )
    brand_voice_version: Mapped[int | None] = mapped_column(Integer)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_generation_presets.id", ondelete="SET NULL")
    )
    preset_version: Mapped[int | None] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    provider_key: Mapped[str] = mapped_column(String(100), default="deterministic_mock_v1")
    model: Mapped[str] = mapped_column(String(120), default="studio-deterministic-v1")
    instructions_fingerprint: Mapped[str | None] = mapped_column(String(64))
    product_count: Mapped[int] = mapped_column(Integer)
    channel_count: Mapped[int] = mapped_column(Integer)
    content_type_count: Mapped[int] = mapped_column(Integer)
    total_outputs: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIStudioBulkOutput(Base):
    __tablename__ = "ai_studio_bulk_outputs"
    __table_args__ = (
        UniqueConstraint(
            "bulk_operation_id",
            "product_id",
            "channel",
            "content_type",
            "locale",
            name="uq_ai_bulk_output_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bulk_operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_studio_bulk_operations.id", ondelete="CASCADE"),
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_generations.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_jobs.id", ondelete="CASCADE"), unique=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(40))
    content_type: Mapped[str] = mapped_column(String(60))
    locale: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_category: Mapped[str | None] = mapped_column(String(80), index=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    stale_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
