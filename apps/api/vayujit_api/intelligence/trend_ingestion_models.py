"""Provider-neutral Trend 12B ingestion ledger models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class TrendIngestionBatch(Base):
    __tablename__ = "intelligence_trend_ingestion_batches"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "idempotency_key", name="uq_trend_ingestion_batch_idempotency"
        ),
        Index(
            "ix_trend_ingestion_batch_owner_context_created", "owner_id", "context_id", "created_at"
        ),
        CheckConstraint(
            "mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')",
            name="ck_trend_ingestion_batch_mode",
        ),
        CheckConstraint(
            "status IN ('REQUESTED','RUNNING','COMPLETED','PARTIAL','FAILED')",
            name="ck_trend_ingestion_batch_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(120), default="LOCAL_FIXTURE", index=True)
    mode: Mapped[str] = mapped_column(String(32), default="LOCAL_FIXTURE", index=True)
    status: Mapped[str] = mapped_column(String(24), default="REQUESTED", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_count: Mapped[int] = mapped_column(Integer, default=0)
    received_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_observation_count: Mapped[int] = mapped_column(Integer, default=0)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    adapter_version: Mapped[str] = mapped_column(String(40), default="trend-adapter-v1")
    normalization_version: Mapped[str] = mapped_column(String(40), default="trend-normalization-v1")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TrendIngestionCandidate(Base):
    __tablename__ = "intelligence_trend_ingestion_candidates"
    __table_args__ = (
        UniqueConstraint("batch_id", "ordinal", name="uq_trend_ingestion_candidate_ordinal"),
        Index("ix_trend_ingestion_candidate_batch_status", "owner_id", "batch_id", "accepted"),
        Index("ix_trend_ingestion_candidate_rejection", "owner_id", "batch_id", "rejection_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_ingestion_batches.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    provider_observation_id: Mapped[str | None] = mapped_column(String(240), index=True)
    signal_key: Mapped[str] = mapped_column(String(80), default="")
    fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    duplicate_classification: Mapped[str] = mapped_column(
        String(32), default="DISTINCT", index=True
    )
    quality_state: Mapped[str] = mapped_column(String(16), default="INVALID", index=True)
    accepted: Mapped[bool] = mapped_column(default=False, index=True)
    rejection_code: Mapped[str | None] = mapped_column(String(80), index=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_foundation_observations.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TrendObservationRevision(Base):
    __tablename__ = "intelligence_trend_observation_revisions"
    __table_args__ = (
        Index(
            "ix_trend_observation_revision_identity_time",
            "owner_id",
            "provider_observation_id",
            "changed_at",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_foundation_observations.id", ondelete="CASCADE"),
        index=True,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_ingestion_batches.id", ondelete="CASCADE"),
        index=True,
    )
    provider_observation_id: Mapped[str] = mapped_column(String(240), index=True)
    old_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    new_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
