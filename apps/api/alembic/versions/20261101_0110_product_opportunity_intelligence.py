"""Add Slice 9B assessment-bound intelligence outputs."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261101_0110"
down_revision = "20261030_0109"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "intelligence_product_opportunity_outputs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("opportunity_id", UUID, nullable=False),
        sa.Column("assessment_id", UUID, nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("calculation_version", sa.String(120), nullable=False),
        sa.Column("input_snapshot", JSONB, nullable=False),
        sa.Column("dimensions", JSONB, nullable=False),
        sa.Column("evidence_summary", JSONB, nullable=False),
        sa.Column("research_gaps", JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["intelligence_product_opportunities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["intelligence_product_opportunity_assessments.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "assessment_id",
            "kind",
            name="uq_product_opportunity_output_assessment_kind",
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_output_idempotency"
        ),
    )
    op.create_index(
        "ix_product_opportunity_output_owner",
        "intelligence_product_opportunity_outputs",
        ["owner_id"],
    )
    op.create_index(
        "ix_product_opportunity_output_opportunity",
        "intelligence_product_opportunity_outputs",
        ["opportunity_id", "assessment_id"],
    )
    op.create_index(
        "ix_product_opportunity_output_kind",
        "intelligence_product_opportunity_outputs",
        ["kind"],
    )
    op.create_index(
        "ix_product_opportunity_output_created",
        "intelligence_product_opportunity_outputs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_opportunity_output_created",
        table_name="intelligence_product_opportunity_outputs",
    )
    op.drop_index(
        "ix_product_opportunity_output_kind",
        table_name="intelligence_product_opportunity_outputs",
    )
    op.drop_index(
        "ix_product_opportunity_output_opportunity",
        table_name="intelligence_product_opportunity_outputs",
    )
    op.drop_index(
        "ix_product_opportunity_output_owner",
        table_name="intelligence_product_opportunity_outputs",
    )
    op.drop_table("intelligence_product_opportunity_outputs")
