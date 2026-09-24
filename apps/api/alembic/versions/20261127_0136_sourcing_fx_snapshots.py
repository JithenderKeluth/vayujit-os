"""Add owner-scoped FX observations and immutable rate snapshots for 13C."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261127_0136"
down_revision = "20261126_0135"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_fx_observations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(30, 16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("provenance", sa.String(24), nullable=False),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("evidence_ref", UUID),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_fx_observation_idempotency"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_fx_observation_fingerprint"),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_fx_observation_base"),
        sa.CheckConstraint("quote_currency ~ '^[A-Z]{3}$'", name="ck_fx_observation_quote"),
        sa.CheckConstraint("base_currency <> quote_currency", name="ck_fx_observation_pair"),
        sa.CheckConstraint("rate > 0", name="ck_fx_observation_rate"),
        sa.CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','LOCAL_FIXTURE')",
            name="ck_fx_observation_provenance",
        ),
        sa.CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')",
            name="ck_fx_observation_freshness",
        ),
        sa.CheckConstraint("mode IN ('LOCAL_FIXTURE','MANUAL')", name="ck_fx_observation_mode"),
    )
    op.create_index("ix_fx_observation_owner", "intelligence_fx_observations", ["owner_id"])
    op.create_index(
        "ix_fx_observation_fingerprint", "intelligence_fx_observations", ["fingerprint"]
    )

    op.create_table(
        "intelligence_fx_rate_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "observation_id",
            UUID,
            sa.ForeignKey("intelligence_fx_observations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(30, 16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("provenance", sa.String(24), nullable=False),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("evidence_ref", UUID),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("source_mode", sa.String(24), nullable=False),
        sa.Column("original_base_currency", sa.String(3), nullable=False),
        sa.Column("original_quote_currency", sa.String(3), nullable=False),
        sa.Column("original_rate", sa.Numeric(30, 16), nullable=False),
        sa.Column("inverted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_fx_snapshot_fingerprint"),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_fx_snapshot_base"),
        sa.CheckConstraint("quote_currency ~ '^[A-Z]{3}$'", name="ck_fx_snapshot_quote"),
        sa.CheckConstraint("base_currency <> quote_currency", name="ck_fx_snapshot_pair"),
        sa.CheckConstraint("rate > 0", name="ck_fx_snapshot_rate"),
        sa.CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','LOCAL_FIXTURE')",
            name="ck_fx_snapshot_provenance",
        ),
        sa.CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')",
            name="ck_fx_snapshot_freshness",
        ),
    )
    op.create_index("ix_fx_snapshot_owner", "intelligence_fx_rate_snapshots", ["owner_id"])
    op.create_index(
        "ix_fx_snapshot_observation", "intelligence_fx_rate_snapshots", ["observation_id"]
    )
    op.create_index("ix_fx_snapshot_fingerprint", "intelligence_fx_rate_snapshots", ["fingerprint"])
    op.add_column(
        "intelligence_economic_calculations", sa.Column("fx_snapshot_id", UUID, nullable=True)
    )
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column("reporting_currency", sa.String(3), nullable=True),
    )
    op.create_foreign_key(
        "fk_economic_calculation_fx_snapshot",
        "intelligence_economic_calculations",
        "intelligence_fx_rate_snapshots",
        ["fx_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_economic_calculations_fx_snapshot_id",
        "intelligence_economic_calculations",
        ["fx_snapshot_id"],
    )
    for _name, column, type_ in (
        ("converted_amount", "converted_amount", sa.Numeric(24, 8)),
        ("fx_snapshot_id", "fx_snapshot_id", UUID),
        ("fx_pair", "fx_pair", sa.String(7)),
        ("fx_rate", "fx_rate", sa.Numeric(30, 16)),
        ("fx_effective_at", "fx_effective_at", sa.DateTime(timezone=True)),
        ("fx_provider", "fx_provider", sa.String(120)),
        ("fx_freshness", "fx_freshness", sa.String(16)),
        ("fx_inverted", "fx_inverted", sa.Boolean),
    ):
        op.add_column(
            "intelligence_economic_calculation_breakdowns", sa.Column(column, type_, nullable=True)
        )
    op.create_index(
        "ix_economic_breakdown_fx_snapshot_id",
        "intelligence_economic_calculation_breakdowns",
        ["fx_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_economic_breakdown_fx_snapshot_id",
        table_name="intelligence_economic_calculation_breakdowns",
    )
    for column in (
        "fx_inverted",
        "fx_freshness",
        "fx_provider",
        "fx_effective_at",
        "fx_rate",
        "fx_pair",
        "fx_snapshot_id",
        "converted_amount",
    ):
        op.drop_column("intelligence_economic_calculation_breakdowns", column)
    op.drop_index(
        "ix_economic_calculations_fx_snapshot_id", table_name="intelligence_economic_calculations"
    )
    op.drop_constraint(
        "fk_economic_calculation_fx_snapshot",
        "intelligence_economic_calculations",
        type_="foreignkey",
    )
    op.drop_column("intelligence_economic_calculations", "reporting_currency")
    op.drop_column("intelligence_economic_calculations", "fx_snapshot_id")
    op.drop_table("intelligence_fx_rate_snapshots")
    op.drop_table("intelligence_fx_observations")
