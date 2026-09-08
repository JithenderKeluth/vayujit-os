"""Durable owner-scoped supplier shortlisting and recommendation records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class SupplierShortlistContext(Base):
    __tablename__ = "intelligence_supplier_shortlist_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_shortlist_context_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_market: Mapped[str | None] = mapped_column(String(120), nullable=True)
    budget_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierShortlistContextVersion(Base):
    __tablename__ = "intelligence_supplier_shortlist_context_versions"
    __table_args__ = (
        UniqueConstraint("context_id", "version", name="uq_shortlist_context_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierShortlistScoreVersion(Base):
    __tablename__ = "intelligence_supplier_shortlist_score_versions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "supplier_id",
            "model_version",
            name="uq_shortlist_score_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(80))
    weights: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    eligibility: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierShortlistVersion(Base):
    __tablename__ = "intelligence_supplier_shortlist_versions"
    __table_args__ = (UniqueConstraint("context_id", "version", name="uq_shortlist_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    context_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierShortlistDecision(Base):
    __tablename__ = "intelligence_supplier_shortlist_decisions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "supplier_id",
            "decision_key",
            name="uq_shortlist_decision_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    shortlist_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_versions.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    decision_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierShortlistHandoff(Base):
    __tablename__ = "intelligence_supplier_shortlist_handoffs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "supplier_id", name="uq_shortlist_handoff_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_decisions.id", ondelete="CASCADE"),
        index=True,
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="ready_for_human_sourcing")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierShortlistEvent(Base):
    __tablename__ = "intelligence_supplier_shortlist_events"
    __table_args__ = (UniqueConstraint("owner_id", "event_key", name="uq_shortlist_event_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    event_key: Mapped[str] = mapped_column(String(240))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
