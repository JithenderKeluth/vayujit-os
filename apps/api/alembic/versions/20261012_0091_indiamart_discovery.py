"""Add normalized IndiaMART read-only discovery records."""

# Explicit Alembic declarations retain full foreign-key and index names.
# ruff: noqa: E501

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261012_0091"
down_revision = "20261011_0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_indiamart_discovery_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("query", sa.String(240), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("region", sa.String(120), nullable=True),
        sa.Column("result_limit", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_indiamart_discovery_request_idempotency"
        ),
    )
    op.create_index(
        "ix_indiamart_discovery_requests_owner_id",
        "intelligence_indiamart_discovery_requests",
        ["owner_id"],
    )
    op.create_index(
        "ix_indiamart_discovery_requests_status",
        "intelligence_indiamart_discovery_requests",
        ["status"],
    )
    op.create_table(
        "intelligence_indiamart_discovery_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_indiamart_discovery_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "offering_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_supplier_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_result_id", sa.String(180), nullable=False),
        sa.Column("supplier_name", sa.String(240), nullable=False),
        sa.Column("listing_name", sa.String(240), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("location", sa.String(240), nullable=True),
        sa.Column("category", sa.String(160), nullable=True),
        sa.Column("price_claim", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("moq_claim", sa.Numeric(18, 4), nullable=True),
        sa.Column("moq_unit", sa.String(40), nullable=True),
        sa.Column("lead_time_claim", sa.String(120), nullable=True),
        sa.Column("availability_claim", sa.String(120), nullable=True),
        sa.Column("verification_claim", sa.String(160), nullable=True),
        sa.Column("identity_match", sa.String(24), nullable=False),
        sa.Column("product_match", sa.String(24), nullable=False),
        sa.Column("freshness_status", sa.String(24), nullable=False),
        sa.Column("classification", sa.String(80), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observation_key", sa.String(240), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "provider_result_id", name="uq_indiamart_discovery_result_identity"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "request_id",
            "idempotency_key",
            name="uq_indiamart_result_request_idempotency",
        ),
    )
    op.create_index(
        "ix_indiamart_discovery_results_owner_id",
        "intelligence_indiamart_discovery_results",
        ["owner_id"],
    )
    op.create_index(
        "ix_indiamart_discovery_results_request_id",
        "intelligence_indiamart_discovery_results",
        ["request_id"],
    )
    op.create_index(
        "ix_indiamart_discovery_results_retrieved_at",
        "intelligence_indiamart_discovery_results",
        ["retrieved_at"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_indiamart_discovery_results")
    op.drop_table("intelligence_indiamart_discovery_requests")
