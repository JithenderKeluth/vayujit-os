"""Owner-scoped Review Intelligence foundation models (Slice 11A)."""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

REVIEW_CONTEXT_STATUSES = ("DRAFT", "ACTIVE", "STALE", "ARCHIVED")
REVIEW_FRESHNESS = ("CURRENT", "STALE", "UNKNOWN")
REVIEW_EVIDENCE_STATES = ("AVAILABLE", "PARTIAL", "MISSING", "UNKNOWN", "UNVERIFIED")
REVIEW_VERIFICATION_STATES = ("UNVERIFIED", "VERIFIED", "REJECTED", "UNKNOWN")
VERIFIED_PURCHASE_STATES = ("TRUE", "FALSE", "UNKNOWN")
INGESTION_MODES = ("DISABLED", "LOCAL_FIXTURE", "LIVE_READ_ONLY")
INGESTION_BATCH_STATUSES = ("REQUESTED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED")
DUPLICATE_CLASSIFICATIONS = (
    "EXACT_REPLAY",
    "AUTHORITATIVE_DUPLICATE",
    "FINGERPRINT_DUPLICATE",
    "POSSIBLE_DUPLICATE",
    "DISTINCT",
)
QUALITY_STATES = ("COMPLETE", "PARTIAL", "MINIMAL", "INVALID")


