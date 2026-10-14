"""Unified order ingestion and local reservation lifecycle.

The fake event endpoint is intentionally explicit and visibly synthetic. It never
calls a marketplace transport.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.commerce.models import (
    ChannelSkuMapping,
    InventoryItem,
    InventoryMovement,
    InventoryReservation,
    MarketplaceAccount,
    MarketplaceOrder,
    MarketplaceOrderEvent,
    MarketplaceOrderItem,
)
from vayujit_api.commerce.schemas import (
    FakeOrderEventRequest,
    ReconciliationResponse,
    UnifiedOrderResponse,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _order(db: Session, user: User, order_id: uuid.UUID, *, lock: bool = False) -> MarketplaceOrder:
    statement = select(MarketplaceOrder).where(
        MarketplaceOrder.id == order_id, MarketplaceOrder.owner_id == user.id
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise HTTPException(404, "Order was not found.")
    return row


def _reservation_state(db: Session, user: User, order: MarketplaceOrder) -> str:
    states = set(
        db.scalars(
            select(InventoryReservation.state).where(
                InventoryReservation.owner_id == user.id,
                InventoryReservation.order_id == order.id,
            )
        ).all()
    )
    if order.status == "failed":
        return "failed"
    if "active" in states:
        return "active"
    if "consumed" in states:
        return "consumed"
    if "released" in states:
        return "released"
    return "none"


def _response(db: Session, user: User, order: MarketplaceOrder) -> UnifiedOrderResponse:
    count = (
        db.scalar(
            select(func.count(MarketplaceOrderItem.id)).where(
                MarketplaceOrderItem.owner_id == user.id, MarketplaceOrderItem.order_id == order.id
            )
        )
        or 0
    )
    return UnifiedOrderResponse(
        id=order.id,
        account_id=order.account_id,
        marketplace=order.marketplace,
        remote_order_id=order.remote_order_id,
        status=order.status,
        fulfilment_status=order.fulfilment_status,
        reservation_state=_reservation_state(db, user, order),
        line_count=int(count),
        fake_provider=True,
        ordered_at=order.ordered_at,
    )


def _account(db: Session, user: User, account_id: uuid.UUID) -> MarketplaceAccount:
    row = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id, MarketplaceAccount.owner_id == user.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace account was not found.")
    return row


def _event_version(db: Session, account_id: uuid.UUID, remote_order_id: str) -> int:
    value = db.scalar(
        select(func.max(MarketplaceOrderEvent.event_version)).where(
            MarketplaceOrderEvent.account_id == account_id,
            MarketplaceOrderEvent.remote_order_id == remote_order_id,
        )
    )
    return int(value or 0)


_LIFECYCLE_TARGET_STATUS = {
    "cancel": "cancelled",
    "ship": "shipped",
    "return": "returned",
}
_LIFECYCLE_ALLOWED_FROM = {
    "cancel": {"pending", "confirmed", "processing"},
    "ship": {"pending", "confirmed", "processing"},
    # A return is allowed for an unshipped synthetic order as well as a
    # shipped/delivered order.  In both cases the canonical model records the
    # return disposition without restocking sellable inventory.
    "return": {"pending", "confirmed", "processing", "shipped", "delivered"},
}


def _movement(
    db: Session,
    user: User,
    item: InventoryItem,
    *,
    movement_type: str,
    source_reference: str,
    idempotency_key: str,
    reason: str,
    before_on_hand: int,
    after_on_hand: int,
    before_reserved: int,
    after_reserved: int,
) -> None:
    stamp = now()
    db.add(
        InventoryMovement(
            owner_id=user.id,
            inventory_item_id=item.id,
            location_code=item.location_code,
            quantity=after_on_hand - before_on_hand,
            movement_type=movement_type,
            source_reference=source_reference,
            actor_type="SYSTEM",
            actor_id=user.id,
            idempotency_key=idempotency_key,
            reason=reason,
            before_on_hand=before_on_hand,
            after_on_hand=after_on_hand,
            before_reserved=before_reserved,
            after_reserved=after_reserved,
            provenance_json={"mode": "LIVE_READ_ONLY", "fake_provider": True},
            created_at=stamp,
            updated_at=stamp,
        )
    )


@router.get("", response_model=list[UnifiedOrderResponse])
def list_orders(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[UnifiedOrderResponse]:
    statement = select(MarketplaceOrder).where(MarketplaceOrder.owner_id == user.id)
    if marketplace:
        statement = statement.where(MarketplaceOrder.marketplace == marketplace)
    if status:
        statement = statement.where(MarketplaceOrder.status == status)
    rows = db.scalars(statement.order_by(MarketplaceOrder.ordered_at.desc()).limit(limit)).all()
    return [_response(db, user, row) for row in rows]


@router.get("/reconciliation/summary", response_model=ReconciliationResponse)
def reconciliation_summary(db: DatabaseSession, user: Owner) -> ReconciliationResponse:
    items = db.scalars(select(InventoryItem).where(InventoryItem.owner_id == user.id)).all()
    active = (
        db.scalar(
            select(func.count(InventoryReservation.id)).where(
                InventoryReservation.owner_id == user.id, InventoryReservation.state == "active"
            )
        )
        or 0
    )
    failures = (
        db.scalar(
            select(func.count(MarketplaceOrderEvent.id)).where(
                MarketplaceOrderEvent.owner_id == user.id,
                MarketplaceOrderEvent.status.in_(["rejected", "reconciliation_required"]),
            )
        )
        or 0
    )
    unmapped_lines = (
        db.scalar(
            select(func.count(MarketplaceOrderItem.id)).where(
                MarketplaceOrderItem.owner_id == user.id,
                MarketplaceOrderItem.product_id.is_(None),
            )
        )
        or 0
    )
    stale_events = (
        db.scalar(
            select(func.count(MarketplaceOrderEvent.id)).where(
                MarketplaceOrderEvent.owner_id == user.id,
                MarketplaceOrderEvent.status == "reconciliation_required",
            )
        )
        or 0
    )
    actions: list[str] = []
    if any(
        item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity
        <= item.low_stock_threshold
        for item in items
    ):
        actions.append("Review low-stock inventory and reservations.")
    if failures:
        actions.append("Review rejected or reconciliation-required provider events.")
    if unmapped_lines:
        actions.append("Resolve order lines that are missing canonical product mappings.")
    if stale_events:
        actions.append("Reconcile provider events that arrived out of order or conflicted.")
    if not actions:
        actions.append("No inventory exception requires action.")
    return ReconciliationResponse(
        inventory_items=len(items),
        low_stock_items=sum(
            1
            for item in items
            if item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity
            <= item.low_stock_threshold
        ),
        out_of_stock_items=sum(
            1
            for item in items
            if item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity <= 0
        ),
        active_reservations=int(active),
        reservation_failures=int(failures),
        unmapped_order_lines=int(unmapped_lines),
        stale_provider_events=int(stale_events),
        next_actions=actions,
    )


@router.get("/insights", response_model=ReconciliationResponse)
def business_agent_insights(db: DatabaseSession, user: Owner) -> ReconciliationResponse:
    """Read-only evidence projection for Business Agent guidance."""
    return reconciliation_summary(db, user)


@router.get("/{order_id}", response_model=UnifiedOrderResponse)
def get_order(order_id: uuid.UUID, db: DatabaseSession, user: Owner) -> UnifiedOrderResponse:
    return _response(db, user, _order(db, user, order_id))


@router.post("/fake/events", response_model=UnifiedOrderResponse, status_code=201)
def ingest_fake_event(
    data: FakeOrderEventRequest, db: DatabaseSession, user: Owner, response: Response
) -> UnifiedOrderResponse:
    # Serialize provider events per account before checking event/order
    # idempotency.  A unique event constraint protects the final write, but it
    # is not enough on its own: two concurrent deliveries of the same event
    # could both pass the preflight lookup and one would otherwise surface as
    # an IntegrityError (500) instead of an idempotent replay.  The account is
    # the canonical owner-scoped lock for all fake-provider events; inventory
    # rows remain the finer-grained overselling lock below.
    account = db.scalar(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.id == data.account_id, MarketplaceAccount.owner_id == user.id)
        .with_for_update()
    )
    if account is None:
        raise HTTPException(404, "Marketplace account was not found.")
    duplicate = db.scalar(
        select(MarketplaceOrderEvent).where(
            MarketplaceOrderEvent.owner_id == user.id,
            MarketplaceOrderEvent.account_id == account.id,
            MarketplaceOrderEvent.event_id == data.event_id,
        )
    )
    existing_order = db.scalar(
        select(MarketplaceOrder).where(
            MarketplaceOrder.owner_id == user.id,
            MarketplaceOrder.account_id == account.id,
            MarketplaceOrder.remote_order_id == data.external_order_id,
        )
    )
    if duplicate is not None and existing_order is not None:
        duplicate.status = "duplicate"
        db.commit()
        response.status_code = 200
        return _response(db, user, existing_order)
    latest = _event_version(db, account.id, data.external_order_id)
    if data.event_version < latest:
        stamp = now()
        db.add(
            MarketplaceOrderEvent(
                owner_id=user.id,
                account_id=account.id,
                marketplace=account.marketplace,
                event_id=data.event_id,
                remote_order_id=data.external_order_id,
                event_type=data.event_type,
                event_version=data.event_version,
                payload_json=data.model_dump(mode="json"),
                status="reconciliation_required",
                error_message="Older event cannot overwrite a newer order state.",
                observed_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()
        raise HTTPException(409, "Out-of-order event requires reconciliation.")
    stamp = now()
    event = MarketplaceOrderEvent(
        owner_id=user.id,
        account_id=account.id,
        marketplace=account.marketplace,
        event_id=data.event_id,
        remote_order_id=data.external_order_id,
        event_type=data.event_type,
        event_version=data.event_version,
        payload_json=data.model_dump(mode="json"),
        status="received",
        observed_at=stamp,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(event)
    if data.event_version == latest and existing_order is not None:
        # Equal-version deliveries are safe only when they describe the
        # already materialized state.  Treat those as idempotent duplicates;
        # a conflicting equal-version event is retained as a reconciliation
        # signal and cannot mutate the order.
        target_status = _LIFECYCLE_TARGET_STATUS.get(data.event_type)
        if data.event_type == "new_order" or target_status == existing_order.status:
            event.status = "duplicate"
            db.commit()
            response.status_code = 200
            return _response(db, user, existing_order)
        event.status = "reconciliation_required"
        event.error_message = "Equal-version provider event conflicts with the current order state."
        db.commit()
        raise HTTPException(409, "Conflicting provider event requires reconciliation.")
    if data.event_type == "new_order" and existing_order is not None:
        event.status = "duplicate"
        db.commit()
        response.status_code = 200
        return _response(db, user, existing_order)
    if data.event_type == "new_order":
        if not data.lines:
            raise HTTPException(422, "A new order must contain at least one line.")
        mappings = []
        for line in data.lines:
            mapping = db.scalar(
                select(ChannelSkuMapping).where(
                    ChannelSkuMapping.owner_id == user.id,
                    ChannelSkuMapping.account_id == account.id,
                    ChannelSkuMapping.external_sku == line.external_sku,
                    ChannelSkuMapping.status == "active",
                )
            )
            if mapping is None:
                event.status = "rejected"
                event.error_message = f"No active mapping for {line.external_sku}."
                db.commit()
                raise HTTPException(409, "Order contains an unmapped channel SKU.")
            mappings.append(mapping)
        items = [
            db.scalar(
                select(InventoryItem)
                .where(
                    InventoryItem.id == mapping.inventory_item_id, InventoryItem.owner_id == user.id
                )
                .with_for_update()
            )
            for mapping in mappings
        ]
        if any(item is None for item in items):
            raise HTTPException(409, "Order mapping references missing inventory.")
        assert all(item is not None for item in items)
        required_by_item: dict[uuid.UUID, int] = {}
        for line, item in zip(data.lines, items, strict=True):
            assert item is not None
            required_by_item[item.id] = required_by_item.get(item.id, 0) + line.quantity
        for item in items:
            assert item is not None
            available = item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity
            if available < required_by_item[item.id]:
                event.status = "rejected"
                event.error_message = f"Insufficient stock for {item.internal_sku}."
                db.commit()
                raise HTTPException(409, "Insufficient stock; no reservation was created.")
        total = sum((line.unit_price * line.quantity for line in data.lines), Decimal("0"))
        order = MarketplaceOrder(
            owner_id=user.id,
            account_id=account.id,
            marketplace=account.marketplace,
            remote_order_id=data.external_order_id,
            status="pending",
            payment_status="unknown",
            fulfilment_status="unfulfilled",
            buyer_snapshot_json={"display_name": "Masked buyer"},
            totals_json={"total": str(total), "currency": "INR", "fake_provider": True},
            ordered_at=stamp,
            remote_raw_status="NEW_ORDER",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(order)
        db.flush()
        for index, (line, item) in enumerate(zip(data.lines, items, strict=True)):
            assert item is not None
            line_key = f"{data.external_order_id}:{index}"
            db.add(
                MarketplaceOrderItem(
                    owner_id=user.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    marketplace_sku=line.external_sku,
                    title_snapshot="Synthetic order item",
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    total_price=line.unit_price * line.quantity,
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            before_reserved = item.reserved_quantity
            item.reserved_quantity += line.quantity
            item.version += 1
            item.updated_at = stamp
            reservation_key = f"fake-order:{data.event_id}:{index}"
            db.add(
                InventoryReservation(
                    owner_id=user.id,
                    inventory_item_id=item.id,
                    order_id=order.id,
                    order_line_key=line_key,
                    quantity=line.quantity,
                    state="active",
                    idempotency_key=reservation_key,
                    source_event_id=data.event_id,
                    provenance_json={"fake_provider": True, "event_id": data.event_id},
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            _movement(
                db,
                user,
                item,
                movement_type="reservation",
                source_reference=data.event_id,
                idempotency_key=f"movement:{reservation_key}",
                reason="Synthetic marketplace order reservation",
                before_on_hand=item.on_hand_quantity,
                after_on_hand=item.on_hand_quantity,
                before_reserved=before_reserved,
                after_reserved=item.reserved_quantity,
            )
        event.status = "applied"
        db.flush()
        record_event(
            db,
            actor_id=user.id,
            action="orders.fake_event_applied",
            entity_type="marketplace_order",
            entity_id=order.id,
            metadata={"event_id": data.event_id, "synthetic": True},
        )
        db.commit()
        return _response(db, user, order)
    if existing_order is None:
        event.status = "rejected"
        event.error_message = "Lifecycle event references an unknown order."
        db.commit()
        raise HTTPException(404, "Order was not found for this lifecycle event.")
    locked_order = db.scalar(
        select(MarketplaceOrder).where(MarketplaceOrder.id == existing_order.id).with_for_update()
    )
    assert locked_order is not None
    allowed_from = _LIFECYCLE_ALLOWED_FROM[data.event_type]
    if locked_order.status not in allowed_from:
        event.status = "reconciliation_required"
        event.error_message = (
            f"Cannot apply {data.event_type} from canonical order state {locked_order.status}."
        )
        db.commit()
        raise HTTPException(409, "Provider event conflicts with the canonical order state.")
    reservations = db.scalars(
        select(InventoryReservation)
        .where(
            InventoryReservation.owner_id == user.id,
            InventoryReservation.order_id == locked_order.id,
            InventoryReservation.state == "active",
        )
        .with_for_update()
    ).all()
    if data.event_type == "cancel":
        for reservation in reservations:
            item = db.scalar(
                select(InventoryItem)
                .where(InventoryItem.id == reservation.inventory_item_id)
                .with_for_update()
            )
            if item is None:
                continue
            before_reserved = item.reserved_quantity
            item.reserved_quantity -= reservation.quantity
            item.version += 1
            item.updated_at = stamp
            reservation.state = "released"
            reservation.released_at = stamp
            reservation.updated_at = stamp
            _movement(
                db,
                user,
                item,
                movement_type="reservation_release",
                source_reference=data.event_id,
                idempotency_key=f"movement:{data.event_id}:{reservation.id}",
                reason=data.reason or "Synthetic cancellation",
                before_on_hand=item.on_hand_quantity,
                after_on_hand=item.on_hand_quantity,
                before_reserved=before_reserved,
                after_reserved=item.reserved_quantity,
            )
        locked_order.status = "cancelled"
        locked_order.fulfilment_status = "cancelled"
    elif data.event_type == "ship":
        for reservation in reservations:
            item = db.scalar(
                select(InventoryItem)
                .where(InventoryItem.id == reservation.inventory_item_id)
                .with_for_update()
            )
            if item is None or item.on_hand_quantity < reservation.quantity:
                event.status = "reconciliation_required"
                event.error_message = "Shipment cannot be applied without sufficient on-hand stock."
                db.commit()
                raise HTTPException(409, "Shipment requires reconciliation.")
            before_on_hand, before_reserved = item.on_hand_quantity, item.reserved_quantity
            item.on_hand_quantity -= reservation.quantity
            item.reserved_quantity -= reservation.quantity
            item.version += 1
            item.updated_at = stamp
            reservation.state = "consumed"
            reservation.consumed_at = stamp
            reservation.updated_at = stamp
            _movement(
                db,
                user,
                item,
                movement_type="shipment",
                source_reference=data.event_id,
                idempotency_key=f"movement:{data.event_id}:{reservation.id}",
                reason="Synthetic shipment consumption",
                before_on_hand=before_on_hand,
                after_on_hand=item.on_hand_quantity,
                before_reserved=before_reserved,
                after_reserved=item.reserved_quantity,
            )
        locked_order.status = "shipped"
        locked_order.fulfilment_status = "shipped"
    else:  # return: release the hold, but do not silently restock sellable inventory.
        for reservation in reservations:
            item = db.scalar(
                select(InventoryItem)
                .where(InventoryItem.id == reservation.inventory_item_id)
                .with_for_update()
            )
            if item is None:
                continue
            before_reserved = item.reserved_quantity
            item.reserved_quantity -= reservation.quantity
            item.version += 1
            item.updated_at = stamp
            reservation.state = "released"
            reservation.released_at = stamp
            reservation.updated_at = stamp
            _movement(
                db,
                user,
                item,
                movement_type="reservation_release",
                source_reference=data.event_id,
                idempotency_key=f"movement:{data.event_id}:{reservation.id}",
                reason=data.reason or "Synthetic return pending physical receipt",
                before_on_hand=item.on_hand_quantity,
                after_on_hand=item.on_hand_quantity,
                before_reserved=before_reserved,
                after_reserved=item.reserved_quantity,
            )
        locked_order.status = "returned"
        locked_order.fulfilment_status = "returned"
    locked_order.updated_at = stamp
    event.status = "applied"
    db.commit()
    response.status_code = 200
    return _response(db, user, locked_order)
