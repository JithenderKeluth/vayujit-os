# ruff: noqa: E501
"""Add immutable 12F Trend to Winning Product projections."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261124_0133"
down_revision = "20261123_0132"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def _json(value: str) -> object:
    return sa.text(f"'{value}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "intelligence_trend_winning_product_projections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            UUID,
            sa.ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id", UUID, sa.ForeignKey("intelligence_trend_contexts.id", ondelete="SET NULL")
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_trend_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analyses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "comparison_id",
            UUID,
            sa.ForeignKey("intelligence_trend_change_comparisons.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "validation_id",
            UUID,
            sa.ForeignKey("intelligence_trend_validations.id", ondelete="SET NULL"),
        ),
        sa.Column("projection_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "contract_version",
            sa.String(120),
            nullable=False,
            server_default="trend-winning-product-v1",
        ),
        sa.Column(
            "calculation_version",
            sa.String(120),
            nullable=False,
            server_default="trend-winning-product-calculation-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "readiness", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column(
            "source_state", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column("validated_hypotheses", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("signal_summaries", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("momentum_summaries", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("evidence_confidence", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("freshness", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("contradictions", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("research_gaps", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("evidence_lineage", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("limitations", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("projection", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "input_fingerprint",
            name="uq_trend_winning_projection_fingerprint",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "projection_version",
            name="uq_trend_winning_projection_version",
        ),
        sa.CheckConstraint(
            "readiness IN ('AVAILABLE','PARTIAL','INSUFFICIENT_EVIDENCE','STALE','CONTRADICTORY','RESEARCH_REQUIRED','NOT_COMPARABLE')",
            name="ck_trend_winning_projection_readiness",
        ),
        sa.CheckConstraint(
            "source_state IN ('AVAILABLE','PARTIAL','INSUFFICIENT_EVIDENCE','STALE','CONTRADICTORY','RESEARCH_REQUIRED','NOT_COMPARABLE')",
            name="ck_trend_winning_projection_source_state",
        ),
    )
    op.create_index(
        "ix_trend_winning_projection_owner",
        "intelligence_trend_winning_product_projections",
        ["owner_id"],
    )
    op.create_index(
        "ix_trend_winning_projection_opportunity",
        "intelligence_trend_winning_product_projections",
        ["owner_id", "opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_trend_winning_projection_assessment",
        "intelligence_trend_winning_product_projections",
        ["owner_id", "assessment_id", "created_at"],
    )
    op.create_index(
        "ix_trend_winning_projection_context",
        "intelligence_trend_winning_product_projections",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_trend_winning_projection_validation",
        "intelligence_trend_winning_product_projections",
        ["owner_id", "validation_id", "created_at"],
    )
    op.create_index(
        "ix_trend_winning_projection_fingerprint",
        "intelligence_trend_winning_product_projections",
        ["owner_id", "input_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trend_winning_projection_fingerprint",
        table_name="intelligence_trend_winning_product_projections",
    )
    op.drop_index(
        "ix_trend_winning_projection_validation",
        table_name="intelligence_trend_winning_product_projections",
    )
    op.drop_index(
        "ix_trend_winning_projection_context",
        table_name="intelligence_trend_winning_product_projections",
    )
    op.drop_index(
        "ix_trend_winning_projection_assessment",
        table_name="intelligence_trend_winning_product_projections",
    )
    op.drop_index(
        "ix_trend_winning_projection_opportunity",
        table_name="intelligence_trend_winning_product_projections",
    )
    op.drop_index(
        "ix_trend_winning_projection_owner",
        table_name="intelligence_trend_winning_product_projections",
    )
    op.drop_table("intelligence_trend_winning_product_projections")
