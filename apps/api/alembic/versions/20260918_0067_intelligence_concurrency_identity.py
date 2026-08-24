"""Add deterministic concurrency identities for Intelligence evaluations."""

from alembic import op

revision = "20260918_0067"
down_revision = "20260917_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_intel_rule_eval_identity",
        "intelligence_rule_evaluations",
        ["owner_id", "rule_id", "rule_version", "subject_type", "subject_id"],
    )
    op.create_unique_constraint(
        "uq_intel_opportunity_owner_candidate",
        "intelligence_opportunities",
        ["owner_id", "candidate_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_intel_opportunity_owner_candidate",
        "intelligence_opportunities",
        type_="unique",
    )
    op.drop_constraint(
        "uq_intel_rule_eval_identity",
        "intelligence_rule_evaluations",
        type_="unique",
    )