class ReviewContext(Base):
    __tablename__ = "intelligence_review_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_review_context_owner_idempotency"),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','STALE','ARCHIVED')", name="ck_review_context_status"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    product_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), index=True
    )
    competitor_context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(180), default="Review context")
    marketplace: Mapped[str] = mapped_column(String(120), default="", index=True)
    market: Mapped[str] = mapped_column(String(120), default="", index=True)
    locale: Mapped[str | None] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    input_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewSource(Base):
    __tablename__ = "intelligence_review_sources"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "source_key", name="uq_review_source_context_key"
        ),
        Index("ix_review_source_context_observed", "owner_id", "context_id", "observed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    intelligence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="SET NULL"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), default="manual")
    provider: Mapped[str] = mapped_column(String(120), default="manual", index=True)
    source_key: Mapped[str] = mapped_column(String(240))
    marketplace: Mapped[str | None] = mapped_column(String(120))
    external_product_identifier: Mapped[str | None] = mapped_column(String(240))
    source_reference: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    freshness_status: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewRecord(Base):
    __tablename__ = "intelligence_review_records"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "provider",
            "provider_review_id",
            name="uq_review_provider_identity",
        ),
        UniqueConstraint("owner_id", "context_id", "fingerprint", name="uq_review_fingerprint"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= rating_scale)",
            name="ck_review_rating_bounds",
        ),
        CheckConstraint("rating_scale IS NULL OR rating_scale > 0", name="ck_review_rating_scale"),
        CheckConstraint(
            "helpful_count IS NULL OR helpful_count >= 0", name="ck_review_helpful_nonnegative"
        ),
        Index("ix_review_record_context_date", "owner_id", "context_id", "review_date"),
        Index("ix_review_record_context_source", "owner_id", "context_id", "source_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_sources.id", ondelete="SET NULL"),
        index=True,
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_evidence.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(120), default="manual", index=True)
    provider_review_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    external_product_id: Mapped[str | None] = mapped_column(String(240))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    rating_scale: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    title: Mapped[str | None] = mapped_column(String(1000))
    body: Mapped[str | None] = mapped_column(Text)
    reviewer_display_id: Mapped[str | None] = mapped_column(String(240))
    verified_purchase: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    language: Mapped[str | None] = mapped_column(String(40))
    locale: Mapped[str | None] = mapped_column(String(40))
    helpful_count: Mapped[int | None] = mapped_column(Integer)
    variant_info: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    verification_status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    freshness_status: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    evidence_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    canonical_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    fingerprint_version: Mapped[str] = mapped_column(String(32), default="review-fingerprint-v1")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    ingestion_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_ingestion_batches.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewSnapshot(Base):
    __tablename__ = "intelligence_review_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "snapshot_version", name="uq_review_snapshot_version"
        ),
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_snapshot_fingerprint"
        ),
        Index("ix_review_snapshot_context_captured", "owner_id", "context_id", "captured_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_snapshots.id", ondelete="SET NULL"),
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    rated_review_count: Mapped[int] = mapped_column(Integer, default=0)
    review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_inventory: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    evidence_coverage: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    freshness_summary: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    statistics_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    calculation_version: Mapped[str] = mapped_column(String(80), default="review-foundation-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewIngestionBatch(Base):
    __tablename__ = "intelligence_review_ingestion_batches"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "idempotency_key",
            name="uq_review_ingestion_batch_idempotency",
        ),
        Index("ix_review_ingestion_batch_context_created", "owner_id", "context_id", "created_at"),
        CheckConstraint(
            "mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')",
            name="ck_review_ingestion_batch_mode",
        ),
        CheckConstraint(
            "status IN ('REQUESTED','RUNNING','COMPLETED','PARTIAL','FAILED')",
            name="ck_review_ingestion_batch_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_review_sources.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(120), default="LOCAL_FIXTURE", index=True)
    mode: Mapped[str] = mapped_column(String(32), default="LOCAL_FIXTURE", index=True)
    status: Mapped[str] = mapped_column(String(24), default="REQUESTED", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_observation_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    adapter_version: Mapped[str] = mapped_column(String(40), default="review-adapter-v1")
    normalization_version: Mapped[str] = mapped_column(
        String(40), default="review-normalization-v1"
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewIngestionCandidate(Base):
    __tablename__ = "intelligence_review_ingestion_candidates"
    __table_args__ = (
        UniqueConstraint("batch_id", "ordinal", name="uq_review_ingestion_candidate_ordinal"),
        Index("ix_review_ingestion_candidate_batch_status", "owner_id", "batch_id", "accepted"),
        Index(
            "ix_review_ingestion_candidate_duplicate",
            "owner_id",
            "batch_id",
            "duplicate_classification",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_ingestion_batches.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_review_sources.id", ondelete="SET NULL")
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    provider_review_id: Mapped[str | None] = mapped_column(String(240))
    fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    duplicate_classification: Mapped[str] = mapped_column(
        String(32), default="DISTINCT", index=True
    )
    quality_state: Mapped[str] = mapped_column(String(16), default="INVALID", index=True)
    accepted: Mapped[bool] = mapped_column(default=False, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(80), index=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_review_records.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewObservation(Base):
    __tablename__ = "intelligence_review_observations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "review_record_id",
            "source_fingerprint",
            name="uq_review_observation_source_state",
        ),
        Index(
            "ix_review_observation_record_observed", "owner_id", "review_record_id", "observed_at"
        ),
        Index("ix_review_observation_batch", "owner_id", "batch_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    review_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_records.id", ondelete="CASCADE"),
        index=True,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_ingestion_batches.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_review_sources.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(120), default="LOCAL_FIXTURE")
    provider_review_id: Mapped[str | None] = mapped_column(String(240))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    normalization_version: Mapped[str] = mapped_column(
        String(40), default="review-normalization-v1"
    )
    raw_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


ANALYSIS_MODES = ("DISABLED", "LOCAL_FIXTURE", "LIVE_READ_ONLY")
ANALYSIS_STATUSES = ("COMPLETED", "FAILED")
SENTIMENT_CLASSES = ("POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "UNKNOWN")
ANALYSIS_ITEM_TYPES = (
    "TOPIC",
    "THEME",
    "PAIN_POINT",
    "PRAISED_ATTRIBUTE",
    "FEATURE_REQUEST",
    "QUALITY_ISSUE",
)
SEVERITY_LEVELS = ("LOW", "MODERATE", "HIGH", "UNKNOWN")
GAP_TYPES = (
    "MISSING_FEATURE",
    "FEATURE_IMPROVEMENT",
    "QUALITY_IMPROVEMENT",
    "DURABILITY_IMPROVEMENT",
    "SIZE_OR_FIT_GAP",
    "VARIANT_GAP",
    "PACKAGING_GAP",
    "USABILITY_GAP",
    "PERFORMANCE_GAP",
    "VALUE_CONCERN",
    "ACCESSORY_GAP",
    "INFORMATION_GAP",
    "PRESERVE_ATTRIBUTE",
    "TRADE_OFF",
    "OTHER",
    "UNKNOWN",
)
GAP_SUPPORT = ("SINGLE_OBSERVATION", "LIMITED", "REPEATED", "STRONG", "UNKNOWN")
SIGNAL_TYPES = (
    "PRODUCT_IMPROVEMENT",
    "FEATURE_ADDITION",
    "QUALITY_IMPROVEMENT",
    "VARIANT_EXPANSION",
    "ACCESSORY_OPPORTUNITY",
    "USABILITY_IMPROVEMENT",
    "POSITIONING_HYPOTHESIS",
    "DIFFERENTIATION_HYPOTHESIS",
    "PRESERVE_STRENGTH",
    "TRADE_OFF",
    "RESEARCH_REQUIRED",
)
SIGNAL_STATUSES = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTORY",
    "RESEARCH_REQUIRED",
)
EVIDENCE_STRENGTHS = ("WEAK", "MODERATE", "STRONG", "UNKNOWN")
CHANGE_COMPARISON_STATUSES = ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED")
REVIEW_CHANGE_TYPES = (
    "REVIEW_COUNT_CHANGE",
    "SOURCE_COVERAGE_CHANGE",
    "EVIDENCE_COVERAGE_CHANGE",
    "FRESHNESS_CHANGE",
    "RATING_DISTRIBUTION_CHANGE",
    "SENTIMENT_DISTRIBUTION_CHANGE",
    "THEME_APPEARED",
    "THEME_DISAPPEARED",
    "THEME_SUPPORT_CHANGED",
    "PAIN_POINT_APPEARED",
    "PAIN_POINT_DISAPPEARED",
    "PAIN_POINT_SUPPORT_CHANGED",
    "PAIN_POINT_SEVERITY_CHANGED",
    "PRAISE_APPEARED",
    "PRAISE_DISAPPEARED",
    "PRAISE_SUPPORT_CHANGED",
    "FEATURE_REQUEST_APPEARED",
    "FEATURE_REQUEST_DISAPPEARED",
    "FEATURE_REQUEST_SUPPORT_CHANGED",
    "QUALITY_SIGNAL_APPEARED",
    "QUALITY_SIGNAL_DISAPPEARED",
    "QUALITY_SIGNAL_CHANGED",
    "QUALITY_SIGNAL_SEVERITY_CHANGED",
    "PRODUCT_GAP_APPEARED",
    "PRODUCT_GAP_DISAPPEARED",
    "PRODUCT_GAP_SUPPORT_CHANGED",
    "OPPORTUNITY_SIGNAL_APPEARED",
    "OPPORTUNITY_SIGNAL_DISAPPEARED",
    "OPPORTUNITY_SIGNAL_STATUS_CHANGED",
    "OPPORTUNITY_SIGNAL_STRENGTH_CHANGED",
    "CONTRADICTION_CHANGED",
    "RESEARCH_GAP_CHANGED",
    "REVIEW_OBSERVATION_CHANGED",
)
CHANGE_SEMANTICS = ("OBSERVED_CHANGE", "DERIVED_DETERMINISTIC_CHANGE", "DERIVED_SEMANTIC_CHANGE")
CHANGE_STATUSES = (
    "NEW",
    "ONGOING",
    "RESOLVED",
    "REVERTED",
    "SUPERSEDED",
    "UNRESOLVED",
    "POSSIBLY_DISAPPEARED",
)
MATERIALITY_LEVELS = ("IMMATERIAL", "LOW", "MODERATE", "HIGH", "UNKNOWN")
ALERT_ELIGIBILITY = ("NO_ALERT", "REVIEW", "ALERT")
REVIEW_CHANGE_CALCULATION_VERSION = "review-change-calculation-v1"
REVIEW_CHANGE_MATERIALITY_VERSION = "review-change-materiality-v1"


class ReviewAnalysis(Base):
    __tablename__ = "intelligence_review_analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_analysis_input"
        ),
        Index("ix_review_analysis_context_created", "owner_id", "context_id", "created_at"),
        CheckConstraint(
            "mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')", name="ck_review_analysis_mode"
        ),
        CheckConstraint("status IN ('COMPLETED','FAILED')", name="ck_review_analysis_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer)
    analysis_version: Mapped[str] = mapped_column(String(40), default="review-analysis-v1")
    calculation_version: Mapped[str] = mapped_column(String(40), default="review-calculation-v1")
    normalization_version: Mapped[str] = mapped_column(
        String(40), default="review-normalization-v1"
    )
    taxonomy_version: Mapped[str] = mapped_column(String(40), default="review-taxonomy-v1")
    semantic_method_version: Mapped[str] = mapped_column(String(60), default="local-rules-v1")
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    mode: Mapped[str] = mapped_column(String(24), default="LOCAL_FIXTURE", index=True)
    status: Mapped[str] = mapped_column(String(24), default="COMPLETED", index=True)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    included_records: Mapped[int] = mapped_column(Integer, default=0)
    excluded_records: Mapped[int] = mapped_column(Integer, default=0)
    cohort_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    rating_distribution: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    sentiment_distribution: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_distribution: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    evidence_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewAnalysisAnnotation(Base):
    __tablename__ = "intelligence_review_analysis_annotations"
    __table_args__ = (
        UniqueConstraint("analysis_id", "review_record_id", name="uq_review_analysis_annotation"),
        Index("ix_review_analysis_annotation_review", "owner_id", "review_record_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    input_language: Mapped[str] = mapped_column(String(24), default="")
    analysis_language: Mapped[str] = mapped_column(String(24), default="")
    translation_lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_records.id", ondelete="CASCADE"),
        index=True,
    )
    sentiment: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    aspect_sentiments: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    quality_state: Mapped[str] = mapped_column(String(16), default="PARTIAL")
    classification_type: Mapped[str] = mapped_column(String(24), default="DERIVED_SEMANTIC")
    method_version: Mapped[str] = mapped_column(String(60), default="local-rules-v1")
    confidence: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    limitation: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewAnalysisItem(Base):
    __tablename__ = "intelligence_review_analysis_items"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "item_type", "canonical_label", name="uq_review_analysis_item"
        ),
        Index("ix_review_analysis_item_analysis_type", "owner_id", "analysis_id", "item_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(32), index=True)
    canonical_label: Mapped[str] = mapped_column(String(120))
    raw_labels: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sentiment: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    sentiment_distribution: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    cohort_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict[str, int | float]] = mapped_column(JSONB, default=dict)
    source_distribution: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    supporting_review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    freshness: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    evidence_state: Mapped[str] = mapped_column(String(24), default="PARTIAL")
    classification_type: Mapped[str] = mapped_column(String(24), default="DERIVED_SEMANTIC")
    method_version: Mapped[str] = mapped_column(String(60), default="local-rules-v1")
    limitation: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewProductGapAnalysis(Base):
    __tablename__ = "intelligence_review_product_gap_analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_gap_analysis_input"
        ),
        Index("ix_review_gap_analysis_context_created", "owner_id", "context_id", "created_at"),
        CheckConstraint("status IN ('COMPLETED','FAILED')", name="ck_review_gap_analysis_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    review_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_analyses.id", ondelete="RESTRICT"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    product_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    analysis_version: Mapped[str] = mapped_column(String(40), default="review-gap-analysis-v1")
    calculation_version: Mapped[str] = mapped_column(
        String(40), default="review-gap-calculation-v1"
    )
    rule_version: Mapped[str] = mapped_column(String(40), default="review-gap-rules-v1")
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(24), default="COMPLETED", index=True)
    gap_count: Mapped[int] = mapped_column(Integer, default=0)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewProductGap(Base):
    __tablename__ = "intelligence_review_product_gaps"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "gap_type", "canonical_label", name="uq_review_product_gap"
        ),
        Index("ix_review_product_gap_analysis", "owner_id", "analysis_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    gap_type: Mapped[str] = mapped_column(String(40), index=True)
    canonical_label: Mapped[str] = mapped_column(String(120))
    hypothesis: Mapped[str] = mapped_column(String(500))
    source_item_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    support_classification: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    cohort_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict[str, int | float]] = mapped_column(JSONB, default=dict)
    source_distribution: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    supporting_review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    opposing_review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    severity: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    evidence_strength: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    confidence: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="RESEARCH_REQUIRED")
    required_validations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    rule_version: Mapped[str] = mapped_column(String(40), default="review-gap-rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewOpportunitySignal(Base):
    __tablename__ = "intelligence_review_opportunity_signals"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "signal_type", "canonical_label", name="uq_review_opportunity_signal"
        ),
        Index("ix_review_opportunity_signal_analysis", "owner_id", "analysis_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    gap_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_product_gaps.id", ondelete="SET NULL"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(String(40), index=True)
    canonical_label: Mapped[str] = mapped_column(String(120))
    hypothesis: Mapped[str] = mapped_column(String(500))
    explanation: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="RESEARCH_REQUIRED", index=True)
    evidence_strength: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    cohort_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict[str, int | float]] = mapped_column(JSONB, default=dict)
    source_distribution: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    supporting_review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    opposing_review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    required_validations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    rule_version: Mapped[str] = mapped_column(String(40), default="review-gap-rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewChangeComparison(Base):
    __tablename__ = "intelligence_review_change_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_change_comparison_input"
        ),
        CheckConstraint(
            "status IN ('COMPLETED','PARTIALLY_COMPLETED','FAILED')",
            name="ck_review_change_comparison_status",
        ),
        Index(
            "ix_review_change_comparison_context_created", "owner_id", "context_id", "created_at"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    baseline_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    current_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    baseline_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_analyses.id", ondelete="RESTRICT"),
        index=True,
    )
    current_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_analyses.id", ondelete="RESTRICT"),
        index=True,
    )
    baseline_gap_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_gap_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    comparison_version: Mapped[int] = mapped_column(Integer, default=1)
    calculation_version: Mapped[str] = mapped_column(
        String(80), default=REVIEW_CHANGE_CALCULATION_VERSION
    )
    materiality_version: Mapped[str] = mapped_column(
        String(80), default=REVIEW_CHANGE_MATERIALITY_VERSION
    )
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewChangeEvent(Base):
    __tablename__ = "intelligence_review_change_events"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "event_fingerprint", name="uq_review_change_event_fingerprint"
        ),
        CheckConstraint(
            "change_type IN (" + ",".join("'" + item + "'" for item in REVIEW_CHANGE_TYPES) + ")",
            name="ck_review_change_event_type",
        ),
        CheckConstraint(
            "observed_or_derived IN ('OBSERVED_CHANGE','DERIVED_DETERMINISTIC_CHANGE','DERIVED_SEMANTIC_CHANGE')",  # noqa: E501
            name="ck_review_change_event_semantics",
        ),
        CheckConstraint(
            "status IN (" + ",".join("'" + item + "'" for item in CHANGE_STATUSES) + ")",
            name="ck_review_change_event_status",
        ),
        CheckConstraint(
            "materiality IN (" + ",".join("'" + item + "'" for item in MATERIALITY_LEVELS) + ")",
            name="ck_review_change_event_materiality",
        ),
        CheckConstraint(
            "alert_eligibility IN ('NO_ALERT','REVIEW','ALERT')",
            name="ck_review_change_event_alert",
        ),
        Index("ix_review_change_event_context_created", "owner_id", "context_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_change_comparisons.id", ondelete="CASCADE"),
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(64), index=True)
    subject_type: Mapped[str] = mapped_column(String(48), default="REVIEW_ANALYSIS")
    subject_key: Mapped[str] = mapped_column(String(180), index=True)
    observed_or_derived: Mapped[str] = mapped_column(String(40), default="DERIVED_SEMANTIC_CHANGE")
    baseline_value: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    current_value: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    absolute_delta: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    relative_delta: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    baseline_support: Mapped[int] = mapped_column(Integer, default=0)
    current_support: Mapped[int] = mapped_column(Integer, default=0)
    baseline_cohort: Mapped[int] = mapped_column(Integer, default=0)
    current_cohort: Mapped[int] = mapped_column(Integer, default=0)
    baseline_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    current_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_distribution: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    freshness: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    materiality: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)
    materiality_version: Mapped[str] = mapped_column(
        String(80), default=REVIEW_CHANGE_MATERIALITY_VERSION
    )
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    alert_eligibility: Mapped[str] = mapped_column(String(16), default="NO_ALERT", index=True)
    alert_reason: Mapped[str] = mapped_column(String(300), default="")
    research_gaps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(String(1200), default="")
    supporting_review_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    event_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    rule_version: Mapped[str] = mapped_column(String(80), default=REVIEW_CHANGE_CALCULATION_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
