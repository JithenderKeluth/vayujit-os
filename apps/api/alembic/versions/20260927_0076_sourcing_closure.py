"""Add deterministic sourcing closure history and projection tables."""

# ruff: noqa
from alembic import op

revision = "20260927_0076"
down_revision = "20260926_0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE intelligence_fx_assumptions ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ NULL"
    )
    op.execute(
        "ALTER TABLE intelligence_fx_assumptions ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ NULL"
    )
    op.execute(
        """CREATE TABLE intelligence_rfq_versions (id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, rfq_id UUID NOT NULL REFERENCES intelligence_rfqs(id) ON DELETE CASCADE, version INTEGER NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(rfq_id,version))"""
    )
    op.execute(
        """CREATE TABLE intelligence_sourcing_assumption_versions (id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, scenario_id UUID NOT NULL REFERENCES intelligence_cost_scenarios(id) ON DELETE CASCADE, kind VARCHAR(32) NOT NULL, version INTEGER NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,scenario_id,kind,version))"""
    )
    op.execute(
        """CREATE TABLE intelligence_sourcing_score_evaluations (id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, requirement_id UUID NOT NULL REFERENCES intelligence_sourcing_requirements(id) ON DELETE CASCADE, quote_id UUID NOT NULL REFERENCES intelligence_supplier_quotes(id) ON DELETE CASCADE, model_version VARCHAR(32) NOT NULL, weights JSONB NOT NULL DEFAULT '{}'::jsonb, dimensions JSONB NOT NULL DEFAULT '[]'::jsonb, score NUMERIC(8,4) NOT NULL DEFAULT 0, confidence VARCHAR(24) NOT NULL DEFAULT 'INSUFFICIENT', created_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,requirement_id,quote_id,model_version))"""
    )
    op.execute(
        """CREATE TABLE intelligence_sourcing_rule_evaluations (id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, requirement_id UUID NOT NULL REFERENCES intelligence_sourcing_requirements(id) ON DELETE CASCADE, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL)"""
    )
    op.execute(
        """CREATE TABLE intelligence_sourcing_calendar_items (id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind VARCHAR(48) NOT NULL, title VARCHAR(240) NOT NULL, due_at TIMESTAMPTZ NULL, entity_type VARCHAR(64) NOT NULL, entity_id UUID NOT NULL, idempotency_key VARCHAR(180) NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,idempotency_key))"""
    )


def downgrade() -> None:
    for table in (
        "intelligence_sourcing_calendar_items",
        "intelligence_sourcing_rule_evaluations",
        "intelligence_sourcing_score_evaluations",
        "intelligence_sourcing_assumption_versions",
        "intelligence_rfq_versions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("ALTER TABLE intelligence_fx_assumptions DROP COLUMN IF EXISTS valid_until")
    op.execute("ALTER TABLE intelligence_fx_assumptions DROP COLUMN IF EXISTS observed_at")
