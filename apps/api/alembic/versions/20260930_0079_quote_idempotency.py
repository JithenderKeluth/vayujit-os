"""Add optional owner-scoped quote idempotency identity."""

# ruff: noqa

from alembic import op

revision = "20260930_0079"
down_revision = "20260929_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE intelligence_supplier_quotes ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(180) NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_quote_idempotency ON intelligence_supplier_quotes(owner_id, idempotency_key)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_supplier_quote_idempotency")
    op.execute("ALTER TABLE intelligence_supplier_quotes DROP COLUMN IF EXISTS idempotency_key")
