"""Immutable, owner-scoped competitive change intelligence persistence (10D)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base
from vayujit_api.intelligence.competitor_models import competitor_now

COMPARISON_STATUSES = ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED")
CHANGE_TYPES = (
    "COMPETITOR_ADDED",
    "COMPETITOR_REMOVED",
    "POSSIBLY_REMOVED",
    "PRICE_INCREASED",
    "PRICE_DECREASED",
    "PRICE_BAND_CHANGED",
    "AVAILABILITY_CHANGED",
    "RATING_CHANGED",
    "REVIEW_COUNT_CHANGED",
    "BRAND_CONCENTRATION_CHANGED",
    "SELLER_CONCENTRATION_CHANGED",
    "ASSORTMENT_ATTRIBUTE_ADDED",
    "ASSORTMENT_ATTRIBUTE_REMOVED",
    "ASSORTMENT_DISTRIBUTION_CHANGED",
    "FEATURE_ADDED",
    "FEATURE_REMOVED",
    "POSITIONING_CHANGED",
    "EVIDENCE_COVERAGE_CHANGED",
    "FRESHNESS_CHANGED",
    "CONTRADICTION_CHANGED",
)
CHANGE_STATUSES = (
    "NEW",
    "ONGOING",
    "RESOLVED",
    "REVERTED",
    "SUPERSEDED",
    "UNRESOLVED",
    "POSSIBLY_REMOVED",
)
MATERIALITY_LEVELS = ("IMMATERIAL", "LOW", "MODERATE", "HIGH", "UNKNOWN")
ALERT_ELIGIBILITY = ("NO_ALERT", "REVIEW", "ALERT")
CALCULATION_VERSION = "competitor-change-v1"
MATERIALITY_POLICY_VERSION = "competitor-change-materiality-v1"


class CompetitorChangeComparison(Base):
    """A reproducible comparison between two immutable commercial states."""

    __tablename__ = "intelligence_competitor_change_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "input_fingerprint",
            name="uq_comp_change_comparison_fingerprint",
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_comp_change_comparison_idempotency"
        ),
        CheckConstraint("comparison_version >= 1", name="ck_comp_change_comparison_version"),
        CheckConstraint(
            "status IN ('COMPLETED','PARTIALLY_COMPLETED','FAILED')",
            name="ck_comp_change_comparison_status",
        ),
        Index("ix_comp_change_comparison_context", "owner_id", "context_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    baseline_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="RESTRICT"),
        index=True,
    )
    current_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="RESTRICT"),
        index=True,
    )
    baseline_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    comparison_version: Mapped[int] = mapped_column(Integer, default=1)
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )


class CompetitorChangeEvent(Base):
    """Append-only fact describing one observed or derived competitive change."""

    __tablename__ = "intelligence_competitor_change_events"
    __table_args__ = (
        UniqueConstraint("owner_id", "event_fingerprint", name="uq_comp_change_event_fingerprint"),
        CheckConstraint(
            "change_type IN (" + ",".join("'" + item + "'" for item in CHANGE_TYPES) + ")",
            name="ck_comp_change_event_type",
        ),
        CheckConstraint(
            "status IN (" + ",".join("'" + item + "'" for item in CHANGE_STATUSES) + ")",
            name="ck_comp_change_event_status",
        ),
        CheckConstraint(
            "materiality IN (" + ",".join("'" + item + "'" for item in MATERIALITY_LEVELS) + ")",
            name="ck_comp_change_event_materiality",
        ),
        CheckConstraint(
            "alert_eligibility IN ('NO_ALERT','REVIEW','ALERT')", name="ck_comp_change_event_alert"
        ),
        Index("ix_comp_change_event_context_created", "owner_id", "context_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_change_comparisons.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_foundation_products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(64), index=True)
    observed_or_derived: Mapped[str] = mapped_column(String(16), default="OBSERVED")
    old_value: Mapped[object] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[object] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    absolute_delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    percentage_delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    baseline_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    current_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    evidence_references: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    first_observed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_state: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    evidence_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    verification_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    materiality: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)
    materiality_policy_version: Mapped[str] = mapped_column(
        String(80), default=MATERIALITY_POLICY_VERSION
    )
    status: Mapped[str] = mapped_column(String(24), default="NEW", index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    alert_eligibility: Mapped[str] = mapped_column(String(16), default="NO_ALERT", index=True)
    alert_reason: Mapped[str] = mapped_column(String(240), default="")
    persistence_count: Mapped[int] = mapped_column(Integer, default=1)
    previous_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_change_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    event_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompetitorChangeAlertEligibility(Base):
    """Separate persisted alert decision; no external notification is sent."""

    __tablename__ = "intelligence_competitor_change_alert_eligibility"
    __table_args__ = (UniqueConstraint("owner_id", "event_id", name="uq_comp_change_alert_event"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_change_events.id", ondelete="CASCADE"),
        index=True,
    )
    eligibility: Mapped[str] = mapped_column(String(16), default="NO_ALERT", index=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
