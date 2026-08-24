"""Persist deterministic research closure lineage."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260916_0065"
down_revision = "20260915_0064"
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


def upgrade() -> None:
    op.create_table(
        "intelligence_trend_observations",
        _id(),
        _owner(),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_opportunities.id", ondelete="CASCADE"),
        ),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("trend_state", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("velocity", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("acceleration", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("seasonality", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        _json("source_evidence_ids", "[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_intel_trends_candidate", "intelligence_trend_observations", ["candidate_id"]
    )
    op.create_index("ix_intel_trends_observed", "intelligence_trend_observations", ["observed_at"])

    op.create_table(
        "intelligence_economic_estimates",
        _id(),
        _owner(),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(120), nullable=False, server_default="economics-v1"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        _json("inputs"),
        _json("outputs"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        _json("assumption_summary", "[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "candidate_id", "model_version", name="uq_intel_economics_candidate_version"
        ),
    )
    op.create_index(
        "ix_intel_economics_candidate", "intelligence_economic_estimates", ["candidate_id"]
    )

    op.create_table(
        "intelligence_research_schedules",
        _id(),
        _owner(),
        sa.Column(
            "mission_id",
            UUID,
            sa.ForeignKey("intelligence_research_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column("frequency", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(24), nullable=False, server_default="materialized"),
        sa.Column(
            "run_id", UUID, sa.ForeignKey("intelligence_research_runs.id", ondelete="SET NULL")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "mission_id", "scheduled_for", name="uq_intel_schedule_mission_due"
        ),
    )
    op.create_index(
        "ix_intel_schedules_due", "intelligence_research_schedules", ["scheduled_for", "status"]
    )

    op.create_table(
        "intelligence_recovery_records",
        _id(),
        _owner(),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("failure_classification", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="completed"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        _json("details"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "run_id", "idempotency_key", name="uq_intel_recovery_idempotency"
        ),
    )
    op.create_index("ix_intel_recovery_run", "intelligence_recovery_records", ["run_id"])


def downgrade() -> None:
    for table in (
        "intelligence_recovery_records",
        "intelligence_research_schedules",
        "intelligence_economic_estimates",
        "intelligence_trend_observations",
    ):
        op.drop_table(table)
