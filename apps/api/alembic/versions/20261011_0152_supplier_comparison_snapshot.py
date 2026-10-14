"""Add immutable PR-8B supplier-comparison snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261011_0152"
down_revision = "20261010_0151"
branch_labels = None
depends_on = None


def _json(default: str = "{}") -> sa.TextClause:
    return sa.text(f"'{default}'::jsonb")


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    op.create_table(
        "intelligence_supplier_comparison_snapshots",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=False),
        sa.Column("assessment_id", uuid, nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEEDS_EVIDENCE"),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("canonical_supplier_ids", js, nullable=False, server_default=_json("[]")),
        sa.Column("supplier_ids", js, nullable=False, server_default=_json("[]")),
        sa.Column("supplier_product_ids", js, nullable=False, server_default=_json("[]")),
        sa.Column("reassessment_ids", js, nullable=False, server_default=_json("[]")),
        sa.Column("quote_versions", js, nullable=False, server_default=_json("[]")),
        sa.Column("input_fingerprints", js, nullable=False, server_default=_json("[]")),
        sa.Column("calculation_versions", js, nullable=False, server_default=_json("[]")),
        sa.Column("suppliers", js, nullable=False, server_default=_json("[]")),
        sa.Column("metrics", js, nullable=False, server_default=_json("[]")),
        sa.Column("unknowns", js, nullable=False, server_default=_json("[]")),
        sa.Column("blockers", js, nullable=False, server_default=_json("[]")),
        sa.Column("contradictions", js, nullable=False, server_default=_json("[]")),
        sa.Column("provenance", js, nullable=False, server_default=_json()),
        sa.Column("lineage", js, nullable=False, server_default=_json()),
        sa.Column("shortlist_context_id", uuid, nullable=True),
        sa.Column("shortlist_version_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["intelligence_product_opportunity_assessments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shortlist_context_id"],
            ["intelligence_supplier_shortlist_contexts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["shortlist_version_id"],
            ["intelligence_supplier_shortlist_versions.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8b_comparison_idempotency"),
        sa.UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr8b_comparison_fingerprint"),
    )
    for name, cols in {
        "owner": ["owner_id"],
        "goal": ["goal_id"],
        "opportunity": ["opportunity_id"],
        "assessment": ["assessment_id"],
        "fingerprint": ["input_fingerprint"],
        "status": ["status"],
        "shortlist_context": ["shortlist_context_id"],
        "shortlist_version": ["shortlist_version_id"],
    }.items():
        op.create_index(
            f"ix_pr8b_comparison_{name}", "intelligence_supplier_comparison_snapshots", cols
        )

    op.add_column(
        "intelligence_supplier_shortlist_decisions",
        sa.Column("comparison_snapshot_id", uuid, nullable=True),
    )
    op.create_index(
        "ix_shortlist_decision_comparison_snapshot",
        "intelligence_supplier_shortlist_decisions",
        ["comparison_snapshot_id"],
    )
    op.create_foreign_key(
        "fk_shortlist_decision_comparison_snapshot",
        "intelligence_supplier_shortlist_decisions",
        "intelligence_supplier_comparison_snapshots",
        ["comparison_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_shortlist_decision_comparison_snapshot",
        "intelligence_supplier_shortlist_decisions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_shortlist_decision_comparison_snapshot",
        table_name="intelligence_supplier_shortlist_decisions",
    )
    op.drop_column("intelligence_supplier_shortlist_decisions", "comparison_snapshot_id")
    op.drop_table("intelligence_supplier_comparison_snapshots")
