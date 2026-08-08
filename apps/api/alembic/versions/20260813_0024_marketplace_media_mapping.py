"""Add marketplace listing mappings to existing Media assets."""

from collections.abc import Sequence

from sqlalchemy import Table

from alembic import op

revision: str = "20260813_0024"
down_revision: str | None = "20260813_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table() -> Table:
    from vayujit_api import main  # noqa: F401
    from vayujit_api.core.database import Base

    return Base.metadata.tables["marketplace_media_mappings"]


def upgrade() -> None:
    _table().create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    _table().drop(bind=op.get_bind(), checkfirst=True)
