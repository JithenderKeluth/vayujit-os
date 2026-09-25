"""Add bounded immutable economic scenarios and sensitivity results for 13F."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261130_0139"
down_revision = "20261129_0138"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_economic_scenarios",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "economic_context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sourcing_scenario_id",
            UUID,
            sa.ForeignKey("intelligence_scenarios.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "baseline_calculation_id",
            UUID,
            sa.ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("overrides", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_economic_scenario_idempotency"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_economic_scenario_fingerprint"),
        sa.CheckConstraint("version > 0", name="ck_economic_scenario_version"),
        sa.CheckConstraint(
            "status IN ('READY','EXECUTED','ARCHIVED')", name="ck_economic_scenario_status"
        ),
    )
    op.create_index("ix_economic_scenario_owner", "intelligence_economic_scenarios", ["owner_id"])
    op.create_index(
        "ix_economic_scenario_context", "intelligence_economic_scenarios", ["economic_context_id"]
    )
    op.create_index(
        "ix_economic_scenario_baseline",
        "intelligence_economic_scenarios",
        ["baseline_calculation_id"],
    )
    op.create_index("ix_economic_scenario_status", "intelligence_economic_scenarios", ["status"])
    op.create_index(
        "ix_economic_scenario_fingerprint", "intelligence_economic_scenarios", ["fingerprint"]
    )

    op.create_table(
        "intelligence_economic_scenario_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "scenario_id",
            UUID,
            sa.ForeignKey("intelligence_economic_scenarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column(
            "baseline_calculation_id",
            UUID,
            sa.ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scenario_calculation_id",
            UUID,
            sa.ForeignKey("intelligence_economic_calculations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scenario_snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_economic_input_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("comparability", sa.String(24), nullable=False),
        sa.Column("baseline_status", sa.String(16), nullable=False),
        sa.Column("scenario_status", sa.String(16), nullable=False),
        sa.Column("baseline_currency", sa.String(3)),
        sa.Column("scenario_currency", sa.String(3)),
        sa.Column("baseline_total", sa.Numeric(24, 8)),
        sa.Column("scenario_total", sa.Numeric(24, 8)),
        sa.Column("absolute_delta", sa.Numeric(24, 8)),
        sa.Column("percentage_delta", sa.Numeric(24, 8)),
        sa.Column("baseline_per_unit", sa.Numeric(24, 8)),
        sa.Column("scenario_per_unit", sa.Numeric(24, 8)),
        sa.Column("per_unit_delta", sa.Numeric(24, 8)),
        sa.Column("changed_inputs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("component_deltas", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assumptions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("missing_inputs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stale_inputs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("warnings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "fingerprint", name="uq_economic_scenario_result_fingerprint"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "scenario_id",
            "idempotency_key",
            name="uq_economic_scenario_result_idempotency",
        ),
        sa.CheckConstraint(
            "comparability IN ('COMPARABLE','PARTIALLY_COMPARABLE','NOT_COMPARABLE')",
            name="ck_economic_scenario_result_comparability",
        ),
    )
    op.create_index(
        "ix_economic_scenario_result_owner", "intelligence_economic_scenario_results", ["owner_id"]
    )
    op.create_index(
        "ix_economic_scenario_result_scenario",
        "intelligence_economic_scenario_results",
        ["scenario_id"],
    )
    op.create_index(
        "ix_economic_scenario_result_baseline",
        "intelligence_economic_scenario_results",
        ["baseline_calculation_id"],
    )
    op.create_index(
        "ix_economic_scenario_result_scenario_calc",
        "intelligence_economic_scenario_results",
        ["scenario_calculation_id"],
    )
    op.create_index(
        "ix_economic_scenario_result_snapshot",
        "intelligence_economic_scenario_results",
        ["scenario_snapshot_id"],
    )
    op.create_index(
        "ix_economic_scenario_result_fingerprint",
        "intelligence_economic_scenario_results",
        ["fingerprint"],
    )

    op.create_table(
        "intelligence_economic_sensitivity_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "scenario_id",
            UUID,
            sa.ForeignKey("intelligence_economic_scenarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("points", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_economic_sensitivity_fingerprint"),
        sa.UniqueConstraint(
            "owner_id",
            "scenario_id",
            "idempotency_key",
            name="uq_economic_sensitivity_idempotency",
        ),
    )
    op.create_index(
        "ix_economic_sensitivity_owner", "intelligence_economic_sensitivity_runs", ["owner_id"]
    )
    op.create_index(
        "ix_economic_sensitivity_scenario",
        "intelligence_economic_sensitivity_runs",
        ["scenario_id"],
    )
    op.create_index(
        "ix_economic_sensitivity_fingerprint",
        "intelligence_economic_sensitivity_runs",
        ["fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_economic_sensitivity_fingerprint", table_name="intelligence_economic_sensitivity_runs"
    )
    op.drop_index(
        "ix_economic_sensitivity_scenario", table_name="intelligence_economic_sensitivity_runs"
    )
    op.drop_index(
        "ix_economic_sensitivity_owner", table_name="intelligence_economic_sensitivity_runs"
    )
    op.drop_table("intelligence_economic_sensitivity_runs")
    op.drop_index(
        "ix_economic_scenario_result_fingerprint",
        table_name="intelligence_economic_scenario_results",
    )
    op.drop_index(
        "ix_economic_scenario_result_snapshot", table_name="intelligence_economic_scenario_results"
    )
    op.drop_index(
        "ix_economic_scenario_result_scenario_calc",
        table_name="intelligence_economic_scenario_results",
    )
    op.drop_index(
        "ix_economic_scenario_result_baseline", table_name="intelligence_economic_scenario_results"
    )
    op.drop_index(
        "ix_economic_scenario_result_scenario", table_name="intelligence_economic_scenario_results"
    )
    op.drop_index(
        "ix_economic_scenario_result_owner", table_name="intelligence_economic_scenario_results"
    )
    op.drop_table("intelligence_economic_scenario_results")
    op.drop_index("ix_economic_scenario_fingerprint", table_name="intelligence_economic_scenarios")
    op.drop_index("ix_economic_scenario_status", table_name="intelligence_economic_scenarios")
    op.drop_index("ix_economic_scenario_baseline", table_name="intelligence_economic_scenarios")
    op.drop_index("ix_economic_scenario_context", table_name="intelligence_economic_scenarios")
    op.drop_index("ix_economic_scenario_owner", table_name="intelligence_economic_scenarios")
    op.drop_table("intelligence_economic_scenarios")
