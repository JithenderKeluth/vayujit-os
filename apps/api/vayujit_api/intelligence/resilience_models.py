"""Append-only 8E.3 resilience dimensions, scores, projections, and recommendations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def resilience_now() -> datetime:
    return datetime.now(UTC)


class SupplierPortfolioResilienceDimensionResult(Base):
    __tablename__ = "intelligence_supplier_portfolio_resilience_dimensions"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "dimension",
            name="uq_portfolio_resilience_dimension",
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
    dimension: Mapped[str] = mapped_column(String(64))
    score: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    classification: Mapped[str] = mapped_column(String(32))
    evidence_status: Mapped[str] = mapped_column(String(16))
    calculation_version: Mapped[str] = mapped_column(String(80))
    supporting_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    evidence_references: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    penalties: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=resilience_now)


class SupplierPortfolioResilienceScore(Base):
    __tablename__ = "intelligence_supplier_portfolio_resilience_scores"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", name="uq_portfolio_resilience_score"),
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
    score: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    classification: Mapped[str] = mapped_column(String(24))
    evidence_status: Mapped[str] = mapped_column(String(16))
    confidence_value: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    confidence_classification: Mapped[str] = mapped_column(String(24))
    score_version: Mapped[str] = mapped_column(String(80))
    component_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    penalty_snapshot: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=resilience_now)


class SupplierPortfolioConfidenceProjection(Base):
    __tablename__ = "intelligence_supplier_portfolio_confidence_projections"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", name="uq_portfolio_confidence_projection"),
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
    value: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    classification: Mapped[str] = mapped_column(String(24))
    evidence_status: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    calculation_version: Mapped[str] = mapped_column(String(80))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=resilience_now)


class SupplierPortfolioRiskProjection(Base):
    __tablename__ = "intelligence_supplier_portfolio_risk_projections"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", name="uq_portfolio_risk_projection"),
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
    classification: Mapped[str] = mapped_column(String(24))
    exposure: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    supporting_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(String(80))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=resilience_now)


class SupplierPortfolioRecommendation(Base):
    __tablename__ = "intelligence_supplier_portfolio_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id", "logical_key", name="uq_portfolio_recommendation"
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
    recommendation_type: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(16))
    affected_supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    affected_product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    affected_dependency_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    logical_key: Mapped[str] = mapped_column(String(240))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    dimensions_affected: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    expected_benefit: Mapped[str] = mapped_column(Text)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    recommendation_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=resilience_now)
