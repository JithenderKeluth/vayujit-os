# ruff: noqa: E501
"""Add generic marketplace lifecycle ledger."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261015_0094"
down_revision = "20261014_0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketplace_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(48), nullable=False),
        sa.Column("logical_key", sa.String(300), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("lineage", postgresql.JSONB(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "provider",
            "entity_type",
            "logical_key",
            name="uq_marketplace_ledger_identity",
        ),
    )
    for name, columns in {
        "ix_marketplace_ledger_owner_id": ["owner_id"],
        "ix_marketplace_ledger_provider": ["provider"],
        "ix_marketplace_ledger_execution_id": ["execution_id"],
        "ix_marketplace_ledger_entity_type": ["entity_type"],
        "ix_marketplace_ledger_correlation_id": ["correlation_id"],
    }.items():
        op.create_index(name, "marketplace_ledger", columns)


def downgrade() -> None:
    for name in (
        "ix_marketplace_ledger_correlation_id",
        "ix_marketplace_ledger_entity_type",
        "ix_marketplace_ledger_execution_id",
        "ix_marketplace_ledger_provider",
        "ix_marketplace_ledger_owner_id",
    ):
        op.drop_index(name, table_name="marketplace_ledger")
    op.drop_table("marketplace_ledger")
