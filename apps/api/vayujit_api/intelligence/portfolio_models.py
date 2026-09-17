"""Owner-scoped supplier portfolio foundation records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class PortfolioScopeType(StrEnum):
    WHOLE_BUSINESS = "whole_business"
    PRODUCT = "product"
    PRODUCT_FAMILY = "product_family"
    CATEGORY = "category"
    BRAND = "brand"
    MARKETPLACE = "marketplace"
    SOURCING_PROGRAM = "sourcing_program"
    MANUAL = "manual"


class PortfolioStatus(StrEnum):
    ACTIVE = "active"
    REVIEW_REQUIRED = "review_required"
    STALE = "stale"
    ARCHIVED = "archived"


def portfolio_now() -> datetime:
    return datetime.now(UTC)


class SupplierPortfolioContext(Base):
    """An owner-scoped portfolio scope; domain entities remain referenced, not copied."""

    __tablename__ = "intelligence_supplier_portfolio_contexts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_portfolio_owner_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    scope_type: Mapped[str] = mapped_column(String(32), default=PortfolioScopeType.MANUAL.value)
    scope_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=PortfolioStatus.ACTIVE.value)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    current_assessment_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioMembership(Base):
    """Versioned relationship between a portfolio and a canonical supplier."""

    __tablename__ = "intelligence_supplier_portfolio_memberships"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "supplier_id",
            "version",
            name="uq_supplier_portfolio_membership_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="RESTRICT"),
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    associated_products: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    associated_opportunities: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    shortlist_lineage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    due_diligence_lineage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    sourcing_scenario_lineage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    allocation_percent: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    evidence_freshness: Mapped[str] = mapped_column(String(24), default="unknown")
    confidence: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    risk: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capabilities: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    alternate_source_status: Mapped[str] = mapped_column(String(32), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioAssessmentVersion(Base):
    """Append-only, reproducible assessment metadata and immutable input snapshot reference."""

    __tablename__ = "intelligence_supplier_portfolio_assessment_versions"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "version", name="uq_supplier_portfolio_assessment_version"
        ),
        UniqueConstraint(
            "portfolio_id", "idempotency_key", name="uq_supplier_portfolio_assessment_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    version: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(24), default="created")
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioInputSnapshot(Base):
    """Immutable copy of the versioned references used to create an assessment."""

    __tablename__ = "intelligence_supplier_portfolio_input_snapshots"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", name="uq_supplier_portfolio_snapshot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_assessment_versions.id", ondelete="CASCADE"),
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioConcentrationMetric(Base):
    """Append-only deterministic concentration output for one assessment version."""

    __tablename__ = "intelligence_supplier_portfolio_concentration_metrics"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "dimension",
            "metric_type",
            name="uq_portfolio_concentration_metric",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_assessment_versions.id", ondelete="CASCADE"),
    )
    dimension: Mapped[str] = mapped_column(String(32))
    metric_type: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    classification: Mapped[str] = mapped_column(String(40))
    denominator: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    contributors: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    evidence_references: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    calculation_version: Mapped[str] = mapped_column(String(80))
    threshold_version: Mapped[str] = mapped_column(String(80))
    explanation: Mapped[str] = mapped_column(Text)
    missing_data: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioDependencyFinding(Base):
    """Append-only deterministic single-point-of-failure finding."""

    __tablename__ = "intelligence_supplier_portfolio_dependency_findings"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "dependency_type",
            "affected_supplier_id",
            "affected_product_id",
            "affected_capability",
            name="uq_portfolio_dependency_finding",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_assessment_versions.id", ondelete="CASCADE"),
    )
    dependency_type: Mapped[str] = mapped_column(String(64))
    affected_supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    affected_product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    affected_capability: Mapped[str | None] = mapped_column(String(160), nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    supporting_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    calculation_version: Mapped[str] = mapped_column(String(80))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioAlternateReadiness(Base):
    """Append-only readiness assessment tied to an immutable portfolio version."""

    __tablename__ = "intelligence_supplier_portfolio_alternate_readiness"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "supplier_id",
            "product_id",
            name="uq_portfolio_alternate_readiness",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_assessment_versions.id", ondelete="CASCADE"),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    readiness_state: Mapped[str] = mapped_column(String(40))
    reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    satisfied_requirements: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    unmet_requirements: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    stale_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    dd_gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    commercial_gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    capability_gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    next_evidence_action: Mapped[str] = mapped_column(String(240))
    calculation_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)


class SupplierPortfolioHumanAction(Base):
    """Idempotent, owner-scoped record of a bounded human portfolio decision."""

    __tablename__ = "intelligence_supplier_portfolio_human_actions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "portfolio_id",
            "action",
            "idempotency_key",
            name="uq_supplier_portfolio_human_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_portfolio_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    assessment_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="RECORDED")
    rationale: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=portfolio_now)
