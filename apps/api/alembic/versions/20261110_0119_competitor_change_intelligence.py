"""Add immutable competitive change intelligence persistence (Slice 10D)."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261110_0119"
down_revision = "20261109_0118"
branch_labels = None
depends_on = None


def _common(name: str, *extra: Any) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *extra,
    )
    prefix = {
        "intelligence_competitor_change_comparisons": "ccmp",
        "intelligence_competitor_change_events": "ccev",
        "intelligence_competitor_change_alert_eligibility": "ccal",
    }[name]
    op.create_index(f"ix_{prefix}_owner", name, ["owner_id"])


def upgrade() -> None:
    _common(
        "intelligence_competitor_change_comparisons",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "baseline_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "baseline_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "current_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("comparison_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "calculation_version",
            sa.String(120),
            nullable=False,
            server_default="competitor-change-v1",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("summary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("comparison_version >= 1", name="ck_ccmp_version"),
        sa.CheckConstraint(
            "status IN ('COMPLETED','PARTIALLY_COMPLETED','FAILED')", name="ck_ccmp_status"
        ),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_ccmp_fingerprint"
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ccmp_idempotency"),
    )
    op.create_index(
        "ix_ccmp_context_created",
        "intelligence_competitor_change_comparisons",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_ccmp_baseline", "intelligence_competitor_change_comparisons", ["baseline_analysis_id"]
    )
    op.create_index(
        "ix_ccmp_current", "intelligence_competitor_change_comparisons", ["current_analysis_id"]
    )
    op.create_index(
        "ix_ccmp_fingerprint", "intelligence_competitor_change_comparisons", ["input_fingerprint"]
    )

    _common(
        "intelligence_competitor_change_events",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "comparison_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_change_comparisons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_foundation_products.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_entities.id", ondelete="SET NULL"),
        ),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("observed_or_derived", sa.String(16), nullable=False, server_default="OBSERVED"),
        sa.Column("old_value", postgresql.JSONB),
        sa.Column("new_value", postgresql.JSONB),
        sa.Column("unit", sa.String(40)),
        sa.Column("currency", sa.String(3)),
        sa.Column("absolute_delta", sa.Numeric(24, 8)),
        sa.Column("percentage_delta", sa.Numeric(24, 8)),
        sa.Column("baseline_reference", sa.String(240)),
        sa.Column("current_reference", sa.String(240)),
        sa.Column("evidence_references", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("first_observed", sa.DateTime(timezone=True)),
        sa.Column("last_observed", sa.DateTime(timezone=True)),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("evidence_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("materiality", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "materiality_policy_version",
            sa.String(80),
            nullable=False,
            server_default="competitor-change-materiality-v1",
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("confidence", sa.Numeric(6, 5)),
        sa.Column("alert_eligibility", sa.String(16), nullable=False, server_default="NO_ALERT"),
        sa.Column("alert_reason", sa.String(240), nullable=False, server_default=""),
        sa.Column("persistence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "previous_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_change_events.id", ondelete="SET NULL"),
        ),
        sa.Column("resolution_reference", sa.String(240)),
        sa.Column(
            "calculation_version",
            sa.String(120),
            nullable=False,
            server_default="competitor-change-v1",
        ),
        sa.Column("event_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "change_type IN ("
            "'COMPETITOR_ADDED','COMPETITOR_REMOVED','POSSIBLY_REMOVED',"
            "'PRICE_INCREASED','PRICE_DECREASED','PRICE_BAND_CHANGED',"
            "'AVAILABILITY_CHANGED','RATING_CHANGED','REVIEW_COUNT_CHANGED',"
            "'BRAND_CONCENTRATION_CHANGED','SELLER_CONCENTRATION_CHANGED',"
            "'ASSORTMENT_ATTRIBUTE_ADDED','ASSORTMENT_ATTRIBUTE_REMOVED',"
            "'ASSORTMENT_DISTRIBUTION_CHANGED','FEATURE_ADDED','FEATURE_REMOVED',"
            "'POSITIONING_CHANGED','EVIDENCE_COVERAGE_CHANGED','FRESHNESS_CHANGED',"
            "'CONTRADICTION_CHANGED')",
            name="ck_ccev_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'NEW','ONGOING','RESOLVED','REVERTED','SUPERSEDED','UNRESOLVED',"
            "'POSSIBLY_REMOVED')",
            name="ck_ccev_status",
        ),
        sa.CheckConstraint(
            "materiality IN ('IMMATERIAL','LOW','MODERATE','HIGH','UNKNOWN')",
            name="ck_ccev_materiality",
        ),
        sa.CheckConstraint(
            "alert_eligibility IN ('NO_ALERT','REVIEW','ALERT')", name="ck_ccev_alert"
        ),
        sa.UniqueConstraint("owner_id", "event_fingerprint", name="uq_ccev_fingerprint"),
    )
    op.create_index(
        "ix_ccev_context_created",
        "intelligence_competitor_change_events",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_ccev_comparison", "intelligence_competitor_change_events", ["comparison_id"]
    )
    op.create_index("ix_ccev_type", "intelligence_competitor_change_events", ["change_type"])
    op.create_index("ix_ccev_materiality", "intelligence_competitor_change_events", ["materiality"])
    op.create_index("ix_ccev_status", "intelligence_competitor_change_events", ["status"])
    op.create_index("ix_ccev_alert", "intelligence_competitor_change_events", ["alert_eligibility"])

    _common(
        "intelligence_competitor_change_alert_eligibility",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_change_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("eligibility", sa.String(16), nullable=False, server_default="NO_ALERT"),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "eligibility IN ('NO_ALERT','REVIEW','ALERT')", name="ck_ccal_eligibility"
        ),
        sa.UniqueConstraint("owner_id", "event_id", name="uq_ccal_event"),
    )
    op.create_index(
        "ix_ccal_event", "intelligence_competitor_change_alert_eligibility", ["event_id"]
    )
    op.create_index(
        "ix_ccal_eligibility", "intelligence_competitor_change_alert_eligibility", ["eligibility"]
    )


def downgrade() -> None:
    op.drop_table("intelligence_competitor_change_alert_eligibility")
    op.drop_table("intelligence_competitor_change_events")
    op.drop_table("intelligence_competitor_change_comparisons")
