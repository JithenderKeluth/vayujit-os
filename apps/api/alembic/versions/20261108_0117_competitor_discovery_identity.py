"""Add deterministic competitor discovery persistence (Slice 10B)."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261108_0117"
down_revision = "20261107_0116"
branch_labels = None
depends_on = None


def _common(name: str, *extra: Any) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *extra,
    )
    op.create_index(f"ix_{name}_owner_id", name, ["owner_id"])


def upgrade() -> None:
    _common(
        "intelligence_competitor_discovery_requests",
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("marketplace", sa.String(120), nullable=False, server_default=""),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("query_inputs", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("filters", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("source_selection", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("maximum_candidates", sa.Integer, nullable=False, server_default="50"),
        sa.Column("provider_mode", sa.String(32), nullable=False, server_default="LOCAL_FIXTURE"),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_reason", sa.String(240)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_comp_discovery_request_idempotency"
        ),
        sa.CheckConstraint(
            (
                "status IN ('PENDING','RUNNING','COMPLETED',"
                "'PARTIALLY_COMPLETED','FAILED','CANCELLED')"
            ),
            name="ck_comp_discovery_request_status",
        ),
        sa.CheckConstraint(
            "provider_mode IN ('DISABLED','LOCAL_FIXTURE','LIVE_READ_ONLY')",
            name="ck_comp_discovery_request_provider_mode",
        ),
        sa.CheckConstraint(
            "maximum_candidates BETWEEN 1 AND 500", name="ck_comp_discovery_max_candidates"
        ),
    )
    op.create_index(
        "ix_comp_discovery_request_context",
        "intelligence_competitor_discovery_requests",
        ["context_id", "created_at"],
    )
    op.create_index(
        "ix_comp_discovery_request_owner_status",
        "intelligence_competitor_discovery_requests",
        ["owner_id", "status"],
    )

    _common(
        "intelligence_competitor_discovery_candidates",
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_discovery_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_mode", sa.String(32), nullable=False),
        sa.Column("source_identifier", sa.String(500), nullable=False),
        sa.Column("listing_identifier", sa.String(240)),
        sa.Column("canonical_url", sa.String(1000)),
        sa.Column("raw_title", sa.String(500), nullable=False),
        sa.Column("normalized_title", sa.String(500), nullable=False),
        sa.Column("brand_claim", sa.String(240)),
        sa.Column("seller_claim", sa.String(240)),
        sa.Column("category", sa.String(120)),
        sa.Column("marketplace", sa.String(120), nullable=False, server_default=""),
        sa.Column("price_amount", sa.Numeric(20, 6)),
        sa.Column("currency", sa.String(3)),
        sa.Column("rating", sa.Numeric(4, 2)),
        sa.Column("review_count", sa.Integer),
        sa.Column("availability_state", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("structured_attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("identity_state", sa.String(24), nullable=False, server_default="CANDIDATE"),
        sa.Column("match_level", sa.String(32), nullable=False, server_default="NONE"),
        sa.Column("match_score", sa.Numeric(5, 4)),
        sa.Column("supporting_signals", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("conflicting_signals", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("missing_signals", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "rule_version", sa.String(80), nullable=False, server_default="competitor-match-v1"
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="CURRENT"),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_evidence.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "competitor_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_foundation_products.id", ondelete="SET NULL"),
        ),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "request_id",
            "source_mode",
            "source_identifier",
            name="uq_comp_discovery_candidate_source",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "request_id",
            "idempotency_key",
            name="uq_comp_discovery_candidate_idempotency",
        ),
        sa.CheckConstraint(
            (
                "identity_state IN ('UNRESOLVED','CANDIDATE','PROBABLE',"
                "'CONFIRMED','REJECTED','AMBIGUOUS')"
            ),
            name="ck_comp_discovery_candidate_identity",
        ),
        sa.CheckConstraint(
            (
                "match_level IN ('NONE','WEAK_CANDIDATE','STRUCTURED_MATCH',"
                "'CANONICAL_PRODUCT','AUTHORITATIVE_IDENTIFIER','HUMAN_CONFIRMED')"
            ),
            name="ck_comp_discovery_candidate_match_level",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_comp_discovery_candidate_rating",
        ),
        sa.CheckConstraint(
            "review_count IS NULL OR review_count >= 0", name="ck_comp_discovery_candidate_reviews"
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0", name="ck_comp_discovery_candidate_price"
        ),
    )
    op.create_index(
        "ix_comp_discovery_candidate_request_state",
        "intelligence_competitor_discovery_candidates",
        ["request_id", "identity_state"],
    )
    op.create_index(
        "ix_comp_discovery_candidate_listing",
        "intelligence_competitor_discovery_candidates",
        ["owner_id", "marketplace", "listing_identifier"],
    )
    op.create_index(
        "ix_comp_discovery_candidate_normalized",
        "intelligence_competitor_discovery_candidates",
        ["owner_id", "normalized_title"],
    )

    _common(
        "intelligence_competitor_discovery_snapshots",
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_discovery_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_version", sa.Integer, nullable=False),
        sa.Column("candidate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("accepted_candidate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ambiguous_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_counts", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("source_diversity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("evidence_coverage", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column(
            "competitor_product_references", postgresql.JSONB, nullable=False, server_default="[]"
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "previous_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("source_freshness", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "request_id", "snapshot_version", name="uq_comp_discovery_snapshot_version"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "request_id",
            "input_fingerprint",
            "snapshot_version",
            name="uq_comp_discovery_snapshot_fingerprint",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "request_id",
            "idempotency_key",
            name="uq_comp_discovery_snapshot_idempotency",
        ),
        sa.CheckConstraint("snapshot_version >= 1", name="ck_comp_discovery_snapshot_version"),
        sa.CheckConstraint("candidate_count >= 0", name="ck_comp_discovery_snapshot_candidates"),
    )
    op.create_index(
        "ix_comp_discovery_snapshot_request",
        "intelligence_competitor_discovery_snapshots",
        ["request_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_competitor_discovery_snapshots")
    op.drop_table("intelligence_competitor_discovery_candidates")
    op.drop_table("intelligence_competitor_discovery_requests")
