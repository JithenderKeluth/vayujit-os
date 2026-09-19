"""Add immutable competitor commercial analysis persistence (Slice 10C)."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261109_0118"
down_revision = "20261108_0117"
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
    prefix = "ccca" if name.endswith("analyses") else "ccce"
    op.create_index(f"ix_{prefix}_owner", name, ["owner_id"])


def upgrade() -> None:
    _common(
        "intelligence_competitor_commercial_analyses",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "discovery_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("analysis_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "calculation_version",
            sa.String(120),
            nullable=False,
            server_default="competitor-commercial-v1",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("cohort_summary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("pricing_analysis", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("concentration_analysis", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("rating_analysis", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("review_analysis", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("assortment_analysis", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("positioning_analysis", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "differentiation_analysis", postgresql.JSONB, nullable=False, server_default="[]"
        ),
        sa.Column("competitive_gaps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("evidence_coverage", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("freshness_summary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("contradictions", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("research_gaps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("explanation", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('COMPLETED','PARTIALLY_COMPLETED','FAILED')",
            name="ck_comp_commercial_analysis_status",
        ),
        sa.CheckConstraint("analysis_version >= 1", name="ck_comp_commercial_analysis_version"),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "input_fingerprint",
            name="uq_comp_commercial_analysis_fingerprint",
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_comp_commercial_analysis_idempotency"
        ),
    )
    op.create_index(
        "ix_ccca_context",
        "intelligence_competitor_commercial_analyses",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_ccca_context_id",
        "intelligence_competitor_commercial_analyses",
        ["context_id"],
    )
    op.create_index(
        "ix_ccca_snapshot",
        "intelligence_competitor_commercial_analyses",
        ["discovery_snapshot_id"],
    )
    op.create_index(
        "ix_ccca_opportunity",
        "intelligence_competitor_commercial_analyses",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_ccca_status",
        "intelligence_competitor_commercial_analyses",
        ["status"],
    )
    op.create_index(
        "ix_ccca_fingerprint",
        "intelligence_competitor_commercial_analyses",
        ["input_fingerprint"],
    )
    op.create_index(
        "ix_ccca_created",
        "intelligence_competitor_commercial_analyses",
        ["created_at"],
    )

    _common(
        "intelligence_competitor_comparable_cohort_entries",
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_foundation_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identity_state", sa.String(24), nullable=False),
        sa.Column("included", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("exclusion_reason", sa.String(240)),
        sa.Column("evidence_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("observation_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("explanation", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            (
                "identity_state IN ('CONFIRMED','PROBABLE','AMBIGUOUS',"
                "'REJECTED','UNRESOLVED','CANDIDATE')"
            ),
            name="ck_comp_cohort_identity_state",
        ),
        sa.UniqueConstraint(
            "owner_id", "analysis_id", "product_id", name="uq_comp_comparable_cohort_product"
        ),
    )
    op.create_index(
        "ix_ccce_analysis_included",
        "intelligence_competitor_comparable_cohort_entries",
        ["owner_id", "analysis_id", "included"],
    )
    op.create_index(
        "ix_ccce_analysis",
        "intelligence_competitor_comparable_cohort_entries",
        ["analysis_id"],
    )
    op.create_index(
        "ix_ccce_context",
        "intelligence_competitor_comparable_cohort_entries",
        ["context_id"],
    )
    op.create_index(
        "ix_ccce_product",
        "intelligence_competitor_comparable_cohort_entries",
        ["product_id"],
    )
    op.create_index(
        "ix_ccce_included",
        "intelligence_competitor_comparable_cohort_entries",
        ["included"],
    )
    op.create_index(
        "ix_ccce_created",
        "intelligence_competitor_comparable_cohort_entries",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_competitor_comparable_cohort_entries")
    op.drop_table("intelligence_competitor_commercial_analyses")
