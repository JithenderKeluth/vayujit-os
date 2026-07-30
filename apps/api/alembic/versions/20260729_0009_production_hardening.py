"""Add production hardening records and audit correlation."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260729_0009"
down_revision = "20260728_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("correlation_id", sa.String(64)))
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])
    op.create_table(
        "backup_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("backup_key", sa.String(80), nullable=False),
        sa.Column("filename", sa.String(160), nullable=False),
        sa.Column("format", sa.String(30), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("application_version", sa.String(30), nullable=False),
        sa.Column("migration_revision", sa.String(40), nullable=False),
        sa.Column("database_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_failure_message", sa.String(500)),
        sa.CheckConstraint("format IN ('postgres-custom')", name="ck_backup_format"),
        sa.CheckConstraint("status IN ('created','verified','failed')", name="ck_backup_status"),
        sa.CheckConstraint(
            "verification_status IN ('pending','verified','invalid')",
            name="ck_backup_verification",
        ),
        sa.UniqueConstraint("backup_key"),
        sa.UniqueConstraint("filename"),
    )
    op.create_index("ix_backup_records_owner_id", "backup_records", ["owner_id"])
    op.create_index("ix_backup_records_backup_key", "backup_records", ["backup_key"], unique=True)
    op.create_index("ix_backup_records_created_at", "backup_records", ["created_at"])


def downgrade() -> None:
    op.drop_table("backup_records")
    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events")
    op.drop_column("audit_events", "correlation_id")
