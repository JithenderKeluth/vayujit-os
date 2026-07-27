"""Add Product Management.

Revision ID: 20260727_0004
Revises: 20260727_0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260727_0004"
down_revision = "20260727_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("sku", sa.String(100)),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("short_description", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(120)),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column("price_amount", sa.Numeric(12, 2)),
        sa.Column("price_currency", sa.String(3)),
        sa.Column("compare_at_price_amount", sa.Numeric(12, 2)),
        sa.Column("cost_amount", sa.Numeric(12, 2)),
        sa.Column("tax_code", sa.String(50)),
        sa.Column("barcode", sa.String(100)),
        sa.Column("weight_value", sa.Numeric(12, 3)),
        sa.Column("weight_unit", sa.String(4)),
        sa.Column("inventory_tracking_enabled", sa.Boolean(), nullable=False),
        sa.Column("inventory_quantity", sa.Integer(), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "brand_id", "normalized_name", name="uq_products_brand_normalized_name"
        ),
        sa.UniqueConstraint("brand_id", "slug", name="uq_products_brand_slug"),
        sa.UniqueConstraint("owner_id", "sku", name="uq_products_owner_sku"),
        sa.UniqueConstraint("owner_id", "barcode", name="uq_products_owner_barcode"),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_products_status"),
        sa.CheckConstraint(
            "product_type IN ('physical', 'digital', 'service', 'affiliate')",
            name="ck_products_type",
        ),
        sa.CheckConstraint(
            "weight_unit IS NULL OR weight_unit IN ('g', 'kg', 'oz', 'lb')",
            name="ck_products_weight_unit",
        ),
        sa.CheckConstraint("price_amount IS NULL OR price_amount >= 0", name="ck_products_price"),
        sa.CheckConstraint(
            "compare_at_price_amount IS NULL OR compare_at_price_amount >= 0",
            name="ck_products_compare_price",
        ),
        sa.CheckConstraint("cost_amount IS NULL OR cost_amount >= 0", name="ck_products_cost"),
        sa.CheckConstraint(
            "compare_at_price_amount IS NULL OR price_amount IS NULL "
            "OR compare_at_price_amount >= price_amount",
            name="ck_products_compare_not_below_price",
        ),
        sa.CheckConstraint("weight_value IS NULL OR weight_value >= 0", name="ck_products_weight"),
        sa.CheckConstraint("inventory_quantity >= 0", name="ck_products_inventory_quantity"),
        sa.CheckConstraint("low_stock_threshold >= 0", name="ck_products_low_stock_threshold"),
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) "
            "OR (status <> 'archived' AND archived_at IS NULL)",
            name="ck_products_archive_timestamp",
        ),
    )
    op.create_index("ix_products_owner_id", "products", ["owner_id"])
    op.create_index("ix_products_brand_id", "products", ["brand_id"])
    op.create_index("ix_products_product_type", "products", ["product_type"])
    op.create_index("ix_products_status", "products", ["status"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_is_featured", "products", ["is_featured"])


def downgrade() -> None:
    op.drop_table("products")
