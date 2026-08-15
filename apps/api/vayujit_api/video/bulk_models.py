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
    video_type: Mapped[str] = mapped_column(String(50))
    target_channel: Mapped[str] = mapped_column(String(40))
    child_key: Mapped[str] = mapped_column(String(220))
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
