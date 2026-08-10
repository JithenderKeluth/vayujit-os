"""Add durable AI provider result checkpoints."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260816_0029"
down_revision: str | None = "20260815_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_studio_jobs", sa.Column("provider_result_json", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "ai_studio_jobs", sa.Column("provider_result_fingerprint", sa.String(64), nullable=True)
    )
    op.add_column("ai_studio_jobs", sa.Column("provider_request_id", sa.String(160), nullable=True))
    op.add_column(
        "ai_studio_jobs",
        sa.Column("provider_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_studio_jobs", sa.Column("usage_metadata_json", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ai_studio_jobs", "usage_metadata_json")
    op.drop_column("ai_studio_jobs", "provider_completed_at")
    op.drop_column("ai_studio_jobs", "provider_request_id")
    op.drop_column("ai_studio_jobs", "provider_result_fingerprint")
    op.drop_column("ai_studio_jobs", "provider_result_json")
