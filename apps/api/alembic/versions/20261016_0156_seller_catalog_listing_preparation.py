"""Add the PR-SOS-01 seller catalog and listing-preparation boundary."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261016_0156"
down_revision = "20261014_0155"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    op.create_table(
        "catalog_product_lineages",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("product_id", uuid, nullable=False),
        sa.Column("opportunity_id", uuid, nullable=True),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("assessment_id", uuid, nullable=True),
        sa.Column("source_kind", sa.String(24), nullable=False, server_default="manual"),
        sa.Column("provenance_json", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["intelligence_product_opportunity_assessments.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("owner_id", "product_id", name="uq_catalog_lineage_product"),
        sa.CheckConstraint(
            "source_kind IN ('manual','opportunity')", name="ck_catalog_lineage_source_kind"
        ),
    )
    op.create_index(
        "ix_catalog_lineages_owner_opportunity",
        "catalog_product_lineages",
        ["owner_id", "opportunity_id"],
    )

    op.create_table(
        "catalog_product_variants",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("product_id", uuid, nullable=False),
        sa.Column("variant_key", sa.String(120), nullable=False),
        sa.Column("title", sa.String(160), nullable=False, server_default=""),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("option_values", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attributes", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("image_refs", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "product_id", "variant_key", name="uq_catalog_variant_key"),
        sa.UniqueConstraint("owner_id", "sku", name="uq_catalog_variant_sku"),
        sa.CheckConstraint(
            "status IN ('draft','active','archived')", name="ck_catalog_variant_status"
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0", name="ck_catalog_variant_price"
        ),
    )
    op.create_index(
        "ix_catalog_variant_product",
        "catalog_product_variants",
        ["owner_id", "product_id", "status"],
    )

    op.create_table(
        "catalog_supplier_associations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("product_id", uuid, nullable=False),
        sa.Column("supplier_id", uuid, nullable=False),
        sa.Column("opportunity_id", uuid, nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="review_required"),
        sa.Column("provenance_json", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["intelligence_suppliers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "owner_id", "product_id", "supplier_id", name="uq_catalog_supplier_product"
        ),
        sa.CheckConstraint(
            "status IN ('candidate','review_required','accepted','archived')",
            name="ck_catalog_supplier_status",
        ),
    )

    op.create_table(
        "catalog_listing_drafts",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("product_id", uuid, nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("bullets", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("category", sa.String(240), nullable=True),
        sa.Column("attributes", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("image_refs", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("intended_price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("intended_currency", sa.String(3), nullable=True),
        sa.Column("compliance", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("missing_fields", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("validation_state", sa.String(24), nullable=False, server_default="incomplete"),
        sa.Column("readiness_state", sa.String(40), nullable=False, server_default="BLOCKED"),
        sa.Column(
            "human_review_state", sa.String(24), nullable=False, server_default="not_reviewed"
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="incomplete"),
        sa.Column("provenance_json", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(220), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "product_id", "channel", name="uq_catalog_listing_product_channel"
        ),
        sa.CheckConstraint(
            "channel IN ('amazon_in','flipkart')", name="ck_catalog_listing_channel"
        ),
        sa.CheckConstraint(
            "status IN ('draft','incomplete','needs_review',"
            "'approved_for_future_submission','blocked','archived')",
            name="ck_catalog_listing_status",
        ),
        sa.CheckConstraint(
            "human_review_state IN ('not_reviewed','needs_review','approved')",
            name="ck_catalog_listing_human_review",
        ),
    )
    op.create_index(
        "ix_catalog_listing_owner_status",
        "catalog_listing_drafts",
        ["owner_id", "channel", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_listing_owner_status", table_name="catalog_listing_drafts")
    op.drop_table("catalog_listing_drafts")
    op.drop_table("catalog_supplier_associations")
    op.drop_index("ix_catalog_variant_product", table_name="catalog_product_variants")
    op.drop_table("catalog_product_variants")
    op.drop_index("ix_catalog_lineages_owner_opportunity", table_name="catalog_product_lineages")
    op.drop_table("catalog_product_lineages")
