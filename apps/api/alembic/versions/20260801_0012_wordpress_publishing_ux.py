"""Add owner-scoped media assets and WordPress remote media mappings."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260801_0012"
down_revision = "20260731_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("safe_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(180), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('ready','archived')", name="ck_media_status"),
        sa.CheckConstraint("size_bytes > 0", name="ck_media_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_media_dimensions"),
        sa.UniqueConstraint("owner_id", "checksum_sha256", name="uq_media_owner_checksum"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_media_assets_owner_id", "media_assets", ["owner_id"])
    op.create_index("ix_media_assets_mime_type", "media_assets", ["mime_type"])
    op.create_index("ix_media_assets_status", "media_assets", ["status"])
    op.create_table(
        "wordpress_media_mappings",
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
        sa.Column("site_fingerprint", sa.String(64), nullable=False),
        sa.Column("remote_media_id", sa.String(100), nullable=False),
        sa.Column("remote_url", sa.String(500)),
        sa.Column("remote_status", sa.String(30), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "media_id",
            "site_fingerprint",
            name="uq_wordpress_media_owner_asset_site",
        ),
    )
    op.create_index(
        "ix_wordpress_media_mappings_owner_id", "wordpress_media_mappings", ["owner_id"]
    )
    op.create_index(
        "ix_wordpress_media_mappings_media_id", "wordpress_media_mappings", ["media_id"]
    )


def downgrade() -> None:
    op.drop_table("wordpress_media_mappings")
    op.drop_table("media_assets")
