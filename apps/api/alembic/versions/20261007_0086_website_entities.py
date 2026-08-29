"""Persist bounded manufacturer and supplier website intelligence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261007_0086"
down_revision = "20261006_0085"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB


def _owner(name: str = "owner_id") -> sa.Column:
    return sa.Column(name, UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "intelligence_website_source_profiles",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("country", sa.String(100), nullable=False, server_default=""),
        sa.Column("region", sa.String(120), nullable=False, server_default=""),
        sa.Column(
            "classification",
            sa.String(80),
            nullable=False,
            server_default="UNTRUSTED_EXTERNAL_DATA",
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("search_allowed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("fetch_allowed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("freshness_policy", sa.String(24), nullable=False, server_default="MANUAL"),
        sa.Column(
            "verification_policy", sa.String(80), nullable=False, server_default="EVIDENCE_REQUIRED"
        ),
        sa.Column("robots_terms_status", sa.String(40), nullable=False, server_default="UNKNOWN"),
        sa.Column("known_mirror_domains", JSON, nullable=False, server_default="[]"),
        sa.Column("business_identity_hints", JSON, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("logical_identity", sa.String(300), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("owner_id", "logical_identity", name="uq_website_profile_identity"),
    )
    op.create_table(
        "intelligence_website_source_profile_versions",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column(
            "profile_id",
            UUID,
            sa.ForeignKey("intelligence_website_source_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("rules", JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("profile_id", "version", name="uq_website_profile_version"),
    )
    op.create_table(
        "intelligence_manufacturer_candidates",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("normalized_name", sa.String(240), nullable=False),
        sa.Column("website", sa.String(1000), nullable=False, server_default=""),
        sa.Column("canonical_domain", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), nullable=False, server_default=""),
        sa.Column("region", sa.String(120), nullable=False, server_default=""),
        sa.Column("business_type", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("manufacturer_status", sa.String(32), nullable=False, server_default="claimed"),
        sa.Column("supplier_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("exporter_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("distributor_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("product_categories", JSON, nullable=False, server_default="[]"),
        sa.Column("capabilities", JSON, nullable=False, server_default="[]"),
        sa.Column("markets_served", JSON, nullable=False, server_default="[]"),
        sa.Column("years_in_business_claim", sa.String(80)),
        sa.Column("public_business_identifiers", JSON, nullable=False, server_default="{}"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("freshness", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("risk", JSON, nullable=False, server_default="[]"),
        sa.Column("last_researched_at", sa.DateTime(timezone=True)),
        sa.Column("logical_identity", sa.String(300), nullable=False),
        sa.Column(
            "current_status", sa.String(32), nullable=False, server_default="REVIEW_REQUIRED"
        ),
        *_timestamps(),
        sa.UniqueConstraint(
            "owner_id", "logical_identity", name="uq_manufacturer_candidate_identity"
        ),
    )
    op.create_table(
        "intelligence_supplier_website_candidates",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column(
            "supplier_id", UUID, sa.ForeignKey("intelligence_suppliers.id", ondelete="SET NULL")
        ),
        sa.Column(
            "manufacturer_candidate_id",
            UUID,
            sa.ForeignKey("intelligence_manufacturer_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column(
            "source_profile_id",
            UUID,
            sa.ForeignKey("intelligence_website_source_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column("identity_state", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("match_state", sa.String(32), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("freshness", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("risk", JSON, nullable=False, server_default="[]"),
        sa.Column("last_researched_at", sa.DateTime(timezone=True)),
        sa.Column("lineage", JSON, nullable=False, server_default="{}"),
        sa.Column("logical_identity", sa.String(300), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "owner_id", "logical_identity", name="uq_supplier_website_candidate_identity"
        ),
    )
    op.create_table(
        "intelligence_website_observations",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "source_profile_id",
            UUID,
            sa.ForeignKey("intelligence_website_source_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_manufacturer_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("page_url", sa.String(1000), nullable=False),
        sa.Column("observation_type", sa.String(40), nullable=False),
        sa.Column("claim_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("normalized_value", JSON, nullable=False, server_default="{}"),
        sa.Column(
            "source_provided_state", sa.String(32), nullable=False, server_default="SOURCE_PROVIDED"
        ),
        sa.Column("verification", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("freshness", sa.String(24), nullable=False, server_default="FRESH"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("evidence_ids", JSON, nullable=False, server_default="[]"),
        sa.Column(
            "previous_observation_id",
            UUID,
            sa.ForeignKey("intelligence_website_observations.id", ondelete="SET NULL"),
        ),
        sa.Column("correlation_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("observation_identity", sa.String(400), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "observation_identity", name="uq_website_observation_identity"
        ),
    )
    op.create_table(
        "intelligence_website_offerings",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_manufacturer_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "supplier_website_candidate_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_website_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("source_name", sa.String(240), nullable=False, server_default=""),
        sa.Column("model_sku", sa.String(160), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("details", JSON, nullable=False, server_default="{}"),
        sa.Column("evidence_ids", JSON, nullable=False, server_default="[]"),
        sa.Column("match_state", sa.String(32), nullable=False, server_default="NO_MATCH"),
        sa.Column("match_confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("match_reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("logical_identity", sa.String(400), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("owner_id", "logical_identity", name="uq_website_offering_identity"),
    )
    op.create_table(
        "intelligence_website_claims",
        sa.Column("id", UUID, primary_key=True),
        _owner(),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_manufacturer_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_type", sa.String(80), nullable=False),
        sa.Column("claim_identity", sa.String(300), nullable=False),
        sa.Column("claim_value", JSON, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(40), nullable=False, server_default="CLAIMED"),
        sa.Column("evidence_ids", JSON, nullable=False, server_default="[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "candidate_id",
            "claim_type",
            "claim_identity",
            name="uq_website_claim_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("intelligence_website_claims")
    op.drop_table("intelligence_website_offerings")
    op.drop_table("intelligence_website_observations")
    op.drop_table("intelligence_supplier_website_candidates")
    op.drop_table("intelligence_manufacturer_candidates")
    op.drop_table("intelligence_website_source_profile_versions")
    op.drop_table("intelligence_website_source_profiles")
