"""Add persisted 10E competitor-to-winning-product projections."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261111_0120"
down_revision = "20261110_0119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_competitor_winning_product_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "competitor_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "change_comparison_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_change_comparisons.id", ondelete="SET NULL"),
        ),
        sa.Column("source_state", sa.String(48), nullable=False),
        sa.Column("contract_version", sa.String(120), nullable=False),
        sa.Column("nine_b_calculation_version", sa.String(120), nullable=False),
        sa.Column("ten_c_calculation_version", sa.String(120)),
        sa.Column("ten_d_calculation_version", sa.String(120)),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("projection", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("evidence_summary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("research_gaps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("freshness_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("contradiction_state", sa.String(32), nullable=False, server_default="NONE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "input_fingerprint",
            name="uq_comp_winning_projection_fingerprint",
        ),
    )
    op.create_index(
        "ix_comp_winning_projection_owner",
        "intelligence_competitor_winning_product_projections",
        ["owner_id"],
    )
    op.create_index(
        "ix_comp_winning_projection_opportunity",
        "intelligence_competitor_winning_product_projections",
        ["owner_id", "opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_comp_winning_projection_context",
        "intelligence_competitor_winning_product_projections",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_comp_winning_projection_analysis",
        "intelligence_competitor_winning_product_projections",
        ["competitor_analysis_id"],
    )
    op.create_index(
        "ix_comp_winning_projection_comparison",
        "intelligence_competitor_winning_product_projections",
        ["change_comparison_id"],
    )
    op.create_index(
        "ix_comp_winning_projection_fingerprint",
        "intelligence_competitor_winning_product_projections",
        ["input_fingerprint"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_competitor_winning_product_projections")
