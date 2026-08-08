"""Add Amazon settlement lifecycle metadata."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0026"
down_revision: str | None = "20260813_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("marketplace_settlements")}
    additions = (
        ("status", sa.String(length=30), "settled"),
        ("other_adjustment_amount", sa.Numeric(12, 2), "0"),
        ("remote_generated_at", sa.DateTime(timezone=True), None),
        ("imported_at", sa.DateTime(timezone=True), None),
    )
    for name, column_type, default in additions:
        if name not in columns:
            kwargs: dict[str, Any] = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = sa.text(f"'{default}'")
            op.add_column("marketplace_settlements", sa.Column(name, column_type, **kwargs))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("marketplace_settlements")}
    for name in ("imported_at", "remote_generated_at", "other_adjustment_amount", "status"):
        if name in columns:
            op.drop_column("marketplace_settlements", name)
