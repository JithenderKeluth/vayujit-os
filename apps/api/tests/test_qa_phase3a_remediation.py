"""Bounded Phase 3A regressions: canonical HTTP authorities, disposable PG only."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
ACTION = "/api/v1/operations/action-center"


@pytest.fixture
def ctx(pr56_client: TestClient) -> dict[str, Any]:
    client = pr56_client
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "[QA SYNTHETIC] Remediation Owner",
            "email": "qa3a@example.com",
            "password": "SyntheticPhase3AOnly123!",
            "password_confirmation": "SyntheticPhase3AOnly123!",
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201
    brand = client.post(
        "/api/v1/brands",
        json={"name": "[QA SYNTHETIC] Remediation", "slug": "qa3a-remediation"},
        headers=ORIGIN,
    )
    assert brand.status_code == 201, brand.text
    product = client.post(
        "/api/v1/products",
        json={
            "name": "[QA SYNTHETIC] Regression",
            "brand_id": brand.json()["id"],
            "product_type": "physical",
            "sku": "QA3A",
            "price_amount": "100.00",
            "price_currency": "INR",
            "cost_amount": "50.00",
        },
        headers=ORIGIN,
    )
    assert product.status_code == 201, product.text
    account = client.post(
        "/api/v1/marketplaces/accounts",
        json={
            "marketplace": "amazon",
            "display_name": "[QA SYNTHETIC] Amazon",
            "seller_account_id": "qa3a-amazon",
            "environment": "sandbox",
            "credentials": {},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201
    item = client.post(
        "/api/v1/inventory/items",
        json={
            "product_id": product.json()["id"],
            "internal_sku": "QA3A",
            "opening_quantity": 0,
            "low_stock_threshold": 5,
            "idempotency_key": "qa3a-opening",
        },
        headers=ORIGIN,
    )
    assert item.status_code == 201
    return {
        "client": client,
        "product": product.json(),
        "account": account.json(),
        "item": item.json(),
    }


def post(ctx: dict[str, Any], route: str, data: Any = None) -> Any:
    response = ctx["client"].post(route, json=data, headers=ORIGIN)
    assert response.status_code < 300, response.text
    return response.json()


def sale(ctx: dict[str, Any], key: str = "qa3a-sale", amount: str = "100.00") -> dict[str, Any]:
    return {
        "account_id": ctx["account"]["id"],
        "product_id": ctx["product"]["id"],
        "marketplace": "amazon",
        "source_event_id": key,
        "event_type": "sale",
        "amount": amount,
        "source_type": "synthetic_fixture",
        "evidence_status": "reported",
    }


def seed_finance(ctx: dict[str, Any]) -> None:
    post(ctx, "/api/v1/financial/events", {**sale(ctx), "effective_at": "2026-01-15T00:00:00Z"})
    post(
        ctx,
        "/api/v1/financial/events",
        {**sale(ctx, "qa3a-fee", "2"), "event_type": "fee", "effective_at": "2026-01-15T00:00:00Z"},
    )


def cost(ctx: dict[str, Any], amount: str | None, date: str, key: str = "qa3a-cost") -> Any:
    return post(
        ctx,
        "/api/v1/financial/costs",
        {
            "product_id": ctx["product"]["id"],
            "cost_key": key,
            "cost_type": "acquisition",
            "amount": amount,
            "evidence_status": "unknown" if amount is None else "observed",
            "effective_from": date,
            "source_type": "synthetic_fixture",
        },
    )


def summary(ctx: dict[str, Any], date: str | None = None) -> Any:
    return (
        ctx["client"]
        .get("/api/v1/financial/summary", params={"date_to": date} if date else {}, headers=ORIGIN)
        .json()
    )


def signal(ctx: dict[str, Any]) -> Any:
    post(ctx, ACTION + "/scan")
    return next(
        row
        for row in ctx["client"].get(ACTION, headers=ORIGIN).json()["signals"]
        if row["source_resource_id"] == ctx["item"]["id"]
    )


def adjust(ctx: dict[str, Any], delta: int, version: int, key: str) -> Any:
    return post(
        ctx,
        f"/api/v1/inventory/{ctx['item']['id']}/adjust",
        {
            "delta": delta,
            "expected_version": version,
            "reason": "[QA SYNTHETIC] receipt",
            "idempotency_key": key,
        },
    )


def test_known_unknown_known_asof_reload_and_lineage(ctx: dict[str, Any]) -> None:
    seed_finance(ctx)
    known = cost(ctx, "20", "2026-01-01T00:00:00Z")
    assert summary(ctx)["contribution"] == "78.00"
    unknown = cost(ctx, None, "2026-02-01T00:00:00Z")
    for _ in range(2):
        current = summary(ctx)
        assert current["contribution"] == "UNKNOWN" and current["estimated_profit"] is None
        assert current["cost_evidence_ids"] == [unknown["id"]]
        assert "product_cost_evidence" in current["missing_inputs"]
        rows = ctx["client"].get("/api/v1/financial/profitability", headers=ORIGIN).json()["rows"]
        assert rows[0]["contribution"] == "UNKNOWN"
        agent = ctx["client"].get("/api/v1/financial/business-agent", headers=ORIGIN).json()
        assert any(row["type"] == "add_cost_evidence" for row in agent["actions"])
    snapshot = post(ctx, "/api/v1/financial/calculations/recalculate")
    assert snapshot["lineage"]["unknown_cost_evidence_ids"] == [unknown["id"]]
    historical = summary(ctx, "2026-01-31T23:59:59Z")
    assert historical["contribution"] == "78.00" and historical["cost_evidence_ids"] == [
        known["id"]
    ]
    recovered = cost(ctx, "30", "2026-03-01T00:00:00Z")
    assert summary(ctx)["contribution"] == "68.00"
    assert summary(ctx)["cost_evidence_ids"] == [recovered["id"]]
    assert summary(ctx, "2026-02-28T23:59:59Z")["contribution"] == "UNKNOWN"


def test_unknown_among_known_keys_blocks_and_zero_is_known(ctx: dict[str, Any]) -> None:
    seed_finance(ctx)
    cost(ctx, "0", "2026-01-01T00:00:00Z")
    assert summary(ctx)["contribution"] == "98.00"
    cost(ctx, "2", "2026-01-01T00:00:00Z", "other-cost")
    cost(ctx, None, "2026-02-01T00:00:00Z")
    current = summary(ctx)
    assert current["known_direct_costs"] == "2.00" and current["contribution"] == "UNKNOWN"


def test_future_unknown_does_not_override_current_and_unchanged_replay(ctx: dict[str, Any]) -> None:
    seed_finance(ctx)
    first = cost(ctx, "20", "2026-01-01T00:00:00Z")
    replay = cost(ctx, "20.00", "2026-01-01T00:00:00Z")
    assert replay["id"] == first["id"]
    cost(ctx, None, "2099-01-01T00:00:00Z")
    assert summary(ctx)["contribution"] == "78.00"
    assert summary(ctx, "2099-02-01T00:00:00Z")["contribution"] == "UNKNOWN"


def test_canonical_product_cost_cannot_override_unknown_evidence(ctx: dict[str, Any]) -> None:
    item = adjust(ctx, 2, 1, "qa3a-stock-receipt")
    post(
        ctx,
        "/api/v1/inventory/mappings",
        {
            "account_id": ctx["account"]["id"],
            "inventory_item_id": item["id"],
            "external_sku": "QA3A",
            "idempotency_key": "qa3a-mapping",
        },
    )
    post(
        ctx,
        "/api/v1/orders/fake/events",
        {
            "account_id": ctx["account"]["id"],
            "external_order_id": "QA3A-ORDER",
            "event_id": "qa3a-order",
            "event_type": "new_order",
            "lines": [{"external_sku": "QA3A", "quantity": 1, "unit_price": "100"}],
        },
    )
    cost(ctx, None, "2026-01-01T00:00:00Z")
    result = ctx["client"].get("/api/v1/financial/profitability", headers=ORIGIN).json()
    assert result["rows"][0]["contribution"] == "UNKNOWN"
    assert result["rows"][0]["known_direct_costs"] == "UNKNOWN"


def test_unknown_status_with_amount_still_does_not_become_known(ctx: dict[str, Any]) -> None:
    seed_finance(ctx)
    post(
        ctx,
        "/api/v1/financial/costs",
        {
            "product_id": ctx["product"]["id"],
            "cost_key": "contradictory-cost",
            "cost_type": "acquisition",
            "amount": "5",
            "evidence_status": "unknown",
            "source_type": "synthetic_fixture",
        },
    )
    assert summary(ctx)["known_direct_costs"] == "UNKNOWN"
    assert summary(ctx)["contribution"] == "UNKNOWN"


def test_stock_sequential_replay_intent_and_scope(ctx: dict[str, Any]) -> None:
    first = adjust(ctx, 2, 1, "qa3a-adjustment")
    assert adjust(ctx, 2, 1, "qa3a-adjustment")["version"] == first["version"]
    route = f"/api/v1/inventory/{ctx['item']['id']}/adjust"
    original = {
        "delta": 2,
        "expected_version": 1,
        "reason": "[QA SYNTHETIC] receipt",
        "idempotency_key": "qa3a-adjustment",
    }
    for change in ({"delta": 99}, {"reason": "Different intent"}, {"expected_version": 2}):
        assert (
            ctx["client"].post(route, json={**original, **change}, headers=ORIGIN).status_code
            == 409
        )
    ledger = (
        ctx["client"].get(f"/api/v1/inventory/{ctx['item']['id']}/ledger", headers=ORIGIN).json()
    )
    assert len(ledger) == 2 and ledger[0]["actor_type"] == "HUMAN"


@pytest.mark.parametrize("conflicting", [False, True])
def test_stock_concurrent_replay(ctx: dict[str, Any], conflicting: bool) -> None:
    route = f"/api/v1/inventory/{ctx['item']['id']}/adjust"
    payload = {
        "delta": 1,
        "expected_version": 1,
        "reason": "Race",
        "idempotency_key": "qa3a-stock-race",
    }
    requests = [payload, {**payload, "delta": 2}] if conflicting else [payload] * 4
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda data: ctx["client"].post(route, json=data, headers=ORIGIN), requests)
        )
    assert sorted(r.status_code for r in results) == ([200, 409] if conflicting else [200] * 4)
    ledger = (
        ctx["client"].get(f"/api/v1/inventory/{ctx['item']['id']}/ledger", headers=ORIGIN).json()
    )
    assert len(ledger) == 2


def test_financial_sequential_semantic_replay_and_field_conflicts(ctx: dict[str, Any]) -> None:
    payload = {
        **sale(ctx, amount="10.005"),
        "payload": {"a": 1, "b": 2},
        "effective_at": "2026-01-15T00:00:00Z",
    }
    first = post(ctx, "/api/v1/financial/events", payload)
    same = {
        **payload,
        "amount": "10.01",
        "payload": {"b": 2, "a": 1},
        "effective_at": "2026-01-15T05:30:00+05:30",
    }
    assert post(ctx, "/api/v1/financial/events", same)["event"]["id"] == first["event"]["id"]
    for change in (
        {"amount": "11"},
        {"event_type": "refund"},
        {"source_reference": "changed"},
        {"payload": {"a": 2}},
        {"effective_at": "2026-01-16T00:00:00Z"},
        {"evidence_status": "verified"},
    ):
        assert (
            ctx["client"]
            .post("/api/v1/financial/events", json={**payload, **change}, headers=ORIGIN)
            .status_code
            == 409
        )
    assert len(ctx["client"].get("/api/v1/financial/events", headers=ORIGIN).json()) == 1


@pytest.mark.parametrize("conflicting", [False, True])
def test_financial_concurrent_replay(ctx: dict[str, Any], conflicting: bool) -> None:
    payload = sale(ctx, "qa3a-financial-race")
    requests = [payload, {**payload, "amount": "101"}] if conflicting else [payload] * 4
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda data: ctx["client"].post(
                    "/api/v1/financial/events", json=data, headers=ORIGIN
                ),
                requests,
            )
        )
    assert sorted(r.status_code for r in results) == ([201, 409] if conflicting else [201] * 4)
    rows = ctx["client"].get("/api/v1/financial/events", headers=ORIGIN).json()
    assert len(rows) == 1


def test_signal_transition_sequential_scope_and_snooze_identity(ctx: dict[str, Any]) -> None:
    row = signal(ctx)
    route = ACTION + f"/signals/{row['id']}"
    payload = {"idempotency_key": "qa3a-acknowledge", "note": "Reviewed"}
    first = post(ctx, route + "/acknowledge", payload)
    assert post(ctx, route + "/acknowledge", payload)["transition_id"] == first["transition_id"]
    assert ctx["client"].post(route + "/resolve", json=payload, headers=ORIGIN).status_code == 409
    assert (
        ctx["client"]
        .post(route + "/acknowledge", json={**payload, "note": "Other"}, headers=ORIGIN)
        .status_code
        == 409
    )
    other_item = post(
        ctx,
        "/api/v1/inventory/items",
        {
            "product_id": ctx["product"]["id"],
            "internal_sku": "QA3A-OTHER",
            "opening_quantity": 0,
            "low_stock_threshold": 5,
            "idempotency_key": "qa3a-other-opening",
        },
    )
    other_signal = signal({**ctx, "item": other_item})
    assert (
        ctx["client"]
        .post(ACTION + f"/signals/{other_signal['id']}/acknowledge", json=payload, headers=ORIGIN)
        .status_code
        == 409
    )
    snooze = {"idempotency_key": "qa3a-snooze", "until": "2099-01-01T00:00:00Z"}
    first_snooze = post(ctx, route + "/snooze", snooze)
    assert (
        ctx["client"]
        .post(route + "/snooze", json={**snooze, "until": "2099-01-02T00:00:00Z"}, headers=ORIGIN)
        .status_code
        == 409
    )
    post(ctx, route + "/resolve", {"idempotency_key": "qa3a-resolve"})
    replay = post(ctx, route + "/snooze", snooze)
    assert replay["transition_id"] == first_snooze["transition_id"]
    assert replay["signal"]["status"] == "RESOLVED" and replay["signal"]["snoozed_until"] is None


@pytest.mark.parametrize("conflicting", [False, True])
def test_signal_concurrent_replay(ctx: dict[str, Any], conflicting: bool) -> None:
    row = signal(ctx)
    route = ACTION + f"/signals/{row['id']}"
    requests = ["acknowledge", "resolve"] if conflicting else ["acknowledge"] * 4
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda target: ctx["client"].post(
                    route + "/" + target,
                    json={"idempotency_key": "qa3a-signal-race"},
                    headers=ORIGIN,
                ),
                requests,
            )
        )
    assert sorted(r.status_code for r in results) == ([200, 409] if conflicting else [200] * 4)
    detail = ctx["client"].get(route, headers=ORIGIN).json()
    assert len([h for h in detail["history"] if h["actor_type"] == "HUMAN"]) == 1


def test_stock_recovery_read_refresh_audit_and_recurrence(ctx: dict[str, Any]) -> None:
    original = signal(ctx)
    before = original["evidence"]
    adjust(ctx, 20, 1, "qa3a-recovery")
    # Read without a scan must not present stale evidence as actionable.
    listed = ctx["client"].get(ACTION, headers=ORIGIN).json()
    assert not any(row["id"] == original["id"] for row in listed["signals"])
    route = ACTION + f"/signals/{original['id']}"
    detail = ctx["client"].get(route, headers=ORIGIN).json()
    assert detail["signal"]["status"] == "STALE" and detail["signal"]["evidence"] == before
    assert detail["history"][0]["actor_type"] == "SYSTEM"
    assert (
        ctx["client"]
        .post(route + "/reopen", json={"idempotency_key": "qa3a-bad-reopen"}, headers=ORIGIN)
        .status_code
        == 409
    )
    assert (
        ctx["client"]
        .post(
            route + "/action",
            json={"idempotency_key": "qa3a-stale-action", "action_type": "review"},
            headers=ORIGIN,
        )
        .status_code
        == 409
    )
    for _ in range(2):
        post(ctx, ACTION + "/scan")
    repeated = ctx["client"].get(route, headers=ORIGIN).json()
    assert len(repeated["history"]) == len(detail["history"])
    adjust(ctx, -20, 2, "qa3a-recur")
    current = signal(ctx)
    assert current["id"] != original["id"] and current["source_version"] == "3"
    assert current["evidence"]["available"] == 0
    assert ctx["client"].get(route, headers=ORIGIN).json()["signal"]["evidence"] == before


def test_stock_recovery_concurrent_scan_and_adjustment(ctx: dict[str, Any]) -> None:
    original = signal(ctx)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(adjust, ctx, 20, 1, "qa3a-concurrent-recovery"),
            pool.submit(post, ctx, ACTION + "/scan"),
        ]
        for future in futures:
            future.result(timeout=20)
    rows = ctx["client"].get(ACTION, headers=ORIGIN).json()["signals"]
    assert not any(row["id"] == original["id"] for row in rows)
    detail = ctx["client"].get(ACTION + f"/signals/{original['id']}", headers=ORIGIN).json()
    assert detail["signal"]["status"] == "STALE"
    other = post(
        ctx,
        "/api/v1/inventory/items",
        {
            "product_id": ctx["product"]["id"],
            "internal_sku": "QA3A-MULTILINE",
            "opening_quantity": 2,
            "low_stock_threshold": 1,
            "idempotency_key": "qa3a-multiline-opening",
        },
    )
    for item, sku in ((ctx["item"], "QA3A-FIRST"), (other, "QA3A-SECOND")):
        post(
            ctx,
            "/api/v1/inventory/mappings",
            {
                "account_id": ctx["account"]["id"],
                "inventory_item_id": item["id"],
                "external_sku": sku,
                "idempotency_key": "qa3a-map-" + sku,
            },
        )
    lines = [
        {"external_sku": "QA3A-SECOND", "quantity": 1, "unit_price": "10"},
        {"external_sku": "QA3A-FIRST", "quantity": 1, "unit_price": "10"},
    ]
    # Derived refresh must not add all-inventory locks that invert a multi-line
    # canonical order writer's lock order. Keep the existing order authority intact.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                post,
                ctx,
                "/api/v1/orders/fake/events",
                {
                    "account_id": ctx["account"]["id"],
                    "external_order_id": "QA3A-MULTILINE-ORDER",
                    "event_id": "qa3a-multiline-event",
                    "event_type": "new_order",
                    "lines": lines,
                },
            ),
            pool.submit(post, ctx, ACTION + "/scan"),
        ]
        for future in futures:
            future.result(timeout=20)
    inventory = ctx["client"].get("/api/v1/inventory", headers=ORIGIN).json()
    assert all(row["reserved_quantity"] == 1 for row in inventory)
    post(ctx, ACTION + "/scan")
    active = ctx["client"].get(ACTION, headers=ORIGIN).json()["signals"]
    assert all(row["id"] != original["id"] for row in active)


def test_persisted_revisions_and_authority_guards(ctx: dict[str, Any]) -> None:
    seed_finance(ctx)
    cost(ctx, "20", "2026-01-01T00:00:00Z")
    cost(ctx, None, "2026-02-01T00:00:00Z")
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = connection.execute(
            text(
                "select amount,evidence_status from financial_cost_evidence order by effective_from"
            )
        ).all()
        assert [tuple(row) for row in rows] == [(Decimal("20.00"), "observed"), (None, "unknown")]
    engine.dispose()
    row = signal(ctx)
    target = ACTION + f"/signals/{row['id']}/action"
    assert (
        ctx["client"]
        .post(
            target,
            json={"actor_type": "AI", "action_type": "review", "idempotency_key": "qa3a-ai-denied"},
            headers=ORIGIN,
        )
        .status_code
        == 403
    )
    assert (
        ctx["client"]
        .post(
            target,
            json={"action_type": "PUBLISH", "idempotency_key": "qa3a-external-denied"},
            headers=ORIGIN,
        )
        .status_code
        == 403
    )
    assert ctx["client"].get(ACTION + f"/signals/{uuid.uuid4()}", headers=ORIGIN).status_code == 404
