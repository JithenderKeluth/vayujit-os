"""Durable, owner-scoped manufacturer and supplier website intelligence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WebsiteSourceProfile(Base):
    __tablename__ = "intelligence_website_source_profiles"
    __table_args__ = (
        UniqueConstraint("owner_id", "logical_identity", name="uq_website_profile_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    domain: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[str] = mapped_column(String(100), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    classification: Mapped[str] = mapped_column(String(80), default="UNTRUSTED_EXTERNAL_DATA")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    search_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    fetch_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    freshness_policy: Mapped[str] = mapped_column(String(24), default="MANUAL")
    refresh_target_type: Mapped[str] = mapped_column(String(64), default="WEBSITE_SOURCE")
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    next_refresh_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    verification_policy: Mapped[str] = mapped_column(String(80), default="EVIDENCE_REQUIRED")
    robots_terms_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    known_mirror_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    business_identity_hints: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    logical_identity: Mapped[str] = mapped_column(String(300), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebsiteSourceProfileVersion(Base):
    __tablename__ = "intelligence_website_source_profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version", name="uq_website_profile_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_source_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    rules: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ManufacturerCandidate(Base):
    __tablename__ = "intelligence_manufacturer_candidates"
    __table_args__ = (
        UniqueConstraint("owner_id", "logical_identity", name="uq_manufacturer_candidate_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(240))
    normalized_name: Mapped[str] = mapped_column(String(240), index=True)
    website: Mapped[str] = mapped_column(String(1000), default="")
    canonical_domain: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str] = mapped_column(String(100), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    business_type: Mapped[str] = mapped_column(String(80), default="unknown")
    manufacturer_status: Mapped[str] = mapped_column(String(32), default="claimed")
    supplier_status: Mapped[str] = mapped_column(String(32), default="unknown")
    exporter_status: Mapped[str] = mapped_column(String(32), default="unknown")
    distributor_status: Mapped[str] = mapped_column(String(32), default="unknown")
    product_categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    markets_served: Mapped[list[str]] = mapped_column(JSONB, default=list)
    years_in_business_claim: Mapped[str | None] = mapped_column(String(80))
    public_business_identifiers: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    verification_state: Mapped[str] = mapped_column(String(32), default="UNVERIFIED", index=True)
    freshness: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    confidence: Mapped[float] = mapped_column(default=0)
    risk: Mapped[list[str]] = mapped_column(JSONB, default=list)
    last_researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    logical_identity: Mapped[str] = mapped_column(String(300), index=True)
    current_status: Mapped[str] = mapped_column(String(32), default="REVIEW_REQUIRED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SupplierWebsiteCandidate(Base):
    __tablename__ = "intelligence_supplier_website_candidates"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "logical_identity", name="uq_supplier_website_candidate_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"), index=True
    )
    manufacturer_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_manufacturer_candidates.id", ondelete="SET NULL"),
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(255), index=True)
    source_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_source_profiles.id", ondelete="SET NULL"),
        index=True,
    )
    identity_state: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")
    match_state: Mapped[str] = mapped_column(String(32), default="REVIEW_REQUIRED")
    confidence: Mapped[float] = mapped_column(default=0)
    verification_state: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")
    freshness: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    risk: Mapped[list[str]] = mapped_column(JSONB, default=list)
    last_researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    logical_identity: Mapped[str] = mapped_column(String(300), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebsiteObservation(Base):
    __tablename__ = "intelligence_website_observations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "observation_identity", name="uq_website_observation_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        index=True,
    )
    source_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_source_profiles.id", ondelete="SET NULL"),
        index=True,
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_manufacturer_candidates.id", ondelete="SET NULL"),
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(255), index=True)
    page_url: Mapped[str] = mapped_column(String(1000))
    observation_type: Mapped[str] = mapped_column(String(40), index=True)
    claim_type: Mapped[str] = mapped_column(String(120), default="")
    normalized_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_provided_state: Mapped[str] = mapped_column(String(32), default="SOURCE_PROVIDED")
    verification: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")
    freshness: Mapped[str] = mapped_column(String(24), default="FRESH")
    confidence: Mapped[float] = mapped_column(default=0)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    previous_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_observations.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    observation_identity: Mapped[str] = mapped_column(String(400), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebsiteOffering(Base):
    __tablename__ = "intelligence_website_offerings"
    __table_args__ = (
        UniqueConstraint("owner_id", "logical_identity", name="uq_website_offering_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_source_profiles.id", ondelete="SET NULL"),
        index=True,
    )
    observation_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    research_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    correlation_id: Mapped[str] = mapped_column(String(80), default="")
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_manufacturer_candidates.id", ondelete="SET NULL"),
        index=True,
    )
    supplier_website_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_website_candidates.id", ondelete="SET NULL"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(240), default="")
    model_sku: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(120), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    match_state: Mapped[str] = mapped_column(String(32), default="NO_MATCH")
    match_confidence: Mapped[float] = mapped_column(default=0)
    match_reason: Mapped[str] = mapped_column(String(500), default="")
    logical_identity: Mapped[str] = mapped_column(String(400), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebsiteClaim(Base):
    __tablename__ = "intelligence_website_claims"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "candidate_id",
            "claim_type",
            "claim_identity",
            name="uq_website_claim_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_manufacturer_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(String(80), index=True)
    claim_identity: Mapped[str] = mapped_column(String(300))
    claim_value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="CLAIMED")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_reference: Mapped[str] = mapped_column(String(1000), default="")
    freshness: Mapped[str] = mapped_column(String(24), default="FRESH")
    confidence: Mapped[float] = mapped_column(default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    current_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_website_observations.id", ondelete="SET NULL")
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebsiteRefreshJob(Base):
    __tablename__ = "intelligence_website_refresh_jobs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "source_profile_id",
            "scheduled_for",
            name="uq_website_refresh_job_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_source_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(64), default="WEBSITE_SOURCE")
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(300), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    claim_count: Mapped[int] = mapped_column(Integer, default=0)


class WebsiteRefreshRecovery(Base):
    __tablename__ = "intelligence_website_refresh_recovery"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "job_id", "idempotency_key", name="uq_website_refresh_recovery_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_website_refresh_jobs.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64))
    failure_code: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED")
    safe_reason_code: Mapped[str] = mapped_column(String(120))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
