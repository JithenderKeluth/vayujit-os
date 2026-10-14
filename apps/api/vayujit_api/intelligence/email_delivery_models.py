"""Durable PR-7B controlled RFQ email delivery records.

These tables are deliberately RFQ-specific.  They are an immutable audit
boundary around the existing PR-7A engagement and PR-6C decision authorities;
they are not a generic notification system.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

RFQ_CHANNELS = ("EMAIL",)
SEND_AUTHORIZATION_STATUSES = ("AUTHORIZED", "REVOKED", "BLOCKED")
SEND_COMMAND_STATUSES = (
    "PENDING",
    "PROCESSING",
    "PROVIDER_ACCEPTED",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
    "UNKNOWN_OUTCOME",
    "BLOCKED",
)
OUTBOX_STATES = SEND_COMMAND_STATUSES
PROVIDER_OUTCOMES = ("ACCEPTED", "RETRYABLE_FAILURE", "FINAL_FAILURE", "UNKNOWN_OUTCOME")


class RfqSendAuthorization(Base):
    __tablename__ = "intelligence_rfq_send_authorizations"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_rfq_send_auth_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_contacts.id", ondelete="RESTRICT"),
        index=True,
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagements.id", ondelete="CASCADE"),
        index=True,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_drafts.id", ondelete="RESTRICT"),
        index=True,
    )
    draft_version: Mapped[int] = mapped_column(Integer)
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_approvals.id", ondelete="RESTRICT"),
        index=True,
    )
    human_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_human_decisions.id", ondelete="RESTRICT"),
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), default="EMAIL")
    recipient: Mapped[str] = mapped_column(String(320))
    subject_fingerprint: Mapped[str] = mapped_column(String(128))
    payload_fingerprint: Mapped[str] = mapped_column(String(128))
    context_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="AUTHORIZED", index=True)
    provenance: Mapped[str] = mapped_column(String(24), default="HUMAN")
    idempotency_key: Mapped[str] = mapped_column(String(220))
    supplier_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    contact_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confirmation_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RfqSendCommand(Base):
    __tablename__ = "intelligence_rfq_send_commands"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_rfq_send_command_idempotency"),
        UniqueConstraint("logical_message_id", name="uq_rfq_send_command_logical_message"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    authorization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_rfq_send_authorizations.id", ondelete="RESTRICT"),
        index=True,
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagements.id", ondelete="CASCADE"),
        index=True,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_engagement_drafts.id", ondelete="RESTRICT"),
    )
    logical_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), default="EMAIL")
    recipient: Mapped[str] = mapped_column(String(320))
    provider: Mapped[str] = mapped_column(String(48), default="fake")
    payload_fingerprint: Mapped[str] = mapped_column(String(128))
    payload_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    provider_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RfqSendOutbox(Base):
    __tablename__ = "intelligence_rfq_send_outbox"
    __table_args__ = (UniqueConstraint("command_id", name="uq_rfq_send_outbox_command"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    command_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_rfq_send_commands.id", ondelete="CASCADE"),
        index=True,
    )
    state: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RfqDeliveryAttempt(Base):
    __tablename__ = "intelligence_rfq_delivery_attempts"
    __table_args__ = (
        UniqueConstraint("command_id", "attempt_number", name="uq_rfq_delivery_attempt"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    command_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_rfq_send_commands.id", ondelete="CASCADE"),
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(48))
    provider_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    outcome: Mapped[str] = mapped_column(String(40))
    error_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retryable: Mapped[bool] = mapped_column(default=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(128))
    receipt_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# Names used by a few integrations/readers that call the records supplier sends.
SupplierSendAuthorization = RfqSendAuthorization
SupplierSendCommand = RfqSendCommand
SupplierSendOutbox = RfqSendOutbox
SupplierDeliveryAttempt = RfqDeliveryAttempt
