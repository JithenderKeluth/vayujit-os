# Persist explicit translation and localization lineage metadata.
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_0036"
down_revision: str | None = "20260822_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generated_artifacts", sa.Column("source_artifact_version", sa.Integer(), nullable=True)
    )
    op.add_column("generated_artifacts", sa.Column("source_locale", sa.String(16), nullable=True))
    op.add_column(
        "generated_artifacts", sa.Column("source_product_context", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("generated_artifacts", "source_product_context")
    op.drop_column("generated_artifacts", "source_locale")
    op.drop_column("generated_artifacts", "source_artifact_version")
