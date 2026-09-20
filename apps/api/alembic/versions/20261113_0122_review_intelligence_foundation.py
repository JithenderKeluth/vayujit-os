"""Create Review Intelligence 11A foundation tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261113_0122"
down_revision = "20261112_0121"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_review_contexts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column(
            "product_opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("brand_id", UUID, sa.ForeignKey("brands.id", ondelete="SET NULL")),
        sa.Column(
            "competitor_context_id",
            UUID,
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="SET NULL"),
        ),
        sa.Column("name", sa.String(180), nullable=False, server_default="Review context"),
        sa.Column("marketplace", sa.String(120), nullable=False, server_default=""),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("locale", sa.String(40)),
        sa.Column("language", sa.String(40)),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("input_fingerprint", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_review_context_owner_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','STALE','ARCHIVED')", name="ck_review_context_status"
        ),
    )
    op.create_index("ix_review_context_owner", "intelligence_review_contexts", ["owner_id"])
    op.create_index("ix_review_context_status", "intelligence_review_contexts", ["status"])
    op.create_index(
        "ix_review_context_links",
        "intelligence_review_contexts",
        ["owner_id", "product_id", "product_opportunity_id"],
    )
    op.create_table(
        "intelligence_review_sources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "intelligence_source_id",
            UUID,
            sa.ForeignKey("intelligence_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("provider", sa.String(120), nullable=False, server_default="manual"),
        sa.Column("source_key", sa.String(240), nullable=False),
        sa.Column("marketplace", sa.String(120)),
        sa.Column("external_product_identifier", sa.String(240)),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "verification_status", sa.String(24), nullable=False, server_default="UNVERIFIED"
        ),
        sa.Column("freshness_status", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "source_key", name="uq_review_source_context_key"
        ),
    )
    op.create_index("ix_review_source_owner", "intelligence_review_sources", ["owner_id"])
    op.create_index(
        "ix_review_source_context_observed",
        "intelligence_review_sources",
        ["owner_id", "context_id", "observed_at"],
    )
    op.create_table(
        "intelligence_review_records",
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
        sa.Column(
            "evidence_id", UUID, sa.ForeignKey("intelligence_evidence.id", ondelete="SET NULL")
        ),
        sa.Column("provider", sa.String(120), nullable=False, server_default="manual"),
        sa.Column("provider_review_id", sa.String(240)),
        sa.Column("external_product_id", sa.String(240)),
        sa.Column("rating", sa.Numeric(12, 4)),
        sa.Column("rating_scale", sa.Numeric(12, 4)),
        sa.Column("title", sa.String(1000)),
        sa.Column("body", sa.Text),
        sa.Column("reviewer_display_id", sa.String(240)),
        sa.Column("verified_purchase", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("review_date", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("language", sa.String(40)),
        sa.Column("locale", sa.String(40)),
        sa.Column("helpful_count", sa.Integer),
        sa.Column("variant_info", JSONB, nullable=False, server_default="{}"),
        sa.Column("source_reference", sa.String(500)),
        sa.Column(
            "verification_status", sa.String(24), nullable=False, server_default="UNVERIFIED"
        ),
        sa.Column("freshness_status", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("evidence_state", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("raw_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("canonical_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "fingerprint_version",
            sa.String(32),
            nullable=False,
            server_default="review-fingerprint-v1",
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "provider",
            "provider_review_id",
            name="uq_review_provider_identity",
        ),
        sa.UniqueConstraint("owner_id", "context_id", "fingerprint", name="uq_review_fingerprint"),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= rating_scale)",
            name="ck_review_rating_bounds",
        ),
        sa.CheckConstraint(
            "rating_scale IS NULL OR rating_scale > 0", name="ck_review_rating_scale"
        ),
        sa.CheckConstraint(
            "helpful_count IS NULL OR helpful_count >= 0", name="ck_review_helpful_nonnegative"
        ),
    )
    op.create_index("ix_review_record_owner", "intelligence_review_records", ["owner_id"])
    op.create_index(
        "ix_review_record_context_date",
        "intelligence_review_records",
        ["owner_id", "context_id", "review_date"],
    )
    op.create_index(
        "ix_review_record_context_source",
        "intelligence_review_records",
        ["owner_id", "context_id", "source_id"],
    )
    op.create_index(
        "ix_review_record_provider_identity",
        "intelligence_review_records",
        ["provider", "provider_review_id"],
    )
    op.create_index("ix_review_record_fingerprint", "intelligence_review_records", ["fingerprint"])
    op.create_table(
        "intelligence_review_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_review_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("snapshot_version", sa.Integer, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rated_review_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("review_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("source_inventory", JSONB, nullable=False, server_default="{}"),
        sa.Column("evidence_coverage", JSONB, nullable=False, server_default="{}"),
        sa.Column("freshness_summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("statistics_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "calculation_version",
            sa.String(80),
            nullable=False,
            server_default="review-foundation-v1",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "snapshot_version", name="uq_review_snapshot_version"
        ),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_snapshot_fingerprint"
        ),
    )
    op.create_index("ix_review_snapshot_owner", "intelligence_review_snapshots", ["owner_id"])
    op.create_index(
        "ix_review_snapshot_context_captured",
        "intelligence_review_snapshots",
        ["owner_id", "context_id", "captured_at"],
    )
    op.create_index(
        "ix_review_snapshot_fingerprint", "intelligence_review_snapshots", ["input_fingerprint"]
    )


def downgrade() -> None:
    op.drop_table("intelligence_review_snapshots")
    op.drop_table("intelligence_review_records")
    op.drop_table("intelligence_review_sources")
    op.drop_table("intelligence_review_contexts")
