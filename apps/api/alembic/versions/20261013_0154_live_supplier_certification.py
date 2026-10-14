"""Add PR-9A scoped supplier-source certification and immutable execution ledger."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20261013_0154"
down_revision = "20261012_0153"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    op.create_table(
        "intelligence_live_supplier_source_approvals",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=True),
        sa.Column("source_profile_id", uuid, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_host", sa.String(255), nullable=False),
        sa.Column("path_scope", sa.Text(), nullable=False, server_default="/"),
        sa.Column("candidate_category", sa.String(64), nullable=False, server_default="supplier_website"),
        sa.Column("operation", sa.String(32), nullable=False, server_default="LIVE_READ_ONLY"),
        sa.Column("purpose", sa.String(500), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="APPROVED"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_profile_id"], ["intelligence_external_source_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_approval_fingerprint"),
    )
    for name, cols in {
        "owner": ["owner_id"], "goal": ["goal_id"], "opportunity": ["opportunity_id"],
        "profile": ["source_profile_id"], "host": ["normalized_host"], "status": ["status"],
        "fingerprint": ["fingerprint"],
    }.items():
        op.create_index(f"ix_live_supplier_approval_{name}", "intelligence_live_supplier_source_approvals", cols)

    op.create_table(
        "intelligence_live_supplier_certification_runs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=True),
        sa.Column("approval_id", uuid, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default="approved_web_fetch"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="LIVE_READ_ONLY"),
        sa.Column("policy_version", sa.String(80), nullable=False, server_default="pr9a-live-supplier-v1"),
        sa.Column("requested_checks", js, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("executed_checks", js, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("gate_outcomes", js, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_refs", js, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("blockers", js, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("external_read_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("external_write_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="NOT_EXECUTED"),
        sa.Column("trust_classification", sa.String(48), nullable=False, server_default="UNKNOWN"),
        sa.Column("supplier_correlation", js, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("product_classification", js, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", sa.String(120), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approval_id"], ["intelligence_live_supplier_source_approvals.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_certification_fingerprint"),
    )
    for name, cols in {
        "owner": ["owner_id"], "goal": ["goal_id"], "opportunity": ["opportunity_id"],
        "approval": ["approval_id"], "status": ["status"], "fingerprint": ["fingerprint"],
        "correlation": ["correlation_id"],
    }.items():
        op.create_index(f"ix_live_supplier_certification_run_{name}", "intelligence_live_supplier_certification_runs", cols)

    op.create_table(
        "intelligence_live_supplier_certification_executions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("run_id", uuid, nullable=False),
        sa.Column("approval_id", uuid, nullable=False),
        sa.Column("external_fetch_id", uuid, nullable=True),
        sa.Column("supplier_id", uuid, nullable=True),
        sa.Column("supplier_source_id", uuid, nullable=True),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("redirect_chain", js, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("provider", sa.String(64), nullable=False, server_default="approved_web_fetch"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="LIVE_READ_ONLY"),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("content_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("extracted", js, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provenance", js, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trust_classification", sa.String(48), nullable=False, server_default="FETCHED_SOURCE"),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["intelligence_live_supplier_certification_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_id"], ["intelligence_live_supplier_source_approvals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["external_fetch_id"], ["intelligence_external_fetches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_source_id"], ["intelligence_supplier_sources.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_execution_fingerprint"),
    )
    for name, cols in {
        "owner": ["owner_id"], "run": ["run_id"], "approval": ["approval_id"],
        "external": ["external_fetch_id"], "supplier": ["supplier_id"],
        "source": ["supplier_source_id"], "domain": ["domain"], "status": ["status"],
        "fingerprint": ["fingerprint"],
    }.items():
        op.create_index(f"ix_live_supplier_execution_{name}", "intelligence_live_supplier_certification_executions", cols)


def downgrade() -> None:
    for table in (
        "intelligence_live_supplier_certification_executions",
        "intelligence_live_supplier_certification_runs",
        "intelligence_live_supplier_source_approvals",
    ):
        op.drop_table(table)
