"""Add brands and append-only audit events.

Revision ID: 20260727_0003
Revises: 20260727_0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260727_0003"
down_revision = "20260727_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("tagline", sa.String(240)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("website_url", sa.String(2048)),
        sa.Column("primary_color", sa.String(7)),
        sa.Column("secondary_color", sa.String(7)),
        sa.Column("logo_asset_path", sa.String(512)),
        sa.Column("is_active_context", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_brands_status"),
        sa.CheckConstraint(
            "(status = 'active') OR (is_active_context = false)",
            name="ck_archived_brand_not_active",
        ),
        sa.UniqueConstraint("owner_id", "normalized_name", name="uq_brands_owner_normalized_name"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_brands_owner_slug"),
    )
    op.create_index("ix_brands_owner_id", "brands", ["owner_id"])
    op.create_index("ix_brands_status", "brands", ["status"])
    op.create_index("ix_brands_is_active_context", "brands", ["is_active_context"])
    op.create_index(
        "uq_brands_one_active_context_per_owner",
        "brands",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_active_context = true"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("brands")
