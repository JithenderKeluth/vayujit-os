"""Add the PR-5A durable commercial-readiness projection."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20261130_0142"
down_revision = "20261130_0141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_commercial_readiness_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scenario_key", sa.String(length=120), nullable=False, server_default="source-evidence"),
        sa.Column("readiness", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("known_inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("claims", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assumptions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("unknown_inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("missing_inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("optional_gaps", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("contradictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("lineage", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["intelligence_product_opportunity_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_commercial_readiness_idempotency"),
    )
    op.create_index("ix_commercial_readiness_owner", "intelligence_commercial_readiness_snapshots", ["owner_id"])
    op.create_index("ix_commercial_readiness_opportunity", "intelligence_commercial_readiness_snapshots", ["opportunity_id"])
    op.create_index("ix_commercial_readiness_assessment", "intelligence_commercial_readiness_snapshots", ["assessment_id"])
    op.create_index("ix_commercial_readiness_supplier", "intelligence_commercial_readiness_snapshots", ["supplier_id"])


def downgrade() -> None:
    op.drop_table("intelligence_commercial_readiness_snapshots")
