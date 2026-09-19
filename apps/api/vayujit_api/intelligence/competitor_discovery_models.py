"""Deterministic competitor discovery and identity-resolution persistence (10B)."""

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

DISCOVERY_REQUEST_STATUSES = (
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
    "CANCELLED",
)
DISCOVERY_SOURCE_MODES = ("DISABLED", "LOCAL_FIXTURE", "LIVE_READ_ONLY", "CANONICAL_LISTINGS")
DISCOVERY_IDENTITY_STATES = (
    "UNRESOLVED",
    "CANDIDATE",
    "PROBABLE",
    "CONFIRMED",
    "REJECTED",
    "AMBIGUOUS",
)
DISCOVERY_MATCH_LEVELS = (
    "NONE",
    "WEAK_CANDIDATE",
    "STRUCTURED_MATCH",
    "CANONICAL_PRODUCT",
    "AUTHORITATIVE_IDENTIFIER",
    "HUMAN_CONFIRMED",
)


class CompetitorDiscoveryRequest(Base):
    __tablename__ = "intelligence_competitor_discovery_requests"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_comp_discovery_request_idempotency"
        ),
        CheckConstraint(
            (
                "status IN ('PENDING','RUNNING','COMPLETED','PARTIALLY_COMPLETED',"
                "'FAILED','CANCELLED')"
            ),
            name="ck_comp_discovery_request_status",
        ),
        CheckConstraint(
            "provider_mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')",
            name="ck_comp_discovery_request_provider_mode",
        ),
        CheckConstraint(
            "maximum_candidates BETWEEN 1 AND 500", name="ck_comp_discovery_max_candidates"
        ),
        Index("ix_comp_discovery_request_owner_status", "owner_id", "status"),
        Index("ix_comp_discovery_request_context", "context_id", "created_at"),
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
    marketplace: Mapped[str] = mapped_column(String(120), default="", index=True)
    market: Mapped[str] = mapped_column(String(120), default="", index=True)
    category: Mapped[str] = mapped_column(String(120), default="")
    query_inputs: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    filters: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_selection: Mapped[list[object]] = mapped_column(JSONB, default=list)
    maximum_candidates: Mapped[int] = mapped_column(Integer, default=50)
    provider_mode: Mapped[str] = mapped_column(String(32), default="LOCAL_FIXTURE", index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(240))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=competitor_now)


class CompetitorDiscoveryCandidate(Base):
    __tablename__ = "intelligence_competitor_discovery_candidates"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "request_id",
            "source_mode",
            "source_identifier",
            name="uq_comp_discovery_candidate_source",
        ),
        UniqueConstraint(
            "owner_id",
            "request_id",
            "idempotency_key",
            name="uq_comp_discovery_candidate_idempotency",
        ),
        CheckConstraint(
            (
                "identity_state IN ('UNRESOLVED','CANDIDATE','PROBABLE','CONFIRMED',"
                "'REJECTED','AMBIGUOUS')"
            ),
            name="ck_comp_discovery_candidate_identity",
        ),
        CheckConstraint(
            "match_level IN ('NONE','WEAK_CANDIDATE','STRUCTURED_MATCH','CANONICAL_PRODUCT',"
            "'AUTHORITATIVE_IDENTIFIER','HUMAN_CONFIRMED')",
            name="ck_comp_discovery_candidate_match_level",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_comp_discovery_candidate_rating",
        ),
        CheckConstraint(
            "review_count IS NULL OR review_count >= 0", name="ck_comp_discovery_candidate_reviews"
        ),
        CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0", name="ck_comp_discovery_candidate_price"
        ),
        Index("ix_comp_discovery_candidate_request_state", "request_id", "identity_state"),
        Index(
            "ix_comp_discovery_candidate_listing", "owner_id", "marketplace", "listing_identifier"
        ),
        Index("ix_comp_discovery_candidate_normalized", "owner_id", "normalized_title"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_discovery_requests.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    source_mode: Mapped[str] = mapped_column(String(32), index=True)
    source_identifier: Mapped[str] = mapped_column(String(500))
    listing_identifier: Mapped[str | None] = mapped_column(String(240), index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    raw_title: Mapped[str] = mapped_column(String(500))
    normalized_title: Mapped[str] = mapped_column(String(500), index=True)
    brand_claim: Mapped[str | None] = mapped_column(String(240))
    seller_claim: Mapped[str | None] = mapped_column(String(240))
    category: Mapped[str | None] = mapped_column(String(120))
    marketplace: Mapped[str] = mapped_column(String(120), default="", index=True)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    availability_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    structured_attributes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    identity_state: Mapped[str] = mapped_column(String(24), default="CANDIDATE", index=True)
    match_level: Mapped[str] = mapped_column(String(32), default="NONE", index=True)
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    supporting_signals: Mapped[list[object]] = mapped_column(JSONB, default=list)
    conflicting_signals: Mapped[list[object]] = mapped_column(JSONB, default=list)
    missing_signals: Mapped[list[object]] = mapped_column(JSONB, default=list)
    rule_version: Mapped[str] = mapped_column(String(80), default="competitor-match-v1")
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    evidence_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN", index=True)
    freshness_state: Mapped[str] = mapped_column(String(16), default="CURRENT", index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_evidence.id", ondelete="RESTRICT"), index=True
    )
    competitor_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_foundation_products.id", ondelete="SET NULL"),
        index=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=competitor_now)


class CompetitorDiscoverySnapshot(Base):
    __tablename__ = "intelligence_competitor_discovery_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "request_id", "snapshot_version", name="uq_comp_discovery_snapshot_version"
        ),
        UniqueConstraint(
            "owner_id",
            "request_id",
            "input_fingerprint",
            "snapshot_version",
            name="uq_comp_discovery_snapshot_fingerprint",
        ),
        UniqueConstraint(
            "owner_id",
            "request_id",
            "idempotency_key",
            name="uq_comp_discovery_snapshot_idempotency",
        ),
        CheckConstraint("snapshot_version >= 1", name="ck_comp_discovery_snapshot_version"),
        CheckConstraint("candidate_count >= 0", name="ck_comp_discovery_snapshot_candidates"),
        Index("ix_comp_discovery_snapshot_request", "request_id", "captured_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_discovery_requests.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    ambiguous_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    source_counts: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_diversity: Mapped[int] = mapped_column(Integer, default=0)
    evidence_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    competitor_product_references: Mapped[list[object]] = mapped_column(JSONB, default=list)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        index=True,
    )
    source_freshness: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
