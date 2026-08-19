"""Add normalized local Ads and Marketing Automation foundation."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0057"
down_revision: str | None = "20260908_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column[Any]]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _fk(
    table: str, name: str, target: str, source: str = "owner_id", ondelete: str = "CASCADE"
) -> None:
    op.create_foreign_key(name, table, target, [source], ["id"], ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "ad_accounts",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("external_account_id", sa.String(180), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False, server_default="local"),
        sa.Column("status", sa.String(20), nullable=False, server_default="disabled"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("validated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("credential_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "credential_metadata_json", postgresql.JSONB, nullable=False, server_default="{}"
        ),
        sa.Column("encrypted_credentials", sa.Text),
        sa.Column("timezone_name", sa.String(80), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("capabilities_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id", "provider", "external_account_id", name="uq_ad_account_remote"
        ),
    )
    _fk("ad_accounts", "fk_ad_accounts_owner", "users")
    op.create_index("ix_ad_accounts_owner_id", "ad_accounts", ["owner_id"])
    op.create_index("ix_ad_accounts_provider", "ad_accounts", ["provider"])
    op.create_table(
        "ad_audiences",
        *_common(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("geography_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("languages_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("age_min", sa.Integer, nullable=False, server_default="18"),
        sa.Column("age_max", sa.Integer, nullable=False, server_default="65"),
        sa.Column("gender", sa.String(20)),
        sa.Column("interests_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("demographics_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("custom_segment_id", sa.String(160)),
        sa.Column("exclusions_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("provenance", sa.String(40), nullable=False, server_default="operator_defined"),
    )
    _fk("ad_audiences", "fk_ad_audiences_owner", "users")
    op.create_index("ix_ad_audiences_owner_id", "ad_audiences", ["owner_id"])
    op.create_table(
        "ad_campaigns",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True)),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("objective", sa.String(40), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("timezone_name", sa.String(80), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("bidding_strategy", sa.String(60)),
        sa.Column("targeting_summary_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("remote_campaign_id", sa.String(180)),
        sa.Column("sync_state", sa.String(30), nullable=False, server_default="local_only"),
        sa.Column("reconciliation_state", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("preview_fingerprint", sa.String(64)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_failure_message", sa.String(500)),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_campaign_idempotency"),
    )
    _fk("ad_campaigns", "fk_ad_campaigns_owner", "users")
    _fk("ad_campaigns", "fk_ad_campaigns_account", "ad_accounts", "account_id", "RESTRICT")
    _fk("ad_campaigns", "fk_ad_campaigns_brand", "brands", "brand_id", "RESTRICT")
    _fk("ad_campaigns", "fk_ad_campaigns_product", "products", "product_id", "RESTRICT")
    op.create_index("ix_ad_campaigns_owner_id", "ad_campaigns", ["owner_id"])
    op.create_index("ix_ad_campaigns_provider", "ad_campaigns", ["provider"])
    op.create_index("ix_ad_campaigns_state", "ad_campaigns", ["state"])
    op.create_table(
        "ad_budgets",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("daily_amount", sa.Numeric(18, 2)),
        sa.Column("lifetime_amount", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("spend_guardrails_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("confirmed", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    _fk("ad_budgets", "fk_ad_budgets_owner", "users")
    _fk("ad_budgets", "fk_ad_budgets_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    op.create_index("ix_ad_budgets_campaign_id", "ad_budgets", ["campaign_id"])
    op.create_table(
        "ad_creatives",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("creative_type", sa.String(20), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True)),
        sa.Column("artifact_version", sa.Integer),
        sa.Column("image_output_id", postgresql.UUID(as_uuid=True)),
        sa.Column("image_media_id", postgresql.UUID(as_uuid=True)),
        sa.Column("image_version", sa.Integer),
        sa.Column("video_generation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("video_output_id", postgresql.UUID(as_uuid=True)),
        sa.Column("video_media_id", postgresql.UUID(as_uuid=True)),
        sa.Column("video_version", sa.Integer),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("headline", sa.String(200)),
        sa.Column("primary_text", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("cta", sa.String(60)),
        sa.Column("destination_url", sa.String(2048)),
        sa.Column("exact_lineage_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("approval_status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("readiness_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("fingerprint", sa.String(64)),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_creative_idempotency"),
    )
    _fk("ad_creatives", "fk_ad_creatives_owner", "users")
    _fk("ad_creatives", "fk_ad_creatives_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    _fk("ad_creatives", "fk_ad_creatives_product", "products", "product_id", "RESTRICT")
    _fk(
        "ad_creatives", "fk_ad_creatives_artifact", "generated_artifacts", "artifact_id", "RESTRICT"
    )
    op.create_index("ix_ad_creatives_campaign_id", "ad_creatives", ["campaign_id"])
    op.create_table(
        "ad_groups",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_group_type", sa.String(20), nullable=False, server_default="ad_group"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("audience_id", postgresql.UUID(as_uuid=True)),
        sa.Column("placements_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("targeting_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("remote_group_id", sa.String(180)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "campaign_id", "idempotency_key", name="uq_ad_group_idempotency"
        ),
    )
    _fk("ad_groups", "fk_ad_groups_owner", "users")
    _fk("ad_groups", "fk_ad_groups_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    _fk("ad_groups", "fk_ad_groups_audience", "ad_audiences", "audience_id", "SET NULL")
    op.create_index("ix_ad_groups_campaign_id", "ad_groups", ["campaign_id"])
    op.create_table(
        "ads",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creative_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("placement", sa.String(80)),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("remote_ad_id", sa.String(180)),
        sa.Column("sync_state", sa.String(30), nullable=False, server_default="local_only"),
        sa.Column("reconciliation_state", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_idempotency"),
    )
    _fk("ads", "fk_ads_owner", "users")
    _fk("ads", "fk_ads_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    _fk("ads", "fk_ads_group", "ad_groups", "group_id", "CASCADE")
    _fk("ads", "fk_ads_creative", "ad_creatives", "creative_id", "RESTRICT")
    _fk("ads", "fk_ads_product", "products", "product_id", "RESTRICT")
    op.create_index("ix_ads_campaign_id", "ads", ["campaign_id"])
    op.create_table(
        "ad_schedules",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("timezone_name", sa.String(80), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
    )
    _fk("ad_schedules", "fk_ad_schedules_owner", "users")
    _fk("ad_schedules", "fk_ad_schedules_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    op.create_table(
        "ad_metrics",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ad_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metric_key", sa.String(40), nullable=False),
        sa.Column("value", sa.Numeric(18, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("availability", sa.String(20), nullable=False, server_default="synthetic"),
        sa.Column("source", sa.String(30), nullable=False, server_default="fake_connector"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "campaign_id", "observed_at", "metric_key", name="uq_ad_metric_snapshot"
        ),
    )
    _fk("ad_metrics", "fk_ad_metrics_owner", "users")
    _fk("ad_metrics", "fk_ad_metrics_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    _fk("ad_metrics", "fk_ad_metrics_group", "ad_groups", "group_id", "CASCADE")
    _fk("ad_metrics", "fk_ad_metrics_ad", "ads", "ad_id", "CASCADE")
    op.create_table(
        "ad_conversions",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_event_id", sa.String(180), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ad_id", postgresql.UUID(as_uuid=True)),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("conversion_type", sa.String(60), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("attribution_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("owner_id", "provider_event_id", name="uq_ad_conversion_event"),
    )
    _fk("ad_conversions", "fk_ad_conversions_owner", "users")
    _fk("ad_conversions", "fk_ad_conversions_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    op.create_table(
        "ad_remote_mappings",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("local_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remote_id", sa.String(180), nullable=False),
        sa.Column("remote_state_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id", "provider", "entity_type", "local_entity_id", name="uq_ad_remote_local"
        ),
        sa.UniqueConstraint(
            "owner_id", "provider", "entity_type", "remote_id", name="uq_ad_remote_remote"
        ),
    )
    _fk("ad_remote_mappings", "fk_ad_remote_mappings_owner", "users")
    op.create_table(
        "ad_optimization_rules",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("rule_json", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    _fk("ad_optimization_rules", "fk_ad_opt_owner", "users")
    _fk("ad_optimization_rules", "fk_ad_opt_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    op.create_table(
        "ad_experiments",
        *_common(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("variants_json", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    _fk("ad_experiments", "fk_ad_experiments_owner", "users")
    _fk("ad_experiments", "fk_ad_experiments_campaign", "ad_campaigns", "campaign_id", "CASCADE")
    op.create_table(
        "ad_jobs",
        *_common(),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result_json", postgresql.JSONB),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_failure_message", sa.String(500)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_job_idempotency"),
    )
    _fk("ad_jobs", "fk_ad_jobs_owner", "users")


def downgrade() -> None:
    for table in (
        "ad_jobs",
        "ad_experiments",
        "ad_optimization_rules",
        "ad_remote_mappings",
        "ad_conversions",
        "ad_metrics",
        "ad_schedules",
        "ads",
        "ad_groups",
        "ad_creatives",
        "ad_budgets",
        "ad_campaigns",
        "ad_audiences",
        "ad_accounts",
    ):
        op.drop_table(table)
