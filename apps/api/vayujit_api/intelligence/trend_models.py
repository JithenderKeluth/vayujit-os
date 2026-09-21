"""Canonical provider-independent Trend Intelligence 12A models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

SUBJECT_TYPES = (
    "PRODUCT",
    "PRODUCT_OPPORTUNITY",
    "BRAND",
    "CATEGORY",
    "KEYWORD",
    "SEARCH_TERM",
    "COMPETITOR_SET",
    "MARKET_SEGMENT",
    "CUSTOM",
)
CONTEXT_STATUSES = ("DRAFT", "ACTIVE", "ARCHIVED")
MEASUREMENT_TYPES = ("COUNT", "DECIMAL", "INDEX", "PERCENTAGE", "BOOLEAN", "ORDINAL", "CATEGORY")
GEOGRAPHY_SCOPES = ("GLOBAL", "COUNTRY", "REGION", "CITY", "MARKETPLACE_MARKET", "UNKNOWN")
GRANULARITIES = ("POINT_IN_TIME", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY")
EVIDENCE_KINDS = ("OBSERVED", "DERIVED_DETERMINISTIC", "DERIVED_SEMANTIC")
VERIFICATION_STATES = ("VERIFIED", "UNVERIFIED", "UNKNOWN")
FRESHNESS_STATES = ("CURRENT", "STALE", "UNKNOWN")
QUALITY_STATES = ("COMPLETE", "PARTIAL", "MINIMAL", "INVALID")


def _check(name: str, field: str, values: tuple[str, ...]) -> CheckConstraint:
    return CheckConstraint(
        f"{field} IN (" + ",".join(f"'{value}'" for value in values) + ")", name=name
    )


class TrendSignalDefinition(Base):
    __tablename__ = "intelligence_trend_signal_definitions"
    __table_args__ = (
        UniqueConstraint("owner_id", "signal_type", "version", name="uq_trend_signal_definition"),
        _check("ck_trend_signal_measurement_type", "measurement_type", MEASUREMENT_TYPES),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(80), index=True)
    measurement_type: Mapped[str] = mapped_column(String(24))
    unit: Mapped[str | None] = mapped_column(String(40))
    scale: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    aggregation_semantics: Mapped[str] = mapped_column(String(80), default="source_reported")
    compatible_source_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    version: Mapped[str] = mapped_column(String(40), default="v1")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrendContext(Base):
    __tablename__ = "intelligence_trend_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_trend_context_owner_idempotency"),
        _check("ck_trend_context_subject_type", "subject_type", SUBJECT_TYPES),
        _check("ck_trend_context_status", "status", CONTEXT_STATUSES),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    product_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), index=True
    )
    subject_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_key: Mapped[str] = mapped_column(String(240), default="")
    name: Mapped[str] = mapped_column(String(180), default="Trend context")
    marketplace: Mapped[str | None] = mapped_column(String(120))
    market: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrendObservation(Base):
    __tablename__ = "intelligence_trend_foundation_observations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "source_id",
            "provider_observation_id",
            name="uq_trend_observation_provider_identity",
        ),
        UniqueConstraint(
            "owner_id", "context_id", "fingerprint", name="uq_trend_observation_fingerprint"
        ),
        _check("ck_trend_observation_measurement_type", "measurement_type", MEASUREMENT_TYPES),
        _check("ck_trend_observation_geography_scope", "geography_scope", GEOGRAPHY_SCOPES),
        _check("ck_trend_observation_granularity", "granularity", GRANULARITIES),
        _check("ck_trend_observation_evidence_kind", "evidence_kind", EVIDENCE_KINDS),
        _check("ck_trend_observation_verification", "verification_state", VERIFICATION_STATES),
        _check("ck_trend_observation_freshness", "freshness_state", FRESHNESS_STATES),
        _check("ck_trend_observation_quality", "quality_state", QUALITY_STATES),
        CheckConstraint(
            "period_end IS NULL OR period_start IS NULL OR period_end >= period_start",
            name="ck_trend_observation_period_order",
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
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_evidence.id", ondelete="SET NULL"), index=True
    )
    signal_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_signal_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    provider_observation_id: Mapped[str | None] = mapped_column(String(240))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    granularity: Mapped[str] = mapped_column(String(24), default="POINT_IN_TIME")
    measurement_type: Mapped[str] = mapped_column(String(24))
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    value_text: Mapped[str | None] = mapped_column(String(2000))
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    unit: Mapped[str | None] = mapped_column(String(40))
    scale: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    geography_scope: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    country: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    marketplace: Mapped[str | None] = mapped_column(String(120))
    source_reference: Mapped[str] = mapped_column(String(500))
    evidence_kind: Mapped[str] = mapped_column(String(28), default="OBSERVED")
    verification_state: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness_state: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)
    quality_state: Mapped[str] = mapped_column(String(16), default="COMPLETE")
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    canonical_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provenance_note: Mapped[str] = mapped_column(Text, default="")
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    fingerprint_version: Mapped[str] = mapped_column(String(40), default="trend-observation-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TrendSnapshot(Base):
    __tablename__ = "intelligence_trend_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_trend_snapshot_fingerprint"
        ),
        UniqueConstraint(
            "owner_id", "context_id", "snapshot_version", name="uq_trend_snapshot_version"
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
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_snapshots.id", ondelete="SET NULL")
    )
    snapshot_version: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observation_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_inventory: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    signal_inventory: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    geographic_inventory: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    granularity_inventory: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    freshness_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    calculation_version: Mapped[str] = mapped_column(String(80), default="trend-snapshot-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


Index(
    "ix_trend_context_owner_status_created",
    TrendContext.owner_id,
    TrendContext.status,
    TrendContext.created_at,
)
Index(
    "ix_trend_observation_context_observed",
    TrendObservation.owner_id,
    TrendObservation.context_id,
    TrendObservation.observed_at,
)
Index("ix_trend_observation_period", TrendObservation.period_start, TrendObservation.period_end)
Index(
    "ix_trend_snapshot_context_version",
    TrendSnapshot.owner_id,
    TrendSnapshot.context_id,
    TrendSnapshot.snapshot_version,
)
