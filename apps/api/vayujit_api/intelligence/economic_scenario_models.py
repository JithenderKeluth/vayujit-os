"""Immutable economic what-if scenarios and sensitivity runs (13F)."""

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

SCENARIO_STATUSES = ("READY", "EXECUTED", "ARCHIVED")
COMPARABILITY_STATES = ("COMPARABLE", "PARTIALLY_COMPARABLE", "NOT_COMPARABLE")


class EconomicScenario(Base):
    __tablename__ = "intelligence_economic_scenarios"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_economic_scenario_idempotency"),
        UniqueConstraint("owner_id", "fingerprint", name="uq_economic_scenario_fingerprint"),
        CheckConstraint("version > 0", name="ck_economic_scenario_version"),
        CheckConstraint(
            "status IN ('READY','EXECUTED','ARCHIVED')", name="ck_economic_scenario_status"
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
    sourcing_scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_scenarios.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    baseline_calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    overrides: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="READY", index=True)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicScenarioResult(Base):
    __tablename__ = "intelligence_economic_scenario_results"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_economic_scenario_result_fingerprint"),
        UniqueConstraint(
            "owner_id",
            "scenario_id",
            "idempotency_key",
            name="uq_economic_scenario_result_idempotency",
        ),
        CheckConstraint(
            "comparability IN ('COMPARABLE','PARTIALLY_COMPARABLE','NOT_COMPARABLE')",
            name="ck_economic_scenario_result_comparability",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_scenarios.id", ondelete="RESTRICT"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    baseline_calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
        index=True,
    )
    scenario_calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
        index=True,
    )
    scenario_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_input_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    calculation_version: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(64))
    comparability: Mapped[str] = mapped_column(String(24))
    baseline_status: Mapped[str] = mapped_column(String(16))
    scenario_status: Mapped[str] = mapped_column(String(16))
    baseline_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    scenario_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    baseline_total: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    scenario_total: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    absolute_delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    percentage_delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    baseline_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    scenario_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    per_unit_delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    changed_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    component_deltas: Mapped[list[object]] = mapped_column(JSONB, default=list)
    assumptions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    missing_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    stale_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EconomicSensitivityRun(Base):
    __tablename__ = "intelligence_economic_sensitivity_runs"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_economic_sensitivity_fingerprint"),
        UniqueConstraint(
            "owner_id",
            "scenario_id",
            "idempotency_key",
            name="uq_economic_sensitivity_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_scenarios.id", ondelete="RESTRICT"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    dimension: Mapped[str] = mapped_column(String(32))
    points: Mapped[list[object]] = mapped_column(JSONB, default=list)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
