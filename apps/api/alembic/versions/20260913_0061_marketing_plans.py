"""Add normalized cross-channel Marketing Plans."""

# mypy: ignore-errors

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260913_0061"
down_revision: str | None = "20260912_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "marketing_plans",
        *_common(),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_ids_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("objective", sa.String(40), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False, server_default="en-IN"),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("timezone_name", sa.String(80), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("target_channels_json", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("budget_envelope_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("strategy_mode", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("automation_mode", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("preview_fingerprint", sa.String(128)),
        sa.Column("creative_mapping_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("targeting_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schedule_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_marketing_plan_idempotency"),
    )
    op.create_index("ix_marketing_plans_owner", "marketing_plans", ["owner_id"])
    op.create_index("ix_marketing_plans_status", "marketing_plans", ["status"])
    op.create_table(
        "marketing_plan_channels",
        *_common(),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version", sa.Integer, nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32)),
        sa.Column("state", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("account_id", postgresql.UUID(as_uuid=True)),
        sa.Column("listing_id", sa.String(180)),
        sa.Column("listing_version", sa.Integer),
        sa.Column("creative_mapping_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("downstream_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("safe_message", sa.String(500)),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["marketing_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id",
            "plan_id",
            "plan_version",
            "channel",
            name="uq_marketing_plan_channel",
        ),
    )
    op.create_index("ix_marketing_plan_channels_owner", "marketing_plan_channels", ["owner_id"])
    op.create_index("ix_marketing_plan_channels_plan", "marketing_plan_channels", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_marketing_plan_channels_plan", table_name="marketing_plan_channels")
    op.drop_index("ix_marketing_plan_channels_owner", table_name="marketing_plan_channels")
    op.drop_table("marketing_plan_channels")
    op.drop_index("ix_marketing_plans_status", table_name="marketing_plans")
    op.drop_index("ix_marketing_plans_owner", table_name="marketing_plans")
    op.drop_table("marketing_plans")
