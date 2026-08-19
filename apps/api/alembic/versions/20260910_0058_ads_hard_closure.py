"""Add Ads hard-closure lineage, budget, recovery, and drift metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260910_0058"
down_revision: str | None = "20260909_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaign_activities", sa.Column("ads_provider", sa.String(20)))
    op.add_column(
        "campaign_activities", sa.Column("ads_campaign_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("campaign_activities", sa.Column("ads_group_id", postgresql.UUID(as_uuid=True)))
    op.add_column("campaign_activities", sa.Column("ads_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "campaign_activities", sa.Column("ads_creative_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("campaign_activities", sa.Column("ads_budget_version", sa.Integer))
    op.add_column("ad_audiences", sa.Column("remarketing_segment_id", sa.String(160)))
    op.add_column(
        "ad_audiences",
        sa.Column("keyword_intent_json", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "ad_audiences",
        sa.Column(
            "provider_compatibility_json", postgresql.JSONB, nullable=False, server_default="{}"
        ),
    )
    op.add_column(
        "ad_audiences",
        sa.Column("validation_status", sa.String(24), nullable=False, server_default="unknown"),
    )
    op.add_column("ad_campaigns", sa.Column("keyword_set_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "ad_budgets",
        sa.Column("budget_type", sa.String(20), nullable=False, server_default="daily"),
    )
    op.add_column("ad_budgets", sa.Column("proposed_from_version", sa.Integer))
    op.add_column("ad_budgets", sa.Column("confirmation_fingerprint", sa.String(64)))
    op.add_column(
        "ad_budgets",
        sa.Column("remote_checkpoint_json", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.add_column("ad_budgets", sa.Column("remote_version", sa.Integer))
    op.add_column(
        "ad_creatives",
        sa.Column(
            "provider_compatibility_json", postgresql.JSONB, nullable=False, server_default="{}"
        ),
    )
    op.add_column(
        "ad_creatives",
        sa.Column(
            "objective_compatibility_json", postgresql.JSONB, nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "ad_creatives",
        sa.Column("placements_json", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "ad_conversions",
        sa.Column("attribution_type", sa.String(24), nullable=False, server_default="unknown"),
    )
    op.add_column("ad_conversions", sa.Column("attribution_window", sa.String(40)))
    op.add_column("ad_jobs", sa.Column("failure_category", sa.String(80)))
    op.add_column("ad_jobs", sa.Column("retry_after_seconds", sa.Integer))
    op.add_column("ad_jobs", sa.Column("next_retry_at", sa.DateTime(timezone=True)))
    op.add_column("ad_jobs", sa.Column("correlation_id", sa.String(64)))
    common = [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]
    op.create_table(
        "ad_failure_records",
        *common,  # type: ignore[arg-type]
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("safe_message", sa.String(500), nullable=False),
        sa.Column("retryable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("recovery_actions_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "correlation_id", name="uq_ad_failure_correlation"),
    )
    op.create_index("ix_ad_failure_records_code", "ad_failure_records", ["code"])
    op.create_index("ix_ad_failure_records_entity_id", "ad_failure_records", ["entity_id"])
    op.create_index(
        "ix_ad_failure_records_correlation_id", "ad_failure_records", ["correlation_id"]
    )
    op.create_table(
        "ad_recovery_records",
        *common,  # type: ignore[arg-type]
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="accepted"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("result_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ad_recovery_idempotency"),
    )
    op.create_index("ix_ad_recovery_records_entity_id", "ad_recovery_records", ["entity_id"])
    op.create_index(
        "ix_ad_recovery_records_correlation_id", "ad_recovery_records", ["correlation_id"]
    )
    op.create_table(
        "ad_drift_findings",
        *common,  # type: ignore[arg-type]
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(80), nullable=False),
        sa.Column("local_value_json", postgresql.JSONB),
        sa.Column("remote_value_json", postgresql.JSONB),
        sa.Column("state", sa.String(24), nullable=False, server_default="open"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ad_drift_findings_campaign_id", "ad_drift_findings", ["campaign_id"])
    op.create_index("ix_ad_drift_findings_entity_id", "ad_drift_findings", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_ad_drift_findings_entity_id", table_name="ad_drift_findings")
    op.drop_index("ix_ad_drift_findings_campaign_id", table_name="ad_drift_findings")
    op.drop_table("ad_drift_findings")
    op.drop_index("ix_ad_recovery_records_correlation_id", table_name="ad_recovery_records")
    op.drop_index("ix_ad_recovery_records_entity_id", table_name="ad_recovery_records")
    op.drop_table("ad_recovery_records")
    op.drop_index("ix_ad_failure_records_correlation_id", table_name="ad_failure_records")
    op.drop_index("ix_ad_failure_records_entity_id", table_name="ad_failure_records")
    op.drop_index("ix_ad_failure_records_code", table_name="ad_failure_records")
    op.drop_table("ad_failure_records")
    op.drop_column("ad_conversions", "attribution_window")
    op.drop_column("ad_jobs", "correlation_id")
    op.drop_column("ad_jobs", "next_retry_at")
    op.drop_column("ad_jobs", "retry_after_seconds")
    op.drop_column("ad_jobs", "failure_category")
    op.drop_column("ad_conversions", "attribution_type")
    op.drop_column("ad_creatives", "placements_json")
    op.drop_column("ad_creatives", "objective_compatibility_json")
    op.drop_column("ad_creatives", "provider_compatibility_json")
    op.drop_column("ad_budgets", "remote_version")
    op.drop_column("ad_budgets", "remote_checkpoint_json")
    op.drop_column("ad_budgets", "confirmation_fingerprint")
    op.drop_column("ad_budgets", "proposed_from_version")
    op.drop_column("ad_budgets", "budget_type")
    op.drop_column("ad_audiences", "validation_status")
    op.drop_column("ad_audiences", "provider_compatibility_json")
    op.drop_column("ad_audiences", "keyword_intent_json")
    op.drop_column("campaign_activities", "ads_budget_version")
    op.drop_column("campaign_activities", "ads_creative_id")
    op.drop_column("campaign_activities", "ads_id")
    op.drop_column("campaign_activities", "ads_group_id")
    op.drop_column("campaign_activities", "ads_campaign_id")
    op.drop_column("campaign_activities", "ads_provider")
    op.drop_column("ad_audiences", "remarketing_segment_id")
    op.drop_column("ad_campaigns", "keyword_set_id")
