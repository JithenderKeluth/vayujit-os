"""Add the non-sending PR-7A controlled supplier engagement foundation."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261007_0148"
down_revision = "20261006_0147"
branch_labels = None
depends_on = None


def _json_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def _array_default() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.create_table(
        "intelligence_supplier_engagements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("human_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("synthesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "decision_target",
            sa.String(length=40),
            nullable=False,
            server_default="SUPPLIER_SELECTION",
        ),
        sa.Column(
            "engagement_type", sa.String(length=40), nullable=False, server_default="REQUEST_QUOTE"
        ),
        sa.Column("engagement_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_draft_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="BLOCKED"),
        sa.Column(
            "blocking_reasons", postgresql.JSONB(), nullable=False, server_default=_array_default()
        ),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=False),
        sa.Column(
            "external_writes", postgresql.JSONB(), nullable=False, server_default=_array_default()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["intelligence_supplier_contacts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["human_decision_id"], ["intelligence_human_decisions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["intelligence_recommendation_assessments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["synthesis_id"], ["intelligence_decision_synthesis_snapshots.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_engagement_idempotency"
        ),
    )
    op.create_index(
        "ix_supplier_engagement_owner", "intelligence_supplier_engagements", ["owner_id"]
    )
    op.create_index(
        "ix_supplier_engagement_opportunity",
        "intelligence_supplier_engagements",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_supplier_engagement_supplier", "intelligence_supplier_engagements", ["supplier_id"]
    )
    op.create_index(
        "ix_supplier_engagement_status", "intelligence_supplier_engagements", ["status"]
    )
    op.create_index(
        "ix_supplier_engagement_fingerprint",
        "intelligence_supplier_engagements",
        ["input_fingerprint"],
    )

    op.create_table(
        "intelligence_supplier_engagement_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("human_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("synthesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column(
            "supplier_snapshot", postgresql.JSONB(), nullable=False, server_default=_json_default()
        ),
        sa.Column(
            "contact_snapshot", postgresql.JSONB(), nullable=False, server_default=_json_default()
        ),
        sa.Column(
            "product_snapshot", postgresql.JSONB(), nullable=False, server_default=_json_default()
        ),
        sa.Column(
            "structured_request", postgresql.JSONB(), nullable=False, server_default=_json_default()
        ),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column(
            "template_version",
            sa.String(length=80),
            nullable=False,
            server_default="rfq-neutral-v1",
        ),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=_array_default()),
        sa.Column("unknowns", postgresql.JSONB(), nullable=False, server_default=_array_default()),
        sa.Column(
            "limitations", postgresql.JSONB(), nullable=False, server_default=_array_default()
        ),
        sa.Column(
            "provenance", sa.String(length=32), nullable=False, server_default="SYSTEM_DRAFT"
        ),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("supersedes_draft_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["intelligence_supplier_engagements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["intelligence_supplier_contacts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_draft_id"],
            ["intelligence_supplier_engagement_drafts.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "engagement_id", "version", name="uq_supplier_engagement_draft_version"
        ),
        sa.UniqueConstraint(
            "engagement_id", "input_fingerprint", name="uq_supplier_engagement_draft_fingerprint"
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_engagement_draft_idempotency"
        ),
    )
    op.create_index(
        "ix_supplier_engagement_draft_owner",
        "intelligence_supplier_engagement_drafts",
        ["owner_id"],
    )
    op.create_index(
        "ix_supplier_engagement_draft_engagement",
        "intelligence_supplier_engagement_drafts",
        ["engagement_id"],
    )
    op.create_index(
        "ix_supplier_engagement_draft_status", "intelligence_supplier_engagement_drafts", ["status"]
    )
    op.create_index(
        "ix_supplier_engagement_draft_fingerprint",
        "intelligence_supplier_engagement_drafts",
        ["input_fingerprint"],
    )

    op.create_table(
        "intelligence_supplier_engagement_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("human_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provenance", sa.String(length=24), nullable=False, server_default="HUMAN"),
        sa.Column("context_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("supersedes_approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "external_writes", postgresql.JSONB(), nullable=False, server_default=_array_default()
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["intelligence_supplier_engagements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"], ["intelligence_supplier_engagement_drafts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_approval_id"],
            ["intelligence_supplier_engagement_approvals.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_supplier_engagement_approval_idempotency"
        ),
    )
    op.create_index(
        "ix_supplier_engagement_approval_owner",
        "intelligence_supplier_engagement_approvals",
        ["owner_id"],
    )
    op.create_index(
        "ix_supplier_engagement_approval_engagement",
        "intelligence_supplier_engagement_approvals",
        ["engagement_id"],
    )
    op.create_index(
        "ix_supplier_engagement_approval_state",
        "intelligence_supplier_engagement_approvals",
        ["state"],
    )
    op.create_index(
        "ix_supplier_engagement_approval_fingerprint",
        "intelligence_supplier_engagement_approvals",
        ["context_fingerprint"],
    )

    op.create_table(
        "intelligence_supplier_engagement_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provenance", sa.String(length=32), nullable=False, server_default="SYSTEM"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=_json_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["intelligence_supplier_engagements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
    )
    op.create_index(
        "ix_supplier_engagement_event_owner",
        "intelligence_supplier_engagement_events",
        ["owner_id"],
    )
    op.create_index(
        "ix_supplier_engagement_event_engagement",
        "intelligence_supplier_engagement_events",
        ["engagement_id"],
    )
    op.create_index(
        "ix_supplier_engagement_event_type",
        "intelligence_supplier_engagement_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_engagement_event_type", table_name="intelligence_supplier_engagement_events"
    )
    op.drop_index(
        "ix_supplier_engagement_event_engagement",
        table_name="intelligence_supplier_engagement_events",
    )
    op.drop_index(
        "ix_supplier_engagement_event_owner", table_name="intelligence_supplier_engagement_events"
    )
    op.drop_table("intelligence_supplier_engagement_events")
    op.drop_index(
        "ix_supplier_engagement_approval_fingerprint",
        table_name="intelligence_supplier_engagement_approvals",
    )
    op.drop_index(
        "ix_supplier_engagement_approval_state",
        table_name="intelligence_supplier_engagement_approvals",
    )
    op.drop_index(
        "ix_supplier_engagement_approval_engagement",
        table_name="intelligence_supplier_engagement_approvals",
    )
    op.drop_index(
        "ix_supplier_engagement_approval_owner",
        table_name="intelligence_supplier_engagement_approvals",
    )
    op.drop_table("intelligence_supplier_engagement_approvals")
    op.drop_index(
        "ix_supplier_engagement_draft_fingerprint",
        table_name="intelligence_supplier_engagement_drafts",
    )
    op.drop_index(
        "ix_supplier_engagement_draft_status", table_name="intelligence_supplier_engagement_drafts"
    )
    op.drop_index(
        "ix_supplier_engagement_draft_engagement",
        table_name="intelligence_supplier_engagement_drafts",
    )
    op.drop_index(
        "ix_supplier_engagement_draft_owner", table_name="intelligence_supplier_engagement_drafts"
    )
    op.drop_table("intelligence_supplier_engagement_drafts")
    op.drop_index(
        "ix_supplier_engagement_fingerprint", table_name="intelligence_supplier_engagements"
    )
    op.drop_index("ix_supplier_engagement_status", table_name="intelligence_supplier_engagements")
    op.drop_index("ix_supplier_engagement_supplier", table_name="intelligence_supplier_engagements")
    op.drop_index(
        "ix_supplier_engagement_opportunity", table_name="intelligence_supplier_engagements"
    )
    op.drop_index("ix_supplier_engagement_owner", table_name="intelligence_supplier_engagements")
    op.drop_table("intelligence_supplier_engagements")
