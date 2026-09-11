"""Owner-scoped supplier due-diligence ledger."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

DUE_DILIGENCE_STATUSES = (
    "OPEN",
    "RESEARCH_REQUIRED",
    "RESEARCH_IN_PROGRESS",
    "REVIEW_REQUIRED",
    "SUFFICIENT",
    "BLOCKED",
    "CLOSED",
)
GAP_DIMENSIONS = (
    "IDENTITY",
    "LEGAL_ENTITY",
    "LOCATION",
    "CONTACTABILITY",
    "MANUFACTURING_CAPABILITY",
    "PRODUCT_CAPABILITY",
    "CERTIFICATION",
    "FACILITY",
    "SPECIFICATION",
    "PRICE",
    "MOQ",
    "LEAD_TIME",
    "AVAILABILITY",
    "PAYMENT_TERMS",
    "SHIPPING_TERMS",
    "EXPORT_CAPABILITY",
    "RISK",
    "REPUTATION",
    "SOURCE_DIVERSITY",
    "FRESHNESS",
    "CONTRADICTION",
    "OTHER",
)
GAP_STATES = (
    "MISSING",
    "WEAK",
    "STALE",
    "CONTRADICTORY",
    "INSUFFICIENT",
    "RESEARCHING",
    "RESOLVED",
    "WAIVED_BY_HUMAN",
    "BLOCKED",
)
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class SupplierDueDiligenceContext(Base):
    __tablename__ = "intelligence_supplier_due_diligence_contexts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_due_diligence_context_idempotency"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    shortlist_context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    shortlist_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    current_assessment_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SupplierDueDiligenceAssessment(Base):
    __tablename__ = "intelligence_supplier_due_diligence_assessments"
    __table_args__ = (
        UniqueConstraint("context_id", "version", name="uq_due_diligence_assessment_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    readiness: Mapped[str] = mapped_column(String(32), default="BLOCKED")
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SupplierEvidenceGap(Base):
    __tablename__ = "intelligence_supplier_evidence_gaps"
    __table_args__ = (
        UniqueConstraint(
            "context_id",
            "assessment_version",
            "dimension",
            name="uq_due_diligence_gap_dimension_version",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    assessment_version: Mapped[int] = mapped_column(Integer)
    dimension: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    classification: Mapped[str] = mapped_column(String(16), default="REQUIRED")
    reason: Mapped[str] = mapped_column(Text, default="")
    required_evidence: Mapped[list[object]] = mapped_column(JSONB, default=list)
    evidence_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    freshness_state: Mapped[str] = mapped_column(String(24), default="unknown")
    contradiction_state: Mapped[str] = mapped_column(String(24), default="none")
    priority_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    priority_level: Mapped[str] = mapped_column(String(16), default="LOW")
    resolution_evidence_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    resolution_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution_observation_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupplierResearchPlan(Base):
    __tablename__ = "intelligence_supplier_due_diligence_plans"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "assessment_version",
            "idempotency_key",
            name="uq_due_diligence_plan_identity",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
        index=True,
    )
    assessment_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    priority: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    budget: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    allowed_methods: Mapped[list[object]] = mapped_column(JSONB, default=list)
    prohibited_methods: Mapped[list[object]] = mapped_column(JSONB, default=list)
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SupplierResearchTask(Base):
    __tablename__ = "intelligence_supplier_due_diligence_tasks"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "plan_id",
            "gap_id",
            "idempotency_key",
            name="uq_due_diligence_task_identity",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_due_diligence_plans.id", ondelete="CASCADE"),
        index=True,
    )
    gap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_evidence_gaps.id", ondelete="CASCADE"),
        index=True,
    )
    shared_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    priority: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
