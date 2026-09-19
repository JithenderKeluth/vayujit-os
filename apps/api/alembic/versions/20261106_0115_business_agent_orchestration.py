"""Add bounded Business Agent orchestration entities (Slice 9G)."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261106_0115"
down_revision = "20261105_0114"
branch_labels = None
depends_on = None


def _common(name: str, *extra: Any) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *extra,
    )
    op.create_index(f"ix_{name}_owner_id", name, ["owner_id"])


def upgrade() -> None:
    _common(
        "intelligence_business_agent_goals",
        sa.Column("raw_goal", sa.Text, nullable=False),
        sa.Column("structured_goal", postgresql.JSONB, nullable=False),
        sa.Column("provenance", postgresql.JSONB, nullable=False),
        sa.Column("assumptions", postgresql.JSONB, nullable=False),
        sa.Column("unresolved_questions", postgresql.JSONB, nullable=False),
        sa.Column("extraction_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_agent_goal_key"),
    )
    _common(
        "intelligence_business_agent_plans",
        sa.Column(
            "goal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_goals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("planner", sa.String(64), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("goal_id", "version", name="uq_agent_plan_version"),
    )
    op.create_index(
        "ix_intelligence_business_agent_plans_goal_id",
        "intelligence_business_agent_plans",
        ["goal_id"],
    )
    _common(
        "intelligence_business_agent_steps",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("capability_id", sa.String(120), nullable=False),
        sa.Column("dependency_keys", postgresql.JSONB, nullable=False),
        sa.Column("input_contract", postgresql.JSONB, nullable=False),
        sa.Column("output_contract", postgresql.JSONB, nullable=False),
        sa.Column("execution_mode", sa.String(32), nullable=False),
        sa.Column("side_effect_class", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer, nullable=False),
        sa.Column("result", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "step_key", name="uq_agent_step_key"),
    )
    op.create_index(
        "ix_intelligence_business_agent_steps_plan_id",
        "intelligence_business_agent_steps",
        ["plan_id"],
    )
    _common(
        "intelligence_business_agent_runs",
        sa.Column(
            "goal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_goals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("budget", postgresql.JSONB, nullable=False),
        sa.Column("usage", postgresql.JSONB, nullable=False),
        sa.Column("result", postgresql.JSONB, nullable=False),
        sa.Column("failure", postgresql.JSONB, nullable=False),
        sa.Column("checkpoint", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_agent_run_key"),
    )
    op.create_index(
        "ix_intelligence_business_agent_runs_goal_id",
        "intelligence_business_agent_runs",
        ["goal_id"],
    )
    _common(
        "intelligence_business_agent_attempts",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_message", sa.String(500)),
        sa.Column("output", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "step_id", "attempt_number", name="uq_agent_attempt"),
    )
    _common(
        "intelligence_business_agent_approvals",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_steps.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("decision_note", sa.String(500)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _common(
        "intelligence_business_agent_artifacts",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("provenance", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _common(
        "intelligence_business_agent_findings",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_type", sa.String(64), nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _common(
        "intelligence_business_agent_tool_invocations",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("capability_id", sa.String(120), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("side_effect_class", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _common(
        "intelligence_business_agent_checkpoints",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("state", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for name in (
        "checkpoints",
        "tool_invocations",
        "findings",
        "artifacts",
        "approvals",
        "attempts",
        "runs",
        "steps",
        "plans",
        "goals",
    ):
        op.drop_table(f"intelligence_business_agent_{name}")
