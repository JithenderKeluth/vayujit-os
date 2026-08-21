from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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

AD_PROVIDERS = ("meta", "google", "amazon", "flipkart")
AD_STATES = (
    "draft",
    "ready",
    "approved",
    "scheduled",
    "active",
    "paused",
    "completed",
    "failed",
    "archived",
)


class AdsBase(Base):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdAccount(AdsBase):
    __tablename__ = "ad_accounts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "provider", "external_account_id", name="uq_ad_account_remote"
        ),
        CheckConstraint(
            "provider IN ('meta','google','amazon','flipkart')", name="ck_ad_account_provider"
        ),
        CheckConstraint("status IN ('active','disabled','archived')", name="ck_ad_account_status"),
        CheckConstraint(
            "environment IN ('local','sandbox','production')", name="ck_ad_account_environment"
        ),
    )
    provider: Mapped[str] = mapped_column(String(20), index=True)
    external_account_id: Mapped[str] = mapped_column(String(180), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    environment: Mapped[str] = mapped_column(String(20), default="local")
    status: Mapped[str] = mapped_column(String(20), default="disabled", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    validation_status: Mapped[str] = mapped_column(String(20), default="unknown")
    credential_version: Mapped[int] = mapped_column(Integer, default=1)
    credential_metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    timezone_name: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    capabilities_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdCampaign(AdsBase):
    __tablename__ = "ad_campaigns"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('meta','google','amazon','flipkart')", name="ck_ad_campaign_provider"
        ),
        CheckConstraint(
            "state IN ('draft','ready','approved','scheduled','active','paused',"
            "'completed','failed','archived')",
            name="ck_ad_campaign_state",
        ),
        Index("ix_ad_campaign_owner_filters", "owner_id", "provider", "state"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_campaign_idempotency"),
    )
    provider: Mapped[str] = mapped_column(String(20), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_accounts.id", ondelete="RESTRICT"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(String(40), default="awareness")
    state: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone_name: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    bidding_strategy: Mapped[str | None] = mapped_column(String(60))
    targeting_summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    keyword_set_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    remote_campaign_id: Mapped[str | None] = mapped_column(String(180), index=True)
    sync_state: Mapped[str] = mapped_column(String(30), default="local_only")
    reconciliation_state: Mapped[str] = mapped_column(String(30), default="unknown")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    preview_fingerprint: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_failure_message: Mapped[str | None] = mapped_column(String(500))
    failure_category: Mapped[str | None] = mapped_column(String(80))
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    marketplace: Mapped[str | None] = mapped_column(String(24), index=True)
    listing_id: Mapped[str | None] = mapped_column(String(180), index=True)
    listing_version: Mapped[int | None] = mapped_column(Integer)
    listing_state: Mapped[str | None] = mapped_column(String(24))


class AdMarketplaceListing(AdsBase):
    __tablename__ = "ad_marketplace_listings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "marketplace", "listing_id", "version", name="uq_ad_marketplace_listing"
        ),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_accounts.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(24), index=True)
    listing_id: Mapped[str] = mapped_column(String(180), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(24), default="active")
    title: Mapped[str] = mapped_column(String(240))
    sku: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class AdGroup(AdsBase):
    __tablename__ = "ad_groups"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "campaign_id", "idempotency_key", name="uq_ad_group_idempotency"
        ),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    provider_group_type: Mapped[str] = mapped_column(String(20), default="ad_group")
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    audience_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_audiences.id", ondelete="SET NULL")
    )
    placements_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    targeting_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    remote_group_id: Mapped[str | None] = mapped_column(String(180), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))


class AdAudience(AdsBase):
    __tablename__ = "ad_audiences"
    __table_args__ = (
        CheckConstraint(
            "age_min >= 0 AND age_max <= 120 AND age_min <= age_max", name="ck_ad_audience_age"
        ),
    )
    name: Mapped[str] = mapped_column(String(160))
    geography_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    languages_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    age_min: Mapped[int] = mapped_column(Integer, default=18)
    age_max: Mapped[int] = mapped_column(Integer, default=65)
    gender: Mapped[str | None] = mapped_column(String(20))
    interests_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    demographics_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    custom_segment_id: Mapped[str | None] = mapped_column(String(160))
    remarketing_segment_id: Mapped[str | None] = mapped_column(String(160))
    keyword_intent_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provider_compatibility_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    validation_status: Mapped[str] = mapped_column(String(24), default="unknown")
    exclusions_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    provenance: Mapped[str] = mapped_column(String(40), default="operator_defined")


