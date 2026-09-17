"""Append-only, owner-scoped supplier portfolio simulations (8E.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vayujit_api.core.database import Base


def simulation_now() -> datetime:
    return datetime.now(UTC)


class PortfolioSimulationLifecycle(StrEnum):
    CREATED = "CREATED"
    CALCULATED = "CALCULATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class PortfolioSimulation(Base):
    """Immutable typed simulation request bound to an assessment version."""

    __tablename__ = "intelligence_supplier_portfolio_simulations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "portfolio_id",
            "assessment_version_id",
            "simulation_type",
            "assumption_hash",
            "idempotency_key",
            name="uq_portfolio_simulation_request",
        ),
        Index("ix_portfolio_simulation_owner_portfolio", "owner_id", "portfolio_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_assessment_versions.id", ondelete="CASCADE"),
    )
    simulation_type: Mapped[str] = mapped_column(String(48))
    policy_version: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    assumption_hash: Mapped[str] = mapped_column(String(64))
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simulation_now)


class PortfolioSimulationResult(Base):
    """Immutable deterministic simulation output; never current sourcing state."""

    __tablename__ = "intelligence_supplier_portfolio_simulation_results"
    __table_args__ = (
        UniqueConstraint("simulation_id", name="uq_portfolio_simulation_result"),
        Index("ix_portfolio_simulation_result_owner", "owner_id", "portfolio_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_simulations.id", ondelete="CASCADE"),
    )
    simulation: Mapped[PortfolioSimulation] = relationship()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_assessment_versions.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(String(32))
    baseline: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    simulated: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    delta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    affected_supplier_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    affected_product_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    allocation_exposed: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    uncovered_exposure: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    calculation_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simulation_now)
