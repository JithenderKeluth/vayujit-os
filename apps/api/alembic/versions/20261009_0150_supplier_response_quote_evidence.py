"""Add the bounded PR-7C inbound supplier-response evidence foundation."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261009_0150"
down_revision = "20261008_0149"
branch_labels = None
depends_on = None


def _json(default: str = "{}") -> sa.TextClause:
    return sa.text(f"'{default}'::jsonb")


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    op.create_table(
        "intelligence_supplier_inbound_responses",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("supplier_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=True),
        sa.Column("engagement_id", uuid, nullable=True),
        sa.Column("draft_id", uuid, nullable=True),
        sa.Column("send_command_id", uuid, nullable=True),
        sa.Column("channel", sa.String(32), nullable=False, server_default="EMAIL"),
        sa.Column("sender_identity", sa.String(320), nullable=True),
        sa.Column("recipient_identity", sa.String(320), nullable=True),
        sa.Column("provider_message_id", sa.String(240), nullable=True),
        sa.Column("provider_thread_id", sa.String(240), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("raw_content_hash", sa.String(128), nullable=False),
        sa.Column("attachment_refs", js, nullable=False, server_default=_json("[]")),
        sa.Column("trust_environment", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("evidence_environment", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("correlation_state", sa.String(24), nullable=False, server_default="UNMATCHED"),
        sa.Column("correlation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("correlation_metadata", js, nullable=False, server_default=_json()),
        sa.Column("classification", sa.String(40), nullable=False, server_default="UNKNOWN"),
        sa.Column("response_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["intelligence_suppliers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["intelligence_supplier_engagements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"], ["intelligence_supplier_engagement_drafts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["send_command_id"], ["intelligence_rfq_send_commands.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "owner_id", "response_fingerprint", name="uq_supplier_response_fingerprint"
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_response_idempotency"),
        sa.CheckConstraint(
            "channel IN ('EMAIL','FORM','MANUAL_IMPORT','OTHER')",
            name="ck_supplier_response_channel",
        ),
        sa.CheckConstraint(
            "correlation_state IN ('CORRELATED','AMBIGUOUS','UNMATCHED')",
            name="ck_supplier_response_correlation",
        ),
    )
    for name, cols in [
        ("owner", ["owner_id"]),
        ("supplier", ["supplier_id"]),
        ("opportunity", ["opportunity_id"]),
        ("engagement", ["engagement_id"]),
        ("command", ["send_command_id"]),
        ("fingerprint", ["response_fingerprint"]),
        ("classification", ["classification"]),
    ]:
        op.create_index(
            f"ix_supplier_response_{name}", "intelligence_supplier_inbound_responses", cols
        )

    op.create_table(
        "intelligence_supplier_response_extractions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("response_id", uuid, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("extracted_fields", js, nullable=False, server_default=_json()),
        sa.Column("field_provenance", js, nullable=False, server_default=_json()),
        sa.Column("source_spans", js, nullable=False, server_default=_json()),
        sa.Column("unknown_fields", js, nullable=False, server_default=_json("[]")),
        sa.Column("warnings", js, nullable=False, server_default=_json("[]")),
        sa.Column(
            "extraction_authority",
            sa.String(40),
            nullable=False,
            server_default="DETERMINISTIC_PARSER",
        ),
        sa.Column("source_raw_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["response_id"], ["intelligence_supplier_inbound_responses.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "response_id", "version", name="uq_supplier_response_extraction_version"
        ),
        sa.CheckConstraint(
            "status IN ('EXTRACTED','PARTIAL','NEEDS_REVIEW','FAILED')",
            name="ck_supplier_response_extraction_status",
        ),
    )
    op.create_index(
        "ix_supplier_response_extraction_owner",
        "intelligence_supplier_response_extractions",
        ["owner_id"],
    )
    op.create_index(
        "ix_supplier_response_extraction_response",
        "intelligence_supplier_response_extractions",
        ["response_id"],
    )

    op.create_table(
        "intelligence_supplier_response_reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("response_id", uuid, nullable=False),
        sa.Column("extraction_id", uuid, nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("provenance", sa.String(24), nullable=False, server_default="HUMAN"),
        sa.Column("corrections", js, nullable=False, server_default=_json()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["response_id"], ["intelligence_supplier_inbound_responses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["intelligence_supplier_response_extractions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_response_review_idempotency"
        ),
        sa.CheckConstraint(
            "decision IN ("
            "'ACCEPT_EXTRACTION','CORRECT_EXTRACTION','REJECT_EXTRACTION','KEEP_UNDER_REVIEW'"
            ")",
            name="ck_supplier_response_review_decision",
        ),
        sa.CheckConstraint("provenance = 'HUMAN'", name="ck_supplier_response_review_provenance"),
    )
    for name, cols in [
        ("owner", ["owner_id"]),
        ("response", ["response_id"]),
        ("extraction", ["extraction_id"]),
        ("actor", ["actor_id"]),
        ("decision", ["decision"]),
    ]:
        op.create_index(
            f"ix_supplier_response_review_{name}", "intelligence_supplier_response_reviews", cols
        )

    op.create_table(
        "intelligence_supplier_response_promotions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("response_id", uuid, nullable=False),
        sa.Column("extraction_id", uuid, nullable=False),
        sa.Column("review_id", uuid, nullable=False),
        sa.Column("supplier_evidence_id", uuid, nullable=True),
        sa.Column("supplier_product_id", uuid, nullable=True),
        sa.Column("commercial_term_id", uuid, nullable=True),
        sa.Column("readiness_snapshot_id", uuid, nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="PROMOTED"),
        sa.Column(
            "provenance", sa.String(32), nullable=False, server_default="SOURCE_PROVIDED_CLAIM"
        ),
        sa.Column("contradictions", js, nullable=False, server_default=_json("[]")),
        sa.Column("lineage", js, nullable=False, server_default=_json()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["response_id"], ["intelligence_supplier_inbound_responses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["intelligence_supplier_response_extractions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["intelligence_supplier_response_reviews.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_evidence_id"], ["intelligence_supplier_evidence.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_product_id"], ["intelligence_supplier_products.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["commercial_term_id"],
            ["intelligence_supplier_commercial_terms.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["readiness_snapshot_id"],
            ["intelligence_commercial_readiness_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("owner_id", "review_id", name="uq_supplier_response_promotion_review"),
    )
    for name, cols in [
        ("owner", ["owner_id"]),
        ("response", ["response_id"]),
        ("review", ["review_id"]),
        ("supplier_product", ["supplier_product_id"]),
        ("term", ["commercial_term_id"]),
        ("readiness", ["readiness_snapshot_id"]),
    ]:
        op.create_index(
            f"ix_supplier_response_promotion_{name}",
            "intelligence_supplier_response_promotions",
            cols,
        )


def downgrade() -> None:
    op.drop_table("intelligence_supplier_response_promotions")
    op.drop_table("intelligence_supplier_response_reviews")
    op.drop_table("intelligence_supplier_response_extractions")
    op.drop_table("intelligence_supplier_inbound_responses")
