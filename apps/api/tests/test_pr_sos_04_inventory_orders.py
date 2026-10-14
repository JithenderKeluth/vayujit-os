"""PR-SOS-04 canonical inventory and local fake-order regression tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from vayujit_api.brands.models import Brand
from vayujit_api.commerce.models import (
    InventoryItem,
    InventoryMovement,
    InventoryReservation,
    MarketplaceAccount,
    MarketplaceOrderEvent,
)
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"


def _factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool),
        expire_on_commit=False,
    )


@pytest.fixture
def inventory_context(
    pr56_client: TestClient,
) -> Generator[tuple[TestClient, uuid.UUID, uuid.UUID], None, None]:
    setup = pr56_client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Inventory Owner",
            "email": "inventory-owner@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    with _factory()() as db:
        owner = db.query(User).one()
        stamp = now()
        brand_id = uuid.uuid4()
        brand = Brand(
            id=brand_id,
            owner_id=owner.id,
            name="Inventory Brand",
            normalized_name="inventory-brand",
            slug="inventory-brand",
            status="active",
            is_active_context=True,
            created_at=stamp,
            updated_at=stamp,
        )
        product = Product(
            owner_id=owner.id,
            brand_id=brand_id,
            name="Canonical Stock Product",
            normalized_name="canonical-stock-product",
            slug="canonical-stock-product",
            sku="STOCK-001",
            product_type="physical",
            status="active",
            category="Kids",
            inventory_quantity=0,
            low_stock_threshold=1,
            inventory_tracking_enabled=True,
            is_featured=False,
            created_at=stamp,
            updated_at=stamp,
        )
        account = MarketplaceAccount(
            owner_id=owner.id,
            marketplace="amazon",
            display_name="Local Amazon",
            seller_account_id="local-amazon",
            environment="sandbox",
            enabled=True,
            credential_status="configured",
            validation_status="valid",
            capabilities_json={"fake_provider": True},
            configuration_json={},
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(brand)
        db.flush()
        db.add_all([product, account])
        db.flush()
        product_id, account_id = product.id, account.id
        db.commit()
    yield pr56_client, product_id, account_id


def test_inventory_reservation_idempotency_and_version_guard(inventory_context) -> None:
    client, product_id, _account_id = inventory_context
    created = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "STOCK-001",
            "opening_quantity": 5,
            "low_stock_threshold": 1,
            "idempotency_key": "opening-1",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    item = created.json()
    replay = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "STOCK-001",
            "opening_quantity": 5,
            "low_stock_threshold": 1,
            "idempotency_key": "opening-1",
        },
        headers=ORIGIN,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == item["id"]
    reserved = client.post(
        f"/api/v1/inventory/{item['id']}/reserve",
        json={"order_line_key": "manual-line-1", "quantity": 3, "idempotency_key": "reserve-1"},
        headers=ORIGIN,
    )
    assert reserved.status_code == 201, reserved.text
    assert reserved.json()["state"] == "active"
    reserve_replay = client.post(
        f"/api/v1/inventory/{item['id']}/reserve",
        json={"order_line_key": "manual-line-1", "quantity": 3, "idempotency_key": "reserve-1"},
        headers=ORIGIN,
    )
    assert reserve_replay.status_code == 201
    assert reserve_replay.json()["id"] == reserved.json()["id"]
    stale = client.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={
            "delta": 1,
            "reason": "late receipt",
            "expected_version": 1,
            "idempotency_key": "adjust-1",
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409, stale.text
    released = client.post(
        f"/api/v1/inventory/reservations/{reserved.json()['id']}/release",
        headers=ORIGIN,
    )
    assert released.status_code == 200, released.text
    assert released.json()["state"] == "released"


def test_fake_order_reserves_atomically_and_rejects_oversell(inventory_context) -> None:
    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "ORDER-001",
            "opening_quantity": 3,
            "idempotency_key": "order-opening",
        },
        headers=ORIGIN,
    ).json()
    mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-ORDER-001",
            "idempotency_key": "mapping-1",
        },
        headers=ORIGIN,
    )
    assert mapping.status_code == 201, mapping.text
    created = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-1",
            "event_id": "EVENT-1",
            "event_type": "new_order",
            "event_version": 1,
            "lines": [{"external_sku": "AMZ-ORDER-001", "quantity": 1, "unit_price": "99.00"}],
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    assert created.json()["reservation_state"] == "active"
    replay = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-1",
            "event_id": "EVENT-1",
            "event_type": "new_order",
            "event_version": 1,
            "lines": [{"external_sku": "AMZ-ORDER-001", "quantity": 1, "unit_price": "99.00"}],
        },
        headers=ORIGIN,
    )
    assert replay.status_code == 200, replay.text
    oversell = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-2",
            "event_id": "EVENT-2",
            "event_type": "new_order",
            "event_version": 1,
            "lines": [
                {"external_sku": "AMZ-ORDER-001", "quantity": 2, "unit_price": "99.00"},
                {"external_sku": "AMZ-ORDER-001", "quantity": 2, "unit_price": "99.00"},
            ],
        },
        headers=ORIGIN,
    )
    assert oversell.status_code == 409, oversell.text
    cancelled = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-1",
            "event_id": "EVENT-3",
            "event_type": "cancel",
            "event_version": 2,
        },
        headers=ORIGIN,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    returned_order = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-3",
            "event_id": "EVENT-4",
            "event_type": "new_order",
            "event_version": 1,
            "lines": [{"external_sku": "AMZ-ORDER-001", "quantity": 1, "unit_price": "99.00"}],
        },
        headers=ORIGIN,
    )
    assert returned_order.status_code == 201, returned_order.text
    returned = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-3",
            "event_id": "EVENT-5",
            "event_type": "return",
            "event_version": 2,
        },
        headers=ORIGIN,
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["reservation_state"] == "released"
    old_event = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "ORDER-1",
            "event_id": "EVENT-OLD",
            "event_type": "ship",
            "event_version": 1,
        },
        headers=ORIGIN,
    )
    assert old_event.status_code == 409, old_event.text


def test_two_fake_orders_competing_for_final_unit_are_serialized(inventory_context) -> None:
    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "RACE-001",
            "opening_quantity": 1,
            "idempotency_key": "race-opening",
        },
        headers=ORIGIN,
    ).json()
    mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-RACE-001",
            "idempotency_key": "race-mapping",
        },
        headers=ORIGIN,
    )
    assert mapping.status_code == 201, mapping.text

    def place(index: int):
        return client.post(
            "/api/v1/orders/fake/events",
            json={
                "account_id": str(account_id),
                "external_order_id": f"RACE-ORDER-{index}",
                "event_id": f"RACE-EVENT-{index}",
                "event_type": "new_order",
                "event_version": 1,
                "lines": [{"external_sku": "AMZ-RACE-001", "quantity": 1, "unit_price": "1.00"}],
            },
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(place, (1, 2)))
    assert sorted(response.status_code for response in responses) == [201, 409]


def test_pr_sos04_concurrency_matrix_preserves_canonical_stock(inventory_context) -> None:
    """Certify multi-unit, adjustment, duplicate-event, and cross-channel races."""

    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "MATRIX-001",
            "opening_quantity": 5,
            "idempotency_key": "matrix-opening",
        },
        headers=ORIGIN,
    ).json()
    amazon_mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-MATRIX-001",
            "idempotency_key": "matrix-amazon-mapping",
        },
        headers=ORIGIN,
    )
    assert amazon_mapping.status_code == 201, amazon_mapping.text

    def place_multi(quantity: int) -> object:
        return client.post(
            "/api/v1/orders/fake/events",
            json={
                "account_id": str(account_id),
                "external_order_id": f"MATRIX-{quantity}",
                "event_id": f"MATRIX-EVENT-{quantity}",
                "event_type": "new_order",
                "event_version": 1,
                "lines": [
                    {"external_sku": "AMZ-MATRIX-001", "quantity": quantity, "unit_price": "1.00"}
                ],
            },
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        multi_unit = list(pool.map(place_multi, (3, 4)))
    assert sorted(response.status_code for response in multi_unit) == [201, 409]
    after_multi = client.get("/api/v1/inventory", headers=ORIGIN).json()
    matrix_after_multi = next(row for row in after_multi if row["id"] == item["id"])
    assert 0 <= matrix_after_multi["available_to_promise"] <= 2
    assert matrix_after_multi["reserved_quantity"] in {3, 4}

    # A stale HUMAN adjustment may lose the race, but it cannot violate the
    # row-version guard or make the reservation balance negative.
    def adjust() -> object:
        return client.post(
            f"/api/v1/inventory/{item['id']}/adjust",
            json={
                "delta": 1,
                "reason": "concurrent receipt",
                "expected_version": 2,
                "idempotency_key": "matrix-adjustment",
            },
            headers=ORIGIN,
        )

    def reserve() -> object:
        return client.post(
            f"/api/v1/inventory/{item['id']}/reserve",
            json={
                "order_line_key": "matrix-manual-line",
                "quantity": 1,
                "idempotency_key": "matrix-reservation",
            },
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        adjustment_and_reservation = list(pool.map(lambda fn: fn(), (adjust, reserve)))
    assert sorted(response.status_code for response in adjustment_and_reservation) in (
        [200, 201],
        [201, 409],
    )
    final_item = client.get("/api/v1/inventory", headers=ORIGIN).json()
    matrix_final = next(row for row in final_item if row["id"] == item["id"])
    assert matrix_final["available_to_promise"] >= 0

    # A second marketplace account mapped to the same internal item shares the
    # canonical pool. Use a fresh two-unit item so both channel reservations
    # can succeed while still proving they consume one shared balance.
    channel_item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "CHANNEL-001",
            "opening_quantity": 2,
            "idempotency_key": "channel-opening",
        },
        headers=ORIGIN,
    ).json()
    amazon_channel_mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": channel_item["id"],
            "external_sku": "AMZ-CHANNEL-001",
            "idempotency_key": "matrix-amazon-channel-mapping",
        },
        headers=ORIGIN,
    )
    assert amazon_channel_mapping.status_code == 201, amazon_channel_mapping.text
    with _factory()() as db:
        owner = db.query(User).one()
        stamp = now()
        flipkart = MarketplaceAccount(
            owner_id=owner.id,
            marketplace="flipkart",
            display_name="Local Flipkart",
            seller_account_id="local-flipkart",
            environment="sandbox",
            enabled=True,
            credential_status="configured",
            validation_status="valid",
            capabilities_json={"fake_provider": True},
            configuration_json={},
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(flipkart)
        db.commit()
        flipkart_id = flipkart.id
    flipkart_mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(flipkart_id),
            "inventory_item_id": channel_item["id"],
            "external_sku": "FK-MATRIX-001",
            "idempotency_key": "matrix-flipkart-mapping",
        },
        headers=ORIGIN,
    )
    assert flipkart_mapping.status_code == 201, flipkart_mapping.text

    def place_channel(args: tuple[uuid.UUID, str, str]) -> object:
        channel_account, external_sku, suffix = args
        return client.post(
            "/api/v1/orders/fake/events",
            json={
                "account_id": str(channel_account),
                "external_order_id": f"CHANNEL-{suffix}",
                "event_id": f"CHANNEL-EVENT-{suffix}",
                "event_type": "new_order",
                "event_version": 1,
                "lines": [{"external_sku": external_sku, "quantity": 1, "unit_price": "1.00"}],
            },
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        channel_orders = list(
            pool.map(
                place_channel,
                ((account_id, "AMZ-CHANNEL-001", "AMZ"), (flipkart_id, "FK-MATRIX-001", "FK")),
            )
        )
    assert [response.status_code for response in channel_orders] == [201, 201]
    combined = client.get("/api/v1/inventory", headers=ORIGIN).json()
    channel_combined = next(row for row in combined if row["id"] == channel_item["id"])
    assert channel_combined["reserved_quantity"] == 2
    assert channel_combined["available_to_promise"] == 0


def test_pr_sos04_duplicate_provider_event_is_exactly_once(inventory_context) -> None:
    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "DUPLICATE-001",
            "opening_quantity": 2,
            "idempotency_key": "duplicate-opening",
        },
        headers=ORIGIN,
    ).json()
    mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-DUPLICATE-001",
            "idempotency_key": "duplicate-mapping",
        },
        headers=ORIGIN,
    )
    assert mapping.status_code == 201, mapping.text
    payload = {
        "account_id": str(account_id),
        "external_order_id": "DUPLICATE-ORDER",
        "event_id": "DUPLICATE-EVENT",
        "event_type": "new_order",
        "event_version": 1,
        "lines": [{"external_sku": "AMZ-DUPLICATE-001", "quantity": 1, "unit_price": "5.00"}],
    }

    def submit() -> object:
        return client.post("/api/v1/orders/fake/events", json=payload, headers=ORIGIN)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _index: submit(), (1, 2)))
    assert sorted(response.status_code for response in responses) == [200, 201]
    orders = client.get("/api/v1/orders", headers=ORIGIN).json()
    assert len(orders) == 1
    ledger = client.get(f"/api/v1/inventory/{item['id']}/ledger", headers=ORIGIN).json()
    assert [row["movement_type"] for row in ledger].count("reservation") == 1
    with _factory()() as db:
        events = db.query(MarketplaceOrderEvent).all()
        assert len(events) == 1
        assert events[0].status in {"applied", "duplicate"}
        reservations = db.query(InventoryReservation).all()
        assert len(reservations) == 1


def test_pr_sos04_mapping_rejects_conflicting_sku_for_same_account_item(inventory_context) -> None:
    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "MAP-CONFLICT-001",
            "opening_quantity": 1,
            "idempotency_key": "map-conflict-opening",
        },
        headers=ORIGIN,
    ).json()
    first = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-MAP-CONFLICT-001",
            "idempotency_key": "map-conflict-first",
        },
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    conflicting = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-MAP-CONFLICT-002",
            "idempotency_key": "map-conflict-second",
        },
        headers=ORIGIN,
    )
    assert conflicting.status_code == 409, conflicting.text
    assert "already maps this inventory item" in conflicting.json()["detail"]


def test_pr_sos04_multiline_failure_and_ledger_reconstruction(inventory_context) -> None:
    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "LEDGER-001",
            "opening_quantity": 3,
            "idempotency_key": "ledger-opening",
        },
        headers=ORIGIN,
    ).json()
    mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-LEDGER-001",
            "idempotency_key": "ledger-mapping",
        },
        headers=ORIGIN,
    )
    assert mapping.status_code == 201, mapping.text
    failed = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "LEDGER-ORDER",
            "event_id": "LEDGER-EVENT",
            "event_type": "new_order",
            "event_version": 1,
            "lines": [
                {"external_sku": "AMZ-LEDGER-001", "quantity": 2, "unit_price": "1.00"},
                {"external_sku": "AMZ-LEDGER-001", "quantity": 2, "unit_price": "1.00"},
            ],
        },
        headers=ORIGIN,
    )
    assert failed.status_code == 409, failed.text
    current = client.get("/api/v1/inventory", headers=ORIGIN).json()[0]
    assert current["reserved_quantity"] == 0
    assert current["on_hand_quantity"] == 3
    positive = client.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={
            "delta": 2,
            "reason": "receipt",
            "expected_version": 1,
            "idempotency_key": "ledger-receipt",
        },
        headers=ORIGIN,
    )
    assert positive.status_code == 200, positive.text
    negative = client.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={
            "delta": -1,
            "reason": "cycle count",
            "expected_version": 2,
            "idempotency_key": "ledger-adjustment",
        },
        headers=ORIGIN,
    )
    assert negative.status_code == 200, negative.text
    invalid = client.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={
            "delta": -20,
            "reason": "invalid",
            "expected_version": 3,
            "idempotency_key": "ledger-invalid",
        },
        headers=ORIGIN,
    )
    assert invalid.status_code == 409, invalid.text
    missing_reason = client.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={
            "delta": 1,
            "reason": "",
            "expected_version": 3,
            "idempotency_key": "ledger-missing-reason",
        },
        headers=ORIGIN,
    )
    assert missing_reason.status_code == 422, missing_reason.text
    ledger = client.get(f"/api/v1/inventory/{item['id']}/ledger", headers=ORIGIN).json()
    assert [row["movement_type"] for row in ledger].count("opening_balance") == 1
    assert [row["movement_type"] for row in ledger].count("adjustment") == 2
    assert all(row["actor_type"] == "HUMAN" for row in ledger)
    reconstructed = sum(row["quantity"] for row in ledger)
    assert reconstructed == negative.json()["on_hand_quantity"]
    with _factory()() as db:
        persisted = db.query(InventoryItem).filter(InventoryItem.id == item["id"]).one()
        movements = (
            db.query(InventoryMovement)
            .filter(InventoryMovement.inventory_item_id == item["id"])
            .all()
        )
        assert persisted.on_hand_quantity == reconstructed
        assert len(movements) == 3


def test_pr_sos04_invalid_lifecycle_transitions_require_reconciliation(inventory_context) -> None:
    client, product_id, account_id = inventory_context
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": str(product_id),
            "internal_sku": "STATE-001",
            "opening_quantity": 2,
            "idempotency_key": "state-opening",
        },
        headers=ORIGIN,
    ).json()
    mapping = client.post(
        "/api/v1/inventory/mappings",
        json={
            "account_id": str(account_id),
            "inventory_item_id": item["id"],
            "external_sku": "AMZ-STATE-001",
            "idempotency_key": "state-mapping",
        },
        headers=ORIGIN,
    )
    assert mapping.status_code == 201, mapping.text

    def order(order_id: str, event_id: str) -> object:
        return client.post(
            "/api/v1/orders/fake/events",
            json={
                "account_id": str(account_id),
                "external_order_id": order_id,
                "event_id": event_id,
                "event_type": "new_order",
                "event_version": 1,
                "lines": [{"external_sku": "AMZ-STATE-001", "quantity": 1, "unit_price": "1.00"}],
            },
            headers=ORIGIN,
        )

    first = order("STATE-CANCEL", "STATE-CANCEL-1")
    assert first.status_code == 201, first.text
    cancelled = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "STATE-CANCEL",
            "event_id": "STATE-CANCEL-2",
            "event_type": "cancel",
            "event_version": 2,
        },
        headers=ORIGIN,
    )
    assert cancelled.status_code == 200, cancelled.text
    ship_cancelled = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "STATE-CANCEL",
            "event_id": "STATE-CANCEL-3",
            "event_type": "ship",
            "event_version": 3,
        },
        headers=ORIGIN,
    )
    assert ship_cancelled.status_code == 409, ship_cancelled.text
    second = order("STATE-SHIP", "STATE-SHIP-1")
    assert second.status_code == 201, second.text
    shipped = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "STATE-SHIP",
            "event_id": "STATE-SHIP-2",
            "event_type": "ship",
            "event_version": 2,
        },
        headers=ORIGIN,
    )
    assert shipped.status_code == 200, shipped.text
    cancel_shipped = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "STATE-SHIP",
            "event_id": "STATE-SHIP-3",
            "event_type": "cancel",
            "event_version": 3,
        },
        headers=ORIGIN,
    )
    assert cancel_shipped.status_code == 409, cancel_shipped.text
    duplicate_ship = client.post(
        "/api/v1/orders/fake/events",
        json={
            "account_id": str(account_id),
            "external_order_id": "STATE-SHIP",
            "event_id": "STATE-SHIP-4",
            "event_type": "ship",
            "event_version": 3,
        },
        headers=ORIGIN,
    )
    assert duplicate_ship.status_code == 200, duplicate_ship.text
    assert duplicate_ship.json()["status"] == "shipped"
    reconciliation = client.get(
        "/api/v1/orders/reconciliation/summary",
        headers=ORIGIN,
    )
    assert reconciliation.status_code == 200, reconciliation.text
    assert reconciliation.json()["stale_provider_events"] >= 2
