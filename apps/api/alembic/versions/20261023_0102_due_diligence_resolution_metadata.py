"""immutable due-diligence resolution metadata"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261023_0102"
down_revision = "20261022_0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_supplier_evidence_gaps",
        sa.Column("resolution_type", sa.String(32), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_evidence_gaps",
        sa.Column(
            "resolution_observation_ids", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "intelligence_supplier_evidence_gaps",
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("intelligence_supplier_evidence_gaps", "resolved_by")
    op.drop_column("intelligence_supplier_evidence_gaps", "resolution_observation_ids")
    op.drop_column("intelligence_supplier_evidence_gaps", "resolution_type")
