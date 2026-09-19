"""Add the bounded Competitor Intelligence foundation (Slice 10A)."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261107_0116"
down_revision = "20261106_0115"
branch_labels = None
depends_on = None


def _common(name: str, *extra: Any) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *extra,
    )
    op.create_index(f"ix_{name}_owner_id", name, ["owner_id"])


def upgrade() -> None:
    _common(
        "intelligence_competitor_contexts",
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_reference", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "product_opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
        ),
        sa.Column("marketplace", sa.String(120), nullable=False, server_default=""),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("currency", sa.String(3)),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id",
            "subject_type",
            "subject_reference",
            "marketplace",
            "market",
            name="uq_comp_context_subject_market",
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_context_idempotency"),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','WATCHING','ARCHIVED')", name="ck_comp_context_status"
        ),
        sa.CheckConstraint(
            "subject_type IN ('PRODUCT_OPPORTUNITY','PRODUCT','BRAND')",
            name="ck_comp_context_subject_type",
        ),
        sa.CheckConstraint("version >= 1", name="ck_comp_context_version"),
        sa.CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_comp_context_currency",
        ),
    )
    for column in (
        "subject_reference",
        "product_opportunity_id",
        "product_id",
        "brand_id",
        "marketplace",
        "market",
        "status",
    ):
        op.create_index(f"ix_comp_context_{column}", "intelligence_competitor_contexts", [column])

    _common(
        "intelligence_competitor_entities",
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("entity_type", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("canonical_name", sa.String(240), nullable=False),
        sa.Column("marketplace_identifiers", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("country_region", sa.String(120)),
        sa.Column("website_domain", sa.String(255)),
        sa.Column("evidence_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("source_lineage", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "entity_type", "canonical_name", name="uq_comp_entity_canonical"
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_entity_idempotency"),
        sa.CheckConstraint(
            "entity_type IN ('BRAND','SELLER','MANUFACTURER','MERCHANT','OPERATOR','UNKNOWN')",
            name="ck_comp_entity_type",
        ),
        sa.CheckConstraint(
            "evidence_state IN ('UNKNOWN','PARTIAL','INSUFFICIENT_EVIDENCE','AVAILABLE')",
            name="ck_comp_entity_evidence_state",
        ),
    )
    op.create_index("ix_comp_entity_type", "intelligence_competitor_entities", ["entity_type"])
    op.create_index(
        "ix_comp_entity_canonical", "intelligence_competitor_entities", ["canonical_name"]
    )

    _common(
        "intelligence_competitor_foundation_products",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_entities.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "canonical_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("brand_reference", sa.String(240)),
        sa.Column("seller_reference", sa.String(240)),
        sa.Column("marketplace", sa.String(120), nullable=False, server_default=""),
        sa.Column("external_identifier", sa.String(240), nullable=False),
        sa.Column("canonical_url", sa.String(1000)),
        sa.Column("category", sa.String(120)),
        sa.Column("availability_state", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("identity_state", sa.String(24), nullable=False, server_default="UNRESOLVED"),
        sa.Column("evidence_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("first_observed", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "marketplace",
            "external_identifier",
            name="uq_comp_product_identity",
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_product_idempotency"),
        sa.CheckConstraint(
            "identity_state IN ('UNRESOLVED','CANDIDATE','PROBABLE','CONFIRMED',"
            "'REJECTED','AMBIGUOUS')",
        ),
        sa.CheckConstraint(
            "availability_state IN ('UNKNOWN','AVAILABLE','UNAVAILABLE',"
            "'OUT_OF_STOCK','DISCONTINUED')",
            name="ck_comp_product_availability_state",
        ),
        sa.CheckConstraint(
            "evidence_state IN ('UNKNOWN','PARTIAL','INSUFFICIENT_EVIDENCE','AVAILABLE')",
            name="ck_comp_product_evidence_state",
        ),
    )
    for column in (
        "context_id",
        "entity_id",
        "canonical_product_id",
        "marketplace",
        "external_identifier",
        "identity_state",
        "evidence_state",
        "last_observed",
    ):
        op.create_index(
            f"ix_comp_product_{column}", "intelligence_competitor_foundation_products", [column]
        )

    _common(
        "intelligence_competitor_observations",
        sa.Column(
            "competitor_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_foundation_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("observation_type", sa.String(80), nullable=False),
        sa.Column("observed_value", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("numeric_value", sa.Numeric(20, 6)),
        sa.Column("unit", sa.String(40)),
        sa.Column("currency", sa.String(3)),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
        ),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_evidence.id", ondelete="RESTRICT"),
        ),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("verification_state", sa.String(24), nullable=False, server_default="UNVERIFIED"),
        sa.Column("observation_key", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "competitor_product_id", "observation_key", name="uq_comp_observation_key"
        ),
        sa.CheckConstraint(
            "numeric_value IS NULL OR numeric_value >= 0", name="ck_comp_observation_numeric"
        ),
        sa.CheckConstraint(
            "freshness_state IN ('CURRENT','STALE','UNKNOWN')", name="ck_comp_observation_freshness"
        ),
        sa.CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_comp_observation_currency",
        ),
    )
    for column in (
        "competitor_product_id",
        "observation_type",
        "source_id",
        "observed_at",
        "retrieved_at",
        "evidence_id",
        "freshness_state",
    ):
        op.create_index(
            f"ix_comp_observation_{column}", "intelligence_competitor_observations", [column]
        )

    _common(
        "intelligence_competitor_foundation_snapshots",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_foundation_products.id", ondelete="CASCADE"),
        ),
        sa.Column("snapshot_version", sa.Integer, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("source_references", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("observation_references", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "schema_version", sa.String(80), nullable=False, server_default="competitor-snapshot-v1"
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "product_id",
            "snapshot_version",
            name="uq_comp_snapshot_version",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "product_id",
            "input_fingerprint",
            name="uq_comp_snapshot_fingerprint",
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_comp_snapshot_idempotency"),
        sa.CheckConstraint("snapshot_version >= 1", name="ck_comp_snapshot_version"),
    )
    for column in (
        "context_id",
        "product_id",
        "snapshot_version",
        "captured_at",
        "input_fingerprint",
    ):
        op.create_index(
            f"ix_comp_snapshot_{column}", "intelligence_competitor_foundation_snapshots", [column]
        )


def downgrade() -> None:
    for name in (
        "intelligence_competitor_foundation_snapshots",
        "intelligence_competitor_observations",
        "intelligence_competitor_foundation_products",
        "intelligence_competitor_entities",
        "intelligence_competitor_contexts",
    ):
        op.drop_table(name)
