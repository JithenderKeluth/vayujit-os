"""Add PR-9B separate execution authorization and evidence review ledgers."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20261014_0155"
down_revision = "20261013_0154"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "intelligence_live_supplier_execution_authorizations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("approval_id", uuid, nullable=False),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_host", sa.String(255), nullable=False),
        sa.Column("path_scope", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default="approved_web_fetch"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="LIVE_READ_ONLY"),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("actor_provenance", sa.String(16), nullable=False, server_default="HUMAN"),
        sa.Column("approval_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
        sa.Column("max_requests", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("execution_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_id"], ["intelligence_live_supplier_source_approvals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_id"], ["intelligence_live_supplier_certification_executions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_exec_auth_fingerprint"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_live_supplier_exec_auth_idempotency"),
    )
    for name, cols in {
        "owner": ["owner_id"], "approval": ["approval_id"], "goal": ["goal_id"],
        "opportunity": ["opportunity_id"], "host": ["normalized_host"],
        "status": ["status"], "fingerprint": ["fingerprint"], "execution": ["execution_id"],
    }.items():
        op.create_index(f"ix_live_supplier_exec_auth_{name}", "intelligence_live_supplier_execution_authorizations", cols)

    op.create_table(
        "intelligence_live_supplier_evidence_reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("execution_id", uuid, nullable=False),
        sa.Column("run_id", uuid, nullable=False),
        sa.Column("evidence_hash", sa.String(128), nullable=False, server_default=""),
        sa.Column("evidence_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("actor_provenance", sa.String(16), nullable=False, server_default="HUMAN"),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["intelligence_live_supplier_certification_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["intelligence_live_supplier_certification_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_live_supplier_evidence_review_fingerprint"),
    )
    for name, cols in {
        "owner": ["owner_id"], "execution": ["execution_id"], "run": ["run_id"],
        "fingerprint": ["fingerprint"],
    }.items():
        op.create_index(f"ix_live_supplier_evidence_review_{name}", "intelligence_live_supplier_evidence_reviews", cols)


def downgrade() -> None:
    op.drop_table("intelligence_live_supplier_evidence_reviews")
    op.drop_table("intelligence_live_supplier_execution_authorizations")
