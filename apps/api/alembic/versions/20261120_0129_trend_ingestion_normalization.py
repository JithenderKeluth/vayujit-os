"""Add Trend 12B ingestion batches, candidates, and correction history."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261120_0129"
down_revision = "20261119_0128"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table("intelligence_trend_ingestion_batches",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("context_id", UUID, sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"), nullable=False), sa.Column("source_id", UUID, sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), nullable=False), sa.Column("provider", sa.String(120), nullable=False, server_default="LOCAL_FIXTURE"), sa.Column("mode", sa.String(32), nullable=False, server_default="LOCAL_FIXTURE"), sa.Column("status", sa.String(24), nullable=False, server_default="REQUESTED"), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("requested_count", sa.Integer, nullable=False, server_default="0"), sa.Column("received_count", sa.Integer, nullable=False, server_default="0"), sa.Column("accepted_count", sa.Integer, nullable=False, server_default="0"), sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"), sa.Column("duplicate_count", sa.Integer, nullable=False, server_default="0"), sa.Column("updated_observation_count", sa.Integer, nullable=False, server_default="0"), sa.Column("input_fingerprint", sa.String(128), nullable=False), sa.Column("adapter_version", sa.String(40), nullable=False, server_default="trend-adapter-v1"), sa.Column("normalization_version", sa.String(40), nullable=False, server_default="trend-normalization-v1"), sa.Column("idempotency_key", sa.String(180), nullable=False), sa.Column("summary_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("error_code", sa.String(80)), sa.Column("error_message", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("owner_id", "context_id", "idempotency_key", name="uq_trend_ingestion_batch_idempotency"), sa.CheckConstraint("mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')", name="ck_trend_ingestion_batch_mode"), sa.CheckConstraint("status IN ('REQUESTED','RUNNING','COMPLETED','PARTIAL','FAILED')", name="ck_trend_ingestion_batch_status"))
    op.create_table("intelligence_trend_ingestion_candidates",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("batch_id", UUID, sa.ForeignKey("intelligence_trend_ingestion_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("context_id", UUID, sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"), nullable=False), sa.Column("source_id", UUID, sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), nullable=False), sa.Column("ordinal", sa.Integer, nullable=False), sa.Column("provider_observation_id", sa.String(240)), sa.Column("signal_key", sa.String(80), nullable=False, server_default=""), sa.Column("fingerprint", sa.String(128)), sa.Column("duplicate_classification", sa.String(32), nullable=False, server_default="DISTINCT"), sa.Column("quality_state", sa.String(16), nullable=False, server_default="INVALID"), sa.Column("accepted", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("rejection_code", sa.String(80)), sa.Column("raw_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("normalized_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("observation_id", UUID, sa.ForeignKey("intelligence_trend_foundation_observations.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("batch_id", "ordinal", name="uq_trend_ingestion_candidate_ordinal"))
    op.create_table("intelligence_trend_observation_revisions",
        sa.Column("id", UUID, primary_key=True), sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("observation_id", UUID, sa.ForeignKey("intelligence_trend_foundation_observations.id", ondelete="CASCADE"), nullable=False), sa.Column("batch_id", UUID, sa.ForeignKey("intelligence_trend_ingestion_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("provider_observation_id", sa.String(240), nullable=False), sa.Column("old_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("new_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_trend_ingestion_candidate_batch_status", "intelligence_trend_ingestion_candidates", ["owner_id", "batch_id", "accepted"])
    op.create_index("ix_trend_ingestion_candidate_rejection", "intelligence_trend_ingestion_candidates", ["owner_id", "batch_id", "rejection_code"])
    op.create_index("ix_trend_ingestion_batch_owner_context_created", "intelligence_trend_ingestion_batches", ["owner_id", "context_id", "created_at"])
    op.create_index("ix_trend_observation_revision_identity_time", "intelligence_trend_observation_revisions", ["owner_id", "provider_observation_id", "changed_at"])


def downgrade() -> None:
    op.drop_table("intelligence_trend_observation_revisions")
    op.drop_table("intelligence_trend_ingestion_candidates")
    op.drop_table("intelligence_trend_ingestion_batches")
