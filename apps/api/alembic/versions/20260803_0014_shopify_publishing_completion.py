"""Complete normalized Shopify publishing mappings and retry metadata."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260803_0014"
down_revision = "20260802_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publishing_execution_attempts", sa.Column("calculated_delay_ms", sa.Integer()))
    op.add_column("publishing_execution_attempts", sa.Column("applied_delay_ms", sa.Integer()))
    op.add_column(
        "shopify_media_mappings",
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="CASCADE"),
        ),
    )
    op.add_column("shopify_media_mappings", sa.Column("remote_product_id", sa.String(160)))
    op.add_column(
        "shopify_media_mappings", sa.Column("alt_text", sa.String(512), server_default="")
    )
    op.add_column("shopify_media_mappings", sa.Column("position", sa.Integer(), server_default="0"))
    op.alter_column("shopify_media_mappings", "alt_text", nullable=False)
    op.alter_column("shopify_media_mappings", "position", nullable=False)
    op.create_index(
        "ix_shopify_media_mappings_destination_id", "shopify_media_mappings", ["destination_id"]
    )
    op.drop_constraint("uq_shopify_media_mapping", "shopify_media_mappings", type_="unique")
    op.create_unique_constraint(
        "uq_shopify_media_mapping",
        "shopify_media_mappings",
        ["owner_id", "destination_id", "media_id", "shop_fingerprint"],
    )

    op.create_table(
        "shopify_variant_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_variant_key", sa.String(100), nullable=False),
        sa.Column("remote_product_id", sa.String(160), nullable=False),
        sa.Column("remote_variant_id", sa.String(160), nullable=False),
        sa.Column("remote_inventory_item_id", sa.String(160)),
        sa.Column("sku", sa.String(100)),
        sa.Column("option_signature", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="mapped"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "destination_id", "product_id", "local_variant_key", name="uq_shopify_variant_mapping"
        ),
    )
    for column in ("owner_id", "destination_id", "product_id"):
        op.create_index(
            f"ix_shopify_variant_mappings_{column}", "shopify_variant_mappings", [column]
        )

    op.create_table(
        "shopify_product_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("remote_product_id", sa.String(160), nullable=False),
        sa.Column("assignment_type", sa.String(20), nullable=False),
        sa.Column("remote_target_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="assigned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "assignment_type IN ('collection','publication')", name="ck_shopify_assignment_type"
        ),
        sa.UniqueConstraint(
            "destination_id",
            "remote_product_id",
            "assignment_type",
            "remote_target_id",
            name="uq_shopify_product_assignment",
        ),
    )
    for column in ("owner_id", "destination_id"):
        op.create_index(
            f"ix_shopify_product_assignments_{column}", "shopify_product_assignments", [column]
        )


def downgrade() -> None:
    op.drop_table("shopify_product_assignments")
    op.drop_table("shopify_variant_mappings")
    op.drop_constraint("uq_shopify_media_mapping", "shopify_media_mappings", type_="unique")
    op.create_unique_constraint(
        "uq_shopify_media_mapping",
        "shopify_media_mappings",
        ["owner_id", "media_id", "shop_fingerprint"],
    )
    op.drop_column("shopify_media_mappings", "position")
    op.drop_column("shopify_media_mappings", "alt_text")
    op.drop_column("shopify_media_mappings", "remote_product_id")
    op.drop_column("shopify_media_mappings", "destination_id")
    op.drop_column("publishing_execution_attempts", "applied_delay_ms")
    op.drop_column("publishing_execution_attempts", "calculated_delay_ms")
