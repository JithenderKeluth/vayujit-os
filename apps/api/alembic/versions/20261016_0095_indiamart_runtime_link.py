"""Link IndiaMART discovery requests to shared marketplace executions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261016_0095"
down_revision = "20261015_0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_indiamart_discovery_requests",
        sa.Column("marketplace_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_indiamart_request_marketplace_execution",
        "intelligence_indiamart_discovery_requests",
        "marketplace_executions",
        ["marketplace_execution_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_indiamart_discovery_requests_marketplace_execution_id",
        "intelligence_indiamart_discovery_requests",
        ["marketplace_execution_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_indiamart_discovery_requests_marketplace_execution_id",
        table_name="intelligence_indiamart_discovery_requests",
    )
    op.drop_constraint(
        "fk_indiamart_request_marketplace_execution",
        "intelligence_indiamart_discovery_requests",
        type_="foreignkey",
    )
    op.drop_column("intelligence_indiamart_discovery_requests", "marketplace_execution_id")
