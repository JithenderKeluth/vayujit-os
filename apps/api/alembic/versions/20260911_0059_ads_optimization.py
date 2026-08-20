"""Add deterministic Ads optimization and marketing intelligence records."""

# ruff: noqa: E501
# mypy: ignore-errors

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260911_0059"
down_revision: str | None = "20260910_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _json(name: str, default: str = "{}") -> sa.Column[object]:
    return sa.Column(name, postgresql.JSONB, nullable=False, server_default=default)


def upgrade() -> None:
    op.alter_column("ad_optimization_rules", "campaign_id", nullable=True)
    op.add_column("ad_optimization_rules", sa.Column("provider", sa.String(20)))
    op.add_column("ad_optimization_rules", sa.Column("objective", sa.String(40)))
    op.add_column(
        "ad_optimization_rules",
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column(
        "ad_optimization_rules",
        sa.Column("mode", sa.String(24), nullable=False, server_default="recommend_only"),
    )
    op.add_column("ad_optimization_rules", _json("guardrails_json"))
    op.add_column(
        "ad_optimization_rules",
        sa.Column("allowed_actions_json", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "ad_optimization_rules",
        sa.Column("metric_window_days", sa.Integer, nullable=False, server_default="7"),
    )
    op.add_column(
        "ad_optimization_rules",
        sa.Column("cooldown_seconds", sa.Integer, nullable=False, server_default="86400"),
    )
    op.add_column(
        "ad_optimization_rules",
        sa.Column("daily_action_limit", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column("ad_optimization_rules", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.create_index("ix_ad_optimization_rules_provider", "ad_optimization_rules", ["provider"])

    op.add_column(
        "ad_experiments",
        sa.Column("provider", sa.String(20), nullable=False, server_default="meta"),
    )
    op.add_column(
        "ad_experiments",
        sa.Column("objective", sa.String(40), nullable=False, server_default="awareness"),
    )
    op.add_column(
        "ad_experiments", sa.Column("hypothesis", sa.String(500), nullable=False, server_default="")
    )
    op.add_column(
        "ad_experiments",
        sa.Column("variable", sa.String(40), nullable=False, server_default="creative"),
    )
    op.add_column(
        "ad_experiments",
        sa.Column("primary_metric", sa.String(40), nullable=False, server_default="ctr"),
    )
    op.add_column("ad_experiments", sa.Column("start_at", sa.DateTime(timezone=True)))
    op.add_column("ad_experiments", sa.Column("end_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ad_experiments",
        sa.Column("allocation_json", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "ad_experiments",
        sa.Column("budget_json", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "ad_experiments",
        sa.Column(
            "confidence_method",
            sa.String(80),
            nullable=False,
            server_default="bounded_deterministic",
        ),
    )
    op.add_column("ad_experiments", sa.Column("winner_variant_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "ad_experiments",
        sa.Column("insufficient_data", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "ad_optimization_recommendations",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("group_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ad_id", postgresql.UUID(as_uuid=True)),
        sa.Column("creative_id", postgresql.UUID(as_uuid=True)),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True)),
        sa.Column("recommendation_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="recommendation"),
        sa.Column("confidence", sa.String(12), nullable=False, server_default="medium"),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        _json("evidence_json"),
        _json("explanation_json"),
        _json("current_state_json"),
        _json("proposed_state_json"),
        sa.Column("action_options_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metric_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="synthetic_local"),
        sa.Column("stale_reason", sa.String(240)),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["ad_optimization_rules.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "owner_id", "fingerprint", name="uq_ad_optimization_recommendation_fingerprint"
        ),
        sa.CheckConstraint(
            "severity IN ('information','recommendation','warning','critical')",
            name="ck_ad_optimization_recommendation_severity",
        ),
        sa.CheckConstraint(
            "confidence IN ('high','medium','low')",
            name="ck_ad_optimization_recommendation_confidence",
        ),
    )
    for name, columns in {
        "campaign_id": ["campaign_id"],
        "product_id": ["product_id"],
        "provider": ["provider"],
        "status": ["status"],
        "fingerprint": ["fingerprint"],
        "metric_window_end": ["metric_window_end"],
    }.items():
        op.create_index(
            f"ix_ad_optimization_recommendations_{name}", "ad_optimization_recommendations", columns
        )

    op.create_table(
        "ad_optimization_decisions",
        *_common(),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("decision_status", sa.String(24), nullable=False, server_default="previewed"),
        _json("preview_json"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="owner"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["ad_optimization_recommendations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "owner_id", "recommendation_id", "action", name="uq_ad_optimization_decision"
        ),
    )
    op.create_index(
        "ix_ad_optimization_decisions_recommendation_id",
        "ad_optimization_decisions",
        ["recommendation_id"],
    )
    op.create_index(
        "ix_ad_optimization_decisions_correlation_id",
        "ad_optimization_decisions",
        ["correlation_id"],
    )

    op.create_table(
        "ad_optimization_executions",
        *_common(),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        _json("before_state_json"),
        _json("after_state_json"),
        _json("rollback_state_json"),
        _json("result_json"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["ad_optimization_recommendations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"], ["ad_optimization_decisions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["ad_jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_ad_optimization_execution_idempotency"
        ),
    )
    op.create_index(
        "ix_ad_optimization_executions_recommendation_id",
        "ad_optimization_executions",
        ["recommendation_id"],
    )
    op.create_index(
        "ix_ad_optimization_executions_status", "ad_optimization_executions", ["status"]
    )

    op.create_table(
        "ad_performance_anomalies",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("anomaly_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        _json("evidence_json"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="synthetic_local"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "fingerprint", name="uq_ad_performance_anomaly_fingerprint"
        ),
    )
    op.create_index(
        "ix_ad_performance_anomalies_campaign_id", "ad_performance_anomalies", ["campaign_id"]
    )
    op.create_index("ix_ad_performance_anomalies_status", "ad_performance_anomalies", ["status"])

    op.create_table(
        "ad_creative_fatigue_signals",
        *_common(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creative_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fatigue_state", sa.String(20), nullable=False, server_default="healthy"),
        sa.Column("creative_age_days", sa.Integer, nullable=False, server_default="0"),
        _json("evidence_json"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="synthetic_local"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creative_id"], ["ad_creatives.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_ad_creative_fatigue_fingerprint"),
    )
    op.create_index(
        "ix_ad_creative_fatigue_signals_campaign_id", "ad_creative_fatigue_signals", ["campaign_id"]
    )
    op.create_index(
        "ix_ad_creative_fatigue_signals_state", "ad_creative_fatigue_signals", ["fatigue_state"]
    )

    op.create_table(
        "ad_experiment_variants",
        *_common(),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("allocation_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("creative_id", postgresql.UUID(as_uuid=True)),
        sa.Column("exact_version_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["ad_experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creative_id"], ["ad_creatives.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "owner_id", "experiment_id", "name", name="uq_ad_experiment_variant_name"
        ),
    )
    op.create_index(
        "ix_ad_experiment_variants_experiment_id", "ad_experiment_variants", ["experiment_id"]
    )

    op.create_table(
        "ad_experiment_results",
        *_common(),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        _json("metrics_json"),
        sa.Column("relative_difference", sa.Numeric(18, 6)),
        sa.Column(
            "confidence_label", sa.String(20), nullable=False, server_default="insufficient_data"
        ),
        sa.Column("is_leader", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "methodology", sa.String(80), nullable=False, server_default="bounded_deterministic"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["ad_experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["ad_experiment_variants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "experiment_id", "variant_id", name="uq_ad_experiment_result_variant"
        ),
    )
    op.create_index(
        "ix_ad_experiment_results_experiment_id", "ad_experiment_results", ["experiment_id"]
    )

    for table, rec_table in (
        ("ad_budget_recommendations", "ad_optimization_recommendations"),
        ("ad_bid_recommendations", "ad_optimization_recommendations"),
    ):
        suffix = "budget" if "budget" in table else "bid"
        op.create_table(
            table,
            *_common(),
            sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("current_value", sa.Numeric(18, 4)),
            sa.Column("proposed_value", sa.Numeric(18, 4)),
            sa.Column("currency", sa.String(3)),
            sa.Column("strategy", sa.String(60)),
            _json("guardrails_json"),
            sa.Column("availability", sa.String(24), nullable=False, server_default="available"),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["recommendation_id"], [rec_table + ".id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "owner_id", "recommendation_id", name=f"uq_ad_{suffix}_recommendation"
            ),
        )
        op.create_index(f"ix_{table}_campaign_id", table, ["campaign_id"])


def downgrade() -> None:
    for table in (
        "ad_bid_recommendations",
        "ad_budget_recommendations",
        "ad_experiment_results",
        "ad_experiment_variants",
        "ad_creative_fatigue_signals",
        "ad_performance_anomalies",
        "ad_optimization_executions",
        "ad_optimization_decisions",
        "ad_optimization_recommendations",
    ):
        op.drop_table(table)
    op.drop_index("ix_ad_optimization_rules_provider", table_name="ad_optimization_rules")
    for column in (
        "archived_at",
        "daily_action_limit",
        "cooldown_seconds",
        "metric_window_days",
        "allowed_actions_json",
        "guardrails_json",
        "mode",
        "version",
        "objective",
        "provider",
    ):
        op.drop_column("ad_optimization_rules", column)
    op.alter_column("ad_optimization_rules", "campaign_id", nullable=False)
    for column in (
        "insufficient_data",
        "winner_variant_id",
        "confidence_method",
        "budget_json",
        "allocation_json",
        "end_at",
        "start_at",
        "primary_metric",
        "variable",
        "hypothesis",
        "objective",
        "provider",
    ):
        op.drop_column("ad_experiments", column)
