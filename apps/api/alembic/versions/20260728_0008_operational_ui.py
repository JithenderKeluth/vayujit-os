"""Add typed owner preferences."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260728_0008"
down_revision = "20260728_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("default_page_size", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("execution_history_page_size", sa.Integer(), nullable=False, server_default="25"),
        sa.Column(
            "default_brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "default_prompt_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "default_publishing_destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id", ondelete="SET NULL"),
        ),
        sa.Column("confirm_before_publish", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("confirm_before_retry", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("theme_preference", sa.String(20), nullable=False, server_default="system"),
        sa.Column(
            "density_preference", sa.String(20), nullable=False, server_default="comfortable"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("default_page_size IN (10,25,50,100)", name="ck_preferences_page_size"),
        sa.CheckConstraint(
            "execution_history_page_size IN (10,25,50,100)",
            name="ck_preferences_history_page_size",
        ),
        sa.CheckConstraint(
            "date_format IN ('medium','short','iso')", name="ck_preferences_date_format"
        ),
        sa.CheckConstraint(
            "theme_preference IN ('system','light','dark')", name="ck_preferences_theme"
        ),
        sa.CheckConstraint(
            "density_preference IN ('comfortable','compact')",
            name="ck_preferences_density",
        ),
    )
    op.create_index("ix_owner_preferences_owner_id", "owner_preferences", ["owner_id"])


def downgrade() -> None:
    op.drop_table("owner_preferences")
