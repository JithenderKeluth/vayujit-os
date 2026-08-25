"""Intelligence-owned sourcing and landed-cost persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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

REQUIREMENT_STATUSES = ("draft", "active", "archived")
RFQ_STATUSES = (
    "draft",
    "ready_for_review",
    "approved",
    "dispatch_pending",
    "dispatched_manually",
    "partially_responded",
    "responded",
    "closed",
    "cancelled",
)
DISPATCH_STATUSES = ("not_sent", "ready_for_manual_send", "sent_manually")
QUOTE_STATUSES = ("draft", "received", "expired", "accepted", "rejected")
SAMPLE_STATUSES = (
    "requested",
    "approved",
    "ordered_manually",
    "in_transit",
    "received",
    "under_review",
    "rejected",
    "archived",
)
SHIPPING_MODES = ("AIR", "SEA", "ROAD", "RAIL", "COURIER", "LOCAL", "UNKNOWN")
INCOTERMS = ("EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP")
ASSUMPTION_CLASSIFICATIONS = ("OBSERVED", "CONFIGURED", "ASSUMED", "UNKNOWN")
FX_CLASSIFICATIONS = ("CONFIGURED", "OBSERVED", "ASSUMED")
EVIDENCE_LABELS = (
    "OBSERVED",
    "SUPPLIER_QUOTED",
    "MANUAL",
    "CONFIGURED",
    "ASSUMED",
    "ESTIMATED",
    "VERIFIED",
    "DERIVED",
)
DECISION_CLASSES = (
    "strong_candidate",
    "promising",
    "review_required",
    "weak",
    "rejected",
    "blocked",
    "insufficient_evidence",
)
DECISIONS = (
    "shortlist_for_order",
    "request_negotiation",
    "request_new_sample",
    "request_requote",
    "reject",
    "hold",
    "approve_for_future_purchase",
)


class SourcingRequirement(Base):
    __tablename__ = "intelligence_sourcing_requirements"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_sourcing_requirement_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingRequirementVersion(Base):
    __tablename__ = "intelligence_sourcing_requirement_versions"
    __table_args__ = (
        UniqueConstraint("requirement_id", "version", name="uq_sourcing_requirement_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RequestForQuote(Base):
    __tablename__ = "intelligence_rfqs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_intelligence_rfq_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    requirement_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    dispatch_status: Mapped[str] = mapped_column(String(32), default="not_sent")
    title: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RFQSupplier(Base):
    __tablename__ = "intelligence_rfq_suppliers"
    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_intelligence_rfq_supplier"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_rfqs.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    supplier_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RFQDraft(Base):
    __tablename__ = "intelligence_rfq_drafts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_rfqs.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SupplierQuote(Base):
    __tablename__ = "intelligence_supplier_quotes"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "rfq_id", "supplier_id", "version", name="uq_supplier_quote_version"
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_quote_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_rfqs.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    quote_reference: Mapped[str] = mapped_column(String(180))
    quote_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 4))
    moq: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="received", index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SupplierQuoteLine(Base):
    __tablename__ = "intelligence_supplier_quote_lines"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SupplierQuoteVersion(Base):
    __tablename__ = "intelligence_supplier_quote_versions"
    __table_args__ = (
        UniqueConstraint("quote_id", "version", name="uq_supplier_quote_version_snapshot"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SampleRequest(Base):
    __tablename__ = "intelligence_sample_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_rfqs.id", ondelete="SET NULL"), nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Sample(Base):
    __tablename__ = "intelligence_samples"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sample_requests.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    evidence: Mapped[list[object]] = mapped_column(JSONB, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SampleEvaluation(Base):
    __tablename__ = "intelligence_sample_evaluations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_samples.id", ondelete="CASCADE"), unique=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Inspection(Base):
    __tablename__ = "intelligence_inspections"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    sample_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_samples.id", ondelete="SET NULL"),
        nullable=True,
    )
    inspection_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="open")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class InspectionFinding(Base):
    __tablename__ = "intelligence_inspection_findings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_inspections.id", ondelete="CASCADE"),
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(64))
    finding: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[object]] = mapped_column(JSONB, default=list)
    quantity_checked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_defective: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class NegotiationRound(Base):
    __tablename__ = "intelligence_negotiation_rounds"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="CASCADE"),
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer)
    requested_change: Mapped[str] = mapped_column(Text, default="")
    supplier_response: Mapped[str] = mapped_column(Text, default="")
    delta: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CostScenario(Base):
    __tablename__ = "intelligence_cost_scenarios"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "requirement_id", "name", "version", name="uq_intelligence_cost_scenario"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_requirements.id", ondelete="SET NULL"),
        nullable=True,
    )
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(32), default="BASE")
    version: Mapped[int] = mapped_column(Integer, default=1)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    inputs: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[str] = mapped_column(String(24), default="INSUFFICIENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LandedCostEstimate(Base):
    __tablename__ = "intelligence_landed_cost_estimates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cost_scenarios.id", ondelete="CASCADE"),
        unique=True,
    )
    per_unit: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    total: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    breakdown: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[str] = mapped_column(String(24), default="INSUFFICIENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LogisticsEstimate(Base):
    __tablename__ = "intelligence_logistics_estimates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cost_scenarios.id", ondelete="CASCADE"),
        unique=True,
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    classification: Mapped[str] = mapped_column(String(24), default="ASSUMED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DutyTaxAssumption(Base):
    __tablename__ = "intelligence_duty_tax_assumptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cost_scenarios.id", ondelete="CASCADE"),
        unique=True,
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    classification: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class FXAssumption(Base):
    __tablename__ = "intelligence_fx_assumptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cost_scenarios.id", ondelete="CASCADE"),
        unique=True,
    )
    from_currency: Mapped[str] = mapped_column(String(3))
    to_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[float] = mapped_column(Numeric(18, 8))
    classification: Mapped[str] = mapped_column(String(24), default="ASSUMED")
    reference: Mapped[str] = mapped_column(String(500), default="")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingDecision(Base):
    __tablename__ = "intelligence_sourcing_decisions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "requirement_id", "quote_id", name="uq_intelligence_sourcing_decision"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="CASCADE"),
        index=True,
    )
    classification: Mapped[str] = mapped_column(String(32), default="review_required")
    decision: Mapped[str] = mapped_column(String(40), default="hold")
    critic: Mapped[list[object]] = mapped_column(JSONB, default=list)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingApproval(Base):
    __tablename__ = "intelligence_sourcing_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_decisions.id", ondelete="CASCADE"),
        unique=True,
    )
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingWorkerJob(Base):
    __tablename__ = "intelligence_sourcing_worker_jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_intelligence_sourcing_worker_job"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    task: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    checkpoint_stage: Mapped[str] = mapped_column(String(64), default="created", index=True)
    checkpoint_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingRecoveryRecord(Base):
    __tablename__ = "intelligence_sourcing_recovery_records"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "entity_type",
            "entity_id",
            "action",
            "idempotency_key",
            name="uq_sourcing_recovery_idempotency",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(180), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RFQVersion(Base):
    __tablename__ = "intelligence_rfq_versions"
    __table_args__ = (UniqueConstraint("rfq_id", "version", name="uq_intelligence_rfq_version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_rfqs.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingAssumptionVersion(Base):
    __tablename__ = "intelligence_sourcing_assumption_versions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "scenario_id", "kind", "version", name="uq_sourcing_assumption_version"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cost_scenarios.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingScoreEvaluation(Base):
    __tablename__ = "intelligence_sourcing_score_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "requirement_id",
            "quote_id",
            "model_version",
            name="uq_sourcing_score_version",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_quotes.id", ondelete="CASCADE"),
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(32))
    weights: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    confidence: Mapped[str] = mapped_column(String(24), default="INSUFFICIENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingRuleEvaluation(Base):
    __tablename__ = "intelligence_sourcing_rule_evaluations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_sourcing_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourcingCalendarItem(Base):
    __tablename__ = "intelligence_sourcing_calendar_items"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_sourcing_calendar_item"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(240))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