class AdBudget(AdsBase):
    __tablename__ = "ad_budgets"
    __table_args__ = (
        CheckConstraint(
            "daily_amount >= 0 AND lifetime_amount >= 0", name="ck_ad_budget_nonnegative"
        ),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    daily_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    lifetime_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    spend_guardrails_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_type: Mapped[str] = mapped_column(String(20), default="daily")
    proposed_from_version: Mapped[int | None] = mapped_column(Integer)
    confirmation_fingerprint: Mapped[str | None] = mapped_column(String(64))
    remote_checkpoint_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    remote_version: Mapped[int | None] = mapped_column(Integer)


class AdCreative(AdsBase):
    __tablename__ = "ad_creatives"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_creative_idempotency"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    creative_type: Mapped[str] = mapped_column(String(20), default="content")
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT"), index=True
    )
    artifact_version: Mapped[int | None] = mapped_column(Integer)
    image_output_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    image_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    image_version: Mapped[int | None] = mapped_column(Integer)
    video_generation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    video_output_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    video_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    video_version: Mapped[int | None] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    headline: Mapped[str | None] = mapped_column(String(200))
    primary_text: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    cta: Mapped[str | None] = mapped_column(String(60))
    destination_url: Mapped[str | None] = mapped_column(String(2048))
    exact_lineage_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    approval_status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    readiness_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provider_compatibility_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    objective_compatibility_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    placements_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str | None] = mapped_column(String(64))


class Ad(AdsBase):
    __tablename__ = "ads"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_idempotency"),)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )
    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_creatives.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20), index=True)
    placement: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    remote_ad_id: Mapped[str | None] = mapped_column(String(180), index=True)
    sync_state: Mapped[str] = mapped_column(String(30), default="local_only")
    reconciliation_state: Mapped[str] = mapped_column(String(30), default="unknown")
    idempotency_key: Mapped[str] = mapped_column(String(180))


class AdSchedule(AdsBase):
    __tablename__ = "ad_schedules"
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone_name: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    state: Mapped[str] = mapped_column(String(24), default="draft")


class AdMetric(AdsBase):
    __tablename__ = "ad_metrics"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "campaign_id", "observed_at", "metric_key", name="uq_ad_metric_snapshot"
        ),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_groups.id", ondelete="CASCADE")
    )
    ad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ads.id", ondelete="CASCADE")
    )
    metric_key: Mapped[str] = mapped_column(String(40))
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    availability: Mapped[str] = mapped_column(String(20), default="synthetic")
    source: Mapped[str] = mapped_column(String(30), default="fake_connector")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdConversion(AdsBase):
    __tablename__ = "ad_conversions"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider_event_id", name="uq_ad_conversion_event"),
    )
    provider: Mapped[str] = mapped_column(String(20))
    provider_event_id: Mapped[str] = mapped_column(String(180))
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_groups.id", ondelete="SET NULL")
    )
    ad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ads.id", ondelete="SET NULL")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    conversion_type: Mapped[str] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(40), default="fake_connector")
    attribution_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    attribution_type: Mapped[str] = mapped_column(String(24), default="unknown")
    attribution_window: Mapped[str | None] = mapped_column(String(40))


class AdFailureRecord(AdsBase):
    __tablename__ = "ad_failure_records"
    __table_args__ = (
        UniqueConstraint("owner_id", "correlation_id", name="uq_ad_failure_correlation"),
    )
    provider: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(80), index=True)
    safe_message: Mapped[str] = mapped_column(String(500))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_actions_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)


class AdRecoveryRecord(AdsBase):
    __tablename__ = "ad_recovery_records"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_recovery_idempotency"),
    )
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="accepted")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    result_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)


class AdDriftFinding(AdsBase):
    __tablename__ = "ad_drift_findings"
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    field_name: Mapped[str] = mapped_column(String(80))
    local_value_json: Mapped[object | None] = mapped_column(JSONB)
    remote_value_json: Mapped[object | None] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(24), default="open")


