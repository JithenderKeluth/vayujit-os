"""Persist durable Social Video context on schedules and jobs."""

from collections.abc import Sequence

from sqlalchemy import JSON, Column

from alembic import op

revision: str = "20260905_0053"
down_revision: str | None = "20260905_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "publishing_schedules", Column("context_json", JSON, nullable=False, server_default="{}")
    )
    op.add_column(
        "publishing_jobs", Column("context_json", JSON, nullable=False, server_default="{}")
    )
    op.alter_column("publishing_schedules", "context_json", server_default=None)
    op.alter_column("publishing_jobs", "context_json", server_default=None)


def downgrade() -> None:
    op.drop_column("publishing_jobs", "context_json")
    op.drop_column("publishing_schedules", "context_json")
