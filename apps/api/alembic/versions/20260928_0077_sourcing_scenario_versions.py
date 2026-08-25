"""Make sourcing cost scenarios immutable and versioned."""

from alembic import op

revision = "20260928_0077"
down_revision = "20260927_0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE intelligence_cost_scenarios "
        "DROP CONSTRAINT IF EXISTS uq_intelligence_cost_scenario"
    )
    op.execute(
        "ALTER TABLE intelligence_cost_scenarios "
        "ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1"
    )
    op.execute(
        "ALTER TABLE intelligence_cost_scenarios "
        "ADD CONSTRAINT uq_intelligence_cost_scenario "
        "UNIQUE(owner_id, requirement_id, name, version)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE intelligence_cost_scenarios "
        "DROP CONSTRAINT IF EXISTS uq_intelligence_cost_scenario"
    )
    op.execute(
        "ALTER TABLE intelligence_cost_scenarios "
        "ADD CONSTRAINT uq_intelligence_cost_scenario "
        "UNIQUE(owner_id, requirement_id, name)"
    )
    op.execute("ALTER TABLE intelligence_cost_scenarios DROP COLUMN IF EXISTS version")
