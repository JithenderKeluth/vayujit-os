"""Intelligence-owned supplier discovery persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

SUPPLIER_TYPES = (
    "manufacturer",
    "wholesaler",
    "distributor",
    "importer",
    "exporter",
    "private_label",
    "dropship",
    "agent",
    "trader",
    "unknown",
)
SUPPLIER_VERIFICATION_STATES = (
    "unverified",
    "self_reported",
    "partially_verified",
    "verified",
    "high_confidence",
    "suspended",
    "blocked",
)
SUPPLIER_DECISIONS = ("shortlist", "reject", "review", "approve_for_rfq")
SUPPLIER_RECOMMENDATIONS = (
    "strong_match",
    "promising",
    "review_required",
    "weak_match",
    "rejected",
    "blocked",
    "insufficient_evidence",
)
SUPPLIER_SOURCE_TYPES = (
    "indiamart",
    "alibaba",
    "tradeindia",
    "global_sources",
    "made_in_china",
    "manufacturer_website",
    "distributor_website",
    "wholesale_directory",
    "trade_association",
    "trade_fair",
    "offline_market",
    "local_manufacturer",
    "local_wholesaler",
    "local_distributor",
    "referral",
    "factory_visit",
    "manual_entry",
    "csv_import",
    "internal_supplier_record",
)
SUPPLIER_ACCESS_MODES = (
    "api",
    "provider_connector",
    "approved_web_fetch",
    "manual_import",
    "manual_entry",
    "offline",
    "internal",
)
SUPPLIER_PRICE_KINDS = (
    "observed_quote",
    "displayed_price",
    "estimated_range",
    "manual_quote",
    "unknown",
)
SUPPLIER_EVIDENCE_KINDS = ("observed", "manual", "self_reported", "verified", "assumed", "derived")
SUPPLIER_FAILURES = (
    "source_unavailable",
    "source_rate_limited",
    "source_auth_failed",
    "invalid_supplier",
    "invalid_offering",
    "unsafe_source",
    "stale_supplier_data",
    "verification_failed",
    "scoring_failed",
    "checkpoint_invalid",
)


class Supplier(Base):
    __tablename__ = "intelligence_suppliers"
    __table_args__ = (
        UniqueConstraint("owner_id", "normalized_identity", name="uq_supplier_owner_identity"),
        CheckConstraint(
            "supplier_type IN (" + ",".join(f"'{v}'" for v in SUPPLIER_TYPES) + ")",
            name="ck_supplier_type",
        ),
        CheckConstraint(
            "verification_state IN ("
            + ",".join(f"'{v}'" for v in SUPPLIER_VERIFICATION_STATES)
            + ")",
            name="ck_supplier_verification",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(240))
    supplier_type: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    normalized_domain: Mapped[str | None] = mapped_column(String(240), index=True)
    business_identifier: Mapped[str | None] = mapped_column(String(160), index=True)
    source_identity: Mapped[str] = mapped_column(String(240), default="manual")
    normalized_identity: Mapped[str] = mapped_column(String(300), index=True)
    is_offline: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    verification_state: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    communication_status: Mapped[str] = mapped_column(String(32), default="not_contacted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierSource(Base):
    __tablename__ = "intelligence_supplier_sources"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "source_type", "external_id", name="uq_supplier_source_identity"
        ),
        CheckConstraint(
            "source_type IN (" + ",".join(f"'{v}'" for v in SUPPLIER_SOURCE_TYPES) + ")",
            name="ck_supplier_source_type",
        ),
        CheckConstraint(
            "access_mode IN (" + ",".join(f"'{v}'" for v in SUPPLIER_ACCESS_MODES) + ")",
            name="ck_supplier_access_mode",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    access_mode: Mapped[str] = mapped_column(String(32), default="manual_entry")
    external_id: Mapped[str | None] = mapped_column(String(180))
    reference: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(40), default="local_fixture")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierContact(Base):
    __tablename__ = "intelligence_supplier_contacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(80))
    whatsapp: Mapped[str | None] = mapped_column(String(80))
    preferred_method: Mapped[str | None] = mapped_column(String(40))
    communication_status: Mapped[str] = mapped_column(String(32), default="not_contacted")
    provenance: Mapped[str] = mapped_column(String(240), default="manual")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierCapability(Base):
    __tablename__ = "intelligence_supplier_capabilities"
    __table_args__ = (UniqueConstraint("supplier_id", "capability", name="uq_supplier_capability"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    capability: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(32), default="claimed")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierProduct(Base):
    __tablename__ = "intelligence_supplier_products"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "source_id", "source_reference", name="uq_supplier_product_source"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
        index=True,
    )
    source_reference: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(120), index=True)
    specifications: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    observed_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    price_kind: Mapped[str] = mapped_column(String(32), default="unknown")
    moq: Mapped[float | None] = mapped_column(Numeric(18, 4))
    moq_unit: Mapped[str | None] = mapped_column(String(40))
    sample_available: Mapped[bool | None] = mapped_column(Boolean)
    sample_moq: Mapped[float | None] = mapped_column(Numeric(18, 4))
    sample_lead_days: Mapped[int | None] = mapped_column(Integer)
    production_lead_days: Mapped[int | None] = mapped_column(Integer)
    dispatch_lead_days: Mapped[int | None] = mapped_column(Integer)
    shipping_lead_days: Mapped[int | None] = mapped_column(Integer)
    private_label: Mapped[bool] = mapped_column(Boolean, default=False)
    customization: Mapped[bool] = mapped_column(Boolean, default=False)
    packaging: Mapped[str | None] = mapped_column(String(240))
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    freshness_status: Mapped[str] = mapped_column(String(24), default="fresh")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierEvidence(Base):
    __tablename__ = "intelligence_supplier_evidence"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_evidence_idempotency"),
        CheckConstraint(
            "evidence_kind IN (" + ",".join(f"'{v}'" for v in SUPPLIER_EVIDENCE_KINDS) + ")",
            name="ck_supplier_evidence_kind",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
        index=True,
    )
    evidence_kind: Mapped[str] = mapped_column(String(24), default="observed")
    reference: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    normalized_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(128))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    freshness_status: Mapped[str] = mapped_column(String(24), default="fresh")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(180))


class SupplierVerification(Base):
    __tablename__ = "intelligence_supplier_verifications"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "supplier_id",
            "idempotency_key",
            name="uq_supplier_verification_idempotency",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(32), default="unverified")
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(180), index=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierCommercialTerm(Base):
    __tablename__ = "intelligence_supplier_commercial_terms"
    __table_args__ = (
        UniqueConstraint("supplier_product_id", "version", name="uq_supplier_term_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    supplier_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_products.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    price_tiers: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    moq: Mapped[float | None] = mapped_column(Numeric(18, 4))
    sample_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    tooling_fee: Mapped[float | None] = mapped_column(Numeric(18, 4))
    packaging_fee: Mapped[float | None] = mapped_column(Numeric(18, 4))
    branding_fee: Mapped[float | None] = mapped_column(Numeric(18, 4))
    payment_terms: Mapped[str | None] = mapped_column(String(160))
    deposit_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    balance_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    incoterm: Mapped[str | None] = mapped_column(String(20))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    sample_lead_days: Mapped[int | None] = mapped_column(Integer)
    production_lead_days: Mapped[int | None] = mapped_column(Integer)
    dispatch_lead_days: Mapped[int | None] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierCertificationClaim(Base):
    __tablename__ = "intelligence_supplier_certification_claims"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "supplier_id",
            "claim",
            "version",
            name="uq_supplier_certification_version",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    claim: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_reference: Mapped[str] = mapped_column(String(500))
    document_reference: Mapped[str | None] = mapped_column(String(500))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verification_state: Mapped[str] = mapped_column(String(32), default="unverified")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)


class SupplierDocumentReference(Base):
    __tablename__ = "intelligence_supplier_document_references"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "supplier_id", "reference_id", name="uq_supplier_document_ref"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    reference_id: Mapped[str] = mapped_column(String(180))
    document_type: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(240))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    source_reference: Mapped[str] = mapped_column(String(500))
    verification_state: Mapped[str] = mapped_column(String(32), default="unverified")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierHistoryEvent(Base):
    __tablename__ = "intelligence_supplier_history"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SupplierRecoveryRecord(Base):
    __tablename__ = "intelligence_supplier_recovery"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_recovery_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_searches.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(32), default="accepted")
    reason_code: Mapped[str | None] = mapped_column(String(80))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SupplierRiskAssessment(Base):
    __tablename__ = "intelligence_supplier_risk_assessments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierScoreEvaluation(Base):
    __tablename__ = "intelligence_supplier_score_evaluations"
    __table_args__ = (
        UniqueConstraint("supplier_id", "model_version", name="uq_supplier_score_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    model_version: Mapped[str] = mapped_column(String(80))
    weights: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    inputs: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    final_score: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    recommendation: Mapped[str] = mapped_column(String(32), default="insufficient_evidence")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SupplierOpportunityMatch(Base):
    __tablename__ = "intelligence_supplier_opportunity_matches"
    __table_args__ = (
        UniqueConstraint(
            "supplier_product_id", "requirement_key", name="uq_supplier_match_requirement"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    supplier_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_products.id", ondelete="CASCADE"),
        index=True,
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_searches.id", ondelete="CASCADE"),
        index=True,
    )
    requirement_key: Mapped[str] = mapped_column(String(180))
    match_score: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    matched_dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    unmatched_requirements: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    explanation: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)


class SupplierDecision(Base):
    __tablename__ = "intelligence_supplier_decisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_decision_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(180), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SupplierSearch(Base):
    __tablename__ = "intelligence_supplier_searches"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_search_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    requirements: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_policy: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    ruleset_version: Mapped[str] = mapped_column(String(80), default="supplier-default-v1")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_classification: Mapped[str | None] = mapped_column(String(80))
    provider_execution_id: Mapped[str | None] = mapped_column(String(180), unique=True)
    lease_token: Mapped[str | None] = mapped_column(String(180))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint_state: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
