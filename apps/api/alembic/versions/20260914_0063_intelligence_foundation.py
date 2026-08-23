# ruff: noqa: E501, E402, I001

"""Create Product Research and Supplier Intelligence foundation tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260914_0063"
down_revision = "20260913_0062"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id(name: str = "id") -> sa.Column:
    return sa.Column(name, UUID, primary_key=True)


def _owner() -> sa.Column:
    return sa.Column(
        "owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "intelligence_research_projects",
        _id(),
        _owner(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("target_market", sa.String(120), nullable=False, server_default=""),
        sa.Column("target_categories", JSONB, nullable=False, server_default="[]"),
        sa.Column("excluded_categories", JSONB, nullable=False, server_default="[]"),
        sa.Column("capital_budget", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("risk_profile", sa.String(40), nullable=False, server_default="balanced"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "name", name="uq_intelligence_project_owner_name"),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','completed','archived')",
            name="ck_intelligence_project_status",
        ),
    )
    op.create_index(
        "ix_intelligence_projects_owner", "intelligence_research_projects", ["owner_id"]
    )
    op.create_index("ix_intelligence_projects_status", "intelligence_research_projects", ["status"])

    op.create_table(
        "intelligence_research_runs",
        _id(),
        _owner(),
        sa.Column(
            "project_id",
            UUID,
            sa.ForeignKey("intelligence_research_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("ruleset_version", sa.String(120), nullable=False, server_default="default-v1"),
        sa.Column(
            "source_policy_reference",
            sa.String(120),
            nullable=False,
            server_default="internal-only",
        ),
        sa.Column("summary_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("failure_classification", sa.String(80)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_intelligence_run_owner_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','waiting','completed','failed','cancelled','stale')",
            name="ck_intelligence_run_status",
        ),
    )
    op.create_index("ix_intelligence_runs_owner", "intelligence_research_runs", ["owner_id"])
    op.create_index("ix_intelligence_runs_project", "intelligence_research_runs", ["project_id"])
    op.create_index("ix_intelligence_runs_status", "intelligence_research_runs", ["status"])

    op.create_table(
        "intelligence_sources",
        _id(),
        _owner(),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False, server_default="manual"),
        sa.Column("url_or_domain", sa.String(500)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "trust_classification",
            sa.String(40),
            nullable=False,
            server_default="untrusted_external_data",
        ),
        sa.Column("access_method", sa.String(32), nullable=False, server_default="manual_entry"),
        sa.Column(
            "configuration_status", sa.String(40), nullable=False, server_default="not_configured"
        ),
        sa.Column("terms_policy_status", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("last_successful_retrieval", sa.DateTime(timezone=True)),
        sa.Column("failure_status", sa.String(120)),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "provider",
            "display_name",
            name="uq_intelligence_source_owner_provider_name",
        ),
    )
    op.create_index("ix_intelligence_sources_owner", "intelligence_sources", ["owner_id"])
    op.create_index("ix_intelligence_sources_type", "intelligence_sources", ["source_type"])
    op.create_index("ix_intelligence_sources_enabled", "intelligence_sources", ["enabled"])

    op.create_table(
        "intelligence_evidence",
        _id(),
        _owner(),
        sa.Column(
            "source_id",
            UUID,
            sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "research_run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "previous_evidence_id",
            UUID,
            sa.ForeignKey("intelligence_evidence.id", ondelete="SET NULL"),
        ),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("normalized_value", JSONB, nullable=False, server_default="{}"),
        sa.Column("excerpt_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column(
            "trust_classification",
            sa.String(40),
            nullable=False,
            server_default="untrusted_external_data",
        ),
        sa.Column(
            "verification_status", sa.String(24), nullable=False, server_default="unverified"
        ),
        sa.Column("freshness_status", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("freshness_ttl_seconds", sa.Integer()),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_intelligence_evidence_owner_idempotency"
        ),
    )
    op.create_index("ix_intelligence_evidence_owner", "intelligence_evidence", ["owner_id"])
    op.create_index("ix_intelligence_evidence_source", "intelligence_evidence", ["source_id"])
    op.create_index("ix_intelligence_evidence_run", "intelligence_evidence", ["research_run_id"])
    op.create_index(
        "ix_intelligence_evidence_previous", "intelligence_evidence", ["previous_evidence_id"]
    )
    op.create_index(
        "ix_intelligence_evidence_freshness", "intelligence_evidence", ["freshness_status"]
    )

    op.create_table(
        "intelligence_claims",
        _id(),
        _owner(),
        sa.Column(
            "research_run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("claim_type", sa.String(80), nullable=False),
        sa.Column("normalized_value", JSONB, nullable=False, server_default="{}"),
        sa.Column("unit", sa.String(40)),
        sa.Column("currency", sa.String(3)),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("verification_state", sa.String(24), nullable=False, server_default="unverified"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_intelligence_claims_owner", "intelligence_claims", ["owner_id"])
    op.create_table(
        "intelligence_claim_evidence",
        _id(),
        sa.Column(
            "claim_id",
            UUID,
            sa.ForeignKey("intelligence_claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            UUID,
            sa.ForeignKey("intelligence_evidence.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("claim_id", "evidence_id", name="uq_intelligence_claim_evidence"),
    )
    op.create_index(
        "ix_intelligence_claim_evidence_claim", "intelligence_claim_evidence", ["claim_id"]
    )
    op.create_index(
        "ix_intelligence_claim_evidence_evidence", "intelligence_claim_evidence", ["evidence_id"]
    )

    op.create_table(
        "intelligence_rule_categories",
        _id(),
        _owner(),
        sa.Column("category_key", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "category_key", name="uq_intelligence_rule_category_owner_key"
        ),
    )
    op.create_index(
        "ix_intelligence_rule_categories_owner", "intelligence_rule_categories", ["owner_id"]
    )
    op.create_table(
        "intelligence_rules",
        _id(),
        _owner(),
        sa.Column(
            "category_id",
            UUID,
            sa.ForeignKey("intelligence_rule_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("logical_key", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("severity", sa.String(24), nullable=False, server_default="warning"),
        sa.Column("hard_block", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("operator", sa.String(32), nullable=False, server_default="exists"),
        sa.Column("conditions", JSONB, nullable=False, server_default="{}"),
        sa.Column("parameters", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "reason_template", sa.String(500), nullable=False, server_default="Rule evaluated."
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "logical_key", "version", name="uq_intelligence_rule_owner_key_version"
        ),
    )
    op.create_index("ix_intelligence_rules_owner", "intelligence_rules", ["owner_id"])
    op.create_index("ix_intelligence_rules_category", "intelligence_rules", ["category_id"])
    op.create_table(
        "intelligence_rule_evaluations",
        _id(),
        _owner(),
        sa.Column(
            "rule_id",
            UUID,
            sa.ForeignKey("intelligence_rules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(80), nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("input_evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("score_impact", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("hard_block", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_intelligence_rule_evaluations_owner", "intelligence_rule_evaluations", ["owner_id"]
    )
    op.create_index(
        "ix_intelligence_rule_evaluations_subject", "intelligence_rule_evaluations", ["subject_id"]
    )

    op.create_table(
        "intelligence_opportunities",
        _id(),
        _owner(),
        sa.Column(
            "research_run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="discovered"),
        sa.Column("score", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("hard_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary_reasons", JSONB, nullable=False, server_default="[]"),
        sa.Column("risk_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("freshness_state", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('discovered','researching','review','shortlisted','rejected','approved','converted')",
            name="ck_intelligence_opportunity_status",
        ),
    )
    op.create_index(
        "ix_intelligence_opportunities_owner", "intelligence_opportunities", ["owner_id"]
    )
    op.create_index(
        "ix_intelligence_opportunities_run", "intelligence_opportunities", ["research_run_id"]
    )
    op.create_index(
        "ix_intelligence_opportunities_status", "intelligence_opportunities", ["status"]
    )
    op.create_table(
        "intelligence_opportunity_reviews",
        _id(),
        _owner(),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_intelligence_opportunity_reviews_owner",
        "intelligence_opportunity_reviews",
        ["owner_id"],
    )
    op.create_index(
        "ix_intelligence_opportunity_reviews_opportunity",
        "intelligence_opportunity_reviews",
        ["opportunity_id"],
    )


def downgrade() -> None:
    for table in (
        "intelligence_opportunity_reviews",
        "intelligence_opportunities",
        "intelligence_rule_evaluations",
        "intelligence_rules",
        "intelligence_rule_categories",
        "intelligence_claim_evidence",
        "intelligence_claims",
        "intelligence_evidence",
        "intelligence_sources",
        "intelligence_research_runs",
        "intelligence_research_projects",
    ):
        op.drop_table(table)
