"""Create immutable 9E risk/evidence synthesis outputs."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261104_0113"
down_revision = "20261103_0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_product_opportunity_risk_evidence_syntheses",
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
        sa.Column("calculation_version", sa.String(120), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("upstream_lineage", postgresql.JSONB, nullable=False),
        sa.Column("summary", postgresql.JSONB, nullable=False),
        sa.Column("risks", postgresql.JSONB, nullable=False),
        sa.Column("domain_readiness", postgresql.JSONB, nullable=False),
        sa.Column("evidence_summary", postgresql.JSONB, nullable=False),
        sa.Column("research_gaps", postgresql.JSONB, nullable=False),
        sa.Column("changes", postgresql.JSONB, nullable=False),
        sa.Column("dimensions", postgresql.JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "assessment_id", name="uq_product_opportunity_synthesis_assessment"
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_synthesis_idempotency"
        ),
    )
    op.create_index(
        "ix_prod_opp_risk_synth_owner_id",
        "intelligence_product_opportunity_risk_evidence_syntheses",
        ["owner_id"],
    )
    op.create_index(
        "ix_prod_opp_risk_synth_assessment_id",
        "intelligence_product_opportunity_risk_evidence_syntheses",
        ["assessment_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_product_opportunity_risk_evidence_syntheses")
