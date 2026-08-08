"""Add safe Amazon account configuration metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "20260813_0025"
down_revision: str | None = "20260813_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("marketplace_accounts")
    }
    if "configuration_json" not in columns:
        op.add_column(
            "marketplace_accounts",
            sa.Column(
                "configuration_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("marketplace_accounts")
    }
    if "configuration_json" in columns:
        op.drop_column("marketplace_accounts", "configuration_json")
