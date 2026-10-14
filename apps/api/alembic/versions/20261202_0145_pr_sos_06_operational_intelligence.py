"""Additive PR-SOS-06 operational intelligence and Action Center state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261202_0145"
down_revision = "20261201_0144"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB()


def _common() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "operational_signals",
        *_common(),
        sa.Column("signal_type", sa.String(80), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("marketplace", sa.String(30)),
        sa.Column("source_authority", sa.String(120), nullable=False),
        sa.Column("source_resource_type", sa.String(80), nullable=False),
        sa.Column("source_resource_id", sa.String(240)),
        sa.Column("source_version", sa.String(80), nullable=False, server_default="v1"),
        sa.Column("signal_kind", sa.String(24), nullable=False, server_default="DERIVED"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Numeric(5, 2)),
        sa.Column("evidence_quality", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fresh_until", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("uncertainty", sa.Text),
        sa.Column("recommended_action", sa.Text, nullable=False),
        sa.Column("recommended_action_type", sa.String(40), nullable=False, server_default="HUMAN_APPROVAL_REQUIRED"),
        sa.Column("source_route", sa.String(500)),
        sa.Column("evidence_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("rule_version", sa.String(60), nullable=False, server_default="pr-sos-06-v1"),
        sa.Column("fingerprint", sa.String(240), nullable=False),
        sa.Column("priority_score", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("snoozed_until", sa.DateTime(timezone=True)),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_operational_signal_fingerprint"),
        sa.CheckConstraint("category IN ('catalog','inventory','orders','financial','supplier','system')", name="ck_operational_signal_category"),
        sa.CheckConstraint("severity IN ('critical','high','medium','low','info')", name="ck_operational_signal_severity"),
        sa.CheckConstraint("status IN ('NEW','ACKNOWLEDGED','SNOOZED','IN_PROGRESS','RESOLVED','REOPENED','STALE')", name="ck_operational_signal_status"),
        sa.CheckConstraint("signal_kind IN ('OBSERVED','DERIVED','RECOMMENDATION','UNKNOWN')", name="ck_operational_signal_kind"),
    )
    for name, cols in (
        ("ix_operational_signals_owner_id", ["owner_id"]),
        ("ix_operational_signal_owner_status_priority", ["owner_id", "status", "priority_score"]),
        ("ix_operational_signal_owner_category", ["owner_id", "category", "severity"]),
        ("ix_operational_signals_marketplace", ["marketplace"]),
    ):
        op.create_index(name, "operational_signals", cols)

    op.create_table(
        "operational_signal_transitions",
        *_common(),
        sa.Column("signal_id", UUID, sa.ForeignKey("operational_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(24)),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="HUMAN"),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("idempotency_key", sa.String(240), nullable=False),
        sa.Column("metadata_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_operational_transition_idempotency"),
    )
    op.create_index("ix_operational_transition_owner_signal", "operational_signal_transitions", ["owner_id", "signal_id", "created_at"])

    op.create_table(
        "operational_automation_policies",
        *_common(),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("emergency_stop", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("severity_threshold", sa.String(20), nullable=False, server_default="high"),
        sa.Column("minimum_confidence", sa.Numeric(5, 2), nullable=False, server_default="0.80"),
        sa.Column("cooldown_seconds", sa.Integer, nullable=False, server_default="3600"),
        sa.Column("maximum_actions_per_run", sa.Integer, nullable=False, server_default="10"),
        sa.Column("signal_types_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notification_preferences_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("policy_version", sa.String(60), nullable=False, server_default="pr-sos-06-policy-v1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", name="uq_operational_policy_owner"),
    )
    op.create_table(
        "operational_notifications",
        *_common(),
        sa.Column("signal_id", UUID, sa.ForeignKey("operational_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(60), nullable=False),
        sa.Column("dedupe_key", sa.String(240), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "dedupe_key", name="uq_operational_notification_dedupe"),
    )
    op.create_index("ix_operational_notification_owner_unread", "operational_notifications", ["owner_id", "read_at"])
    op.create_table(
        "operational_briefings",
        *_common(),
        sa.Column("snapshot_key", sa.String(80), nullable=False),
        sa.Column("source_scan_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "snapshot_key", name="uq_operational_briefing_snapshot"),
    )


def downgrade() -> None:
    op.drop_table("operational_briefings")
    op.drop_table("operational_notifications")
    op.drop_table("operational_automation_policies")
    op.drop_table("operational_signal_transitions")
    op.drop_table("operational_signals")
