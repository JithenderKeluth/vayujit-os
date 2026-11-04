"""Preserve canonical product/supplier identity without repurposing legacy FKs."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261204_0147"
down_revision = "20261203_0146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column, table in (
        ("product_opportunity_id", "intelligence_product_opportunities"),
        ("canonical_supplier_id", "intelligence_cross_marketplace_suppliers"),
    ):
        op.add_column(
            "intelligence_economic_contexts",
            sa.Column(column, postgresql.UUID(as_uuid=True)),
        )
        op.create_foreign_key(
            f"fk_economic_{column}",
            "intelligence_economic_contexts",
            table,
            [column],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            f"ix_intelligence_economic_contexts_{column}",
            "intelligence_economic_contexts",
            [column],
        )


def downgrade() -> None:
    for column in ("canonical_supplier_id", "product_opportunity_id"):
        op.drop_index(
            f"ix_intelligence_economic_contexts_{column}",
            table_name="intelligence_economic_contexts",
        )
        op.drop_constraint(
            f"fk_economic_{column}",
            "intelligence_economic_contexts",
            type_="foreignkey",
        )
        op.drop_column("intelligence_economic_contexts", column)