class AdOptimizationRule(AdsBase):
    __tablename__ = "ad_optimization_rules"
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    provider: Mapped[str | None] = mapped_column(String(20), index=True)
    objective: Mapped[str | None] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    mode: Mapped[str] = mapped_column(String(24), default="recommend_only")
    rule_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    guardrails_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    allowed_actions_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    metric_window_days: Mapped[int] = mapped_column(Integer, default=7)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    daily_action_limit: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdExperiment(AdsBase):
    __tablename__ = "ad_experiments"
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    provider: Mapped[str] = mapped_column(String(20), default="meta")
    objective: Mapped[str] = mapped_column(String(40), default="awareness")
    hypothesis: Mapped[str] = mapped_column(String(500), default="")
    variable: Mapped[str] = mapped_column(String(40), default="creative")
    primary_metric: Mapped[str] = mapped_column(String(40), default="ctr")
    status: Mapped[str] = mapped_column(String(24), default="draft")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    variants_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    allocation_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    budget_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence_method: Mapped[str] = mapped_column(String(80), default="bounded_deterministic")
    winner_variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    insufficient_data: Mapped[bool] = mapped_column(Boolean, default=False)


class AdOptimizationRecommendation(AdsBase):
    __tablename__ = "ad_optimization_recommendations"
    provider: Mapped[str] = mapped_column(String(20), index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    ad_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    creative_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_optimization_rules.id", ondelete="SET NULL"), index=True
    )
    recommendation_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="recommendation")
    confidence: Mapped[str] = mapped_column(String(12), default="medium")
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    explanation_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    current_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    proposed_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    action_options_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    metric_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metric_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(40), default="synthetic_local")
    stale_reason: Mapped[str | None] = mapped_column(String(240))


class AdOptimizationDecision(AdsBase):
    __tablename__ = "ad_optimization_decisions"
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ad_optimization_recommendations.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(60))
    decision_status: Mapped[str] = mapped_column(String(24), default="previewed")
    preview_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="owner")


class AdOptimizationExecution(AdsBase):
    __tablename__ = "ad_optimization_executions"
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ad_optimization_recommendations.id", ondelete="CASCADE"),
        index=True,
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_optimization_decisions.id", ondelete="SET NULL")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_jobs.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    before_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    after_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    rollback_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64))


class AdPerformanceAnomaly(AdsBase):
    __tablename__ = "ad_performance_anomalies"
    provider: Mapped[str] = mapped_column(String(20))
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    anomaly_type: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(40), default="synthetic_local")


class AdCreativeFatigueSignal(AdsBase):
    __tablename__ = "ad_creative_fatigue_signals"
    provider: Mapped[str] = mapped_column(String(20))
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_creatives.id", ondelete="CASCADE"), index=True
    )
    fatigue_state: Mapped[str] = mapped_column(String(20), default="healthy", index=True)
    creative_age_days: Mapped[int] = mapped_column(Integer, default=0)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(40), default="synthetic_local")


class AdExperimentVariant(AdsBase):
    __tablename__ = "ad_experiment_variants"
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_experiments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    allocation_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    creative_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_creatives.id", ondelete="SET NULL")
    )
    exact_version_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="ready")


class AdExperimentResult(AdsBase):
    __tablename__ = "ad_experiment_results"
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_experiments.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_experiment_variants.id", ondelete="CASCADE")
    )
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    relative_difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    confidence_label: Mapped[str] = mapped_column(String(20), default="insufficient_data")
    is_leader: Mapped[bool] = mapped_column(Boolean, default=False)
    methodology: Mapped[str] = mapped_column(String(80), default="bounded_deterministic")


class AdBudgetRecommendation(AdsBase):
    __tablename__ = "ad_budget_recommendations"
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ad_optimization_recommendations.id", ondelete="CASCADE"),
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    proposed_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    strategy: Mapped[str | None] = mapped_column(String(60))
    guardrails_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    availability: Mapped[str] = mapped_column(String(24), default="available")


class AdBidRecommendation(AdsBase):
    __tablename__ = "ad_bid_recommendations"
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ad_optimization_recommendations.id", ondelete="CASCADE"),
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    proposed_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    strategy: Mapped[str | None] = mapped_column(String(60))
    guardrails_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    availability: Mapped[str] = mapped_column(String(24), default="available")


class AdRemoteMapping(AdsBase):
    __tablename__ = "ad_remote_mappings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "provider", "entity_type", "local_entity_id", name="uq_ad_remote_local"
        ),
        UniqueConstraint(
            "owner_id", "provider", "entity_type", "remote_id", name="uq_ad_remote_remote"
        ),
    )
    provider: Mapped[str] = mapped_column(String(20), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    local_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    remote_id: Mapped[str] = mapped_column(String(180), index=True)
    remote_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdJob(AdsBase):
    __tablename__ = "ad_jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_job_idempotency"),
    )
    operation: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    provider: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    request_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_failure_message: Mapped[str | None] = mapped_column(String(500))
    failure_category: Mapped[str | None] = mapped_column(String(80))
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


AdSet = AdGroup
