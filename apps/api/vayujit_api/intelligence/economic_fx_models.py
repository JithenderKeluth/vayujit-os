"""Owner-scoped immutable FX observations and snapshots for sourcing economics 13C."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

FX_PROVENANCES = ("OBSERVED", "QUOTED", "CONFIGURED", "ASSUMED", "LOCAL_FIXTURE")
FX_FRESHNESS = ("CURRENT", "STALE", "UNKNOWN")
FX_MODES = ("LOCAL_FIXTURE", "MANUAL")


class FXObservation(Base):
    __tablename__ = "intelligence_fx_observations"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_fx_observation_idempotency"),
        UniqueConstraint("owner_id", "fingerprint", name="uq_fx_observation_fingerprint"),
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_fx_observation_base"),
        CheckConstraint("quote_currency ~ '^[A-Z]{3}$'", name="ck_fx_observation_quote"),
        CheckConstraint("base_currency <> quote_currency", name="ck_fx_observation_pair"),
        CheckConstraint("rate > 0", name="ck_fx_observation_rate"),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','LOCAL_FIXTURE')",
            name="ck_fx_observation_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')",
            name="ck_fx_observation_freshness",
        ),
        CheckConstraint(
            "mode IN ('LOCAL_FIXTURE','MANUAL')",
            name="ck_fx_observation_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(24), default="LOCAL_FIXTURE")
    provenance: Mapped[str] = mapped_column(String(24))
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class FXRateSnapshot(Base):
    __tablename__ = "intelligence_fx_rate_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_fx_snapshot_fingerprint"),
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_fx_snapshot_base"),
        CheckConstraint("quote_currency ~ '^[A-Z]{3}$'", name="ck_fx_snapshot_quote"),
        CheckConstraint("base_currency <> quote_currency", name="ck_fx_snapshot_pair"),
        CheckConstraint("rate > 0", name="ck_fx_snapshot_rate"),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','LOCAL_FIXTURE')",
            name="ck_fx_snapshot_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')",
            name="ck_fx_snapshot_freshness",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_fx_observations.id", ondelete="RESTRICT"),
        index=True,
    )
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(120))
    provenance: Mapped[str] = mapped_column(String(24))
    freshness: Mapped[str] = mapped_column(String(16))
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_mode: Mapped[str] = mapped_column(String(24))
    original_base_currency: Mapped[str] = mapped_column(String(3))
    original_quote_currency: Mapped[str] = mapped_column(String(3))
    original_rate: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    inverted: Mapped[bool] = mapped_column(default=False)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32), default="fx-snapshot-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
