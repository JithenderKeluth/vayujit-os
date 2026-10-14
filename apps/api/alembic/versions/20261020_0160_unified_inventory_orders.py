"""Add canonical local inventory, reservations, SKU mappings, and order events."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261020_0160"
down_revision = "20261019_0159"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    op.create_table(
        "inventory_items",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("product_id", uuid, nullable=False),
        sa.Column("variant_id", uuid, nullable=True),
        sa.Column("internal_sku", sa.String(100), nullable=False),
        sa.Column("location_code", sa.String(80), nullable=False, server_default="default"),
        sa.Column("unit", sa.String(24), nullable=False, server_default="each"),
        sa.Column("on_hand_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("damaged_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["catalog_product_variants.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "owner_id", "internal_sku", "location_code", name="uq_inventory_item_sku_location"
        ),
        sa.CheckConstraint("on_hand_quantity >= 0", name="ck_inventory_on_hand_nonnegative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
        sa.CheckConstraint("damaged_quantity >= 0", name="ck_inventory_damaged_nonnegative"),
        sa.CheckConstraint(
            "reserved_quantity + damaged_quantity <= on_hand_quantity",
            name="ck_inventory_reserved_within_on_hand",
        ),
        sa.CheckConstraint("low_stock_threshold >= 0", name="ck_inventory_low_stock_threshold"),
    )
    op.create_index(
        "ix_inventory_item_owner_product", "inventory_items", ["owner_id", "product_id"]
    )
    op.create_index("ix_inventory_item_product", "inventory_items", ["product_id"])

    op.create_table(
        "inventory_movements",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("inventory_item_id", uuid, nullable=False),
        sa.Column("location_code", sa.String(80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(240)),
        sa.Column("actor_type", sa.String(12), nullable=False, server_default="HUMAN"),
        sa.Column("actor_id", uuid),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("before_on_hand", sa.Integer(), nullable=False),
        sa.Column("after_on_hand", sa.Integer(), nullable=False),
        sa.Column("before_reserved", sa.Integer(), nullable=False),
        sa.Column("after_reserved", sa.Integer(), nullable=False),
        sa.Column("provenance_json", jsonb, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "owner_id", "inventory_item_id", "idempotency_key", name="uq_inventory_movement_key"
        ),
        sa.CheckConstraint(
            "movement_type IN ('opening_balance','receipt','adjustment','reservation','reservation_release','shipment','return_receipt','damage','reconciliation')",
            name="ck_inventory_movement_type",
        ),
        sa.CheckConstraint(
            "actor_type IN ('HUMAN','SYSTEM')", name="ck_inventory_movement_actor_type"
        ),
    )
    op.create_index(
        "ix_inventory_movement_item_time",
        "inventory_movements",
        ["inventory_item_id", "created_at"],
    )

    op.create_table(
        "inventory_reservations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("inventory_item_id", uuid, nullable=False),
        sa.Column("order_id", uuid),
        sa.Column("order_line_key", sa.String(240), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("source_event_id", sa.String(240)),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("provenance_json", jsonb, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["marketplace_orders.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "owner_id", "inventory_item_id", "order_line_key", name="uq_inventory_reservation_line"
        ),
        sa.UniqueConstraint(
            "owner_id", "inventory_item_id", "idempotency_key", name="uq_inventory_reservation_key"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity"),
        sa.CheckConstraint(
            "state IN ('active','released','consumed','failed')",
            name="ck_inventory_reservation_state",
        ),
    )
    op.create_index(
        "ix_inventory_reservation_item", "inventory_reservations", ["inventory_item_id"]
    )

    op.create_table(
        "channel_sku_mappings",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("inventory_item_id", uuid, nullable=False),
        sa.Column("account_id", uuid, nullable=False),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("external_sku", sa.String(160), nullable=False),
        sa.Column("listing_id", uuid),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("effective_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provenance_json", jsonb, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["marketplace_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "owner_id", "account_id", "external_sku", name="uq_channel_sku_account_external"
        ),
        sa.UniqueConstraint(
            "owner_id", "account_id", "inventory_item_id", name="uq_channel_sku_account_item"
        ),
        sa.CheckConstraint(
            "status IN ('active','archived','conflict')", name="ck_channel_sku_mapping_status"
        ),
    )
    op.create_index("ix_channel_sku_mapping_owner", "channel_sku_mappings", ["owner_id"])

    op.create_table(
        "marketplace_order_events",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("account_id", uuid, nullable=False),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("event_id", sa.String(240), nullable=False),
        sa.Column("remote_order_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload_json", jsonb, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("error_message", sa.String(500)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["marketplace_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id", "account_id", "event_id", name="uq_marketplace_order_event"
        ),
        sa.CheckConstraint(
            "status IN ('received','applied','duplicate','rejected','reconciliation_required')",
            name="ck_marketplace_order_event_status",
        ),
    )
    op.create_index(
        "ix_marketplace_order_event_order", "marketplace_order_events", ["remote_order_id"]
    )


def downgrade() -> None:
    op.drop_table("marketplace_order_events")
    op.drop_table("channel_sku_mappings")
    op.drop_table("inventory_reservations")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_items")
