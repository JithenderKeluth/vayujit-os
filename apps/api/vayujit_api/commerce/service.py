"""Commerce service helpers shared by API and workers."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.credentials import encrypt_credential
from vayujit_api.commerce.connector import connector_for
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceCategory,
    MarketplaceDriftRecord,
    MarketplaceIdempotencyKey,
    MarketplaceListing,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplaceSettlement,
    MarketplaceSettlementLine,
)
from vayujit_api.commerce.schemas import CAPABILITIES
from vayujit_api.core.config import get_settings
from vayujit_api.identity.service import now


def account_or_none(
    db: Session, owner_id: uuid.UUID, account_id: uuid.UUID
) -> MarketplaceAccount | None:
    return db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id, MarketplaceAccount.owner_id == owner_id
        )
    )


def encrypt_credentials(credentials: dict[str, str]) -> str | None:
    if not credentials:
        return None
    payload = json.dumps(credentials, sort_keys=True, separators=(",", ":"))
    return encrypt_credential(payload, get_settings().credential_encryption_key)


def capabilities(marketplace: str) -> dict[str, object]:
    return {"marketplace": marketplace, "operations": CAPABILITIES.get(marketplace, [])}


def create_categories(db: Session, account: MarketplaceAccount) -> list[MarketplaceCategory]:
    connector = connector_for(account.marketplace)
    stamp = now()
    rows: list[MarketplaceCategory] = []
    for item in connector.discover_categories():
        remote_id = str(item["remote_id"])
        row = db.scalar(
            select(MarketplaceCategory).where(
                MarketplaceCategory.account_id == account.id,
                MarketplaceCategory.remote_id == remote_id,
            )
        )
        if row is None:
            row = MarketplaceCategory(
                owner_id=account.owner_id,
                account_id=account.id,
                marketplace=account.marketplace,
                remote_id=remote_id,
                name=str(item["name"]),
                parent_remote_id=item.get("parent_remote_id"),
                attributes_json={},
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(row)
        else:
            row.updated_at = stamp
        rows.append(row)
    db.flush()
    return rows


def idempotent_resource(
    db: Session, owner_id: uuid.UUID, account_id: uuid.UUID, operation: str, key: str
) -> uuid.UUID | None:
    if not key:
        return None
    row = db.scalar(
        select(MarketplaceIdempotencyKey).where(
            MarketplaceIdempotencyKey.owner_id == owner_id,
            MarketplaceIdempotencyKey.account_id == account_id,
            MarketplaceIdempotencyKey.operation == operation,
            MarketplaceIdempotencyKey.idempotency_key == key,
        )
    )
    return row.resource_id if row else None


def remember_idempotency(
    db: Session,
    *,
    owner_id: uuid.UUID,
    account_id: uuid.UUID,
    operation: str,
    key: str,
    resource_type: str,
    resource_id: uuid.UUID,
) -> None:
    if key:
        db.add(
            MarketplaceIdempotencyKey(
                owner_id=owner_id,
                account_id=account_id,
                operation=operation,
                idempotency_key=key,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=now(),
                updated_at=now(),
            )
        )


def import_fake_order(db: Session, account: MarketplaceAccount) -> MarketplaceOrder:
    item = connector_for(account.marketplace).get_orders()[0]
    stamp = now()
    order = db.scalar(
        select(MarketplaceOrder).where(
            MarketplaceOrder.account_id == account.id,
            MarketplaceOrder.remote_order_id == str(item["remote_id"]),
        )
    )
    if order is None:
        order = MarketplaceOrder(
            owner_id=account.owner_id,
            account_id=account.id,
            marketplace=account.marketplace,
            remote_order_id=str(item["remote_id"]),
            status=str(item["status"]),
            payment_status="paid",
            fulfilment_status="unfulfilled",
            buyer_snapshot_json={"display_name": "Masked buyer"},
            totals_json={"total": str(item["total"]), "currency": "INR"},
            ordered_at=stamp,
            remote_raw_status=str(item["status"]),
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(order)
        db.flush()
        db.add(
            MarketplaceOrderItem(
                owner_id=account.owner_id,
                order_id=order.id,
                product_id=None,
                variant_id=None,
                marketplace_sku=None,
                title_snapshot="Imported fake order item",
                quantity=1,
                unit_price=1250,
                total_price=1250,
                created_at=stamp,
                updated_at=stamp,
            )
        )
    return order


def import_fake_settlement(db: Session, account: MarketplaceAccount) -> MarketplaceSettlement:
    item = connector_for(account.marketplace).get_settlements()[0]
    stamp = now()
    settlement = db.scalar(
        select(MarketplaceSettlement).where(
            MarketplaceSettlement.account_id == account.id,
            MarketplaceSettlement.remote_settlement_id == str(item["remote_id"]),
        )
    )
    if settlement is None:
        from decimal import Decimal

        gross, fees, net = (Decimal(str(item[k])) for k in ("gross", "fees", "net"))
        settlement = MarketplaceSettlement(
            owner_id=account.owner_id,
            account_id=account.id,
            marketplace=account.marketplace,
            remote_settlement_id=str(item["remote_id"]),
            period_start=stamp,
            period_end=stamp,
            gross_amount=gross,
            fee_amount=fees,
            refund_amount=Decimal("0"),
            tax_withholding_amount=Decimal("0"),
            net_amount=net,
            currency="INR",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(settlement)
        db.flush()
        db.add(
            MarketplaceSettlementLine(
                owner_id=account.owner_id,
                settlement_id=settlement.id,
                order_id=None,
                line_type="commission",
                amount=-fees,
                currency="INR",
                description="Fake connector commission",
                created_at=stamp,
                updated_at=stamp,
            )
        )
    return settlement


def safe_drift(
    db: Session, listing: MarketplaceListing, remote: dict[str, object]
) -> list[MarketplaceDriftRecord]:
    rows: list[MarketplaceDriftRecord] = []
    if remote.get("title") and remote["title"] != listing.title:
        row = MarketplaceDriftRecord(
            owner_id=listing.owner_id,
            listing_id=listing.id,
            field_name="title",
            local_value_json=listing.title,
            remote_value_json=remote["title"],
            state="detected",
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        rows.append(row)
    listing.drift_state = "detected" if rows else "none"
    return rows
