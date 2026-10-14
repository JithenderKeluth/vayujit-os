"""Add shared HUMAN review and execution controls for non-Amazon marketplaces."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261019_0159"
down_revision = "20261018_0158"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "marketplace_listing_reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("account_id", uuid, nullable=False),
        sa.Column("listing_id", uuid, nullable=False),
        sa.Column("artifact_id", uuid, nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("payload_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("reviewed_by", uuid, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["marketplace_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["generated_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "owner_id", "listing_id", "payload_fingerprint",
            name="uq_marketplace_listing_review_payload",
        ),
        sa.CheckConstraint(
            "status IN ('approved','revoked')",
            name="ck_marketplace_listing_review_status",
        ),
    )
    op.create_index("ix_marketplace_listing_reviews_owner", "marketplace_listing_reviews", ["owner_id"])
    op.create_index("ix_marketplace_listing_reviews_marketplace", "marketplace_listing_reviews", ["marketplace"])
    op.create_index("ix_marketplace_listing_reviews_listing", "marketplace_listing_reviews", ["listing_id"])
    op.create_index("ix_marketplace_listing_reviews_fingerprint", "marketplace_listing_reviews", ["payload_fingerprint"])

    op.create_table(
        "marketplace_listing_execution_authorizations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("marketplace", sa.String(30), nullable=False),
        sa.Column("account_id", uuid, nullable=False),
        sa.Column("listing_id", uuid, nullable=False),
        sa.Column("review_id", uuid, nullable=False),
        sa.Column("operation", sa.String(40), nullable=False, server_default="listing_submit"),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("payload_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="issued"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("issued_by", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["marketplace_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_id"], ["marketplace_listing_reviews.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "owner_id", "listing_id", "operation", "idempotency_key",
            name="uq_marketplace_listing_execution_auth_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('issued','consumed','revoked','expired')",
            name="ck_marketplace_listing_execution_auth_status",
        ),
    )
    op.create_index("ix_marketplace_listing_exec_auth_owner", "marketplace_listing_execution_authorizations", ["owner_id"])
    op.create_index("ix_marketplace_listing_exec_auth_marketplace", "marketplace_listing_execution_authorizations", ["marketplace"])
    op.create_index("ix_marketplace_listing_exec_auth_listing", "marketplace_listing_execution_authorizations", ["listing_id"])
    op.create_index("ix_marketplace_listing_exec_auth_status", "marketplace_listing_execution_authorizations", ["status"])
    op.create_index("ix_marketplace_listing_exec_auth_fingerprint", "marketplace_listing_execution_authorizations", ["payload_fingerprint"])


def downgrade() -> None:
    op.drop_table("marketplace_listing_execution_authorizations")
    op.drop_table("marketplace_listing_reviews")
