"""Focused PR-SOS-06 operational signal and Action Center regressions."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from vayujit_api.brands.models import Brand
from vayujit_api.commerce.models import InventoryItem, MarketplaceAccount, MarketplaceOrder
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
def action_context(pr56_client: TestClient) -> Generator[tuple[TestClient, uuid.UUID], None, None]:
    setup = pr56_client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Action Center Owner",
            "email": "action-center-owner@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    with _factory()() as db:
        owner = db.query(User).one()
        stamp = now()
        brand = Brand(
            owner_id=owner.id,
            name="Action Brand",
            normalized_name="action-brand",
            slug="action-brand",
            status="active",
            is_active_context=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(brand)
        db.flush()
        product = Product(
            owner_id=owner.id,
            brand_id=brand.id,
            name="Action Product",
            normalized_name="action-product",
            slug="action-product",
            sku="ACTION-001",
            product_type="physical",
            status="active",
            category="Kids",
            created_at=stamp,
            updated_at=stamp,
        )
        account = MarketplaceAccount(
            owner_id=owner.id,
            marketplace="amazon",
            display_name="Action Amazon",
            seller_account_id="action-amazon",
            environment="sandbox",
            enabled=True,
            credential_status="configured",
            validation_status="valid",
            capabilities_json={"fake_provider": True},
            configuration_json={"currency": "INR"},
            created_at=stamp,
            updated_at=stamp,
        )
        db.add_all([product, account])
        db.flush()
        db.add(
            InventoryItem(
                owner_id=owner.id,
                product_id=product.id,
                internal_sku="ACTION-001",
                location_code="default",
                unit="each",
                on_hand_quantity=0,
                reserved_quantity=0,
                damaged_quantity=0,
                low_stock_threshold=5,
                version=1,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            MarketplaceOrder(
                owner_id=owner.id,
                account_id=account.id,
                marketplace="amazon",
                remote_order_id="ACTION-ORDER-1",
                status="failed",
                payment_status="unknown",
                fulfilment_status="unfulfilled",
                ordered_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()
        yield pr56_client, owner.id


def test_scan_projects_owner_scoped_signals_and_is_idempotent(action_context) -> None:
    client, _owner_id = action_context
    first = client.post("/api/v1/operations/action-center/scan", headers=ORIGIN)
    assert first.status_code == 200, first.text
    assert first.json()["external_writes"] is False
    listed = client.get("/api/v1/operations/action-center", headers=ORIGIN)
    assert listed.status_code == 200, listed.text
    signals = listed.json()["signals"]
    assert {item["category"] for item in signals} >= {"inventory", "orders"}
    count = listed.json()["total"]
    second = client.post("/api/v1/operations/action-center/scan", headers=ORIGIN)
    assert second.status_code == 200
    assert client.get("/api/v1/operations/action-center", headers=ORIGIN).json()["total"] == count


def test_signal_lifecycle_idempotency_and_snooze_expiry(action_context) -> None:
    client, _owner_id = action_context
    client.post("/api/v1/operations/action-center/scan", headers=ORIGIN)
    signal = client.get("/api/v1/operations/action-center", headers=ORIGIN).json()["signals"][0]
    signal_id = signal["id"]
    acknowledge = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/acknowledge",
        json={"idempotency_key": "ack-action-001"},
        headers=ORIGIN,
    )
    assert acknowledge.status_code == 200
    replay = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/acknowledge",
        json={"idempotency_key": "ack-action-001"},
        headers=ORIGIN,
    )
    assert replay.status_code == 200
    snooze = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/snooze",
        json={"until": "2099-01-01T00:00:00Z", "idempotency_key": "snooze-action-001"},
        headers=ORIGIN,
    )
    assert snooze.status_code == 200 and snooze.json()["signal"]["status"] == "SNOOZED"
    resolved = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/resolve",
        json={"idempotency_key": "resolve-action-001"},
        headers=ORIGIN,
    )
    assert resolved.status_code == 200 and resolved.json()["signal"]["status"] == "RESOLVED"
    detail = client.get(f"/api/v1/operations/action-center/signals/{signal_id}", headers=ORIGIN)
    assert detail.status_code == 200 and detail.json()["history"]


def test_policy_default_dry_run_and_external_actions_fail_closed(action_context) -> None:
    client, _owner_id = action_context
    policy = client.get("/api/v1/operations/action-center/policy", headers=ORIGIN)
    assert policy.status_code == 200
    assert policy.json()["dry_run"] is True and policy.json()["emergency_stop"] is False
    client.post("/api/v1/operations/action-center/scan", headers=ORIGIN)
    signal_id = client.get("/api/v1/operations/action-center", headers=ORIGIN).json()["signals"][0][
        "id"
    ]
    ai = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/action",
        json={"action_type": "review", "actor_type": "AI", "idempotency_key": "ai-action-001"},
        headers=ORIGIN,
    )
    assert ai.status_code == 403
    external = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/action",
        json={
            "action_type": "PUBLISH",
            "actor_type": "HUMAN",
            "idempotency_key": "publish-action-001",
        },
        headers=ORIGIN,
    )
    assert external.status_code == 403
    allowed = client.post(
        f"/api/v1/operations/action-center/signals/{signal_id}/action",
        json={
            "action_type": "refresh_projection",
            "actor_type": "HUMAN",
            "idempotency_key": "refresh-action-001",
        },
        headers=ORIGIN,
    )
    assert allowed.status_code == 200 and allowed.json()["external_writes"] is False


def test_unauthenticated_action_center_is_rejected() -> None:
    from fastapi.testclient import TestClient

    from vayujit_api.main import create_app

    response = TestClient(create_app()).get("/api/v1/operations/action-center", headers=ORIGIN)
    assert response.status_code == 401
