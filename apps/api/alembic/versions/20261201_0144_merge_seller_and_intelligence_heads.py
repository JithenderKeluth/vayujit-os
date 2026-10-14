"""Merge the historical Seller OS and intelligence migration heads."""

from alembic import op

revision = "20261201_0144"
down_revision = ("20261020_0160", "20261201_0143")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
