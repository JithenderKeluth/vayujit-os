"""Add normalized local marketplace Ads support."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260912_0060"
down_revision: str | None = "20260911_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ad_campaigns", sa.Column("marketplace", sa.String(24)))
    op.add_column("ad_campaigns", sa.Column("listing_id", sa.String(180)))
    op.add_column("ad_campaigns", sa.Column("listing_version", sa.Integer()))
    op.add_column("ad_campaigns", sa.Column("listing_state", sa.String(24)))
    op.create_index("ix_ad_campaigns_marketplace", "ad_campaigns", ["marketplace"])
    op.create_index("ix_ad_campaigns_listing_id", "ad_campaigns", ["listing_id"])
    op.create_table(
        "ad_marketplace_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marketplace", sa.String(24), nullable=False),
        sa.Column("listing_id", sa.String(180), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(24), nullable=False, server_default="active"),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("sku", sa.String(120)),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "owner_id", "marketplace", "listing_id", "version", name="uq_ad_marketplace_listing"
        ),
    )
    op.create_index("ix_ad_marketplace_listings_owner", "ad_marketplace_listings", ["owner_id"])
    op.create_index("ix_ad_marketplace_listings_product", "ad_marketplace_listings", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_ad_marketplace_listings_product", table_name="ad_marketplace_listings")
    op.drop_index("ix_ad_marketplace_listings_owner", table_name="ad_marketplace_listings")
    op.drop_table("ad_marketplace_listings")
    op.drop_index("ix_ad_campaigns_listing_id", table_name="ad_campaigns")
    op.drop_index("ix_ad_campaigns_marketplace", table_name="ad_campaigns")
    op.drop_column("ad_campaigns", "listing_state")
    op.drop_column("ad_campaigns", "listing_version")
    op.drop_column("ad_campaigns", "listing_id")
    op.drop_column("ad_campaigns", "marketplace")
