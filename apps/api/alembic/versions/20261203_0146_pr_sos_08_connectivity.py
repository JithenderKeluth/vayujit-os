"""Add durable read-only marketplace connectivity import jobs for PR-SOS-08."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261203_0146"
down_revision = "20261202_0145"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "marketplace_import_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "account_id",
            UUID,
            sa.ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False, server_default="SYNTHETIC"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.String(240), nullable=False),
        sa.Column("correlation_id", sa.String(120), nullable=False),
        sa.Column("checkpoint_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provenance_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pages_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_seen", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_reused", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_sync", sa.DateTime(timezone=True)),
        sa.Column("stale_after", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "account_id",
            "operation",
            "idempotency_key",
            name="uq_marketplace_import_job_idempotency",
        ),
        sa.CheckConstraint(
            "operation IN ('catalog','orders','inventory','financial')",
            name="ck_marketplace_import_job_operation",
        ),
        sa.CheckConstraint(
            "mode IN ('SYNTHETIC','SANDBOX','LIVE_READ_ONLY')",
            name="ck_marketplace_import_job_mode",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','PARTIAL','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_marketplace_import_job_status",
        ),
    )
    op.create_index(
        "ix_marketplace_import_job_owner_account_time",
        "marketplace_import_jobs",
        ["owner_id", "account_id", "created_at"],
    )
    op.create_index(
        "ix_marketplace_import_jobs_account_id",
        "marketplace_import_jobs",
        ["account_id"],
    )
    op.create_index(
        "ix_marketplace_import_jobs_correlation_id",
        "marketplace_import_jobs",
        ["correlation_id"],
    )
    op.create_index(
        "ix_marketplace_import_jobs_operation",
        "marketplace_import_jobs",
        ["operation"],
    )
    op.create_index(
        "ix_marketplace_import_jobs_status",
        "marketplace_import_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_marketplace_import_jobs_status", table_name="marketplace_import_jobs")
    op.drop_index("ix_marketplace_import_jobs_operation", table_name="marketplace_import_jobs")
    op.drop_index(
        "ix_marketplace_import_jobs_correlation_id", table_name="marketplace_import_jobs"
    )
    op.drop_index("ix_marketplace_import_jobs_account_id", table_name="marketplace_import_jobs")
    op.drop_index(
        "ix_marketplace_import_job_owner_account_time", table_name="marketplace_import_jobs"
    )
    op.drop_table("marketplace_import_jobs")
