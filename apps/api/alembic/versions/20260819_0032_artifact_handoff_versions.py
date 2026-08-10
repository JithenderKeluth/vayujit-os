"""Persist exact Artifact versions on marketplace listings."""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260819_0032"
down_revision = "20260818_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("marketplace_listings")
    }
    if "content_artifact_version" not in columns:
        op.add_column("marketplace_listings", sa.Column("content_artifact_version", sa.Integer()))


def downgrade() -> None:
    columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("marketplace_listings")
    }
    if "content_artifact_version" in columns:
        op.drop_column("marketplace_listings", "content_artifact_version")
