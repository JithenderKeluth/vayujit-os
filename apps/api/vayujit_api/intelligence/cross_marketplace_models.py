"""Persistence for the provider-independent supplier intelligence projection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

IDENTITY_STATES = ("MATCH", "POSSIBLE_MATCH", "NO_MATCH", "UNKNOWN")
EVENT_TYPES = ("change", "alert", "history", "report")


class CrossMarketplaceSupplier(Base):
    """Canonical owner-scoped supplier view, rebuilt only from accepted evidence."""

    __tablename__ = "intelligence_cross_marketplace_suppliers"
    __table_args__ = (
        UniqueConstraint("owner_id", "canonical_key", name="uq_cross_marketplace_supplier_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canonical_key: Mapped[str] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(240))
    identity_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    view_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    source_diversity_score: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    freshness_status: Mapped[str] = mapped_column(String(24), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CrossMarketplaceSupplierLink(Base):
    """Immutable source-to-canonical identity reconciliation decision."""

    __tablename__ = "intelligence_cross_marketplace_supplier_links"
    __table_args__ = (
        UniqueConstraint("canonical_supplier_id", "supplier_id", name="uq_cross_supplier_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canonical_supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    match_state: Mapped[str] = mapped_column(String(24), default="MATCH")
    rationale: Mapped[str] = mapped_column(String(500), default="")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CrossMarketplaceSupplierEvaluation(Base):
    """Append-only confidence/ranking evaluation with explicit model version."""

    __tablename__ = "intelligence_cross_marketplace_supplier_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "canonical_supplier_id",
            "model_version",
            "idempotency_key",
            name="uq_cross_supplier_evaluation_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canonical_supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(80))
    weights: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    final_score: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CrossMarketplaceSupplierEvent(Base):
    """Append-only history, change, alert, and report records."""

    __tablename__ = "intelligence_cross_marketplace_supplier_events"
    __table_args__ = (
        UniqueConstraint("owner_id", "event_key", name="uq_cross_supplier_event_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canonical_supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(24), index=True)
    event_key: Mapped[str] = mapped_column(String(240))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
