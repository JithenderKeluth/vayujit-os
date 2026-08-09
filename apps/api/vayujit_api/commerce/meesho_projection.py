"""Durable normalized projections for the deterministic Meesho boundary.

The projection layer deliberately stores only normalized, seller-safe values.
Vendor payloads never cross into the database or API response models.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.commerce.meesho import MeeshoCommerceConnector
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceCancellation,
    MarketplaceFee,
    MarketplaceFulfilment,
    MarketplaceIdempotencyKey,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplaceRefund,
    MarketplaceReturn,
    MarketplaceSettlement,
    MarketplaceSettlementLine,
)
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product


def _remember_import(
    db: Session,
    account: MarketplaceAccount,
    *,
    operation: str,
    key: str,
    resource_type: str,
    resource_id: Any,
) -> None:
    """Persist a replay-safe import marker without storing vendor payloads."""
    if not key:
        return
    exists = db.scalar(
        select(MarketplaceIdempotencyKey).where(
            MarketplaceIdempotencyKey.owner_id == account.owner_id,
            MarketplaceIdempotencyKey.account_id == account.id,
            MarketplaceIdempotencyKey.operation == operation,
            MarketplaceIdempotencyKey.idempotency_key == key,
        )
    )
    if exists is None:
        stamp = now()
        db.add(
            MarketplaceIdempotencyKey(
                owner_id=account.owner_id,
                account_id=account.id,
                operation=operation,
                idempotency_key=key,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=stamp,
                updated_at=stamp,
            )
        )


def _decimal(value: object, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def _status(raw: object) -> str:
    value = str(raw or "unknown").casefold().replace(" ", "_")
    return {
        "confirmed": "confirmed",
        "pending": "pending",
        "processing": "processing",
        "unshipped": "confirmed",
        "partially_shipped": "processing",
        "partiallyshipped": "processing",
        "shipped": "shipped",
        "delivered": "delivered",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "returned": "returned",
        "refunded": "refunded",
    }.get(value, "pending")


def _fulfilment_status(raw: object) -> str:
    value = str(raw or "unknown").casefold().replace(" ", "_")
    return {
        "pending": "unfulfilled",
        "unfulfilled": "unfulfilled",
        "processing": "processing",
        "partially_shipped": "partially_shipped",
        "partiallyshipped": "partially_shipped",
        "shipped": "shipped",
        "delivered": "delivered",
        "cancelled": "cancelled",
    }.get(value, "unknown")


def _parse_timestamp(value: object, fallback: datetime) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            pass
    return fallback


def _order(db: Session, account: MarketplaceAccount, remote_id: str) -> MarketplaceOrder:
    row = db.scalar(
        select(MarketplaceOrder).where(
            MarketplaceOrder.owner_id == account.owner_id,
            MarketplaceOrder.account_id == account.id,
            MarketplaceOrder.remote_order_id == remote_id,
        )
    )
    if row is not None:
        return row
    stamp = now()
    row = MarketplaceOrder(
        owner_id=account.owner_id,
        account_id=account.id,
        marketplace="meesho",
        remote_order_id=remote_id,
        status="pending",
        payment_status="unknown",
        fulfilment_status="unknown",
        buyer_snapshot_json={"display_name": "Masked buyer"},
        totals_json={"currency": "INR", "mapping_status": "unknown"},
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        discount_amount=Decimal("0"),
        ordered_at=stamp,
        remote_raw_status="UNKNOWN",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    return row


def project_order(
    db: Session, account: MarketplaceAccount, value: dict[str, Any]
) -> MarketplaceOrder:
    stamp = now()
    order = _order(db, account, str(value.get("remote_id", "unknown-order")))
    raw_status = str(value.get("status", "UNKNOWN"))
    order.status = _status(raw_status)
    order.remote_raw_status = raw_status[:120]
    order.payment_status = str(value.get("payment_status", "unknown"))[:30].casefold()
    order.fulfilment_status = _fulfilment_status(value.get("fulfilment_status"))
    currency = str(value.get("currency", "INR"))[:3].upper()
    total = _decimal(value.get("total"))
    order.totals_json = {"total": str(total), "currency": currency}
    order.tax_amount = _decimal(value.get("tax"))
    order.shipping_amount = _decimal(value.get("shipping"))
    order.discount_amount = _decimal(value.get("discount"))
    order.ordered_at = _parse_timestamp(value.get("ordered_at"), order.ordered_at)
    order.updated_at = stamp
    items = value.get("items")
    if not isinstance(items, list):
        items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sku = str(item.get("sku")) if item.get("sku") else None
        existing_item = db.scalar(
            select(MarketplaceOrderItem).where(
                MarketplaceOrderItem.owner_id == account.owner_id,
                MarketplaceOrderItem.order_id == order.id,
                MarketplaceOrderItem.marketplace_sku == sku,
            )
        )
        quantity = max(int(item.get("quantity", 1)), 1)
        unit = _decimal(item.get("unit_price", total))
        if existing_item is None:
            db.add(
                MarketplaceOrderItem(
                    owner_id=account.owner_id,
                    order_id=order.id,
                    product_id=None,
                    variant_id=None,
                    marketplace_sku=sku,
                    title_snapshot=str(item.get("title", "Meesho order item"))[:500],
                    quantity=quantity,
                    unit_price=unit,
                    total_price=unit * quantity,
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        else:
            existing_item.quantity = quantity
            existing_item.unit_price = unit
            existing_item.total_price = unit * quantity
            existing_item.updated_at = stamp
    fulfilment_id = value.get("fulfilment_id")
    if fulfilment_id:
        fulfilment = db.scalar(
            select(MarketplaceFulfilment).where(
                MarketplaceFulfilment.owner_id == account.owner_id,
                MarketplaceFulfilment.order_id == order.id,
                MarketplaceFulfilment.remote_fulfilment_id == str(fulfilment_id),
            )
        )
        if fulfilment is None:
            fulfilment = MarketplaceFulfilment(
                owner_id=account.owner_id,
                order_id=order.id,
                remote_fulfilment_id=str(fulfilment_id),
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(fulfilment)
        fulfilment.status = _fulfilment_status(value.get("fulfilment_status"))
        fulfilment.carrier = str(value.get("carrier")) if value.get("carrier") else None
        fulfilment.tracking_reference = (
            str(value.get("tracking_reference")) if value.get("tracking_reference") else None
        )
        fulfilment.updated_at = stamp
    return order


def import_order_events(
    db: Session, account: MarketplaceAccount, connector: MeeshoCommerceConnector
) -> dict[str, int]:
    orders = connector.get_orders()
    for value in orders:
        order = project_order(db, account, value)
        _remember_import(
            db,
            account,
            operation="order_import",
            key=str(value.get("remote_id", order.remote_order_id)),
            resource_type="marketplace_order",
            resource_id=order.id,
        )
    cancellations = 0
    for value in connector.get_cancellations():
        order = _order(db, account, str(value.get("order_id", "unknown-order")))
        reference = str(value.get("reference", "unknown-cancellation"))
        existing_cancellation = db.scalar(
            select(MarketplaceCancellation).where(
                MarketplaceCancellation.owner_id == account.owner_id,
                MarketplaceCancellation.order_id == order.id,
                MarketplaceCancellation.marketplace_reference == reference,
            )
        )
        if existing_cancellation is None:
            stamp = now()
            existing_cancellation = MarketplaceCancellation(
                owner_id=account.owner_id,
                order_id=order.id,
                reason=str(value.get("reason", "unknown"))[:240],
                quantity=int(value.get("quantity", 1)),
                requested_at=stamp,
                status=str(value.get("status", "requested")).casefold()[:30],
                marketplace_reference=reference,
                safe_notes="Imported from deterministic Meesho boundary.",
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(existing_cancellation)
            db.flush()
            cancellations += 1
        _remember_import(
            db,
            account,
            operation="cancellation_import",
            key=reference,
            resource_type="marketplace_cancellation",
            resource_id=existing_cancellation.id,
        )
    returns = 0
    refunds = 0
    for value in connector.get_returns():
        order = _order(db, account, str(value.get("order_id", "unknown-order")))
        reference = str(value.get("reference", "unknown-return"))
        existing_return = db.scalar(
            select(MarketplaceReturn).where(
                MarketplaceReturn.owner_id == account.owner_id,
                MarketplaceReturn.order_id == order.id,
                MarketplaceReturn.marketplace_reference == reference,
            )
        )
        amount = _decimal(value.get("refund_amount"))
        if existing_return is None:
            stamp = now()
            existing_return = MarketplaceReturn(
                owner_id=account.owner_id,
                order_id=order.id,
                reason=str(value.get("reason", "unknown"))[:240],
                quantity=int(value.get("quantity", 1)),
                requested_at=_parse_timestamp(value.get("requested_at"), stamp),
                status=str(value.get("status", "requested")).casefold()[:30],
                marketplace_reference=reference,
                refund_amount=amount,
                safe_notes="Imported from deterministic Meesho boundary.",
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(existing_return)
            db.flush()
            returns += 1
        _remember_import(
            db,
            account,
            operation="return_import",
            key=reference,
            resource_type="marketplace_return",
            resource_id=existing_return.id,
        )
    for value in connector.get_refunds():
        order = _order(db, account, str(value.get("order_id", "unknown-order")))
        reference = str(value.get("reference", "unknown-refund"))
        exists = db.scalar(
            select(MarketplaceRefund).where(
                MarketplaceRefund.owner_id == account.owner_id,
                MarketplaceRefund.order_id == order.id,
                MarketplaceRefund.marketplace_reference == reference,
            )
        )
        if exists is None:
            stamp = now()
            exists = MarketplaceRefund(
                owner_id=account.owner_id,
                order_id=order.id,
                amount=_decimal(value.get("amount")),
                currency=str(value.get("currency", "INR"))[:3].upper(),
                reason=str(value.get("reason", "Meesho refund"))[:240],
                status=str(value.get("status", "reported")).casefold()[:30],
                marketplace_reference=reference,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(exists)
            db.flush()
            refunds += 1
        _remember_import(
            db,
            account,
            operation="refund_import",
            key=reference,
            resource_type="marketplace_refund",
            resource_id=exists.id,
        )
    db.flush()
    return {
        "orders": len(orders),
        "cancellations": cancellations,
        "returns": returns,
        "refunds": refunds,
    }


def import_financials(
    db: Session, account: MarketplaceAccount, connector: MeeshoCommerceConnector
) -> dict[str, int]:
    stamp = now()
    settlements = 0
    lines = 0
    for value in connector.get_financial_events():
        remote_id = str(value.get("settlement_id", "unknown-settlement"))
        settlement = db.scalar(
            select(MarketplaceSettlement).where(
                MarketplaceSettlement.owner_id == account.owner_id,
                MarketplaceSettlement.account_id == account.id,
                MarketplaceSettlement.remote_settlement_id == remote_id,
            )
        )
        if settlement is None:
            fee_values = value.get("fees", [])
            if not isinstance(fee_values, list):
                fee_values = []
            settlement = MarketplaceSettlement(
                owner_id=account.owner_id,
                account_id=account.id,
                marketplace="meesho",
                remote_settlement_id=remote_id,
                period_start=_parse_timestamp(value.get("period_start"), stamp),
                period_end=_parse_timestamp(value.get("period_end"), stamp),
                status="settled",
                currency=str(value.get("currency", "INR"))[:3].upper(),
                gross_amount=_decimal(value.get("gross")),
                fee_amount=sum(
                    (_decimal(item.get("amount")) for item in fee_values if isinstance(item, dict)),
                    Decimal("0"),
                ),
                refund_amount=_decimal(value.get("refunds")),
                tax_withholding_amount=_decimal(value.get("withholding")),
                other_adjustment_amount=_decimal(value.get("adjustments")),
                net_amount=_decimal(value.get("net")),
                remote_generated_at=stamp,
                imported_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(settlement)
            db.flush()
            settlements += 1
        _remember_import(
            db,
            account,
            operation="settlement_import",
            key=remote_id,
            resource_type="marketplace_settlement",
            resource_id=settlement.id,
        )
        fee_items = value.get("fees", [])
        if not isinstance(fee_items, list):
            fee_items = []
        for fee in fee_items:
            if not isinstance(fee, dict):
                continue
            raw_type = str(fee.get("type", "other")).casefold()
            category = {
                "commission": "commission",
                "shipping_fee": "shipping",
                "fulfilment_fee": "fulfilment",
                "payment_fee": "payment",
                "tax": "tax",
                "withholding": "withholding",
                "refund": "refund",
            }.get(raw_type, "other")
            amount = _decimal(fee.get("amount"))
            existing = db.scalar(
                select(MarketplaceFee).where(
                    MarketplaceFee.owner_id == account.owner_id,
                    MarketplaceFee.account_id == account.id,
                    MarketplaceFee.settlement_id == settlement.id,
                    MarketplaceFee.fee_type == category,
                    MarketplaceFee.amount == amount,
                )
            )
            line = db.scalar(
                select(MarketplaceSettlementLine).where(
                    MarketplaceSettlementLine.owner_id == account.owner_id,
                    MarketplaceSettlementLine.settlement_id == settlement.id,
                    MarketplaceSettlementLine.line_type == category,
                    MarketplaceSettlementLine.amount == -amount,
                )
            )
            if existing is None:
                existing = MarketplaceFee(
                    owner_id=account.owner_id,
                    account_id=account.id,
                    settlement_id=settlement.id,
                    fee_type=category,
                    amount=amount,
                    currency=settlement.currency,
                    description="Meesho normalized financial event",
                    occurred_at=stamp,
                    created_at=stamp,
                    updated_at=stamp,
                )
                db.add(existing)
                db.flush()
                lines += 1
            if line is None:
                line = MarketplaceSettlementLine(
                    owner_id=account.owner_id,
                    settlement_id=settlement.id,
                    order_id=None,
                    line_type=category,
                    amount=-amount,
                    currency=settlement.currency,
                    description="Meesho normalized fee line",
                    created_at=stamp,
                    updated_at=stamp,
                )
                db.add(line)
            _remember_import(
                db,
                account,
                operation="fee_import",
                key=f"{remote_id}:{category}:{amount}",
                resource_type="marketplace_fee",
                resource_id=existing.id,
            )
    db.flush()
    return {"settlements": settlements, "lines": lines}


def profitability(db: Session, account: MarketplaceAccount) -> dict[str, object]:
    orders = list(
        db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.account_id == account.id))
    )
    fees = list(db.scalars(select(MarketplaceFee).where(MarketplaceFee.account_id == account.id)))
    refunds = list(
        db.scalars(
            select(MarketplaceRefund)
            .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceRefund.order_id)
            .where(MarketplaceOrder.account_id == account.id)
        )
    )
    gross = sum((_decimal(order.totals_json.get("total")) for order in orders), Decimal("0"))
    fee_total = sum((fee.amount for fee in fees), Decimal("0"))
    refund_total = sum((refund.amount for refund in refunds), Decimal("0"))
    cogs = Decimal("0")
    missing: list[str] = []
    for order in orders:
        for item in db.scalars(
            select(MarketplaceOrderItem).where(MarketplaceOrderItem.order_id == order.id)
        ):
            if item.product_id is None:
                missing.append("Product cost")
                continue
            product = db.get(Product, item.product_id)
            if product is None or product.cost_amount is None:
                missing.append("Product cost")
            else:
                cogs += product.cost_amount * item.quantity
    missing = sorted(set(missing))
    contribution = gross - refund_total - fee_total
    estimated = contribution - cogs if orders and not missing else None
    return {
        "gross_sales": gross,
        "refunds": refund_total,
        "fees": fee_total,
        "cogs": cogs if orders and not missing else None,
        "contribution": contribution,
        "estimated_profit": estimated,
        "profit_status": "available" if estimated is not None else "unavailable",
        "missing_inputs": missing or ([] if orders else ["orders"]),
        "accounting_semantics": (
            "Settlement net is not profit; contribution excludes unavailable inputs."
        ),
    }
