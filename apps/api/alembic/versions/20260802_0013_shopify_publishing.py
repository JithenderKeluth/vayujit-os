"""Add Shopify connector configuration and media mappings."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260802_0013"
down_revision = "20260801_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopify_connector_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shop_domain", sa.String(255), nullable=False),
        sa.Column("encrypted_access_token", sa.Text()),
        sa.Column("credential_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("api_version", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_product_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "default_publication_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "inventory_policy",
            sa.String(40),
            nullable=False,
            server_default="no_inventory_write",
        ),
        sa.Column(
            "variant_policy", sa.String(40), nullable=False, server_default="default_variant"
        ),
        sa.Column("media_policy", sa.String(40), nullable=False, server_default="fail"),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("max_retry_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("safe_validation_message", sa.String(500)),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.Column("last_validation_latency_ms", sa.Integer()),
        sa.Column(
            "capabilities_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("request_timeout_seconds BETWEEN 10 AND 120", name="ck_shopify_timeout"),
        sa.CheckConstraint("max_retry_attempts BETWEEN 1 AND 5", name="ck_shopify_retries"),
        sa.CheckConstraint(
            "default_product_status IN ('draft','active')", name="ck_shopify_default_status"
        ),
        sa.CheckConstraint(
            "inventory_policy IN ('no_inventory_write','track_without_quantity')",
            name="ck_shopify_inventory_policy",
        ),
        sa.UniqueConstraint("owner_id", name="uq_shopify_configuration_owner"),
    )
    op.create_index(
        "ix_shopify_connector_configurations_owner_id",
        "shopify_connector_configurations",
        ["owner_id"],
    )
    op.create_table(
        "shopify_media_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shop_fingerprint", sa.String(64), nullable=False),
        sa.Column("remote_media_id", sa.String(160), nullable=False),
        sa.Column("remote_url", sa.String(500)),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="mapped"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "media_id", "shop_fingerprint", name="uq_shopify_media_mapping"
        ),
    )
    op.create_index("ix_shopify_media_mappings_owner_id", "shopify_media_mappings", ["owner_id"])
    op.create_index("ix_shopify_media_mappings_media_id", "shopify_media_mappings", ["media_id"])


def downgrade() -> None:
    op.drop_table("shopify_media_mappings")
    op.drop_table("shopify_connector_configurations")
