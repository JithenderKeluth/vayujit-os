"""Add durable sourcing worker checkpoint and recovery idempotency state."""

# ruff: noqa

from alembic import op

revision = "20260929_0078"
down_revision = "20260928_0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS checkpoint_stage VARCHAR(64) NOT NULL DEFAULT 'created'"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS checkpoint_payload JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ NULL"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(160) NULL"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ NULL"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ NULL"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_worker_jobs ADD COLUMN IF NOT EXISTS last_error TEXT NULL"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_recovery_records ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(180) NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_recovery_records ADD CONSTRAINT uq_sourcing_recovery_idempotency UNIQUE(owner_id, entity_type, entity_id, action, idempotency_key)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE intelligence_sourcing_recovery_records DROP CONSTRAINT IF EXISTS uq_sourcing_recovery_idempotency"
    )
    op.execute(
        "ALTER TABLE intelligence_sourcing_recovery_records DROP COLUMN IF EXISTS idempotency_key"
    )
    for column in (
        "last_error",
        "heartbeat_at",
        "lease_expires_at",
        "lease_owner",
        "claimed_at",
        "attempt_count",
        "checkpoint_payload",
        "checkpoint_stage",
    ):
        op.execute(f"ALTER TABLE intelligence_sourcing_worker_jobs DROP COLUMN IF EXISTS {column}")
