"""Immutable sourcing scenarios; no existing data is rewritten."""

# ruff: noqa: E501
from alembic import op

revision = "20261024_0103"
down_revision = "20261023_0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE intelligence_scenario_contexts (\n\tshortlist_version_id UUID NOT NULL, \n\tproduct_id UUID, \n\topportunity_id UUID, \n\tcurrent_version INTEGER NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\tsettings JSONB NOT NULL, \n\tidempotency_key VARCHAR(160) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_context_key UNIQUE (owner_id, idempotency_key), \n\tCONSTRAINT ck_scenario_context_version CHECK (current_version > 0), \n\tFOREIGN KEY(shortlist_version_id) REFERENCES intelligence_supplier_shortlist_versions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(opportunity_id) REFERENCES intelligence_opportunities (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_contexts_opportunity_id ON intelligence_scenario_contexts (opportunity_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_contexts_owner_id ON intelligence_scenario_contexts (owner_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_contexts_product_id ON intelligence_scenario_contexts (product_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_contexts_shortlist_version_id ON intelligence_scenario_contexts (shortlist_version_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenarios (\n\tcontext_id UUID NOT NULL, \n\tname VARCHAR(120) NOT NULL, \n\tscenario_type VARCHAR(40) NOT NULL, \n\tcurrent_version INTEGER NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\tidempotency_key VARCHAR(160) NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_key UNIQUE (context_id, idempotency_key), \n\tCONSTRAINT ck_scenario_version CHECK (current_version > 0), \n\tFOREIGN KEY(context_id) REFERENCES intelligence_scenario_contexts (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenarios_context_id ON intelligence_scenarios (context_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenarios_owner_id ON intelligence_scenarios (owner_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenario_versions (\n\tscenario_id UUID NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcalculation_version VARCHAR(64) NOT NULL, \n\tscoring_version VARCHAR(64) NOT NULL, \n\tlanded_cost_version VARCHAR(64) NOT NULL, \n\tsnapshot JSONB NOT NULL, \n\tresult JSONB NOT NULL, \n\tlineage_hash VARCHAR(64) NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_version UNIQUE (scenario_id, version), \n\tCONSTRAINT ck_scenario_version_positive CHECK (version > 0), \n\tFOREIGN KEY(scenario_id) REFERENCES intelligence_scenarios (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_versions_owner_id ON intelligence_scenario_versions (owner_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_versions_scenario_id ON intelligence_scenario_versions (scenario_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenario_allocations (\n\tversion_id UUID NOT NULL, \n\tsupplier_id UUID NOT NULL, \n\tdue_diligence_id UUID NOT NULL, \n\tquantity INTEGER NOT NULL, \n\tsnapshot JSONB NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_allocation UNIQUE (version_id, supplier_id), \n\tCONSTRAINT ck_scenario_allocation_quantity CHECK (quantity > 0), \n\tFOREIGN KEY(version_id) REFERENCES intelligence_scenario_versions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(supplier_id) REFERENCES intelligence_cross_marketplace_suppliers (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(due_diligence_id) REFERENCES intelligence_supplier_due_diligence_contexts (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_allocations_due_diligence_id ON intelligence_scenario_allocations (due_diligence_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_allocations_owner_id ON intelligence_scenario_allocations (owner_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_allocations_supplier_id ON intelligence_scenario_allocations (supplier_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_allocations_version_id ON intelligence_scenario_allocations (version_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenario_recommendations (\n\tcontext_id UUID NOT NULL, \n\tscenario_version_id UUID, \n\tversion INTEGER NOT NULL, \n\tpayload JSONB NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_recommendation UNIQUE (context_id, version), \n\tFOREIGN KEY(context_id) REFERENCES intelligence_scenario_contexts (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(scenario_version_id) REFERENCES intelligence_scenario_versions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_recommendations_context_id ON intelligence_scenario_recommendations (context_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_recommendations_owner_id ON intelligence_scenario_recommendations (owner_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenario_decisions (\n\tversion_id UUID NOT NULL, \n\taction VARCHAR(40) NOT NULL, \n\treason VARCHAR(500) NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(version_id) REFERENCES intelligence_scenario_versions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_decisions_owner_id ON intelligence_scenario_decisions (owner_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_decisions_version_id ON intelligence_scenario_decisions (version_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenario_handoffs (\n\tversion_id UUID NOT NULL, \n\tdecision_id UUID NOT NULL, \n\tpayload JSONB NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_handoff_version UNIQUE (version_id), \n\tFOREIGN KEY(version_id) REFERENCES intelligence_scenario_versions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(decision_id) REFERENCES intelligence_scenario_decisions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_handoffs_decision_id ON intelligence_scenario_handoffs (decision_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_handoffs_owner_id ON intelligence_scenario_handoffs (owner_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_handoffs_version_id ON intelligence_scenario_handoffs (version_id)"
    )
    op.execute(
        "CREATE TABLE intelligence_scenario_events (\n\tcontext_id UUID NOT NULL, \n\tversion_id UUID, \n\tevent_key VARCHAR(240) NOT NULL, \n\tevent_type VARCHAR(64) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_scenario_event UNIQUE (owner_id, event_key), \n\tFOREIGN KEY(context_id) REFERENCES intelligence_scenario_contexts (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(version_id) REFERENCES intelligence_scenario_versions (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_events_context_id ON intelligence_scenario_events (context_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_events_owner_id ON intelligence_scenario_events (owner_id)"
    )
    op.execute(
        "CREATE INDEX ix_intelligence_scenario_events_version_id ON intelligence_scenario_events (version_id)"
    )
    op.execute(
        "ALTER TABLE intelligence_scenarios ADD CONSTRAINT fk_scenario_current_version FOREIGN KEY(id, current_version) REFERENCES intelligence_scenario_versions (scenario_id, version) DEFERRABLE INITIALLY DEFERRED"
    )
    op.execute(
        "CREATE FUNCTION protect_sourcing_scenario_history() RETURNS trigger LANGUAGE plpgsql AS $$\nBEGIN RAISE EXCEPTION 'Sourcing scenario history is immutable'; END; $$"
    )
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON intelligence_scenario_versions FOR EACH ROW EXECUTE FUNCTION protect_sourcing_scenario_history()"
    )
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON intelligence_scenario_allocations FOR EACH ROW EXECUTE FUNCTION protect_sourcing_scenario_history()"
    )
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON intelligence_scenario_recommendations FOR EACH ROW EXECUTE FUNCTION protect_sourcing_scenario_history()"
    )
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON intelligence_scenario_decisions FOR EACH ROW EXECUTE FUNCTION protect_sourcing_scenario_history()"
    )
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON intelligence_scenario_handoffs FOR EACH ROW EXECUTE FUNCTION protect_sourcing_scenario_history()"
    )
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON intelligence_scenario_events FOR EACH ROW EXECUTE FUNCTION protect_sourcing_scenario_history()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE intelligence_scenarios DROP CONSTRAINT fk_scenario_current_version")
    op.execute("DROP TABLE intelligence_scenario_events")
    op.execute("DROP TABLE intelligence_scenario_handoffs")
    op.execute("DROP TABLE intelligence_scenario_decisions")
    op.execute("DROP TABLE intelligence_scenario_recommendations")
    op.execute("DROP TABLE intelligence_scenario_allocations")
    op.execute("DROP TABLE intelligence_scenario_versions")
    op.execute("DROP TABLE intelligence_scenarios")
    op.execute("DROP TABLE intelligence_scenario_contexts")
    op.execute("DROP FUNCTION protect_sourcing_scenario_history()")
