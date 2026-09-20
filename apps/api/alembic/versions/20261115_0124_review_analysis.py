"""Add Review Intelligence 11C deterministic analysis tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261115_0124"
down_revision = "20261114_0123"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_review_analyses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("snapshot_version", sa.Integer, nullable=False),
        sa.Column(
            "analysis_version", sa.String(40), nullable=False, server_default="review-analysis-v1"
        ),
        sa.Column(
            "calculation_version",
            sa.String(40),
            nullable=False,
            server_default="review-calculation-v1",
        ),
        sa.Column(
            "normalization_version",
            sa.String(40),
            nullable=False,
            server_default="review-normalization-v1",
        ),
        sa.Column(
            "taxonomy_version", sa.String(40), nullable=False, server_default="review-taxonomy-v1"
        ),
        sa.Column(
            "semantic_method_version",
            sa.String(60),
            nullable=False,
            server_default="local-rules-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False, server_default="LOCAL_FIXTURE"),
        sa.Column("status", sa.String(24), nullable=False, server_default="COMPLETED"),
        sa.Column("total_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("included_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("excluded_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cohort_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "rating_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "sentiment_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "source_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("evidence_gaps", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_analysis_input"
        ),
        sa.CheckConstraint(
            "mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')", name="ck_review_analysis_mode"
        ),
        sa.CheckConstraint("status IN ('COMPLETED','FAILED')", name="ck_review_analysis_status"),
    )
    op.create_index(
        "ix_review_analysis_context_created",
        "intelligence_review_analyses",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_review_analysis_input_fingerprint",
        "intelligence_review_analyses",
        ["input_fingerprint"],
    )
    op.create_index("ix_review_analysis_owner", "intelligence_review_analyses", ["owner_id"])
    op.create_index("ix_review_analysis_context", "intelligence_review_analyses", ["context_id"])

    op.create_table(
        "intelligence_review_analysis_annotations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_language", sa.String(24), nullable=False, server_default=""),
        sa.Column("analysis_language", sa.String(24), nullable=False, server_default=""),
        sa.Column(
            "translation_lineage",
            JSONB,
            nullable=False,
            server_default=sa.text("\x27{}\x27::jsonb"),
        ),
        sa.Column(
            "review_record_id",
            UUID,
            sa.ForeignKey("intelligence_review_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sentiment", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "aspect_sentiments", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("topics", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quality_state", sa.String(16), nullable=False, server_default="PARTIAL"),
        sa.Column(
            "classification_type", sa.String(24), nullable=False, server_default="DERIVED_SEMANTIC"
        ),
        sa.Column("method_version", sa.String(60), nullable=False, server_default="local-rules-v1"),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("limitation", sa.String(240)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "analysis_id", "review_record_id", name="uq_review_analysis_annotation"
        ),
    )
    op.create_index(
        "ix_review_analysis_annotation_review",
        "intelligence_review_analysis_annotations",
        ["owner_id", "review_record_id"],
    )
    op.create_index(
        "ix_review_analysis_annotation_analysis",
        "intelligence_review_analysis_annotations",
        ["analysis_id"],
    )

    op.create_table(
        "intelligence_review_analysis_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("canonical_label", sa.String(120), nullable=False),
        sa.Column("raw_labels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sentiment", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "sentiment_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("severity", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("support_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cohort_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("coverage", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "source_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "supporting_review_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "supporting_evidence_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("freshness", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("evidence_state", sa.String(24), nullable=False, server_default="PARTIAL"),
        sa.Column(
            "classification_type", sa.String(24), nullable=False, server_default="DERIVED_SEMANTIC"
        ),
        sa.Column("method_version", sa.String(60), nullable=False, server_default="local-rules-v1"),
        sa.Column("limitation", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "analysis_id", "item_type", "canonical_label", name="uq_review_analysis_item"
        ),
    )
    op.create_index(
        "ix_review_analysis_item_analysis_type",
        "intelligence_review_analysis_items",
        ["owner_id", "analysis_id", "item_type"],
    )
    op.create_index(
        "ix_review_analysis_item_analysis", "intelligence_review_analysis_items", ["analysis_id"]
    )


def downgrade() -> None:
    op.drop_table("intelligence_review_analysis_items")
    op.drop_table("intelligence_review_analysis_annotations")
    op.drop_table("intelligence_review_analyses")
