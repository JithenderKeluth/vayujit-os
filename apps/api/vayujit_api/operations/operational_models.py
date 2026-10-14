"""Owner-scoped operational signals and local Action Center state.

Signals are a derived, auditable projection. They never replace catalog,
inventory, order, financial, or marketplace authorities and never authorize an
external mutation.
"""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class OperationalSignal(Base):
    __tablename__ = "operational_signals"
    __table_args__ = (
        CheckConstraint(
            "category IN ('catalog','inventory','orders','financial','supplier','system')",
            name="ck_operational_signal_category",
        ),
        CheckConstraint(
            "severity IN ('critical','high','medium','low','info')",
            name="ck_operational_signal_severity",
        ),
        CheckConstraint(
            "status IN ("
            "'NEW','ACKNOWLEDGED','SNOOZED','IN_PROGRESS',"
            "'RESOLVED','REOPENED','STALE')",
            name="ck_operational_signal_status",
        ),
        CheckConstraint(
            "signal_kind IN ('OBSERVED','DERIVED','RECOMMENDATION','UNKNOWN')",
            name="ck_operational_signal_kind",
        ),
        Index(
            "ix_operational_signal_owner_status_priority", "owner_id", "status", "priority_score"
        ),
        Index("ix_operational_signal_owner_category", "owner_id", "category", "severity"),
        UniqueConstraint("owner_id", "fingerprint", name="uq_operational_signal_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    signal_type: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    marketplace: Mapped[str | None] = mapped_column(String(30), index=True)
    source_authority: Mapped[str] = mapped_column(String(120))
    source_resource_type: Mapped[str] = mapped_column(String(80))
    source_resource_id: Mapped[str | None] = mapped_column(String(240))
    source_version: Mapped[str] = mapped_column(String(80), default="v1")
    signal_kind: Mapped[str] = mapped_column(String(24), default="DERIVED")
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    evidence_quality: Mapped[str] = mapped_column(String(30), default="unknown")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fresh_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="NEW", index=True)
    title: Mapped[str] = mapped_column(String(240))
    explanation: Mapped[str] = mapped_column(Text)
    uncertainty: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text)
    recommended_action_type: Mapped[str] = mapped_column(
        String(40), default="HUMAN_APPROVAL_REQUIRED"
    )
    source_route: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    rule_version: Mapped[str] = mapped_column(String(60), default="pr-sos-06-v1")
    fingerprint: Mapped[str] = mapped_column(String(240), unique=False)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_transition_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationalSignalTransition(Base):
    __tablename__ = "operational_signal_transitions"
    __table_args__ = (
        Index("ix_operational_transition_owner_signal", "owner_id", "signal_id", "created_at"),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_operational_transition_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operational_signals.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24))
    actor_type: Mapped[str] = mapped_column(String(20), default="HUMAN")
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(240))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationalAutomationPolicy(Base):
    __tablename__ = "operational_automation_policies"
    __table_args__ = (Index("ix_operational_policy_owner", "owner_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    enabled: Mapped[bool] = mapped_column(default=False)
    dry_run: Mapped[bool] = mapped_column(default=True)
    emergency_stop: Mapped[bool] = mapped_column(default=False)
    severity_threshold: Mapped[str] = mapped_column(String(20), default="high")
    minimum_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.80"))
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    maximum_actions_per_run: Mapped[int] = mapped_column(Integer, default=10)
    signal_types_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    notification_preferences_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_version: Mapped[str] = mapped_column(String(60), default="pr-sos-06-policy-v1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationalNotification(Base):
    __tablename__ = "operational_notifications"
    __table_args__ = (
        Index("ix_operational_notification_owner_unread", "owner_id", "read_at"),
        UniqueConstraint("owner_id", "dedupe_key", name="uq_operational_notification_dedupe"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operational_signals.id", ondelete="CASCADE"), index=True
    )
    notification_type: Mapped[str] = mapped_column(String(60))
    dedupe_key: Mapped[str] = mapped_column(String(240))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationalBriefing(Base):
    __tablename__ = "operational_briefings"
    __table_args__ = (
        Index("ix_operational_briefing_owner_snapshot", "owner_id", "snapshot_key", unique=True),
        UniqueConstraint("owner_id", "snapshot_key", name="uq_operational_briefing_snapshot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    snapshot_key: Mapped[str] = mapped_column(String(80))
    source_scan_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
