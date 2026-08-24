"""Add Intelligence-owned supplier discovery tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260921_0070"
down_revision = "20260920_0069"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _base(name: str) -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "intelligence_suppliers",
        *_base("intelligence_suppliers"),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("legal_name", sa.String(240)),
        sa.Column("supplier_type", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("country_code", sa.String(2)),
        sa.Column("country", sa.String(100)),
        sa.Column("region", sa.String(120)),
        sa.Column("city", sa.String(120)),
        sa.Column("address", sa.Text()),
        sa.Column("website", sa.String(500)),
        sa.Column("normalized_domain", sa.String(240)),
        sa.Column("business_identifier", sa.String(160)),
        sa.Column("source_identity", sa.String(240), nullable=False, server_default="manual"),
        sa.Column("normalized_identity", sa.String(300), nullable=False),
        sa.Column("is_offline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column(
            "communication_status", sa.String(32), nullable=False, server_default="not_contacted"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "normalized_identity", name="uq_supplier_owner_identity"),
    )
    op.create_table(
        "intelligence_supplier_searches",
        *_base("intelligence_supplier_searches"),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("product_id", UUID),
        sa.Column("requirements", JSONB, nullable=False, server_default="{}"),
        sa.Column("source_policy", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "ruleset_version", sa.String(80), nullable=False, server_default="supplier-default-v1"
        ),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("summary_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("failure_classification", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_search_idempotency"),
    )
    op.create_table(
        "intelligence_supplier_sources",
        *_base("intelligence_supplier_sources"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("access_mode", sa.String(32), nullable=False, server_default="manual_entry"),
        sa.Column("external_id", sa.String(180)),
        sa.Column("reference", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("status", sa.String(40), nullable=False, server_default="local_fixture"),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "supplier_id", "source_type", "external_id", name="uq_supplier_source_identity"
        ),
    )
    op.create_table(
        "intelligence_supplier_contacts",
        *_base("intelligence_supplier_contacts"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(120)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(80)),
        sa.Column("whatsapp", sa.String(80)),
        sa.Column("preferred_method", sa.String(40)),
        sa.Column("provenance", sa.String(240), nullable=False, server_default="manual"),
        sa.Column(
            "verification_status", sa.String(32), nullable=False, server_default="unverified"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_supplier_capabilities",
        *_base("intelligence_supplier_capabilities"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="claimed"),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("supplier_id", "capability", name="uq_supplier_capability"),
    )
    op.create_table(
        "intelligence_supplier_products",
        *_base("intelligence_supplier_products"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("specifications", JSONB, nullable=False, server_default="{}"),
        sa.Column("observed_price", sa.Numeric(18, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("price_kind", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("moq", sa.Numeric(18, 4)),
        sa.Column("moq_unit", sa.String(40)),
        sa.Column("sample_available", sa.Boolean()),
        sa.Column("sample_moq", sa.Numeric(18, 4)),
        sa.Column("sample_lead_days", sa.Integer()),
        sa.Column("production_lead_days", sa.Integer()),
        sa.Column("dispatch_lead_days", sa.Integer()),
        sa.Column("shipping_lead_days", sa.Integer()),
        sa.Column("private_label", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("customization", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("packaging", sa.String(240)),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_status", sa.String(24), nullable=False, server_default="fresh"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "supplier_id", "source_id", "source_reference", name="uq_supplier_product_source"
        ),
    )
    op.create_table(
        "intelligence_supplier_evidence",
        *_base("intelligence_supplier_evidence"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("evidence_kind", sa.String(24), nullable=False, server_default="observed"),
        sa.Column("reference", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("normalized_value", JSONB, nullable=False, server_default="{}"),
        sa.Column("excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_status", sa.String(24), nullable=False, server_default="fresh"),
        sa.Column(
            "verification_status", sa.String(32), nullable=False, server_default="unverified"
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_evidence_idempotency"),
    )
    op.create_table(
        "intelligence_supplier_verifications",
        *_base("intelligence_supplier_verifications"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("verified_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_supplier_commercial_terms",
        *_base("intelligence_supplier_commercial_terms"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_product_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("price_tiers", JSONB, nullable=False, server_default="[]"),
        sa.Column("moq", sa.Numeric(18, 4)),
        sa.Column("sample_price", sa.Numeric(18, 4)),
        sa.Column("tooling_fee", sa.Numeric(18, 4)),
        sa.Column("packaging_fee", sa.Numeric(18, 4)),
        sa.Column("branding_fee", sa.Numeric(18, 4)),
        sa.Column("payment_terms", sa.String(160)),
        sa.Column("deposit_percent", sa.Numeric(5, 2)),
        sa.Column("balance_percent", sa.Numeric(5, 2)),
        sa.Column("incoterm", sa.String(20)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("source_evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("supplier_product_id", "version", name="uq_supplier_term_version"),
    )
    op.create_table(
        "intelligence_supplier_certification_claims",
        *_base("intelligence_supplier_certification_claims"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim", sa.String(120), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("document_reference", sa.String(500)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="[]"),
    )
    op.create_table(
        "intelligence_supplier_risk_assessments",
        *_base("intelligence_supplier_risk_assessments"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimensions", JSONB, nullable=False, server_default="{}"),
        sa.Column("warnings", JSONB, nullable=False, server_default="[]"),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_supplier_score_evaluations",
        *_base("intelligence_supplier_score_evaluations"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("weights", JSONB, nullable=False, server_default="{}"),
        sa.Column("inputs", JSONB, nullable=False, server_default="{}"),
        sa.Column("dimensions", JSONB, nullable=False, server_default="{}"),
        sa.Column("final_score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column(
            "recommendation", sa.String(32), nullable=False, server_default="insufficient_evidence"
        ),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("supplier_id", "model_version", name="uq_supplier_score_version"),
    )
    op.create_table(
        "intelligence_supplier_opportunity_matches",
        *_base("intelligence_supplier_opportunity_matches"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_product_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_key", sa.String(180), nullable=False),
        sa.Column("match_score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("matched_dimensions", JSONB, nullable=False, server_default="{}"),
        sa.Column("unmatched_requirements", JSONB, nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("explanation", JSONB, nullable=False, server_default="[]"),
        sa.UniqueConstraint(
            "supplier_product_id", "requirement_key", name="uq_supplier_match_requirement"
        ),
    )
    op.create_table(
        "intelligence_supplier_decisions",
        *_base("intelligence_supplier_decisions"),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "intelligence_supplier_decisions",
        "intelligence_supplier_opportunity_matches",
        "intelligence_supplier_score_evaluations",
        "intelligence_supplier_risk_assessments",
        "intelligence_supplier_certification_claims",
        "intelligence_supplier_commercial_terms",
        "intelligence_supplier_verifications",
        "intelligence_supplier_evidence",
        "intelligence_supplier_products",
        "intelligence_supplier_capabilities",
        "intelligence_supplier_contacts",
        "intelligence_supplier_sources",
        "intelligence_supplier_searches",
        "intelligence_suppliers",
    ):
        op.drop_table(table)
