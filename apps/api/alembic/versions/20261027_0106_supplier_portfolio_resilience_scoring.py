"""Add 8E.3 resilience dimensions, scores, projections, and recommendations."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261027_0106"
down_revision = "20261026_0105"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete="CASCADE")


def _indexes(prefix: str, table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{prefix}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "intelligence_supplier_portfolio_resilience_dimensions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("dimension", sa.String(64), nullable=False),
        sa.Column("score", sa.Numeric(7, 4), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("evidence_status", sa.String(16), nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("supporting_inputs", JSONB, nullable=False),
        sa.Column("evidence_references", JSONB, nullable=False),
        sa.Column("penalties", JSONB, nullable=False),
        sa.Column("limitations", JSONB, nullable=False),
        sa.Column("missing_evidence", JSONB, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint(
            "assessment_version_id", "dimension", name="uq_portfolio_resilience_dimension"
        ),
    )
    _indexes(
        "sprd",
        "intelligence_supplier_portfolio_resilience_dimensions",
        ("owner_id", "portfolio_id", "assessment_version_id"),
    )

    op.create_table(
        "intelligence_supplier_portfolio_resilience_scores",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("score", sa.Numeric(7, 4), nullable=True),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("evidence_status", sa.String(16), nullable=False),
        sa.Column("confidence_value", sa.Numeric(7, 4), nullable=True),
        sa.Column("confidence_classification", sa.String(24), nullable=False),
        sa.Column("score_version", sa.String(80), nullable=False),
        sa.Column("component_snapshot", JSONB, nullable=False),
        sa.Column("penalty_snapshot", JSONB, nullable=False),
        sa.Column("missing_evidence", JSONB, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint("assessment_version_id", name="uq_portfolio_resilience_score"),
    )
    _indexes(
        "sprs",
        "intelligence_supplier_portfolio_resilience_scores",
        ("owner_id", "portfolio_id", "assessment_version_id"),
    )

    op.create_table(
        "intelligence_supplier_portfolio_confidence_projections",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("value", sa.Numeric(7, 4), nullable=True),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("evidence_status", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("limitations", JSONB, nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint("assessment_version_id", name="uq_portfolio_confidence_projection"),
    )
    _indexes(
        "spcp",
        "intelligence_supplier_portfolio_confidence_projections",
        ("owner_id", "portfolio_id", "assessment_version_id"),
    )

    op.create_table(
        "intelligence_supplier_portfolio_risk_projections",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("exposure", sa.Numeric(7, 4), nullable=True),
        sa.Column("supporting_inputs", JSONB, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint("assessment_version_id", name="uq_portfolio_risk_projection"),
    )
    _indexes(
        "sprp",
        "intelligence_supplier_portfolio_risk_projections",
        ("owner_id", "portfolio_id", "assessment_version_id"),
    )

    op.create_table(
        "intelligence_supplier_portfolio_recommendations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("assessment_version_id", UUID, nullable=False),
        sa.Column("recommendation_type", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("affected_supplier_id", UUID, nullable=True),
        sa.Column("affected_product_id", UUID, nullable=True),
        sa.Column("affected_dependency_type", sa.String(80), nullable=True),
        sa.Column("logical_key", sa.String(240), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB, nullable=False),
        sa.Column("dimensions_affected", JSONB, nullable=False),
        sa.Column("expected_benefit", sa.Text(), nullable=False),
        sa.Column("missing_evidence", JSONB, nullable=False),
        sa.Column("recommendation_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("owner_id", "users.id"),
        _fk("portfolio_id", "intelligence_supplier_portfolio_contexts.id"),
        _fk("assessment_version_id", "intelligence_supplier_portfolio_assessment_versions.id"),
        sa.UniqueConstraint(
            "assessment_version_id", "logical_key", name="uq_portfolio_recommendation"
        ),
    )
    _indexes(
        "sprr",
        "intelligence_supplier_portfolio_recommendations",
        ("owner_id", "portfolio_id", "assessment_version_id"),
    )


def downgrade() -> None:
    op.drop_table("intelligence_supplier_portfolio_recommendations")
    op.drop_table("intelligence_supplier_portfolio_risk_projections")
    op.drop_table("intelligence_supplier_portfolio_confidence_projections")
    op.drop_table("intelligence_supplier_portfolio_resilience_scores")
    op.drop_table("intelligence_supplier_portfolio_resilience_dimensions")
