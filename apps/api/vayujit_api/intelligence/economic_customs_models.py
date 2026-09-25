"""Bounded customs, tax, and regulatory cost evidence (13E)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
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

CLASSIFICATION_PROVENANCES = ("UNKNOWN", "USER_PROVIDED", "SOURCE_OBSERVED")
CUSTOMS_RATE_KINDS = ("DUTY", "IMPORT_TAX", "SURCHARGE", "CESS", "LEVY")
CUSTOMS_RATE_CATEGORIES = ("CUSTOMS_DUTY", "IMPORT_TAX", "OTHER")
CUSTOMS_BASES = (
    "PRODUCT_VALUE",
    "PRODUCT_PLUS_FREIGHT",
    "EXPLICIT_CUSTOMS_VALUE",
    "EXPLICIT_TAXABLE_VALUE",
    "UNKNOWN",
)
REGULATORY_COST_CATEGORIES = ("BROKERAGE", "INSPECTION", "OTHER")
REGULATORY_REQUIREMENT_TYPES = (
    "BIS",
    "FSSAI",
    "WPC",
    "CDSCO",
    "LEGAL_METROLOGY",
    "OTHER",
    "UNKNOWN",
)
REGULATORY_REQUIREMENT_STATES = ("OBSERVED_REQUIREMENT", "USER_CONFIGURED", "UNKNOWN")
PROVENANCE = ("OBSERVED", "QUOTED", "CONFIGURED", "ASSUMED", "CALCULATED", "UNKNOWN")
FRESHNESS = ("CURRENT", "STALE", "UNKNOWN")
SNAPSHOT_COMPLETENESS = ("COMPLETE", "PARTIAL", "UNKNOWN")


class CustomsTaxContext(Base):
    __tablename__ = "intelligence_customs_tax_contexts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_customs_tax_context_idempotency"),
        CheckConstraint(
            "classification_provenance IN ('UNKNOWN','USER_PROVIDED','SOURCE_OBSERVED')",
            name="ck_customs_context_classification_provenance",
        ),
        CheckConstraint(
            "status IN ('DRAFT','CURRENT','ARCHIVED')", name="ck_customs_context_status"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    economic_context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reporting_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    classification_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_scheme: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_provenance: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ClassificationEvidence(Base):
    __tablename__ = "intelligence_classification_evidence"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_classification_evidence_idempotency"
        ),
        UniqueConstraint("owner_id", "fingerprint", name="uq_classification_evidence_fingerprint"),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED',"
            "'USER_PROVIDED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_classification_evidence_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')",
            name="ck_classification_evidence_freshness",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_customs_tax_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    classification_code: Mapped[str] = mapped_column(String(64))
    classification_scheme: Mapped[str] = mapped_column(String(64))
    jurisdiction: Mapped[str] = mapped_column(String(80))
    supplied_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provenance: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32), default="classification-evidence-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CustomsRateEvidence(Base):
    __tablename__ = "intelligence_customs_rate_evidence"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_customs_rate_evidence_idempotency"
        ),
        UniqueConstraint("owner_id", "fingerprint", name="uq_customs_rate_evidence_fingerprint"),
        CheckConstraint(
            "rate_kind IN ('DUTY','IMPORT_TAX','SURCHARGE','CESS','LEVY')",
            name="ck_customs_rate_kind",
        ),
        CheckConstraint(
            "category IN ('CUSTOMS_DUTY','IMPORT_TAX','OTHER')", name="ck_customs_rate_category"
        ),
        CheckConstraint("rate >= 0 AND rate <= 1", name="ck_customs_rate_range"),
        CheckConstraint("rate_scale = 'FRACTION_OF_ONE'", name="ck_customs_rate_scale"),
        CheckConstraint(
            "basis IN ('PRODUCT_VALUE','PRODUCT_PLUS_FREIGHT','EXPLICIT_CUSTOMS_VALUE',"
            "'EXPLICIT_TAXABLE_VALUE','UNKNOWN')",
            name="ck_customs_rate_basis",
        ),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED',"
            "'USER_PROVIDED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_customs_rate_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_customs_rate_freshness"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_customs_tax_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    classification_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_classification_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    rate_kind: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(24))
    tax_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rate: Mapped[float] = mapped_column(Numeric(24, 12))
    rate_scale: Mapped[str] = mapped_column(String(24), default="FRACTION_OF_ONE")
    basis: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    jurisdiction: Mapped[str] = mapped_column(String(80))
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(120))
    provenance: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32), default="customs-rate-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RegulatoryCostEvidence(Base):
    __tablename__ = "intelligence_regulatory_cost_evidence"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_regulatory_cost_idempotency"),
        UniqueConstraint("owner_id", "fingerprint", name="uq_regulatory_cost_fingerprint"),
        CheckConstraint(
            "cost_category IN ('BROKERAGE','INSPECTION','OTHER')",
            name="ck_regulatory_cost_category",
        ),
        CheckConstraint(
            "requirement_type IN ('BIS','FSSAI','WPC','CDSCO','LEGAL_METROLOGY','OTHER','UNKNOWN')",
            name="ck_regulatory_requirement_type",
        ),
        CheckConstraint(
            "requirement_state IN ('OBSERVED_REQUIREMENT','USER_CONFIGURED','UNKNOWN')",
            name="ck_regulatory_requirement_state",
        ),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_regulatory_cost_amount"),
        CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_regulatory_cost_currency"
        ),
        CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED',"
            "'USER_PROVIDED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_regulatory_cost_provenance",
        ),
        CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_regulatory_cost_freshness"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_customs_tax_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    cost_category: Mapped[str] = mapped_column(String(24))
    amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    requirement_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    requirement_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    source: Mapped[str] = mapped_column(String(120))
    provenance: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    freshness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assumption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32), default="regulatory-cost-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CustomsTaxSnapshot(Base):
    __tablename__ = "intelligence_customs_tax_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_customs_tax_snapshot_fingerprint"),
        CheckConstraint(
            "completeness IN ('COMPLETE','PARTIAL','UNKNOWN')",
            name="ck_customs_tax_snapshot_completeness",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_customs_tax_contexts.id", ondelete="RESTRICT"),
        index=True,
    )
    version: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    completeness: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    missing_inputs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[object]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
