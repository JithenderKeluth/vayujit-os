"""Add the single local owner and server-managed sessions.

Revision ID: 20260727_0002
Revises: 20260727_0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260727_0002"
down_revision = "20260727_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    role = postgresql.ENUM("OWNER", name="userrole", create_type=False)
    status = postgresql.ENUM("ACTIVE", "DISABLED", name="userstatus", create_type=False)
    role.create(op.get_bind())
    status.create(op.get_bind())
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton_key", sa.SmallInteger(), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("singleton_key = 1", name="ck_users_single_owner"),
        sa.UniqueConstraint("singleton_key"),
        sa.UniqueConstraint("normalized_email"),
    )
    op.create_index("ix_users_normalized_email", "users", ["normalized_email"], unique=True)
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_sessions")
    op.drop_table("users")
    sa.Enum(name="userstatus").drop(op.get_bind())
    sa.Enum(name="userrole").drop(op.get_bind())
