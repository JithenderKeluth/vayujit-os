"""Durable, non-sending supplier engagement foundation for PR-7A."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

ENGAGEMENT_INTENTS = ("REQUEST_INFORMATION", "REQUEST_QUOTE")
ENGAGEMENT_STATUSES = ("BLOCKED", "DRAFT", "NEEDS_REVIEW", "APPROVED_FOR_SEND", "CANCELLED")
DRAFT_STATUSES = ("DRAFT", "NEEDS_REVIEW", "CANCELLED")
APPROVAL_STATES = ("APPROVED_FOR_SEND", "INVALIDATED")


class SupplierEngagement(Base):
    __tablename__ = "intelligence_supplier_engagements"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_engagement_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_contacts.id", ondelete="SET NULL"),
        index=True,
    )
    human_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_human_decisions.id", ondelete="SET NULL"),
        index=True,
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_recommendation_assessments.id", ondelete="SET NULL"),
    )
    synthesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_decision_synthesis_snapshots.id", ondelete="SET NULL"),
    )
    decision_target: Mapped[str] = mapped_column(String(40), default="SUPPLIER_SELECTION")
    engagement_type: Mapped[str] = mapped_column(String(40), default="REQUEST_QUOTE")
    engagement_version: Mapped[int] = mapped_column(Integer, default=1)
    current_draft_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="BLOCKED", index=True)
    blocking_reasons: Mapped[list[object]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    external_writes: Mapped[list[object]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierEngagementDraft(Base):
    __tablename__ = "intelligence_supplier_engagement_drafts"
    __table_args__ = (
        UniqueConstraint("engagement_id", "version", name="uq_supplier_engagement_draft_version"),
        UniqueConstraint(
            "engagement_id", "input_fingerprint", name="uq_supplier_engagement_draft_fingerprint"
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_engagement_draft_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagements.id", ondelete="CASCADE"),
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_contacts.id", ondelete="SET NULL"),
        index=True,
    )
    human_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    synthesis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="NEEDS_REVIEW", index=True)
    supplier_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    contact_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    product_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    structured_request: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    subject: Mapped[str] = mapped_column(String(240))
    message_body: Mapped[str] = mapped_column(Text)
    template_version: Mapped[str] = mapped_column(String(80), default="rfq-neutral-v1")
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    unknowns: Mapped[list[object]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[object]] = mapped_column(JSONB, default=list)
    provenance: Mapped[str] = mapped_column(String(32), default="SYSTEM_DRAFT")
    idempotency_key: Mapped[str] = mapped_column(String(220))
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    supersedes_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_drafts.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierEngagementApproval(Base):
    __tablename__ = "intelligence_supplier_engagement_approvals"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_engagement_approval_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagements.id", ondelete="CASCADE"),
        index=True,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_drafts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    human_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    provenance: Mapped[str] = mapped_column(String(24), default="HUMAN")
    context_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    supersedes_approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_approvals.id", ondelete="SET NULL"),
    )
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    external_writes: Mapped[list[object]] = mapped_column(JSONB, default=list)


class SupplierEngagementEvent(Base):
    __tablename__ = "intelligence_supplier_engagement_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagements.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    draft_version: Mapped[int] = mapped_column(Integer, default=0)
    provenance: Mapped[str] = mapped_column(String(32), default="SYSTEM")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
