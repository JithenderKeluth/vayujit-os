"""Add bounded Shopify media polling and managed assignment ownership."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260804_0015"
down_revision = "20260803_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shopify_media_mappings",
        sa.Column("reuse_state", sa.String(30), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "shopify_media_mappings",
        sa.Column("polling_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("shopify_media_mappings", sa.Column("safe_error_message", sa.String(500)))
    op.add_column(
        "shopify_product_assignments",
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        """
        UPDATE shopify_product_assignments AS assignment
        SET product_id = execution.product_id
        FROM publishing_executions AS execution
        WHERE execution.destination_id = assignment.destination_id
          AND execution.remote_entity_id = assignment.remote_product_id
        """
    )
    op.alter_column("shopify_product_assignments", "product_id", nullable=False)
    op.create_foreign_key(
        "fk_shopify_product_assignments_product_id",
        "shopify_product_assignments",
        "products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_shopify_product_assignments_product_id",
        "shopify_product_assignments",
        ["product_id"],
    )
    op.add_column(
        "shopify_product_assignments",
        sa.Column("managed_by_vayujit", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "shopify_product_assignments",
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute("UPDATE shopify_product_assignments SET updated_at = created_at")
    op.alter_column("shopify_product_assignments", "updated_at", nullable=False)
    op.create_table(
        "shopify_media_poll_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "media_mapping_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shopify_media_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("remote_status", sa.String(30), nullable=False),
        sa.Column("delay_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "media_mapping_id", "attempt_number", name="uq_shopify_media_poll_attempt"
        ),
    )
    for column in ("owner_id", "execution_id", "media_mapping_id"):
        op.create_index(
            f"ix_shopify_media_poll_attempts_{column}",
            "shopify_media_poll_attempts",
            [column],
        )


def downgrade() -> None:
    op.drop_table("shopify_media_poll_attempts")
    op.drop_column("shopify_product_assignments", "updated_at")
    op.drop_column("shopify_product_assignments", "managed_by_vayujit")
    op.drop_index(
        "ix_shopify_product_assignments_product_id",
        table_name="shopify_product_assignments",
    )
    op.drop_constraint(
        "fk_shopify_product_assignments_product_id",
        "shopify_product_assignments",
        type_="foreignkey",
    )
    op.drop_column("shopify_product_assignments", "product_id")
    op.drop_column("shopify_media_mappings", "safe_error_message")
    op.drop_column("shopify_media_mappings", "polling_attempt_count")
    op.drop_column("shopify_media_mappings", "reuse_state")
