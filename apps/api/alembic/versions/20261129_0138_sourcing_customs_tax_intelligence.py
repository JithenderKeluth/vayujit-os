"""Add bounded customs, tax, and regulatory evidence for 13E."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261129_0138"
down_revision = "20261128_0137"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def _common(
    name: str, context_fk: str, extra: list[sa.Column[Any]], constraints: list[Any]
) -> None:
    op.create_table(
        name,
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id", UUID, sa.ForeignKey(context_fk, ondelete="CASCADE"), nullable=False
        ),
        *extra,
        *constraints,
    )


def upgrade() -> None:
    op.create_table(
        "intelligence_customs_tax_contexts",
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
        sa.Column("destination_country", sa.String(80)),
        sa.Column("reporting_currency", sa.String(3)),
        sa.Column("classification_code", sa.String(64)),
        sa.Column("classification_scheme", sa.String(64)),
        sa.Column("classification_version", sa.String(64)),
        sa.Column("classification_provenance", sa.String(24), nullable=False),
        sa.Column(
            "evidence_ref",
            UUID,
            sa.ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_customs_tax_context_idempotency"
        ),
        sa.CheckConstraint(
            "classification_provenance IN ('UNKNOWN','USER_PROVIDED','SOURCE_OBSERVED')",
            name="ck_customs_context_classification_provenance",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','CURRENT','ARCHIVED')", name="ck_customs_context_status"
        ),
    )
    op.create_index(
        "ix_customs_tax_context_owner", "intelligence_customs_tax_contexts", ["owner_id"]
    )
    op.create_index(
        "ix_customs_tax_context_economic",
        "intelligence_customs_tax_contexts",
        ["economic_context_id"],
    )
    _common(
        "intelligence_classification_evidence",
        "intelligence_customs_tax_contexts.id",
        [
            sa.Column("idempotency_key", sa.String(180), nullable=False),
            sa.Column("classification_code", sa.String(64), nullable=False),
            sa.Column("classification_scheme", sa.String(64), nullable=False),
            sa.Column("jurisdiction", sa.String(80), nullable=False),
            sa.Column("supplied_description", sa.Text),
            sa.Column("source", sa.String(120), nullable=False),
            sa.Column("provider", sa.String(120)),
            sa.Column("source_reference", sa.String(500)),
            sa.Column("provenance", sa.String(16), nullable=False),
            sa.Column("freshness", sa.String(16), nullable=False),
            sa.Column("effective_at", sa.DateTime(timezone=True)),
            sa.Column("valid_until", sa.DateTime(timezone=True)),
            sa.Column("notes", sa.Text, nullable=False),
            sa.Column(
                "metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
            ),
            sa.Column("fingerprint", sa.String(128), nullable=False),
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.UniqueConstraint(
                "owner_id", "idempotency_key", name="uq_classification_evidence_idempotency"
            ),
            sa.UniqueConstraint(
                "owner_id", "fingerprint", name="uq_classification_evidence_fingerprint"
            ),
            sa.CheckConstraint(
                "provenance IN ('OBSERVED','QUOTED','CONFIGURED',"
                "'USER_PROVIDED','ASSUMED','CALCULATED','UNKNOWN')",
                name="ck_classification_evidence_provenance",
            ),
            sa.CheckConstraint(
                "freshness IN ('CURRENT','STALE','UNKNOWN')",
                name="ck_classification_evidence_freshness",
            ),
        ],
    )
    op.create_index(
        "ix_classification_evidence_owner", "intelligence_classification_evidence", ["owner_id"]
    )
    op.create_index(
        "ix_classification_evidence_context", "intelligence_classification_evidence", ["context_id"]
    )
    _common(
        "intelligence_customs_rate_evidence",
        "intelligence_customs_tax_contexts.id",
        [
            sa.Column(
                "classification_evidence_id",
                UUID,
                sa.ForeignKey("intelligence_classification_evidence.id", ondelete="RESTRICT"),
            ),
            sa.Column("idempotency_key", sa.String(180), nullable=False),
            sa.Column("rate_kind", sa.String(24), nullable=False),
            sa.Column("category", sa.String(24), nullable=False),
            sa.Column("tax_type", sa.String(120)),
            sa.Column("rate", sa.Numeric(24, 12), nullable=False),
            sa.Column("rate_scale", sa.String(24), nullable=False),
            sa.Column("basis", sa.String(32), nullable=False),
            sa.Column("jurisdiction", sa.String(80), nullable=False),
            sa.Column("origin_country", sa.String(80)),
            sa.Column("destination_country", sa.String(80)),
            sa.Column("effective_at", sa.DateTime(timezone=True)),
            sa.Column("valid_until", sa.DateTime(timezone=True)),
            sa.Column("source", sa.String(120), nullable=False),
            sa.Column("provenance", sa.String(16), nullable=False),
            sa.Column("freshness", sa.String(16), nullable=False),
            sa.Column(
                "evidence_ref",
                UUID,
                sa.ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
            ),
            sa.Column("assumption_reason", sa.Text),
            sa.Column(
                "metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
            ),
            sa.Column("fingerprint", sa.String(128), nullable=False),
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.UniqueConstraint(
                "owner_id", "idempotency_key", name="uq_customs_rate_evidence_idempotency"
            ),
            sa.UniqueConstraint(
                "owner_id", "fingerprint", name="uq_customs_rate_evidence_fingerprint"
            ),
            sa.CheckConstraint(
                "rate_kind IN ('DUTY','IMPORT_TAX','SURCHARGE','CESS','LEVY')",
                name="ck_customs_rate_kind",
            ),
            sa.CheckConstraint(
                "category IN ('CUSTOMS_DUTY','IMPORT_TAX','OTHER')",
                name="ck_customs_rate_category",
            ),
            sa.CheckConstraint("rate >= 0 AND rate <= 1", name="ck_customs_rate_range"),
            sa.CheckConstraint("rate_scale = 'FRACTION_OF_ONE'", name="ck_customs_rate_scale"),
            sa.CheckConstraint(
                "basis IN ('PRODUCT_VALUE','PRODUCT_PLUS_FREIGHT',"
                "'EXPLICIT_CUSTOMS_VALUE','EXPLICIT_TAXABLE_VALUE','UNKNOWN')",
                name="ck_customs_rate_basis",
            ),
            sa.CheckConstraint(
                "provenance IN ('OBSERVED','QUOTED','CONFIGURED',"
                "'USER_PROVIDED','ASSUMED','CALCULATED','UNKNOWN')",
                name="ck_customs_rate_provenance",
            ),
            sa.CheckConstraint(
                "freshness IN ('CURRENT','STALE','UNKNOWN')",
                name="ck_customs_rate_freshness",
            ),
        ],
    )
    op.create_index("ix_customs_rate_owner", "intelligence_customs_rate_evidence", ["owner_id"])
    op.create_index("ix_customs_rate_context", "intelligence_customs_rate_evidence", ["context_id"])
    _common(
        "intelligence_regulatory_cost_evidence",
        "intelligence_customs_tax_contexts.id",
        [
            sa.Column("idempotency_key", sa.String(180), nullable=False),
            sa.Column("cost_category", sa.String(24), nullable=False),
            sa.Column("amount", sa.Numeric(24, 8)),
            sa.Column("currency", sa.String(3)),
            sa.Column("requirement_type", sa.String(32), nullable=False),
            sa.Column("requirement_state", sa.String(32), nullable=False),
            sa.Column("source", sa.String(120), nullable=False),
            sa.Column("provenance", sa.String(16), nullable=False),
            sa.Column("freshness", sa.String(16), nullable=False),
            sa.Column("effective_at", sa.DateTime(timezone=True)),
            sa.Column("valid_until", sa.DateTime(timezone=True)),
            sa.Column(
                "evidence_ref",
                UUID,
                sa.ForeignKey("intelligence_supplier_evidence.id", ondelete="RESTRICT"),
            ),
            sa.Column("assumption_reason", sa.Text),
            sa.Column(
                "metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
            ),
            sa.Column("fingerprint", sa.String(128), nullable=False),
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.UniqueConstraint(
                "owner_id", "idempotency_key", name="uq_regulatory_cost_idempotency"
            ),
            sa.UniqueConstraint("owner_id", "fingerprint", name="uq_regulatory_cost_fingerprint"),
            sa.CheckConstraint(
                "cost_category IN ('BROKERAGE','INSPECTION','OTHER')",
                name="ck_regulatory_cost_category",
            ),
            sa.CheckConstraint(
                "requirement_type IN ('BIS','FSSAI','WPC','CDSCO',"
                "'LEGAL_METROLOGY','OTHER','UNKNOWN')",
                name="ck_regulatory_requirement_type",
            ),
            sa.CheckConstraint(
                "requirement_state IN ('OBSERVED_REQUIREMENT','USER_CONFIGURED','UNKNOWN')",
                name="ck_regulatory_requirement_state",
            ),
            sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_regulatory_cost_amount"),
            sa.CheckConstraint(
                "amount IS NULL OR currency IS NOT NULL",
                name="ck_regulatory_cost_currency",
            ),
            sa.CheckConstraint(
                "provenance IN ('OBSERVED','QUOTED','CONFIGURED',"
                "'USER_PROVIDED','ASSUMED','CALCULATED','UNKNOWN')",
                name="ck_regulatory_cost_provenance",
            ),
            sa.CheckConstraint(
                "freshness IN ('CURRENT','STALE','UNKNOWN')",
                name="ck_regulatory_cost_freshness",
            ),
        ],
    )
    op.create_index(
        "ix_regulatory_cost_owner", "intelligence_regulatory_cost_evidence", ["owner_id"]
    )
    op.create_index(
        "ix_regulatory_cost_context", "intelligence_regulatory_cost_evidence", ["context_id"]
    )
    _common(
        "intelligence_customs_tax_snapshots",
        "intelligence_customs_tax_contexts.id",
        [
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("fingerprint", sa.String(128), nullable=False),
            sa.Column("completeness", sa.String(16), nullable=False),
            sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column(
                "missing_inputs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
            ),
            sa.Column("warnings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.UniqueConstraint(
                "owner_id", "fingerprint", name="uq_customs_tax_snapshot_fingerprint"
            ),
            sa.CheckConstraint(
                "completeness IN ('COMPLETE','PARTIAL','UNKNOWN')",
                name="ck_customs_tax_snapshot_completeness",
            ),
        ],
    )
    op.create_index(
        "ix_customs_tax_snapshot_owner", "intelligence_customs_tax_snapshots", ["owner_id"]
    )
    op.create_index(
        "ix_customs_tax_snapshot_context", "intelligence_customs_tax_snapshots", ["context_id"]
    )
    op.add_column(
        "intelligence_economic_calculations",
        sa.Column("customs_tax_snapshot_id", UUID, nullable=True),
    )
    op.create_foreign_key(
        "fk_economic_calculation_customs_tax_snapshot",
        "intelligence_economic_calculations",
        "intelligence_customs_tax_snapshots",
        ["customs_tax_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_economic_calculation_customs_tax_snapshot",
        "intelligence_economic_calculations",
        ["customs_tax_snapshot_id"],
    )
    op.add_column(
        "intelligence_economic_calculation_breakdowns",
        sa.Column("customs_tax_snapshot_id", UUID, nullable=True),
    )
    op.create_index(
        "ix_economic_breakdown_customs_tax_snapshot",
        "intelligence_economic_calculation_breakdowns",
        ["customs_tax_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_economic_breakdown_customs_tax_snapshot",
        table_name="intelligence_economic_calculation_breakdowns",
    )
    op.drop_column("intelligence_economic_calculation_breakdowns", "customs_tax_snapshot_id")
    op.drop_index(
        "ix_economic_calculation_customs_tax_snapshot",
        table_name="intelligence_economic_calculations",
    )
    op.drop_constraint(
        "fk_economic_calculation_customs_tax_snapshot",
        "intelligence_economic_calculations",
        type_="foreignkey",
    )
    op.drop_column("intelligence_economic_calculations", "customs_tax_snapshot_id")
    for index, table in [
        ("ix_customs_tax_snapshot_context", "intelligence_customs_tax_snapshots"),
        ("ix_customs_tax_snapshot_owner", "intelligence_customs_tax_snapshots"),
        ("ix_regulatory_cost_context", "intelligence_regulatory_cost_evidence"),
        ("ix_regulatory_cost_owner", "intelligence_regulatory_cost_evidence"),
        ("ix_customs_rate_context", "intelligence_customs_rate_evidence"),
        ("ix_customs_rate_owner", "intelligence_customs_rate_evidence"),
        ("ix_classification_evidence_context", "intelligence_classification_evidence"),
        ("ix_classification_evidence_owner", "intelligence_classification_evidence"),
        ("ix_customs_tax_context_economic", "intelligence_customs_tax_contexts"),
        ("ix_customs_tax_context_owner", "intelligence_customs_tax_contexts"),
    ]:
        op.drop_index(index, table_name=table)
    for table in [
        "intelligence_customs_tax_snapshots",
        "intelligence_regulatory_cost_evidence",
        "intelligence_customs_rate_evidence",
        "intelligence_classification_evidence",
        "intelligence_customs_tax_contexts",
    ]:
        op.drop_table(table)
