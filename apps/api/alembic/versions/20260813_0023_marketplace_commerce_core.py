"""Create normalized Marketplace Commerce Core tables."""

from collections.abc import Sequence

from sqlalchemy import Table

from alembic import op

revision: str = "20260813_0023"
down_revision: str | None = "20260812_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "marketplace_accounts",
    "marketplace_categories",
    "marketplace_listings",
    "marketplace_attribute_definitions",
    "marketplace_listing_attributes",
    "marketplace_identifier_mappings",
    "marketplace_variants",
    "marketplace_prices",
    "marketplace_inventory",
    "marketplace_orders",
    "marketplace_order_items",
    "marketplace_address_snapshots",
    "marketplace_fulfilments",
    "marketplace_cancellations",
    "marketplace_returns",
    "marketplace_refunds",
    "marketplace_settlements",
    "marketplace_settlement_lines",
    "marketplace_fees",
    "marketplace_drift_records",
    "marketplace_idempotency_keys",
)


def _metadata_table(name: str) -> Table:
    from vayujit_api import main  # noqa: F401
    from vayujit_api.core.database import Base

    return Base.metadata.tables[name]


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        _metadata_table(name).create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        _metadata_table(name).drop(bind=bind, checkfirst=True)
