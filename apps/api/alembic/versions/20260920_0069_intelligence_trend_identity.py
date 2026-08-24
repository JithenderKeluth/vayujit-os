"""Add deterministic identity for intelligence trend observations."""

from alembic import op

revision = "20260920_0069"
down_revision = "20260919_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_intel_trend_candidate_observed",
        "intelligence_trend_observations",
        ["owner_id", "candidate_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_intel_trend_candidate_observed",
        "intelligence_trend_observations",
        type_="unique",
    )
