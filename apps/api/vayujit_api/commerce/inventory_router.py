"""Canonical owner-scoped inventory, ledger, reservation, and SKU mapping API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.catalog.models import CatalogProductVariant
from vayujit_api.commerce.models import (
    ChannelSkuMapping,
    InventoryItem,
    InventoryMovement,
    InventoryReservation,
    MarketplaceAccount,
)
from vayujit_api.commerce.schemas import (
    ChannelSkuMappingCreate,
    ChannelSkuMappingResponse,
    InventoryAdjustmentRequest,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryMovementResponse,
    InventoryReservationResponse,
    InventoryReserveRequest,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _item(db: Session, owner: User, item_id: uuid.UUID, *, lock: bool = False) -> InventoryItem:
    statement = select(InventoryItem).where(
        InventoryItem.id == item_id, InventoryItem.owner_id == owner.id
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise HTTPException(404, "Inventory item was not found.")
    return row


def _response(row: InventoryItem) -> InventoryItemResponse:
    return InventoryItemResponse(
        id=row.id,
        product_id=row.product_id,
        variant_id=row.variant_id,
        internal_sku=row.internal_sku,
        location_code=row.location_code,
        unit=row.unit,
        on_hand_quantity=row.on_hand_quantity,
        reserved_quantity=row.reserved_quantity,
        damaged_quantity=row.damaged_quantity,
        available_to_promise=max(
            0, row.on_hand_quantity - row.reserved_quantity - row.damaged_quantity
        ),
        low_stock_threshold=row.low_stock_threshold,
        version=row.version,
        last_reconciled_at=row.last_reconciled_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _movement_response(row: InventoryMovement) -> InventoryMovementResponse:
    return InventoryMovementResponse.model_validate(row, from_attributes=True)


def _reservation(
    db: Session, owner: User, reservation_id: uuid.UUID, *, lock: bool = False
) -> InventoryReservation:
    statement = select(InventoryReservation).where(
        InventoryReservation.id == reservation_id,
        InventoryReservation.owner_id == owner.id,
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise HTTPException(404, "Inventory reservation was not found.")
    return row


@router.get("", response_model=list[InventoryItemResponse])
def list_inventory(
    db: DatabaseSession,
    user: Owner,
    sku: str | None = None,
    low_stock: bool = False,
) -> list[InventoryItemResponse]:
    statement = select(InventoryItem).where(InventoryItem.owner_id == user.id)
    if sku:
        statement = statement.where(InventoryItem.internal_sku.ilike(f"%{sku}%"))
    rows = db.scalars(
        statement.order_by(InventoryItem.internal_sku, InventoryItem.location_code)
    ).all()
    if low_stock:
        rows = [
            row
            for row in rows
            if row.on_hand_quantity - row.reserved_quantity - row.damaged_quantity
            <= row.low_stock_threshold
        ]
    return [_response(row) for row in rows]


@router.post("/items", response_model=InventoryItemResponse, status_code=201)
def create_inventory_item(
    data: InventoryItemCreate, db: DatabaseSession, user: Owner
) -> InventoryItemResponse:
    # A creation key identifies one immutable opening intent for this owner,
    # including SKU/location. Serialize only this short local creation transaction
    # on the existing owner row; no new ownership or approval authority.
    # PostgreSQL FOR NO KEY UPDATE: serialize creators, but permit the KEY SHARE
    # FK checks used by concurrent catalog/audit writes. FOR UPDATE can deadlock
    # those writers when they already hold the Product row we need next.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update(key_share=True))
    intent = data.model_dump(mode="json", exclude={"idempotency_key"})
    duplicates = list(
        db.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.owner_id == user.id,
                InventoryMovement.movement_type == "opening_balance",
                InventoryMovement.idempotency_key == data.idempotency_key,
            )
            .limit(2)
        )
    )
    if duplicates:
        if len(duplicates) != 1:
            raise HTTPException(409, "This historical opening key is ambiguous; review the ledger.")
        movement = duplicates[0]
        replay_item = _item(db, user, movement.inventory_item_id)
        original = movement.provenance_json.get("opening_intent")
        if original is None:
            # Legacy openings have no intent envelope. Their original quantity is
            # the movement, not today's possibly adjusted balance.
            original = {
                "product_id": str(replay_item.product_id),
                "variant_id": str(replay_item.variant_id) if replay_item.variant_id else None,
                "internal_sku": replay_item.internal_sku,
                "location_code": replay_item.location_code,
                "unit": replay_item.unit,
                "opening_quantity": movement.quantity,
                "low_stock_threshold": replay_item.low_stock_threshold,
            }
        if original != intent or movement.actor_type != "HUMAN" or movement.actor_id != user.id:
            raise HTTPException(
                409, "Idempotency key belongs to a different opening stock request."
            )
        return _response(replay_item)
    product = db.scalar(
        select(Product)
        .where(Product.id == data.product_id, Product.owner_id == user.id)
        .with_for_update()
    )
    if product is None:
        raise HTTPException(404, "Product was not found.")
    if product.product_type != "physical" or product.status == "archived":
        raise HTTPException(409, "Opening stock requires a non-archived physical catalog product.")
    if data.variant_id:
        variant = db.scalar(
            select(CatalogProductVariant)
            .where(
                CatalogProductVariant.id == data.variant_id,
                CatalogProductVariant.owner_id == user.id,
                CatalogProductVariant.product_id == data.product_id,
            )
            .with_for_update()
        )
        if variant is None:
            raise HTTPException(404, "Catalog variant was not found for this product.")
        if variant.status == "archived":
            raise HTTPException(
                409, "This catalog variant is archived; choose an available variant."
            )
    existing = db.scalar(
        select(InventoryItem).where(
            InventoryItem.owner_id == user.id,
            InventoryItem.internal_sku == data.internal_sku,
            InventoryItem.location_code == data.location_code,
        )
    )
    if existing is not None:
        raise HTTPException(409, "An inventory item already exists for this SKU and location.")
    stamp = now()
    row = InventoryItem(
        owner_id=user.id,
        product_id=data.product_id,
        variant_id=data.variant_id,
        internal_sku=data.internal_sku.strip(),
        location_code=data.location_code.strip(),
        unit=data.unit.strip(),
        on_hand_quantity=data.opening_quantity,
        reserved_quantity=0,
        damaged_quantity=0,
        low_stock_threshold=data.low_stock_threshold,
        version=1,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    db.add(
        InventoryMovement(
            owner_id=user.id,
            inventory_item_id=row.id,
            location_code=row.location_code,
            quantity=data.opening_quantity,
            movement_type="opening_balance",
            source_reference="human-opening-balance",
            actor_type="HUMAN",
            actor_id=user.id,
            idempotency_key=data.idempotency_key,
            reason="Opening balance",
            before_on_hand=0,
            after_on_hand=data.opening_quantity,
            before_reserved=0,
            after_reserved=0,
            provenance_json={
                "mode": "LOCAL_READ_ONLY",
                "synthetic": False,
                "opening_intent": intent,
            },
            created_at=stamp,
            updated_at=stamp,
        )
    )
    record_event(
        db,
        actor_id=user.id,
        action="inventory.opening_balance_created",
        entity_type="inventory_item",
        entity_id=row.id,
        metadata={"sku": row.internal_sku, "quantity": data.opening_quantity},
    )
    db.commit()
    return _response(row)


@router.post("/{item_id}/adjust", response_model=InventoryItemResponse)
def adjust_inventory(
    item_id: uuid.UUID,
    data: InventoryAdjustmentRequest,
    db: DatabaseSession,
    user: Owner,
) -> InventoryItemResponse:
    row = _item(db, user, item_id, lock=True)
    duplicate = db.scalar(
        select(InventoryMovement).where(
            InventoryMovement.owner_id == user.id,
            InventoryMovement.inventory_item_id == row.id,
            InventoryMovement.idempotency_key == data.idempotency_key,
        )
    )
    if duplicate is not None:
        if (
            duplicate.movement_type != "adjustment"
            or duplicate.quantity != data.delta
            or duplicate.reason != data.reason
            or duplicate.actor_type != "HUMAN"
            or duplicate.actor_id != user.id
            or (
                duplicate.provenance_json.get("expected_version") is not None
                and duplicate.provenance_json["expected_version"] != data.expected_version
            )
        ):
            raise HTTPException(409, "Idempotency key belongs to a different stock adjustment.")
        return _response(row)
    if row.version != data.expected_version:
        raise HTTPException(409, "Inventory changed; refresh before adjusting stock.")
    before = row.on_hand_quantity
    after = before + data.delta
    if after < row.reserved_quantity + row.damaged_quantity:
        raise HTTPException(409, "Adjustment would make available stock negative.")
    row.on_hand_quantity = after
    row.version += 1
    row.updated_at = now()
    stamp = now()
    db.add(
        InventoryMovement(
            owner_id=user.id,
            inventory_item_id=row.id,
            location_code=row.location_code,
            quantity=data.delta,
            movement_type="adjustment",
            source_reference="human-adjustment",
            actor_type="HUMAN",
            actor_id=user.id,
            idempotency_key=data.idempotency_key,
            reason=data.reason,
            before_on_hand=before,
            after_on_hand=after,
            before_reserved=row.reserved_quantity,
            after_reserved=row.reserved_quantity,
            provenance_json={"mode": "LOCAL_READ_ONLY", "expected_version": data.expected_version},
            created_at=stamp,
            updated_at=stamp,
        )
    )
    record_event(
        db,
        actor_id=user.id,
        action="inventory.human_adjustment",
        entity_type="inventory_item",
        entity_id=row.id,
        metadata={"delta": data.delta, "reason": data.reason},
    )
    db.commit()
    return _response(row)


@router.get("/{item_id}/ledger", response_model=list[InventoryMovementResponse])
def inventory_ledger(
    item_id: uuid.UUID, db: DatabaseSession, user: Owner, limit: int = Query(100, ge=1, le=500)
) -> list[InventoryMovementResponse]:
    _item(db, user, item_id)
    rows = db.scalars(
        select(InventoryMovement)
        .where(
            InventoryMovement.owner_id == user.id, InventoryMovement.inventory_item_id == item_id
        )
        .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
        .limit(limit)
    ).all()
    return [_movement_response(row) for row in rows]


@router.get("/mappings", response_model=list[ChannelSkuMappingResponse])
def list_mappings(db: DatabaseSession, user: Owner) -> list[ChannelSkuMappingResponse]:
    rows = db.scalars(
        select(ChannelSkuMapping)
        .where(ChannelSkuMapping.owner_id == user.id)
        .order_by(ChannelSkuMapping.marketplace, ChannelSkuMapping.external_sku)
    ).all()
    return [ChannelSkuMappingResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/mappings", response_model=ChannelSkuMappingResponse, status_code=201)
def create_mapping(
    data: ChannelSkuMappingCreate, db: DatabaseSession, user: Owner
) -> ChannelSkuMappingResponse:
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == data.account_id, MarketplaceAccount.owner_id == user.id
        )
    )
    item = _item(db, user, data.inventory_item_id)
    if account is None:
        raise HTTPException(404, "Marketplace account was not found.")
    if data.listing_id:
        from vayujit_api.commerce.models import MarketplaceListing

        listing = db.scalar(
            select(MarketplaceListing).where(
                MarketplaceListing.id == data.listing_id,
                MarketplaceListing.owner_id == user.id,
                MarketplaceListing.account_id == account.id,
            )
        )
        if listing is None:
            raise HTTPException(404, "Listing was not found for this account.")
    existing = db.scalar(
        select(ChannelSkuMapping).where(
            ChannelSkuMapping.owner_id == user.id,
            ChannelSkuMapping.account_id == account.id,
            ChannelSkuMapping.external_sku == data.external_sku,
        )
    )
    if existing:
        if existing.inventory_item_id != item.id:
            raise HTTPException(409, "This channel SKU is mapped to a different inventory item.")
        return ChannelSkuMappingResponse.model_validate(existing, from_attributes=True)
    existing_item_mapping = db.scalar(
        select(ChannelSkuMapping).where(
            ChannelSkuMapping.owner_id == user.id,
            ChannelSkuMapping.account_id == account.id,
            ChannelSkuMapping.inventory_item_id == item.id,
        )
    )
    if existing_item_mapping:
        raise HTTPException(
            409,
            "This marketplace account already maps this inventory item to "
            f"{existing_item_mapping.external_sku}.",
        )
    stamp = now()
    row = ChannelSkuMapping(
        owner_id=user.id,
        inventory_item_id=item.id,
        account_id=account.id,
        marketplace=account.marketplace,
        external_sku=data.external_sku.strip(),
        listing_id=data.listing_id,
        status="active",
        effective_version=1,
        provenance_json={"mode": "LOCAL_READ_ONLY", "human_configured": True},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=user.id,
        action="inventory.channel_sku_mapped",
        entity_type="channel_sku_mapping",
        entity_id=row.id,
        metadata={"marketplace": account.marketplace, "external_sku": row.external_sku},
    )
    db.commit()
    return ChannelSkuMappingResponse.model_validate(row, from_attributes=True)


@router.get("/{item_id}/reservations", response_model=list[InventoryReservationResponse])
def item_reservations(
    item_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[InventoryReservationResponse]:
    _item(db, user, item_id)
    rows = db.scalars(
        select(InventoryReservation)
        .where(
            InventoryReservation.owner_id == user.id,
            InventoryReservation.inventory_item_id == item_id,
        )
        .order_by(InventoryReservation.created_at.desc())
    ).all()
    return [InventoryReservationResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/{item_id}/reserve", response_model=InventoryReservationResponse, status_code=201)
def reserve_inventory(
    item_id: uuid.UUID,
    data: InventoryReserveRequest,
    db: DatabaseSession,
    user: Owner,
) -> InventoryReservationResponse:
    """Reserve ATP under a row lock; this endpoint never calls a marketplace."""
    item = _item(db, user, item_id, lock=True)
    duplicate = db.scalar(
        select(InventoryReservation).where(
            InventoryReservation.owner_id == user.id,
            InventoryReservation.inventory_item_id == item.id,
            InventoryReservation.idempotency_key == data.idempotency_key,
        )
    )
    if duplicate is not None:
        return InventoryReservationResponse.model_validate(duplicate, from_attributes=True)
    if data.order_id:
        from vayujit_api.commerce.models import MarketplaceOrder

        order = db.scalar(
            select(MarketplaceOrder).where(
                MarketplaceOrder.id == data.order_id,
                MarketplaceOrder.owner_id == user.id,
            )
        )
        if order is None:
            raise HTTPException(404, "Order was not found for this reservation.")
    line = db.scalar(
        select(InventoryReservation).where(
            InventoryReservation.owner_id == user.id,
            InventoryReservation.inventory_item_id == item.id,
            InventoryReservation.order_line_key == data.order_line_key,
            InventoryReservation.state == "active",
        )
    )
    if line is not None:
        raise HTTPException(409, "This order line already has an active reservation.")
    available = item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity
    if available < data.quantity:
        raise HTTPException(409, "Insufficient available stock for this reservation.")
    stamp = now()
    before_reserved = item.reserved_quantity
    item.reserved_quantity += data.quantity
    item.version += 1
    item.updated_at = stamp
    reservation = InventoryReservation(
        owner_id=user.id,
        inventory_item_id=item.id,
        order_id=data.order_id,
        order_line_key=data.order_line_key,
        quantity=data.quantity,
        state="active",
        idempotency_key=data.idempotency_key,
        source_event_id=data.source_event_id,
        provenance_json={"mode": "LOCAL_READ_ONLY", "human_requested": True},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(reservation)
    db.flush()
    db.add(
        InventoryMovement(
            owner_id=user.id,
            inventory_item_id=item.id,
            location_code=item.location_code,
            quantity=0,
            movement_type="reservation",
            source_reference=data.source_event_id,
            actor_type="HUMAN",
            actor_id=user.id,
            idempotency_key=f"movement:{data.idempotency_key}",
            reason="Human reservation",
            before_on_hand=item.on_hand_quantity,
            after_on_hand=item.on_hand_quantity,
            before_reserved=before_reserved,
            after_reserved=item.reserved_quantity,
            provenance_json={"mode": "LOCAL_READ_ONLY"},
            created_at=stamp,
            updated_at=stamp,
        )
    )
    record_event(
        db,
        actor_id=user.id,
        action="inventory.reservation_created",
        entity_type="inventory_reservation",
        entity_id=reservation.id,
        metadata={"quantity": data.quantity, "synthetic": False},
    )
    db.commit()
    return InventoryReservationResponse.model_validate(reservation, from_attributes=True)


def _transition_reservation(
    reservation_id: uuid.UUID,
    target_state: str,
    db: Session,
    user: User,
) -> InventoryReservationResponse:
    reservation = _reservation(db, user, reservation_id, lock=True)
    if reservation.state == target_state:
        return InventoryReservationResponse.model_validate(reservation, from_attributes=True)
    if reservation.state != "active":
        raise HTTPException(409, "Only an active reservation can be transitioned.")
    item = _item(db, user, reservation.inventory_item_id, lock=True)
    stamp = now()
    before_reserved = item.reserved_quantity
    if before_reserved < reservation.quantity:
        raise HTTPException(409, "Reservation balance requires reconciliation.")
    item.reserved_quantity -= reservation.quantity
    if target_state == "consumed":
        if item.on_hand_quantity < reservation.quantity:
            raise HTTPException(409, "Reservation cannot be consumed without on-hand stock.")
        item.on_hand_quantity -= reservation.quantity
        movement_type = "shipment"
    else:
        movement_type = "reservation_release"
    item.version += 1
    item.updated_at = stamp
    reservation.state = target_state
    reservation.released_at = stamp if target_state == "released" else None
    reservation.consumed_at = stamp if target_state == "consumed" else None
    reservation.updated_at = stamp
    db.add(
        InventoryMovement(
            owner_id=user.id,
            inventory_item_id=item.id,
            location_code=item.location_code,
            quantity=-reservation.quantity if target_state == "consumed" else 0,
            movement_type=movement_type,
            source_reference=str(reservation.id),
            actor_type="HUMAN",
            actor_id=user.id,
            idempotency_key=f"transition:{reservation.id}:{target_state}",
            reason=f"Human reservation {target_state}",
            before_on_hand=item.on_hand_quantity
            + (reservation.quantity if target_state == "consumed" else 0),
            after_on_hand=item.on_hand_quantity,
            before_reserved=before_reserved,
            after_reserved=item.reserved_quantity,
            provenance_json={"mode": "LOCAL_READ_ONLY"},
            created_at=stamp,
            updated_at=stamp,
        )
    )
    record_event(
        db,
        actor_id=user.id,
        action=f"inventory.reservation_{target_state}",
        entity_type="inventory_reservation",
        entity_id=reservation.id,
        metadata={"quantity": reservation.quantity},
    )
    db.commit()
    return InventoryReservationResponse.model_validate(reservation, from_attributes=True)


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=InventoryReservationResponse,
)
def release_reservation(
    reservation_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> InventoryReservationResponse:
    return _transition_reservation(reservation_id, "released", db, user)


@router.post(
    "/reservations/{reservation_id}/consume",
    response_model=InventoryReservationResponse,
)
def consume_reservation(
    reservation_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> InventoryReservationResponse:
    return _transition_reservation(reservation_id, "consumed", db, user)
