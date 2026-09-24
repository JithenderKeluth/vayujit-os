"""Owner-scoped logistics, freight observations, and immutable freight snapshots (13D)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

TRANSPORT_MODES = ("AIR", "SEA", "ROAD", "RAIL", "COURIER", "MULTIMODAL", "OTHER", "UNKNOWN")
SEA_FREIGHT_TYPES = ("LCL", "FCL", "UNKNOWN")
LOGISTICS_STATUSES = ("DRAFT", "CURRENT", "ARCHIVED")
FREIGHT_BASES = (
    "PER_SHIPMENT",
    "PER_KG",
    "PER_CBM",
    "PER_CARTON",
    "PER_CONTAINER",
    "FIXED_QUOTE",
    "UNKNOWN",
)
WEIGHT_UNITS = ("G", "KG", "OZ", "LB")
VOLUME_UNITS = ("CBM", "M3", "L", "CM3")


class LogisticsContext(Base):
    __tablename__ = "intelligence_logistics_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_logistics_context_idempotency"),
        CheckConstraint(
            "transport_mode IN ("
            "'AIR','SEA','ROAD','RAIL','COURIER','MULTIMODAL','OTHER','UNKNOWN')",
            name="ck_logistics_context_transport_mode",
        ),
        CheckConstraint(
            "sea_freight_type IN ('LCL','FCL','UNKNOWN')", name="ck_logistics_context_sea_type"
        ),
        CheckConstraint(
            "status IN ('DRAFT','CURRENT','ARCHIVED')", name="ck_logistics_context_status"
        ),
        CheckConstraint(
            "target_quantity IS NULL OR target_quantity > 0", name="ck_logistics_context_quantity"
        ),
        CheckConstraint(
            "total_weight IS NULL OR total_weight >= 0", name="ck_logistics_context_weight"
        ),
        CheckConstraint(
            "total_volume IS NULL OR total_volume >= 0", name="ck_logistics_context_volume"
        ),
        CheckConstraint(
            "package_count IS NULL OR package_count > 0", name="ck_logistics_context_package_count"
        ),
        CheckConstraint(
            "container_count IS NULL OR container_count > 0",
            name="ck_logistics_context_container_count",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    economic_context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origin_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    transport_mode: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    sea_freight_type: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    container_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    total_weight: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    weight_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    total_volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    volume_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    package_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    requested_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class FreightObservation(Base):
    __tablename__ = "intelligence_freight_observations"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_freight_observation_idempotency"),
        UniqueConstraint("owner_id", "fingerprint", name="uq_freight_observation_fingerprint"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_freight_observation_amount"),
        CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_freight_observation_currency"
        ),
        CheckConstraint(
            "basis IN ("
            "'PER_SHIPMENT','PER_KG','PER_CBM','PER_CARTON','PER_CONTAINER','FIXED_QUOTE','UNKNOWN')",
            name="ck_freight_observation_basis",
        ),
        CheckConstraint(
            "transport_mode IN ("
            "'AIR','SEA','ROAD','RAIL','COURIER','MULTIMODAL','OTHER','UNKNOWN')",
            name="ck_freight_observation_transport_mode",
        ),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_freight_observation_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_freight_observation_freshness"
        ),
        CheckConstraint("mode IN ('LOCAL_FIXTURE','MANUAL')", name="ck_freight_observation_mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    logistics_context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_logistics_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    basis: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    transport_mode: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origin_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quoted_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quoted_quantity_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quoted_weight: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quoted_weight_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quoted_volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quoted_volume_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quoted_package_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quoted_container_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(24), default="LOCAL_FIXTURE")
    provenance: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[str] = mapped_column(String(32), default="freight-observation-v1")
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class FreightSnapshot(Base):
    __tablename__ = "intelligence_freight_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_freight_snapshot_fingerprint"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_freight_snapshot_amount"),
        CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_freight_snapshot_currency"
        ),
        CheckConstraint(
            "basis IN ("
            "'PER_SHIPMENT','PER_KG','PER_CBM','PER_CARTON','PER_CONTAINER','FIXED_QUOTE','UNKNOWN')",
            name="ck_freight_snapshot_basis",
        ),
        CheckConstraint(
            "transport_mode IN ("
            "'AIR','SEA','ROAD','RAIL','COURIER','MULTIMODAL','OTHER','UNKNOWN')",
            name="ck_freight_snapshot_transport_mode",
        ),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_freight_snapshot_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_freight_snapshot_freshness"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    logistics_context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_logistics_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_freight_observations.id", ondelete="RESTRICT"),
        index=True,
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    basis: Mapped[str] = mapped_column(String(24))
    transport_mode: Mapped[str] = mapped_column(String(16))
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origin_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quoted_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quoted_quantity_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quoted_weight: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quoted_weight_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quoted_volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    quoted_volume_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quoted_package_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quoted_container_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(24))
    provenance: Mapped[str] = mapped_column(String(16))
    freshness: Mapped[str] = mapped_column(String(16))
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_mode: Mapped[str] = mapped_column(String(24))
    version: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
