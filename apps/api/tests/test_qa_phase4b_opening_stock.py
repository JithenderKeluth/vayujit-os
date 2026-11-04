"""Opening stock: real HTTP authorities, persisted disposable PostgreSQL only."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
BASE = "/api/v1/inventory"


@pytest.fixture
def ctx(pr56_client: TestClient) -> dict[str, Any]:
    c = pr56_client
    r = c.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "[QA SYNTHETIC] Stock owner",
            "email": "qa4b@example.com",
            "password": "SyntheticPhase4BOnly123!",
            "password_confirmation": "SyntheticPhase4BOnly123!",
        },
        headers=ORIGIN,
    )
    assert r.status_code == 201, r.text
    r = c.post(
        "/api/v1/brands", json={"name": "[QA SYNTHETIC] Stock", "slug": "qa4b"}, headers=ORIGIN
    )
    assert r.status_code == 201, r.text
    brand = r.json()["id"]
    r = c.post(
        "/api/v1/products",
        json={
            "name": "[QA SYNTHETIC] Counted product",
            "sku": "QA4B",
            "brand_id": brand,
            "product_type": "physical",
        },
        headers=ORIGIN,
    )
    assert r.status_code == 201, r.text
    return {"c": c, "product": r.json(), "brand": brand}


def payload(ctx: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "product_id": ctx["product"]["id"],
        "variant_id": None,
        "internal_sku": "QA4B",
        "location_code": "default",
        "unit": "each",
        "opening_quantity": 12,
        "low_stock_threshold": 3,
        "idempotency_key": "qa4b-opening",
        **changes,
    }


def post(ctx: dict[str, Any], **changes: Any) -> Any:
    return ctx["c"].post(BASE + "/items", json=payload(ctx, **changes), headers=ORIGIN)


def rows(sql: str, **params: Any) -> list[Any]:
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    try:
        with engine.connect() as db:
            return list(db.execute(text(sql), params).mappings())
    finally:
        engine.dispose()


@pytest.mark.parametrize("quantity", [0, 12, 2_000_000_000])
def test_opening_persists_ledger_audit_and_does_not_invent_cost(
    ctx: dict[str, Any], quantity: int
) -> None:
    r = post(ctx, opening_quantity=quantity)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["on_hand_quantity"] == item["available_to_promise"] == quantity
    assert item["reserved_quantity"] == item["damaged_quantity"] == 0
    assert item["version"] == 1
    assert ctx["c"].get(BASE).json() == [item]
    ledger = ctx["c"].get(f"{BASE}/{item['id']}/ledger").json()
    assert len(ledger) == 1
    assert ledger[0]["movement_type"] == "opening_balance"
    assert ledger[0]["actor_type"] == "HUMAN"
    assert ledger[0]["quantity"] == quantity
    assert (
        len(
            rows(
                "select * from audit_events where action='inventory.opening_balance_created' "
                "and entity_id=:id",
                id=item["id"],
            )
        )
        == 1
    )
    product = ctx["c"].get(f"/api/v1/products/{item['product_id']}").json()
    assert product["inventory_quantity"] == ctx["product"]["inventory_quantity"]
    assert product["cost_amount"] is None


@pytest.mark.parametrize("quantity", [-1, 0.5, True, "12", 2_000_000_001, None])
def test_invalid_quantity_is_not_coerced(ctx: dict[str, Any], quantity: Any) -> None:
    assert post(ctx, opening_quantity=quantity).status_code == 422
    assert ctx["c"].get(BASE).json() == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("internal_sku", " "),
        ("location_code", " "),
        ("unit", " "),
        ("actor_type", "HUMAN"),
        ("source_reference", "fake-approved"),
        ("low_stock_threshold", False),
    ],
)
def test_invalid_or_impersonated_inputs_fail_closed(
    ctx: dict[str, Any], field: str, value: Any
) -> None:
    assert post(ctx, **{field: value}).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("opening_quantity", 13),
        ("internal_sku", "OTHER"),
        ("location_code", "warehouse"),
        ("unit", "pack"),
        ("low_stock_threshold", 4),
        ("product_id", str(uuid.UUID(int=1))),
        ("variant_id", str(uuid.UUID(int=2))),
    ],
)
def test_conflicting_key_cannot_create_another_opening(
    ctx: dict[str, Any], field: str, value: Any
) -> None:
    assert post(ctx).status_code == 201
    assert post(ctx, **{field: value}).status_code == 409
    assert len(ctx["c"].get(BASE).json()) == 1


def test_identical_replay_after_adjustment_preserves_original_movement(ctx: dict[str, Any]) -> None:
    r = post(ctx, internal_sku=" QA4B ", location_code=" default ", unit=" each ")
    assert r.status_code == 201, r.text
    item = r.json()
    changed = ctx["c"].post(
        f"{BASE}/{item['id']}/adjust",
        json={
            "delta": 2,
            "reason": "[QA SYNTHETIC] Later receipt",
            "expected_version": 1,
            "idempotency_key": "later",
        },
        headers=ORIGIN,
    )
    assert changed.status_code == 200, changed.text
    replay = post(ctx)
    assert replay.status_code == 201
    assert replay.json()["id"] == item["id"]
    assert replay.json()["on_hand_quantity"] == 14
    assert len(ctx["c"].get(f"{BASE}/{item['id']}/ledger").json()) == 2
    assert post(ctx, idempotency_key="different").status_code == 409
    assert (
        post(
            ctx, location_code="separate-counted-location", idempotency_key="other-location"
        ).status_code
        == 201
    )


@pytest.mark.parametrize("mode", ["identical", "different_keys", "conflict"])
def test_concurrent_confirmations_are_atomic(ctx: dict[str, Any], mode: str) -> None:
    def create(index: int) -> Any:
        changes = (
            {"idempotency_key": f"key-{index}"}
            if mode == "different_keys"
            else {"opening_quantity": 12 + index} if mode == "conflict" else {}
        )
        return post(ctx, **changes)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(create, range(2)))
    assert sorted(r.status_code for r in responses) == (
        [201, 201] if mode == "identical" else [201, 409]
    )
    assert len(ctx["c"].get(BASE).json()) == 1
    assert len(rows("select * from inventory_movements where movement_type='opening_balance'")) == 1
    assert (
        len(rows("select * from audit_events where action='inventory.opening_balance_created'"))
        == 1
    )


@pytest.mark.parametrize("kind", ["digital", "service", "affiliate", "archived", "missing"])
def test_unavailable_product_rejected_at_confirmation(ctx: dict[str, Any], kind: str) -> None:
    if kind == "missing":
        ctx["product"]["id"] = str(uuid.uuid4())
    elif kind == "archived":
        r = ctx["c"].post(f"/api/v1/products/{ctx['product']['id']}/archive", headers=ORIGIN)
        assert r.status_code == 200, r.text
    else:
        r = ctx["c"].patch(
            f"/api/v1/products/{ctx['product']['id']}",
            json={"product_type": kind},
            headers=ORIGIN,
        )
        assert r.status_code == 200, r.text
    assert post(ctx).status_code == (404 if kind == "missing" else 409)
    assert ctx["c"].get(BASE).json() == []


def test_unauthenticated_and_unknown_contexts(ctx: dict[str, Any]) -> None:
    assert post(ctx, variant_id=str(uuid.uuid4())).status_code == 404
    assert ctx["c"].get(f"{BASE}/{uuid.uuid4()}/ledger").status_code == 404
    ctx["c"].post("/api/v1/auth/logout", headers=ORIGIN)
    assert post(ctx).status_code == 401
    assert ctx["c"].get(BASE).status_code == 401


@pytest.mark.parametrize("kind", ["valid", "archived", "wrong_product"])
def test_variant_scope_and_eligibility(ctx: dict[str, Any], kind: str) -> None:
    c = ctx["c"]
    r = c.post(
        f"/api/v1/catalog/products/{ctx['product']['id']}/variants",
        json={"variant_key": "blue", "title": "[QA SYNTHETIC] Blue", "sku": "QA4B-BLUE"},
        headers=ORIGIN,
    )
    assert r.status_code == 201, r.text
    variant = r.json()
    if kind == "archived":
        r = c.patch(
            f"/api/v1/catalog/variants/{variant['id']}",
            json={
                "variant_key": "blue",
                "title": variant["title"],
                "sku": variant["sku"],
                "version": variant["version"],
                "status": "archived",
            },
            headers=ORIGIN,
        )
        assert r.status_code == 200, r.text
    if kind == "wrong_product":
        r = c.post(
            "/api/v1/products",
            json={
                "brand_id": ctx["brand"],
                "name": "[QA SYNTHETIC] Another",
                "product_type": "physical",
                "sku": "QA4B-OTHER",
            },
            headers=ORIGIN,
        )
        assert r.status_code == 201, r.text
        ctx["product"] = r.json()
    opened = post(ctx, variant_id=variant["id"], internal_sku="QA4B-BLUE")
    assert opened.status_code == {"valid": 201, "archived": 409, "wrong_product": 404}[kind]
    if kind == "valid":
        assert opened.json()["variant_id"] == variant["id"]
        assert (
            post(ctx, variant_id=variant["id"], internal_sku="QA4B-BLUE").json()["id"]
            == opened.json()["id"]
        )


def test_opening_lock_compatibility_with_catalog_audit_foreign_key(ctx: dict[str, Any]) -> None:
    """Creation must serialize itself without deadlocking a catalog FK check.

    Hold an existing Product row read-lock, as a catalog update would, while the
    canonical opening waits for that row. A concurrent audit FK check requires
    KEY SHARE on User and must not be blocked by the opening's serialization lock.
    No business state is seeded or changed through SQL.
    """
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    waiting_for_product = threading.Event()

    def observe(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        if "FROM products" in statement and "FOR UPDATE" in statement:
            waiting_for_product.set()

    executor = ThreadPoolExecutor(max_workers=1)
    future = None
    try:
        with engine.begin() as catalog_transaction:
            catalog_transaction.execute(
                text("select id from products where id=:id for update"),
                {"id": ctx["product"]["id"]},
            )
            event.listen(Engine, "before_cursor_execute", observe)
            future = executor.submit(post, ctx)
            assert waiting_for_product.wait(10), "Canonical opening did not reach Product lock"
            with engine.begin() as audit_check:
                audit_check.execute(text("set local lock_timeout = '2s'"))
                audit_check.execute(text("select id from users for key share"))
        assert future.result(timeout=10).status_code == 201
        assert len(ctx["c"].get(BASE).json()) == 1
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
        executor.shutdown(wait=True)
        engine.dispose()
