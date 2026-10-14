"""Add the bounded PR-7B RFQ EMAIL authorization/outbox boundary."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261008_0149"
down_revision = "20261007_0148"
branch_labels = None
depends_on = None


def _json(default: str = "{}") -> sa.TextClause:
    return sa.text(f"'{default}'::jsonb")


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    op.create_table(
        "intelligence_rfq_send_authorizations",
        sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False), sa.Column("actor_id", uuid, nullable=False),
        sa.Column("goal_id", uuid), sa.Column("opportunity_id", uuid, nullable=False), sa.Column("supplier_id", uuid, nullable=False), sa.Column("contact_id", uuid, nullable=False), sa.Column("engagement_id", uuid, nullable=False), sa.Column("draft_id", uuid, nullable=False), sa.Column("draft_version", sa.Integer(), nullable=False), sa.Column("approval_id", uuid, nullable=False), sa.Column("human_decision_id", uuid, nullable=False), sa.Column("channel", sa.String(32), nullable=False, server_default="EMAIL"), sa.Column("recipient", sa.String(320), nullable=False), sa.Column("subject_fingerprint", sa.String(128), nullable=False), sa.Column("payload_fingerprint", sa.String(128), nullable=False), sa.Column("context_fingerprint", sa.String(128), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="AUTHORIZED"), sa.Column("provenance", sa.String(24), nullable=False, server_default="HUMAN"), sa.Column("idempotency_key", sa.String(220), nullable=False), sa.Column("supplier_snapshot", js, nullable=False, server_default=_json()), sa.Column("contact_snapshot", js, nullable=False, server_default=_json()), sa.Column("confirmation_snapshot", js, nullable=False, server_default=_json()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["contact_id"], ["intelligence_supplier_contacts.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["engagement_id"], ["intelligence_supplier_engagements.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["draft_id"], ["intelligence_supplier_engagement_drafts.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["approval_id"], ["intelligence_supplier_engagement_approvals.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["human_decision_id"], ["intelligence_human_decisions.id"], ondelete="RESTRICT"), sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_rfq_send_auth_idempotency"),
    )
    for name, cols in [("owner", ["owner_id"]), ("engagement", ["engagement_id"]), ("status", ["status"]), ("fingerprint", ["context_fingerprint"])]:
        op.create_index(f"ix_rfq_send_auth_{name}", "intelligence_rfq_send_authorizations", cols)

    op.create_table(
        "intelligence_rfq_send_commands",
        sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False), sa.Column("authorization_id", uuid, nullable=False), sa.Column("engagement_id", uuid, nullable=False), sa.Column("draft_id", uuid, nullable=False), sa.Column("logical_message_id", uuid, nullable=False), sa.Column("channel", sa.String(32), nullable=False, server_default="EMAIL"), sa.Column("recipient", sa.String(320), nullable=False), sa.Column("provider", sa.String(48), nullable=False), sa.Column("payload_fingerprint", sa.String(128), nullable=False), sa.Column("payload_snapshot", js, nullable=False, server_default=_json()), sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("provider_reference", sa.String(180)), sa.Column("last_error", sa.Text()), sa.Column("idempotency_key", sa.String(220), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["authorization_id"], ["intelligence_rfq_send_authorizations.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["engagement_id"], ["intelligence_supplier_engagements.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["draft_id"], ["intelligence_supplier_engagement_drafts.id"], ondelete="RESTRICT"), sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_rfq_send_command_idempotency"), sa.UniqueConstraint("logical_message_id", name="uq_rfq_send_command_logical_message"),
    )
    for name, cols in [("owner", ["owner_id"]), ("authorization", ["authorization_id"]), ("engagement", ["engagement_id"]), ("status", ["status"]), ("logical", ["logical_message_id"])]:
        op.create_index(f"ix_rfq_send_command_{name}", "intelligence_rfq_send_commands", cols)

    op.create_table(
        "intelligence_rfq_send_outbox",
        sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False), sa.Column("command_id", uuid, nullable=False), sa.Column("state", sa.String(32), nullable=False, server_default="PENDING"), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("available_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["command_id"], ["intelligence_rfq_send_commands.id"], ondelete="CASCADE"), sa.UniqueConstraint("command_id", name="uq_rfq_send_outbox_command"),
    )
    op.create_index("ix_rfq_send_outbox_owner", "intelligence_rfq_send_outbox", ["owner_id"])
    op.create_index("ix_rfq_send_outbox_command", "intelligence_rfq_send_outbox", ["command_id"])
    op.create_index("ix_rfq_send_outbox_state", "intelligence_rfq_send_outbox", ["state"])

    op.create_table(
        "intelligence_rfq_delivery_attempts",
        sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False), sa.Column("command_id", uuid, nullable=False), sa.Column("attempt_number", sa.Integer(), nullable=False), sa.Column("provider", sa.String(48), nullable=False), sa.Column("provider_reference", sa.String(180)), sa.Column("outcome", sa.String(40), nullable=False), sa.Column("error_category", sa.String(80)), sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("payload_fingerprint", sa.String(128), nullable=False), sa.Column("receipt_metadata", js, nullable=False, server_default=_json()), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["command_id"], ["intelligence_rfq_send_commands.id"], ondelete="CASCADE"), sa.UniqueConstraint("command_id", "attempt_number", name="uq_rfq_delivery_attempt"),
    )
    op.create_index("ix_rfq_delivery_attempt_owner", "intelligence_rfq_delivery_attempts", ["owner_id"])
    op.create_index("ix_rfq_delivery_attempt_command", "intelligence_rfq_delivery_attempts", ["command_id"])


def downgrade() -> None:
    op.drop_index("ix_rfq_delivery_attempt_command", table_name="intelligence_rfq_delivery_attempts")
    op.drop_index("ix_rfq_delivery_attempt_owner", table_name="intelligence_rfq_delivery_attempts")
    op.drop_table("intelligence_rfq_delivery_attempts")
    op.drop_index("ix_rfq_send_outbox_state", table_name="intelligence_rfq_send_outbox")
    op.drop_index("ix_rfq_send_outbox_command", table_name="intelligence_rfq_send_outbox")
    op.drop_index("ix_rfq_send_outbox_owner", table_name="intelligence_rfq_send_outbox")
    op.drop_table("intelligence_rfq_send_outbox")
    for name in ["logical", "status", "engagement", "authorization", "owner"]:
        op.drop_index(f"ix_rfq_send_command_{name}", table_name="intelligence_rfq_send_commands")
    op.drop_table("intelligence_rfq_send_commands")
    for name in ["fingerprint", "status", "engagement", "owner"]:
        op.drop_index(f"ix_rfq_send_auth_{name}", table_name="intelligence_rfq_send_authorizations")
    op.drop_table("intelligence_rfq_send_authorizations")
