"""Add Review Intelligence 11B ingestion, normalization, and observations."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261114_0123"
down_revision = "20261113_0122"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_review_ingestion_batches",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", UUID, sa.ForeignKey("intelligence_review_sources.id", ondelete="SET NULL")
        ),
        sa.Column("provider", sa.String(120), nullable=False, server_default="LOCAL_FIXTURE"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="LOCAL_FIXTURE"),
        sa.Column("status", sa.String(24), nullable=False, server_default="REQUESTED"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("input_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_observation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "adapter_version", sa.String(40), nullable=False, server_default="review-adapter-v1"
        ),
        sa.Column(
            "normalization_version",
            sa.String(40),
            nullable=False,
            server_default="review-normalization-v1",
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "idempotency_key",
            name="uq_review_ingestion_batch_idempotency",
        ),
        sa.CheckConstraint(
            "mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')",
            name="ck_review_ingestion_batch_mode",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED','RUNNING','COMPLETED','PARTIAL','FAILED')",
            name="ck_review_ingestion_batch_status",
        ),
    )
    op.create_index(
        "ix_review_ingestion_batch_context_created",
        "intelligence_review_ingestion_batches",
        ["owner_id", "context_id", "created_at"],
    )
    op.add_column(
        "intelligence_review_records",
        sa.Column(
            "ingestion_batch_id",
            UUID,
            sa.ForeignKey("intelligence_review_ingestion_batches.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_review_record_ingestion_batch",
        "intelligence_review_records",
        ["ingestion_batch_id"],
    )
    op.create_table(
        "intelligence_review_ingestion_candidates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "batch_id",
            UUID,
            sa.ForeignKey("intelligence_review_ingestion_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", UUID, sa.ForeignKey("intelligence_review_sources.id", ondelete="SET NULL")
        ),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("provider_review_id", sa.String(240)),
        sa.Column("fingerprint", sa.String(128)),
        sa.Column(
            "duplicate_classification", sa.String(32), nullable=False, server_default="DISTINCT"
        ),
        sa.Column("quality_state", sa.String(16), nullable=False, server_default="INVALID"),
        sa.Column("accepted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("rejection_reason", sa.String(80)),
        sa.Column("raw_payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("normalized_payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "review_record_id",
            UUID,
            sa.ForeignKey("intelligence_review_records.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "ordinal", name="uq_review_ingestion_candidate_ordinal"),
    )
    op.create_index(
        "ix_review_ingestion_candidate_batch_status",
        "intelligence_review_ingestion_candidates",
        ["owner_id", "batch_id", "accepted"],
    )
    op.create_index(
        "ix_review_ingestion_candidate_duplicate",
        "intelligence_review_ingestion_candidates",
        ["owner_id", "batch_id", "duplicate_classification"],
    )
    op.create_table(
        "intelligence_review_observations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "review_record_id",
            UUID,
            sa.ForeignKey("intelligence_review_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            UUID,
            sa.ForeignKey("intelligence_review_ingestion_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", UUID, sa.ForeignKey("intelligence_review_sources.id", ondelete="SET NULL")
        ),
        sa.Column("provider", sa.String(120), nullable=False, server_default="LOCAL_FIXTURE"),
        sa.Column("provider_review_id", sa.String(240)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "normalization_version",
            sa.String(40),
            nullable=False,
            server_default="review-normalization-v1",
        ),
        sa.Column("raw_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "review_record_id",
            "source_fingerprint",
            name="uq_review_observation_source_state",
        ),
    )
    op.create_index(
        "ix_review_observation_record_observed",
        "intelligence_review_observations",
        ["owner_id", "review_record_id", "observed_at"],
    )
    op.create_index(
        "ix_review_observation_batch",
        "intelligence_review_observations",
        ["owner_id", "batch_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_review_observations")
    op.drop_table("intelligence_review_ingestion_candidates")
    op.drop_index("ix_review_record_ingestion_batch", table_name="intelligence_review_records")
    op.drop_column("intelligence_review_records", "ingestion_batch_id")
    op.drop_table("intelligence_review_ingestion_batches")
