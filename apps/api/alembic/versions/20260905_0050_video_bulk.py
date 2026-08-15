"""Add parent/child durable Video bulk operations."""

from collections.abc import Sequence

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260905_0050"
down_revision: str | None = "20260905_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_bulk_operations",
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column(
            "owner_id",
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("idempotency_key", String(160), nullable=False),
        Column("product_ids_json", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        Column("video_types_json", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        Column("targets_json", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        Column("total_children", Integer, nullable=False),
        Column("status", String(32), nullable=False, server_default="queued"),
        Column("correlation_id", String(64), nullable=False),
        Column("cancellation_requested", Boolean, nullable=False, server_default="false"),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_video_bulk_idempotency", "video_bulk_operations", ["owner_id", "idempotency_key"]
    )
    op.create_index("ix_video_bulk_operations_owner_id", "video_bulk_operations", ["owner_id"])
    op.create_index("ix_video_bulk_operations_status", "video_bulk_operations", ["status"])
    op.create_index(
        "ix_video_bulk_operations_correlation_id", "video_bulk_operations", ["correlation_id"]
    )
    op.create_table(
        "video_bulk_children",
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column(
            "bulk_id",
            UUID(as_uuid=True),
            ForeignKey("video_bulk_operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column(
            "owner_id",
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column(
            "product_id",
            UUID(as_uuid=True),
            ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column("video_type", String(50), nullable=False),
        Column("target_channel", String(40), nullable=False),
        Column("child_key", String(220), nullable=False),
        Column(
            "generation_id",
            UUID(as_uuid=True),
            ForeignKey("video_generations.id", ondelete="SET NULL"),
        ),
        Column(
            "output_id", UUID(as_uuid=True), ForeignKey("video_outputs.id", ondelete="SET NULL")
        ),
        Column("status", String(32), nullable=False, server_default="queued"),
        Column("retryable", Boolean, nullable=False, server_default="false"),
        Column("failure_code", String(80)),
        Column("safe_error_message", String(500)),
        Column("cancellation_requested", Boolean, nullable=False, server_default="false"),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_video_bulk_child_key", "video_bulk_children", ["bulk_id", "child_key"]
    )
    for table, names in {
        "video_bulk_children": ("bulk_id", "owner_id", "product_id", "status")
    }.items():
        for name in names:
            op.create_index(f"ix_video_bulk_children_{name}", table, [name])


def downgrade() -> None:
    for name in ("status", "product_id", "owner_id", "bulk_id"):
        op.drop_index(f"ix_video_bulk_children_{name}", table_name="video_bulk_children")
    op.drop_constraint("uq_video_bulk_child_key", "video_bulk_children", type_="unique")
    op.drop_table("video_bulk_children")
    for name in ("correlation_id", "status", "owner_id"):
        op.drop_index(f"ix_video_bulk_operations_{name}", table_name="video_bulk_operations")
    op.drop_constraint("uq_video_bulk_idempotency", "video_bulk_operations", type_="unique")
    op.drop_table("video_bulk_operations")
