"""Add deterministic identities for intelligence supporting ledger rows."""

from alembic import op

revision = "20260919_0068"
down_revision = "20260918_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_intel_competitor_snapshot_identity",
        "intelligence_competitor_snapshots",
        ["owner_id", "competitor_id", "observed_at"],
    )
    op.create_unique_constraint(
        "uq_intel_review_theme_identity",
        "intelligence_review_themes",
        ["owner_id", "candidate_id", "theme_type", "label"],
    )
    op.create_unique_constraint(
        "uq_intel_pain_point_identity",
        "intelligence_pain_points",
        ["owner_id", "candidate_id", "issue"],
    )
    op.create_unique_constraint(
        "uq_intel_differentiation_identity",
        "intelligence_differentiations",
        ["owner_id", "candidate_id", "idea"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_intel_differentiation_identity",
        "intelligence_differentiations",
        type_="unique",
    )
    op.drop_constraint(
        "uq_intel_pain_point_identity",
        "intelligence_pain_points",
        type_="unique",
    )
    op.drop_constraint(
        "uq_intel_review_theme_identity",
        "intelligence_review_themes",
        type_="unique",
    )
    op.drop_constraint(
        "uq_intel_competitor_snapshot_identity",
        "intelligence_competitor_snapshots",
        type_="unique",
    )
