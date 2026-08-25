# ruff: noqa: E501
"""Create deterministic sourcing, RFQ, sample, economics and decision tables."""


from alembic import op

revision = "20260926_0075"
down_revision = "20260925_0074"
branch_labels = None
depends_on = None
TABLES = [
    (
        "intelligence_sourcing_requirements",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, opportunity_id UUID NULL REFERENCES intelligence_opportunities(id) ON DELETE SET NULL, product_id UUID NULL, current_version INTEGER NOT NULL DEFAULT 1, status VARCHAR(24) NOT NULL DEFAULT 'draft', idempotency_key VARCHAR(180) NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,idempotency_key)""",
    ),
    (
        "intelligence_sourcing_requirement_versions",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, requirement_id UUID NOT NULL REFERENCES intelligence_sourcing_requirements(id) ON DELETE CASCADE, version INTEGER NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(requirement_id,version)""",
    ),
    (
        "intelligence_rfqs",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, requirement_id UUID NOT NULL REFERENCES intelligence_sourcing_requirements(id) ON DELETE CASCADE, requirement_version INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1, status VARCHAR(32) NOT NULL DEFAULT 'draft', dispatch_status VARCHAR(32) NOT NULL DEFAULT 'not_sent', title VARCHAR(200) NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, idempotency_key VARCHAR(180) NOT NULL, approved_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,idempotency_key)""",
    ),
    (
        "intelligence_rfq_suppliers",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, rfq_id UUID NOT NULL REFERENCES intelligence_rfqs(id) ON DELETE CASCADE, supplier_id UUID NOT NULL REFERENCES intelligence_suppliers(id) ON DELETE CASCADE, supplier_context JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(rfq_id,supplier_id)""",
    ),
    (
        "intelligence_rfq_drafts",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, rfq_id UUID NOT NULL UNIQUE REFERENCES intelligence_rfqs(id) ON DELETE CASCADE, content JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_supplier_quotes",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, rfq_id UUID NOT NULL REFERENCES intelligence_rfqs(id) ON DELETE CASCADE, supplier_id UUID NOT NULL REFERENCES intelligence_suppliers(id) ON DELETE CASCADE, version INTEGER NOT NULL DEFAULT 1, quote_reference VARCHAR(180) NOT NULL, quote_date TIMESTAMPTZ NOT NULL, valid_until TIMESTAMPTZ NULL, currency VARCHAR(3) NOT NULL, unit_price NUMERIC(18,4) NOT NULL, moq INTEGER NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'received', payload JSONB NOT NULL DEFAULT '{}'::jsonb, evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,rfq_id,supplier_id,version)""",
    ),
    (
        "intelligence_supplier_quote_lines",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, quote_id UUID NOT NULL REFERENCES intelligence_supplier_quotes(id) ON DELETE CASCADE, kind VARCHAR(64) NOT NULL, description TEXT NOT NULL DEFAULT '', amount NUMERIC(18,4) NOT NULL DEFAULT 0, currency VARCHAR(3) NOT NULL, created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_supplier_quote_versions",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, quote_id UUID NOT NULL REFERENCES intelligence_supplier_quotes(id) ON DELETE CASCADE, version INTEGER NOT NULL, snapshot JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, UNIQUE(quote_id,version)""",
    ),
    (
        "intelligence_sample_requests",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, rfq_id UUID NULL REFERENCES intelligence_rfqs(id) ON DELETE SET NULL, supplier_id UUID NOT NULL REFERENCES intelligence_suppliers(id) ON DELETE CASCADE, status VARCHAR(32) NOT NULL DEFAULT 'requested', quantity INTEGER NOT NULL DEFAULT 1, notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_samples",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, request_id UUID NOT NULL REFERENCES intelligence_sample_requests(id) ON DELETE CASCADE, status VARCHAR(32) NOT NULL DEFAULT 'requested', evidence JSONB NOT NULL DEFAULT '[]'::jsonb, notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_sample_evaluations",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, sample_id UUID NOT NULL UNIQUE REFERENCES intelligence_samples(id) ON DELETE CASCADE, decision VARCHAR(32) NOT NULL, dimensions JSONB NOT NULL DEFAULT '{}'::jsonb, notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_inspections",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, sample_id UUID NULL REFERENCES intelligence_samples(id) ON DELETE SET NULL, inspection_type VARCHAR(32) NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'open', notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_inspection_findings",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, inspection_id UUID NOT NULL REFERENCES intelligence_inspections(id) ON DELETE CASCADE, severity VARCHAR(24) NOT NULL, category VARCHAR(64) NOT NULL, finding TEXT NOT NULL, evidence JSONB NOT NULL DEFAULT '[]'::jsonb, quantity_checked INTEGER NULL, quantity_defective INTEGER NULL, created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_negotiation_rounds",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, quote_id UUID NOT NULL REFERENCES intelligence_supplier_quotes(id) ON DELETE CASCADE, round_number INTEGER NOT NULL, requested_change TEXT NOT NULL DEFAULT '', supplier_response TEXT NOT NULL DEFAULT '', delta JSONB NOT NULL DEFAULT '{}'::jsonb, evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb, created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_cost_scenarios",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, requirement_id UUID NULL REFERENCES intelligence_sourcing_requirements(id) ON DELETE SET NULL, quote_id UUID NULL REFERENCES intelligence_supplier_quotes(id) ON DELETE SET NULL, name VARCHAR(32) NOT NULL DEFAULT 'BASE', currency VARCHAR(3) NOT NULL DEFAULT 'INR', inputs JSONB NOT NULL DEFAULT '{}'::jsonb, result JSONB NOT NULL DEFAULT '{}'::jsonb, confidence VARCHAR(24) NOT NULL DEFAULT 'INSUFFICIENT', created_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,requirement_id,name)""",
    ),
    (
        "intelligence_landed_cost_estimates",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, scenario_id UUID NOT NULL UNIQUE REFERENCES intelligence_cost_scenarios(id) ON DELETE CASCADE, per_unit NUMERIC(18,4) NOT NULL DEFAULT 0, total NUMERIC(18,4) NOT NULL DEFAULT 0, breakdown JSONB NOT NULL DEFAULT '{}'::jsonb, confidence VARCHAR(24) NOT NULL DEFAULT 'INSUFFICIENT', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_logistics_estimates",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, scenario_id UUID NOT NULL UNIQUE REFERENCES intelligence_cost_scenarios(id) ON DELETE CASCADE, payload JSONB NOT NULL DEFAULT '{}'::jsonb, classification VARCHAR(24) NOT NULL DEFAULT 'ASSUMED', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_duty_tax_assumptions",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, scenario_id UUID NOT NULL UNIQUE REFERENCES intelligence_cost_scenarios(id) ON DELETE CASCADE, payload JSONB NOT NULL DEFAULT '{}'::jsonb, classification VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_fx_assumptions",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, scenario_id UUID NOT NULL UNIQUE REFERENCES intelligence_cost_scenarios(id) ON DELETE CASCADE, from_currency VARCHAR(3) NOT NULL, to_currency VARCHAR(3) NOT NULL, rate NUMERIC(18,8) NOT NULL, classification VARCHAR(24) NOT NULL DEFAULT 'ASSUMED', reference VARCHAR(500) NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_sourcing_decisions",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, requirement_id UUID NOT NULL REFERENCES intelligence_sourcing_requirements(id) ON DELETE CASCADE, quote_id UUID NOT NULL REFERENCES intelligence_supplier_quotes(id) ON DELETE CASCADE, classification VARCHAR(32) NOT NULL DEFAULT 'review_required', decision VARCHAR(40) NOT NULL DEFAULT 'hold', critic JSONB NOT NULL DEFAULT '[]'::jsonb, confirmed BOOLEAN NOT NULL DEFAULT false, created_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,requirement_id,quote_id)""",
    ),
    (
        "intelligence_sourcing_approvals",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, decision_id UUID NOT NULL UNIQUE REFERENCES intelligence_sourcing_decisions(id) ON DELETE CASCADE, approved BOOLEAN NOT NULL DEFAULT false, note TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
    (
        "intelligence_sourcing_worker_jobs",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, task VARCHAR(64) NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'pending', idempotency_key VARCHAR(180) NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, result JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, UNIQUE(owner_id,idempotency_key)""",
    ),
    (
        "intelligence_sourcing_recovery_records",
        """id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, entity_type VARCHAR(64) NOT NULL, entity_id UUID NOT NULL, action VARCHAR(64) NOT NULL, result VARCHAR(64) NOT NULL, reason TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL""",
    ),
]


def upgrade() -> None:
    for name, definition in TABLES:
        op.execute(f"CREATE TABLE {name} ({definition})")


def downgrade() -> None:
    for name, _ in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {name}")
