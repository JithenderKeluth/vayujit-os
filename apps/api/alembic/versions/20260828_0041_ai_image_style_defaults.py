"""Add image style default ownership metadata."""

import sqlalchemy as sa

from alembic import op

revision = "20260828_0041"
down_revision = "20260827_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_image_styles",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_ai_image_styles_is_default", "ai_image_styles", ["is_default"])


def downgrade() -> None:
    op.drop_index("ix_ai_image_styles_is_default", table_name="ai_image_styles")
    op.drop_column("ai_image_styles", "is_default")
