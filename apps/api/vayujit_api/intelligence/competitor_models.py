"""Owner-scoped competitor intelligence foundation (Slice 10A)."""

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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CONTEXT_STATUSES = ("DRAFT", "ACTIVE", "WATCHING", "ARCHIVED")
ENTITY_TYPES = ("BRAND", "SELLER", "MANUFACTURER", "MERCHANT", "OPERATOR", "UNKNOWN")
IDENTITY_STATES = ("UNRESOLVED", "CANDIDATE", "PROBABLE", "CONFIRMED", "REJECTED", "AMBIGUOUS")
EVIDENCE_STATES = ("UNKNOWN", "PARTIAL", "INSUFFICIENT_EVIDENCE", "AVAILABLE")
FRESHNESS_STATES = ("CURRENT", "STALE", "UNKNOWN")
AVAILABILITY_STATES = ("UNKNOWN", "AVAILABLE", "UNAVAILABLE", "OUT_OF_STOCK", "DISCONTINUED")


def competitor_now() -> datetime:
    return datetime.now(UTC)


class CompetitorContext(Base):
    __tablename__ = "intelligence_competitor_contexts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "subject_type",
            "subject_reference",
            "marketplace",
            "market",
            name="uq_comp_context_subject_market",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_context_idempotency"),
        CheckConstraint(
            "subject_type IN ('PRODUCT_OPPORTUNITY','PRODUCT','BRAND')",
            name="ck_comp_context_subject_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','WATCHING','ARCHIVED')",
            name="ck_comp_context_status",
        ),
        CheckConstraint("version >= 1", name="ck_comp_context_version"),
        CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_comp_context_currency",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_reference: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    product_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True
    )
    marketplace: Mapped[str] = mapped_column(String(120), default="", index=True)
    market: Mapped[str] = mapped_column(String(120), default="", index=True)
    category: Mapped[str] = mapped_column(String(120), default="")
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=competitor_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompetitorEntity(Base):
    __tablename__ = "intelligence_competitor_entities"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "entity_type", "canonical_name", name="uq_comp_entity_canonical"
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_entity_idempotency"),
        CheckConstraint(
            "entity_type IN ('BRAND','SELLER','MANUFACTURER','MERCHANT','OPERATOR','UNKNOWN')",
            name="ck_comp_entity_type",
        ),
        CheckConstraint(
            "evidence_state IN ('UNKNOWN','PARTIAL','INSUFFICIENT_EVIDENCE','AVAILABLE')",
            name="ck_comp_entity_evidence_state",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(240))
    entity_type: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    canonical_name: Mapped[str] = mapped_column(String(240), index=True)
    marketplace_identifiers: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    country_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN", index=True)
    source_lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=competitor_now)


class CompetitorProduct(Base):
    __tablename__ = "intelligence_competitor_foundation_products"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "marketplace",
            "external_identifier",
            name="uq_comp_product_identity",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_product_idempotency"),
        CheckConstraint(
            "availability_state IN ('UNKNOWN','AVAILABLE','UNAVAILABLE',"
            "'OUT_OF_STOCK','DISCONTINUED')",
            name="ck_comp_product_availability_state",
        ),
        CheckConstraint(
            "identity_state IN ('UNRESOLVED','CANDIDATE','PROBABLE',"
            "'CONFIRMED','REJECTED','AMBIGUOUS')",
            name="ck_comp_product_identity_state",
        ),
        CheckConstraint(
            "evidence_state IN ('UNKNOWN','PARTIAL','INSUFFICIENT_EVIDENCE','AVAILABLE')",
            name="ck_comp_product_evidence_state",
        ),
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
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    canonical_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500))
    brand_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    seller_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    marketplace: Mapped[str] = mapped_column(String(120), default="", index=True)
    external_identifier: Mapped[str] = mapped_column(String(240), index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    availability_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    identity_state: Mapped[str] = mapped_column(String(24), default="UNRESOLVED", index=True)
    evidence_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN", index=True)
    first_observed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now
    )
    last_observed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=competitor_now)


class CompetitorObservation(Base):
    __tablename__ = "intelligence_competitor_observations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "competitor_product_id", "observation_key", name="uq_comp_observation_key"
        ),
        CheckConstraint(
            "numeric_value IS NULL OR numeric_value >= 0", name="ck_comp_observation_numeric"
        ),
        CheckConstraint(
            "freshness_state IN ('CURRENT','STALE','UNKNOWN')",
            name="ck_comp_observation_freshness",
        ),
        CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_comp_observation_currency",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    competitor_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_foundation_products.id", ondelete="CASCADE"),
        index=True,
    )
    observation_type: Mapped[str] = mapped_column(String(80), index=True)
    observed_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source_reference: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    freshness_state: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)
    verification_state: Mapped[str] = mapped_column(String(24), default="UNVERIFIED", index=True)
    observation_key: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )


class CompetitorSnapshot(Base):
    __tablename__ = "intelligence_competitor_foundation_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "product_id",
            "snapshot_version",
            name="uq_comp_snapshot_version",
        ),
        UniqueConstraint(
            "owner_id",
            "context_id",
            "product_id",
            "input_fingerprint",
            name="uq_comp_snapshot_fingerprint",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_snapshot_idempotency"),
        CheckConstraint("snapshot_version >= 1", name="ck_comp_snapshot_version"),
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
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_foundation_products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    source_references: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observation_references: Mapped[list[str]] = mapped_column(JSONB, default=list)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[str] = mapped_column(String(80), default="competitor-snapshot-v1")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
