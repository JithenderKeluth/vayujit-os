"""Durable PR-7C inbound supplier response and quote-evidence records.

This module intentionally models an inbound evidence boundary, not a mailbox.  A
response may be supplied by a deterministic test harness or a future approved
inbound adapter, but the raw payload is always retained and every downstream
commercial write remains behind an explicit HUMAN review.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

RESPONSE_CHANNELS = ("EMAIL", "FORM", "MANUAL_IMPORT", "OTHER")
TRUST_ENVIRONMENTS = ("DETERMINISTIC_TEST", "LIVE_READ_ONLY", "UNKNOWN")
EVIDENCE_ENVIRONMENTS = ("DETERMINISTIC_TEST", "LIVE_READ_ONLY", "UNKNOWN")
CORRELATION_STATES = ("CORRELATED", "AMBIGUOUS", "UNMATCHED")
RESPONSE_CLASSIFICATIONS = (
    "QUOTE",
    "REQUEST_FOR_CLARIFICATION",
    "DECLINED",
    "GENERAL_RESPONSE",
    "UNKNOWN",
)
EXTRACTION_STATUSES = ("EXTRACTED", "PARTIAL", "NEEDS_REVIEW", "FAILED")
REVIEW_DECISIONS = (
    "ACCEPT_EXTRACTION",
    "CORRECT_EXTRACTION",
    "REJECT_EXTRACTION",
    "KEEP_UNDER_REVIEW",
)
PROMOTION_STATUSES = ("PROMOTED", "BLOCKED", "REJECTED")


class SupplierInboundResponse(Base):
    """Immutable owner-scoped inbound response envelope and raw evidence."""

    __tablename__ = "intelligence_supplier_inbound_responses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "response_fingerprint", name="uq_supplier_response_fingerprint"
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_response_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"), index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagements.id", ondelete="SET NULL"),
        index=True,
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_drafts.id", ondelete="SET NULL"),
        index=True,
    )
    send_command_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_rfq_send_commands.id", ondelete="SET NULL"),
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), default="EMAIL")
    sender_identity: Mapped[str | None] = mapped_column(String(320))
    recipient_identity: Mapped[str | None] = mapped_column(String(320))
    provider_message_id: Mapped[str | None] = mapped_column(String(240), index=True)
    provider_thread_id: Mapped[str | None] = mapped_column(String(240), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_content: Mapped[str] = mapped_column(Text)
    raw_content_hash: Mapped[str] = mapped_column(String(128))
    attachment_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    trust_environment: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    evidence_environment: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    correlation_state: Mapped[str] = mapped_column(String(24), default="UNMATCHED", index=True)
    correlation_reason: Mapped[str] = mapped_column(Text, default="")
    correlation_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    classification: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    response_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))


class SupplierResponseExtraction(Base):
    """Append-only deterministic extraction of one immutable response."""

    __tablename__ = "intelligence_supplier_response_extractions"
    __table_args__ = (
        UniqueConstraint("response_id", "version", name="uq_supplier_response_extraction_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_inbound_responses.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="NEEDS_REVIEW", index=True)
    extracted_fields: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    field_provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_spans: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    unknown_fields: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    extraction_authority: Mapped[str] = mapped_column(String(40), default="DETERMINISTIC_PARSER")
    source_raw_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SupplierResponseReview(Base):
    """Append-only explicit HUMAN review of one extraction."""

    __tablename__ = "intelligence_supplier_response_reviews"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_response_review_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_inbound_responses.id", ondelete="CASCADE"),
        index=True,
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_response_extractions.id", ondelete="RESTRICT"),
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32), index=True)
    provenance: Mapped[str] = mapped_column(String(24), default="HUMAN")
    corrections: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))


class SupplierResponsePromotion(Base):
    """Durable lineage from a reviewed response into PR-5A authorities."""

    __tablename__ = "intelligence_supplier_response_promotions"
    __table_args__ = (
        UniqueConstraint("owner_id", "review_id", name="uq_supplier_response_promotion_review"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_inbound_responses.id", ondelete="CASCADE"),
        index=True,
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_response_extractions.id", ondelete="RESTRICT"),
        index=True,
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_response_reviews.id", ondelete="RESTRICT"),
        index=True,
    )
    supplier_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_supplier_evidence.id", ondelete="SET NULL")
    )
    supplier_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_supplier_products.id", ondelete="SET NULL")
    )
    commercial_term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_commercial_terms.id", ondelete="SET NULL"),
    )
    readiness_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_commercial_readiness_snapshots.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(24), default="PROMOTED", index=True)
    provenance: Mapped[str] = mapped_column(String(32), default="SOURCE_PROVIDED_CLAIM")
    contradictions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
