"""Owner-scoped immutable sourcing analysis records; no procurement execution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

STATES = (
    "DRAFT",
    "READY",
    "CALCULATING",
    "REVIEW_REQUIRED",
    "SUFFICIENT",
    "BLOCKED",
    "APPROVED_FOR_INTERNAL_SOURCING",
    "REJECTED",
    "ARCHIVED",
)


class OwnedRecord:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SourcingScenarioContext(OwnedRecord, Base):
    __tablename__ = "intelligence_scenario_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_scenario_context_key"),
        CheckConstraint("current_version > 0", name="ck_scenario_context_version"),
    )
    shortlist_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_supplier_shortlist_versions.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("intelligence_opportunities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="READY")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourcingScenario(OwnedRecord, Base):
    __tablename__ = "intelligence_scenarios"
    __table_args__ = (
        UniqueConstraint("context_id", "idempotency_key", name="uq_scenario_key"),
        CheckConstraint("current_version > 0", name="ck_scenario_version"),
        ForeignKeyConstraint(
            ["id", "current_version"],
            [
                "intelligence_scenario_versions.scenario_id",
                "intelligence_scenario_versions.version",
            ],
            name="fk_scenario_current_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_contexts.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    scenario_type: Mapped[str] = mapped_column(String(40))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="REVIEW_REQUIRED")
    idempotency_key: Mapped[str] = mapped_column(String(160))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourcingScenarioVersion(OwnedRecord, Base):
    __tablename__ = "intelligence_scenario_versions"
    __table_args__ = (
        UniqueConstraint("scenario_id", "version", name="uq_scenario_version"),
        CheckConstraint("version > 0", name="ck_scenario_version_positive"),
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenarios.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    calculation_version: Mapped[str] = mapped_column(String(64))
    scoring_version: Mapped[str] = mapped_column(String(64))
    landed_cost_version: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    lineage_hash: Mapped[str] = mapped_column(String(64))


class ScenarioSupplierAllocation(OwnedRecord, Base):
    __tablename__ = "intelligence_scenario_allocations"
    __table_args__ = (
        UniqueConstraint("version_id", "supplier_id", name="uq_scenario_allocation"),
        CheckConstraint("quantity > 0", name="ck_scenario_allocation_quantity"),
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_versions.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="RESTRICT"), index=True
    )
    due_diligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SourcingScenarioRecommendation(OwnedRecord, Base):
    __tablename__ = "intelligence_scenario_recommendations"
    __table_args__ = (UniqueConstraint("context_id", "version", name="uq_scenario_recommendation"),)
    context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_contexts.id", ondelete="RESTRICT"), index=True
    )
    scenario_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("intelligence_scenario_versions.id", ondelete="RESTRICT"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SourcingScenarioDecision(OwnedRecord, Base):
    __tablename__ = "intelligence_scenario_decisions"
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_versions.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(500))


class InternalSourcingHandoff(OwnedRecord, Base):
    __tablename__ = "intelligence_scenario_handoffs"
    __table_args__ = (UniqueConstraint("version_id", name="uq_scenario_handoff_version"),)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_versions.id", ondelete="RESTRICT"), index=True
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_decisions.id", ondelete="RESTRICT"), index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SourcingScenarioEvent(OwnedRecord, Base):
    """Transactional domain history and exact request replay; not a worker runtime."""

    __tablename__ = "intelligence_scenario_events"
    __table_args__ = (UniqueConstraint("owner_id", "event_key", name="uq_scenario_event"),)
    context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_scenario_contexts.id", ondelete="RESTRICT"), index=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("intelligence_scenario_versions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(240))
    event_type: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
