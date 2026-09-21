"""Add provider-independent Trend Intelligence 12A foundation."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261119_0128"
down_revision = "20261118_0127"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def _json(name: str) -> sa.Column:
    return sa.Column(name, JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))


def upgrade() -> None:
    op.create_table("intelligence_trend_signal_definitions",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("signal_type", sa.String(80), nullable=False), sa.Column("measurement_type", sa.String(24), nullable=False),
        sa.Column("unit", sa.String(40)), sa.Column("scale", sa.Numeric(30, 10)), sa.Column("aggregation_semantics", sa.String(80), nullable=False, server_default="source_reported"),
        sa.Column("compatible_source_types", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("version", sa.String(40), nullable=False, server_default="v1"), sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "signal_type", "version", name="uq_trend_signal_definition"),
        sa.CheckConstraint("measurement_type IN ('COUNT','DECIMAL','INDEX','PERCENTAGE','BOOLEAN','ORDINAL','CATEGORY')", name="ck_trend_signal_measurement_type"))
    op.create_table("intelligence_trend_contexts",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")), sa.Column("product_opportunity_id", UUID, sa.ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL")), sa.Column("brand_id", UUID, sa.ForeignKey("brands.id", ondelete="SET NULL")),
        sa.Column("subject_type", sa.String(32), nullable=False), sa.Column("subject_key", sa.String(240), nullable=False, server_default=""), sa.Column("name", sa.String(180), nullable=False, server_default="Trend context"),
        sa.Column("marketplace", sa.String(120)), sa.Column("market", sa.String(120)), sa.Column("country", sa.String(80)), sa.Column("region", sa.String(120)), sa.Column("language", sa.String(40)), sa.Column("currency", sa.String(3)),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"), sa.Column("version", sa.Integer, nullable=False, server_default="1"), sa.Column("idempotency_key", sa.String(180), nullable=False), sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_trend_context_owner_idempotency"),
        sa.CheckConstraint("subject_type IN ('PRODUCT','PRODUCT_OPPORTUNITY','BRAND','CATEGORY','KEYWORD','SEARCH_TERM','COMPETITOR_SET','MARKET_SEGMENT','CUSTOM')", name="ck_trend_context_subject_type"),
        sa.CheckConstraint("status IN ('DRAFT','ACTIVE','ARCHIVED')", name="ck_trend_context_status"))
    op.create_table("intelligence_trend_foundation_observations",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("context_id", UUID, sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"), nullable=False), sa.Column("source_id", UUID, sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), nullable=False), sa.Column("evidence_id", UUID, sa.ForeignKey("intelligence_evidence.id", ondelete="SET NULL")), sa.Column("signal_definition_id", UUID, sa.ForeignKey("intelligence_trend_signal_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_observation_id", sa.String(240)), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False), sa.Column("period_start", sa.DateTime(timezone=True)), sa.Column("period_end", sa.DateTime(timezone=True)), sa.Column("granularity", sa.String(24), nullable=False, server_default="POINT_IN_TIME"), sa.Column("measurement_type", sa.String(24), nullable=False), sa.Column("value_numeric", sa.Numeric(30, 10)), sa.Column("value_text", sa.String(2000)), sa.Column("value_boolean", sa.Boolean), sa.Column("unit", sa.String(40)), sa.Column("scale", sa.Numeric(30, 10)), sa.Column("geography_scope", sa.String(24), nullable=False, server_default="UNKNOWN"), sa.Column("country", sa.String(80)), sa.Column("region", sa.String(120)), sa.Column("city", sa.String(120)), sa.Column("marketplace", sa.String(120)), sa.Column("source_reference", sa.String(500), nullable=False, server_default=""), sa.Column("evidence_kind", sa.String(28), nullable=False, server_default="OBSERVED"), sa.Column("verification_state", sa.String(16), nullable=False, server_default="UNKNOWN"), sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"), sa.Column("quality_state", sa.String(16), nullable=False, server_default="COMPLETE"), _json("raw_metadata"), _json("canonical_metadata"), sa.Column("provenance_note", sa.Text, nullable=False, server_default=""), sa.Column("fingerprint", sa.String(128), nullable=False), sa.Column("fingerprint_version", sa.String(40), nullable=False, server_default="trend-observation-v1"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "context_id", "source_id", "provider_observation_id", name="uq_trend_observation_provider_identity"), sa.UniqueConstraint("owner_id", "context_id", "fingerprint", name="uq_trend_observation_fingerprint"), sa.CheckConstraint("period_end IS NULL OR period_start IS NULL OR period_end >= period_start", name="ck_trend_observation_period_order"))
    op.create_table("intelligence_trend_snapshots",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("context_id", UUID, sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"), nullable=False), sa.Column("previous_snapshot_id", UUID, sa.ForeignKey("intelligence_trend_snapshots.id", ondelete="SET NULL")), sa.Column("snapshot_version", sa.Integer, nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False), sa.Column("observation_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")), _json("source_inventory"), _json("signal_inventory"), _json("geographic_inventory"), _json("granularity_inventory"), _json("evidence_summary"), _json("freshness_summary"), sa.Column("observation_count", sa.Integer, nullable=False, server_default="0"), sa.Column("input_fingerprint", sa.String(128), nullable=False), sa.Column("calculation_version", sa.String(80), nullable=False, server_default="trend-snapshot-v1"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("owner_id", "context_id", "input_fingerprint", name="uq_trend_snapshot_fingerprint"), sa.UniqueConstraint("owner_id", "context_id", "snapshot_version", name="uq_trend_snapshot_version"))
    for name, table, cols in (("ix_trend_context_owner_status_created", "intelligence_trend_contexts", ["owner_id", "status", "created_at"]), ("ix_trend_observation_context_observed", "intelligence_trend_foundation_observations", ["owner_id", "context_id", "observed_at"]), ("ix_trend_observation_period", "intelligence_trend_foundation_observations", ["period_start", "period_end"]), ("ix_trend_snapshot_context_version", "intelligence_trend_snapshots", ["owner_id", "context_id", "snapshot_version"])):
        op.create_index(name, table, cols)


def downgrade() -> None:
    op.drop_table("intelligence_trend_snapshots")
    op.drop_table("intelligence_trend_foundation_observations")
    op.drop_table("intelligence_trend_contexts")
    op.drop_table("intelligence_trend_signal_definitions")
