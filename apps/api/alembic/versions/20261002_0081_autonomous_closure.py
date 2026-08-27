# ruff: noqa: E501
"""Harden autonomous audit/change/research scheduler identities."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261002_0081"
down_revision = "20261001_0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("idempotency_key", sa.String(180), nullable=True))
    op.create_index(
        "ix_audit_events_idempotency_key", "audit_events", ["idempotency_key"], unique=True
    )
    op.add_column(
        "intelligence_autonomous_changes", sa.Column("identity_key", sa.String(300), nullable=True)
    )
    op.add_column(
        "intelligence_autonomous_changes",
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "intelligence_autonomous_changes",
        sa.Column("materiality", sa.String(24), nullable=False, server_default="NON_MATERIAL"),
    )
    op.add_column(
        "intelligence_autonomous_changes",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_autonomous_changes", sa.Column("correlation_id", sa.String(80), nullable=True)
    )
    op.execute(
        "UPDATE intelligence_autonomous_changes SET observed_at = created_at WHERE observed_at IS NULL"
    )
    op.execute(
        "UPDATE intelligence_autonomous_changes SET identity_key = md5(change_type || ':' || id::text) WHERE identity_key IS NULL"
    )
    op.alter_column("intelligence_autonomous_changes", "identity_key", nullable=False)
    op.alter_column("intelligence_autonomous_changes", "observed_at", nullable=False)
    op.create_unique_constraint(
        "uq_autonomous_change_identity",
        "intelligence_autonomous_changes",
        ["owner_id", "mission_id", "identity_key"],
    )
    op.add_column(
        "intelligence_autonomous_schedules",
        sa.Column("catch_up_policy", sa.String(24), nullable=False, server_default="SKIP"),
    )
    op.add_column(
        "intelligence_autonomous_schedules",
        sa.Column("materialized_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("intelligence_autonomous_schedules", "materialized_at")
    op.drop_column("intelligence_autonomous_schedules", "catch_up_policy")
    op.drop_constraint(
        "uq_autonomous_change_identity", "intelligence_autonomous_changes", type_="unique"
    )
    op.drop_column("intelligence_autonomous_changes", "correlation_id")
    op.drop_column("intelligence_autonomous_changes", "observed_at")
    op.drop_column("intelligence_autonomous_changes", "materiality")
    op.drop_column("intelligence_autonomous_changes", "evidence_ids")
    op.drop_column("intelligence_autonomous_changes", "identity_key")
    op.drop_index("ix_audit_events_idempotency_key", table_name="audit_events")
    op.drop_column("audit_events", "idempotency_key")
