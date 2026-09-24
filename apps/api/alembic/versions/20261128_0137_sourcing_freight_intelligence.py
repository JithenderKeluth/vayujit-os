"""Add bounded logistics and freight evidence for 13D."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261128_0137"
down_revision = "20261127_0136"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_logistics_contexts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "economic_context_id",
            UUID,
            sa.ForeignKey("intelligence_economic_contexts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("origin_country", sa.String(80)),
        sa.Column("origin_location", sa.String(160)),
        sa.Column("destination_country", sa.String(80)),
        sa.Column("destination_location", sa.String(160)),
        sa.Column("transport_mode", sa.String(16), nullable=False),
        sa.Column("sea_freight_type", sa.String(16), nullable=False),
        sa.Column("container_type", sa.String(80)),
        sa.Column("target_quantity", sa.Numeric(24, 8)),
        sa.Column("quantity_unit", sa.String(40)),
        sa.Column("total_weight", sa.Numeric(24, 8)),
        sa.Column("weight_unit", sa.String(8)),
        sa.Column("total_volume", sa.Numeric(24, 8)),
        sa.Column("volume_unit", sa.String(8)),
        sa.Column("package_count", sa.Integer),
        sa.Column("container_count", sa.Integer),
        sa.Column("incoterm", sa.String(8)),
        sa.Column("requested_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_logistics_context_idempotency"),
        sa.CheckConstraint(
            "transport_mode IN ("
            "'AIR','SEA','ROAD','RAIL','COURIER','MULTIMODAL','OTHER','UNKNOWN')",
            name="ck_logistics_context_transport_mode",
        ),
        sa.CheckConstraint(
            "sea_freight_type IN ('LCL','FCL','UNKNOWN')", name="ck_logistics_context_sea_type"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','CURRENT','ARCHIVED')", name="ck_logistics_context_status"
        ),
        sa.CheckConstraint(
            "target_quantity IS NULL OR target_quantity > 0", name="ck_logistics_context_quantity"
        ),
        sa.CheckConstraint(
            "total_weight IS NULL OR total_weight >= 0", name="ck_logistics_context_weight"
        ),
        sa.CheckConstraint(
            "total_volume IS NULL OR total_volume >= 0", name="ck_logistics_context_volume"
        ),
        sa.CheckConstraint(
            "package_count IS NULL OR package_count > 0", name="ck_logistics_context_package_count"
        ),
        sa.CheckConstraint(
            "container_count IS NULL OR container_count > 0",
            name="ck_logistics_context_container_count",
        ),
    )
    op.create_index("ix_logistics_context_owner", "intelligence_logistics_contexts", ["owner_id"])
    op.create_index(
        "ix_logistics_context_economic", "intelligence_logistics_contexts", ["economic_context_id"]
    )
    op.create_index("ix_logistics_context_status", "intelligence_logistics_contexts", ["status"])

    common_observation: list[sa.Column[Any]] = [
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "logistics_context_id",
            UUID,
            sa.ForeignKey("intelligence_logistics_contexts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8)),
        sa.Column("currency", sa.String(3)),
        sa.Column("basis", sa.String(24), nullable=False),
        sa.Column("transport_mode", sa.String(16), nullable=False),
        sa.Column("origin_country", sa.String(80)),
        sa.Column("origin_location", sa.String(160)),
        sa.Column("destination_country", sa.String(80)),
        sa.Column("destination_location", sa.String(160)),
        sa.Column("quoted_quantity", sa.Numeric(24, 8)),
        sa.Column("quoted_quantity_unit", sa.String(40)),
        sa.Column("quoted_weight", sa.Numeric(24, 8)),
        sa.Column("quoted_weight_unit", sa.String(8)),
        sa.Column("quoted_volume", sa.Numeric(24, 8)),
        sa.Column("quoted_volume_unit", sa.String(8)),
        sa.Column("quoted_package_count", sa.Integer),
        sa.Column("quoted_container_count", sa.Integer),
        sa.Column("incoterm", sa.String(8)),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("evidence_ref", UUID),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]
    op.create_table(
        "intelligence_freight_observations",
        *common_observation,
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_freight_observation_idempotency"
        ),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_freight_observation_fingerprint"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_freight_observation_amount"),
        sa.CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_freight_observation_currency"
        ),
        sa.CheckConstraint(
            "basis IN ("
            "'PER_SHIPMENT','PER_KG','PER_CBM','PER_CARTON','PER_CONTAINER','FIXED_QUOTE','UNKNOWN')",
            name="ck_freight_observation_basis",
        ),
        sa.CheckConstraint(
            "transport_mode IN ("
            "'AIR','SEA','ROAD','RAIL','COURIER','MULTIMODAL','OTHER','UNKNOWN')",
            name="ck_freight_observation_transport_mode",
        ),
        sa.CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_freight_observation_provenance",
        ),
        sa.CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_freight_observation_freshness"
        ),
        sa.CheckConstraint(
            "mode IN ('LOCAL_FIXTURE','MANUAL')", name="ck_freight_observation_mode"
        ),
    )
    op.create_index(
        "ix_freight_observation_owner", "intelligence_freight_observations", ["owner_id"]
    )
    op.create_index(
        "ix_freight_observation_context",
        "intelligence_freight_observations",
        ["logistics_context_id"],
    )
    op.create_index(
        "ix_freight_observation_fingerprint", "intelligence_freight_observations", ["fingerprint"]
    )

    snapshot_columns: list[sa.Column[Any]] = [
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "logistics_context_id",
            UUID,
            sa.ForeignKey("intelligence_logistics_contexts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            UUID,
            sa.ForeignKey("intelligence_freight_observations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(24, 8)),
        sa.Column("currency", sa.String(3)),
        sa.Column("basis", sa.String(24), nullable=False),
        sa.Column("transport_mode", sa.String(16), nullable=False),
        sa.Column("origin_country", sa.String(80)),
        sa.Column("origin_location", sa.String(160)),
        sa.Column("destination_country", sa.String(80)),
        sa.Column("destination_location", sa.String(160)),
        sa.Column("quoted_quantity", sa.Numeric(24, 8)),
        sa.Column("quoted_quantity_unit", sa.String(40)),
        sa.Column("quoted_weight", sa.Numeric(24, 8)),
        sa.Column("quoted_weight_unit", sa.String(8)),
        sa.Column("quoted_volume", sa.Numeric(24, 8)),
        sa.Column("quoted_volume_unit", sa.String(8)),
        sa.Column("quoted_package_count", sa.Integer),
        sa.Column("quoted_container_count", sa.Integer),
        sa.Column("incoterm", sa.String(8)),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("evidence_ref", UUID),
        sa.Column("assumption_reason", sa.Text),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_mode", sa.String(24), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]
    op.create_table(
        "intelligence_freight_snapshots",
        *snapshot_columns,
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_freight_snapshot_fingerprint"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_freight_snapshot_amount"),
        sa.CheckConstraint(
            "amount IS NULL OR currency IS NOT NULL", name="ck_freight_snapshot_currency"
        ),
        sa.CheckConstraint(
            "basis IN ("
            "'PER_SHIPMENT','PER_KG','PER_CBM','PER_CARTON','PER_CONTAINER','FIXED_QUOTE','UNKNOWN')",
            name="ck_freight_snapshot_basis",
        ),
        sa.CheckConstraint(
            "transport_mode IN ("
            "'AIR','SEA','ROAD','RAIL','COURIER','MULTIMODAL','OTHER','UNKNOWN')",
            name="ck_freight_snapshot_transport_mode",
        ),
        sa.CheckConstraint(
            "provenance IN ('OBSERVED','QUOTED','CONFIGURED','ASSUMED','CALCULATED','UNKNOWN')",
            name="ck_freight_snapshot_provenance",
        ),
        sa.CheckConstraint(
            "freshness IN ('CURRENT','STALE','UNKNOWN')", name="ck_freight_snapshot_freshness"
        ),
    )
    op.create_index("ix_freight_snapshot_owner", "intelligence_freight_snapshots", ["owner_id"])
    op.create_index(
        "ix_freight_snapshot_context", "intelligence_freight_snapshots", ["logistics_context_id"]
    )
    op.create_index(
        "ix_freight_snapshot_observation", "intelligence_freight_snapshots", ["observation_id"]
    )
    op.create_index(
        "ix_freight_snapshot_fingerprint", "intelligence_freight_snapshots", ["fingerprint"]
    )

    op.add_column(
        "intelligence_economic_calculations", sa.Column("freight_snapshot_id", UUID, nullable=True)
    )
    op.create_foreign_key(
        "fk_economic_calculation_freight_snapshot",
        "intelligence_economic_calculations",
        "intelligence_freight_snapshots",
        ["freight_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_economic_calculations_freight_snapshot_id",
        "intelligence_economic_calculations",
        ["freight_snapshot_id"],
    )
    op.add_column(
        "intelligence_economic_calculation_breakdowns",
        sa.Column("freight_snapshot_id", UUID, nullable=True),
    )
    op.create_foreign_key(
        "fk_economic_breakdown_freight_snapshot",
        "intelligence_economic_calculation_breakdowns",
        "intelligence_freight_snapshots",
        ["freight_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_economic_breakdown_freight_snapshot_id",
        "intelligence_economic_calculation_breakdowns",
        ["freight_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_economic_breakdown_freight_snapshot_id",
        table_name="intelligence_economic_calculation_breakdowns",
    )
    op.drop_constraint(
        "fk_economic_breakdown_freight_snapshot",
        "intelligence_economic_calculation_breakdowns",
        type_="foreignkey",
    )
    op.drop_column("intelligence_economic_calculation_breakdowns", "freight_snapshot_id")
    op.drop_index(
        "ix_economic_calculations_freight_snapshot_id",
        table_name="intelligence_economic_calculations",
    )
    op.drop_constraint(
        "fk_economic_calculation_freight_snapshot",
        "intelligence_economic_calculations",
        type_="foreignkey",
    )
    op.drop_column("intelligence_economic_calculations", "freight_snapshot_id")
    op.drop_table("intelligence_freight_snapshots")
    op.drop_table("intelligence_freight_observations")
    op.drop_table("intelligence_logistics_contexts")
