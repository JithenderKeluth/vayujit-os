"""Add concentration, dependency, and alternate-readiness portfolio outputs."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261026_0105"
down_revision = "20261025_0104"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "intelligence_supplier_portfolio_concentration_metrics",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("metric_type", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(18, 10), nullable=True),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("denominator", sa.Numeric(18, 10), nullable=True),
        sa.Column("contributors", JSONB, nullable=False),
        sa.Column("evidence_references", JSONB, nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("threshold_version", sa.String(80), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("missing_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["intelligence_supplier_portfolio_contexts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["intelligence_supplier_portfolio_assessment_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "assessment_version_id",
            "dimension",
            "metric_type",
            name="uq_portfolio_concentration_metric",
        ),
    )
    for column in ("owner_id", "portfolio_id", "assessment_version_id"):
        op.create_index(
            f"ix_spcm_{column}",
            "intelligence_supplier_portfolio_concentration_metrics",
            [column],
        )

    op.create_table(
        "intelligence_supplier_portfolio_dependency_findings",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("dependency_type", sa.String(64), nullable=False),
        sa.Column("affected_supplier_id", UUID, nullable=True),
        sa.Column("affected_product_id", UUID, nullable=True),
        sa.Column("affected_capability", sa.String(160), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 2), nullable=True),
        sa.Column("supporting_evidence", JSONB, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("missing_evidence", JSONB, nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["intelligence_supplier_portfolio_contexts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["intelligence_supplier_portfolio_assessment_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "assessment_version_id",
            "dependency_type",
            "affected_supplier_id",
            "affected_product_id",
            "affected_capability",
            name="uq_portfolio_dependency_finding",
        ),
    )
    for column in ("owner_id", "portfolio_id", "assessment_version_id"):
        op.create_index(
            f"ix_spdf_{column}",
            "intelligence_supplier_portfolio_dependency_findings",
            [column],
        )

    op.create_table(
        "intelligence_supplier_portfolio_alternate_readiness",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("supplier_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=True),
        sa.Column("readiness_state", sa.String(40), nullable=False),
        sa.Column("reasons", JSONB, nullable=False),
        sa.Column("satisfied_requirements", JSONB, nullable=False),
        sa.Column("unmet_requirements", JSONB, nullable=False),
        sa.Column("missing_evidence", JSONB, nullable=False),
        sa.Column("stale_evidence", JSONB, nullable=False),
        sa.Column("contradictions", JSONB, nullable=False),
        sa.Column("dd_gaps", JSONB, nullable=False),
        sa.Column("commercial_gaps", JSONB, nullable=False),
        sa.Column("capability_gaps", JSONB, nullable=False),
        sa.Column("confidence", sa.Numeric(6, 2), nullable=True),
        sa.Column("next_evidence_action", sa.String(240), nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["intelligence_supplier_portfolio_contexts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["intelligence_supplier_portfolio_assessment_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "assessment_version_id",
            "supplier_id",
            "product_id",
            name="uq_portfolio_alternate_readiness",
        ),
    )
    for column in ("owner_id", "portfolio_id", "assessment_version_id", "supplier_id"):
        op.create_index(
            f"ix_spar_{column}",
            "intelligence_supplier_portfolio_alternate_readiness",
            [column],
        )


def downgrade() -> None:
    op.drop_table("intelligence_supplier_portfolio_alternate_readiness")
    op.drop_table("intelligence_supplier_portfolio_dependency_findings")
    op.drop_table("intelligence_supplier_portfolio_concentration_metrics")
