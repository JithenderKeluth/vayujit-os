"""Add secure, owner-scoped catalog product image associations (PR-SOS-01.1)."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261017_0157"
down_revision = "20261016_0156"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "catalog_product_images",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("product_id", uuid, nullable=False),
        sa.Column("media_id", uuid, nullable=False),
        sa.Column("alt_text", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "owner_id", "product_id", "media_id", name="uq_catalog_product_image_media"
        ),
        sa.CheckConstraint("position >= 0", name="ck_catalog_product_image_position"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_product_image_version"),
    )
    op.create_index(
        "ix_catalog_product_image_order",
        "catalog_product_images",
        ["owner_id", "product_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_product_image_order", table_name="catalog_product_images")
    op.drop_table("catalog_product_images")
