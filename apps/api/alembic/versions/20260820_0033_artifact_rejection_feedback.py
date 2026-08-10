"""Persist structured Artifact rejection feedback."""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260820_0033"
down_revision = "20260819_0032"
branch_labels = None
depends_on = None

_COLUMNS = {
    "rejection_category": sa.Column("rejection_category", sa.String(80)),
    "rejection_feedback": sa.Column("rejection_feedback", sa.Text()),
    "rejection_field_notes": sa.Column("rejection_field_notes", sa.JSON()),
    "rejection_regeneration_guidance": sa.Column(
        "rejection_regeneration_guidance", sa.String(1000)
    ),
}


def upgrade() -> None:
    existing = {
        column["name"] for column in inspect(op.get_bind()).get_columns("generated_artifacts")
    }
    for name, column in _COLUMNS.items():
        if name not in existing:
            op.add_column("generated_artifacts", column)


def downgrade() -> None:
    existing = {
        column["name"] for column in inspect(op.get_bind()).get_columns("generated_artifacts")
    }
    for name in reversed(tuple(_COLUMNS)):
        if name in existing:
            op.drop_column("generated_artifacts", name)
