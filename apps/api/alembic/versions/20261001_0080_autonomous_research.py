"""Add durable autonomous research orchestration foundation."""

# ruff: noqa: E501
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261001_0080"
down_revision = "20260930_0079"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True)


def _owner() -> sa.Column:
    return sa.Column(
        "owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def _json(name: str, default: str = "{}") -> sa.Column:
    return sa.Column(name, JSONB, nullable=False, server_default=default)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False
    )


def upgrade() -> None:
    mission_types = "'PRODUCT_DISCOVERY','PRODUCT_VALIDATION','TREND_RESEARCH','COMPETITOR_RESEARCH','REVIEW_RESEARCH','SUPPLIER_DISCOVERY','SUPPLIER_VERIFICATION','PRICING_RESEARCH','ECONOMICS_RESEARCH','RISK_RESEARCH','SOURCE_REFRESH','FULL_OPPORTUNITY_RESEARCH'"
    mission_statuses = "'DRAFT','QUEUED','RUNNING','COMPLETED','COMPLETED_WITH_WARNINGS','PARTIAL','FAILED','PAUSED','CANCELLED','REQUIRES_REVIEW','STALE'"
    task_statuses = "'QUEUED','WAITING_DEPENDENCY','RUNNING','CHECKPOINTED','COMPLETED','FAILED','RETRY_WAIT','CANCELLED','STALE','SKIPPED'"
    op.create_table(
        "intelligence_autonomous_missions",
        _id(),
        _owner(),
        sa.Column("mission_type", sa.String(40), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        _json("scope"),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("product_id", UUID),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("supplier_id", UUID),
        _json("research_profile"),
        _json("ruleset"),
        _json("source_policy"),
        _json("budget_policy"),
        sa.Column(
            "provider_mode", sa.String(32), nullable=False, server_default="LOCAL_DETERMINISTIC"
        ),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("unknown_ratio", sa.Numeric(6, 4), nullable=False, server_default="1"),
        sa.Column("required_confidence", sa.Numeric(6, 4), nullable=False, server_default="0.7"),
        sa.Column("max_tasks", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_provider_calls", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_elapsed_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("frequency", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_autonomous_mission_owner_idempotency"
        ),
        sa.CheckConstraint(f"mission_type IN ({mission_types})", name="ck_autonomous_mission_type"),
        sa.CheckConstraint(f"status IN ({mission_statuses})", name="ck_autonomous_mission_status"),
    )
    op.create_index(
        "ix_autonomous_missions_owner", "intelligence_autonomous_missions", ["owner_id"]
    )
    op.create_index("ix_autonomous_missions_status", "intelligence_autonomous_missions", ["status"])
    op.create_table(
        "intelligence_autonomous_tasks",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(64), nullable=False),
        _json("dependency_ids", "[]"),
        sa.Column("source_class", sa.String(64), nullable=False, server_default="INTERNAL"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        _json("checkpoint"),
        _json("result_projection"),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "mission_id", "idempotency_key", name="uq_autonomous_task_identity"
        ),
        sa.CheckConstraint(f"status IN ({task_statuses})", name="ck_autonomous_task_status"),
    )
    op.create_index("ix_autonomous_tasks_mission", "intelligence_autonomous_tasks", ["mission_id"])
    op.create_index("ix_autonomous_tasks_status", "intelligence_autonomous_tasks", ["status"])
    op.create_table(
        "intelligence_autonomous_attempts",
        _id(),
        _owner(),
        sa.Column(
            "task_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        _json("checkpoint"),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id", "task_id", "attempt_number", name="uq_autonomous_attempt_identity"
        ),
    )
    op.create_table(
        "intelligence_autonomous_evidence",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_class", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("retrieval_identity", sa.String(500), nullable=False),
        sa.Column(
            "content_type", sa.String(120), nullable=False, server_default="application/json"
        ),
        _json("normalized_value"),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column(
            "verification_status", sa.String(32), nullable=False, server_default="UNVERIFIED"
        ),
        sa.Column("freshness_status", sa.String(32), nullable=False, server_default="FRESH"),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("evidence_class", sa.String(64), nullable=False, server_default="GENERAL"),
        sa.Column(
            "is_untrusted_external_data", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "retrieval_identity", name="uq_autonomous_evidence_retrieval"
        ),
    )
    op.create_index(
        "ix_autonomous_evidence_mission", "intelligence_autonomous_evidence", ["mission_id"]
    )
    op.create_index(
        "ix_autonomous_evidence_verification",
        "intelligence_autonomous_evidence",
        ["verification_status"],
    )
    op.create_table(
        "intelligence_autonomous_claims",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_type", sa.String(80), nullable=False),
        _json("value"),
        _json("evidence_ids", "[]"),
        sa.Column(
            "verification_status", sa.String(32), nullable=False, server_default="UNVERIFIED"
        ),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_autonomous_contradictions",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identity_key", sa.String(300), nullable=False),
        sa.Column("contradiction_type", sa.String(64), nullable=False),
        sa.Column(
            "evidence_a_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_b_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNRESOLVED"),
        sa.Column("resolution_strategy", sa.String(64)),
        sa.Column("resolution_note", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id", "mission_id", "identity_key", name="uq_autonomous_contradiction_identity"
        ),
    )
    op.create_table(
        "intelligence_autonomous_changes",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_type", sa.String(64), nullable=False),
        _json("previous_value"),
        _json("current_value"),
        sa.Column("delta", sa.Numeric(12, 4)),
        sa.Column("material", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_autonomous_schedules",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column("frequency", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(32), nullable=False, server_default="SCHEDULED"),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "mission_id", "scheduled_for", name="uq_autonomous_schedule_identity"
        ),
    )
    op.create_table(
        "intelligence_autonomous_recovery",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id", UUID, sa.ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL")
        ),
        sa.Column("failure_code", sa.String(80), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column(
            "safe_reason_code", sa.String(120), nullable=False, server_default="AUTONOMOUS_RECOVERY"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "mission_id", "idempotency_key", name="uq_autonomous_recovery_identity"
        ),
    )
    op.create_table(
        "intelligence_autonomous_alerts",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False, server_default="REQUIRES_REVIEW"),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False, server_default=""),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_autonomous_reports",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _json("provenance"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "mission_id", "format", name="uq_autonomous_report_identity"
        ),
    )


def downgrade() -> None:
    for table in (
        "intelligence_autonomous_reports",
        "intelligence_autonomous_alerts",
        "intelligence_autonomous_recovery",
        "intelligence_autonomous_schedules",
        "intelligence_autonomous_changes",
        "intelligence_autonomous_contradictions",
        "intelligence_autonomous_claims",
        "intelligence_autonomous_evidence",
        "intelligence_autonomous_attempts",
        "intelligence_autonomous_tasks",
        "intelligence_autonomous_missions",
    ):
        op.drop_table(table)
