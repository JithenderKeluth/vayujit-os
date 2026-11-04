"""WP5 persisted local projection contracts; no provider transport or real credentials."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from test_qa_phase3a_remediation import ACTION, ORIGIN, adjust, ctx, post, sale, signal

from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceOrder
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now

pytestmark = pytest.mark.integration
__all__ = ["ctx"]


@pytest.mark.parametrize("kind", ["fake", "sandbox", "reported", "missing", "contradictory"])
def test_order_provenance_is_canonical_and_unknown_never_becomes_real(ctx, kind):
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    try:
        with Session(engine) as db:
            account = db.get(MarketplaceAccount, uuid.UUID(ctx["account"]["id"]))
            account.environment = "sandbox" if kind == "sandbox" else "production"
            account.capabilities_json = {}
            owner = db.scalar(select(User))
            row = MarketplaceOrder(
                owner_id=owner.id,
                account_id=account.id,
                marketplace="amazon",
                remote_order_id="[QA SYNTHETIC CONTRACT] WP5-" + kind,
                status="pending",
                totals_json={
                    "currency": "INR",
                    **({"fake_provider": True} if kind in {"fake", "contradictory"} else {}),
                    **(
                        {"source_type": "marketplace_reported"}
                        if kind in {"reported", "contradictory"}
                        else {}
                    ),
                },
                ordered_at=now(),
                created_at=now(),
                updated_at=now(),
            )
            db.add(row)
            db.commit()
            order_id = row.id
        expected = (
            "SYNTHETIC"
            if kind in {"fake", "sandbox", "contradictory"}
            else "REPORTED" if kind == "reported" else "UNKNOWN"
        )
        for _ in range(2):
            response = ctx["client"].get(f"/api/v1/orders/{order_id}")
            assert response.status_code == 200
            value = response.json()
            assert value["provenance_status"] == expected
            assert value["fake_provider"] == (expected == "SYNTHETIC")
            assert value["lines"] == []
        assert ctx["client"].get(f"/api/v1/orders/{uuid.uuid4()}").status_code == 404
    finally:
        engine.dispose()


def test_owned_order_lines_and_exact_product_handoff_survive_reload_and_replay(ctx):
    client = ctx["client"]
    adjust(ctx, 10, 1, "wp5-stock")
    post(
        ctx,
        "/api/v1/inventory/mappings",
        {
            "inventory_item_id": ctx["item"]["id"],
            "account_id": ctx["account"]["id"],
            "external_sku": "QA3A",
            "idempotency_key": "wp5-map",
        },
    )
    payload = {
        "account_id": ctx["account"]["id"],
        "external_order_id": "WP5-ORDER",
        "event_id": "wp5-event",
        "event_type": "new_order",
        "event_version": 1,
        "lines": [{"external_sku": "QA3A", "quantity": 2, "unit_price": "100.125"}],
    }
    first = post(ctx, "/api/v1/orders/fake/events", payload)
    assert post(ctx, "/api/v1/orders/fake/events", payload)["id"] == first["id"]
    value = client.get("/api/v1/orders/" + first["id"]).json()
    assert value["fake_provider"] is True and value["provenance_status"] == "SYNTHETIC"
    assert value["lines"][0]["product_id"] == ctx["product"]["id"]
    assert value["lines"][0]["marketplace_sku"] == "QA3A"
    assert value["lines"][0]["quantity"] == 2
    assert client.get("/api/v1/orders/" + first["id"]).json() == value
    assert len(client.get("/api/v1/orders").json()) == 1
    assert client.get("/api/v1/inventory").json()[0]["reserved_quantity"] == 2


def test_signal_source_scope_and_stale_notice_are_not_execution(ctx):
    value = signal(ctx)
    assert value["source_route"] == "/marketplaces/inventory?product_id=" + ctx["product"]["id"]
    old = post(ctx, ACTION + f"/signals/{value['id']}/resolve", {"idempotency_key": "wp5-resolve"})
    assert old["signal"]["status"] == "RESOLVED"
    post(ctx, ACTION + "/scan")
    current = ctx["client"].get(ACTION).json()["signals"]
    assert any(row["id"] == value["id"] and row["status"] == "REOPENED" for row in current)
    adjust(ctx, 10, 1, "wp5-source-repair")
    assert not ctx["client"].get(ACTION).json()["signals"]
    stale = ctx["client"].get(ACTION, params={"status": "STALE"}).json()["signals"]
    assert stale and stale[0]["status"] == "STALE"
    denied = ctx["client"].post(
        ACTION + f"/signals/{value['id']}/acknowledge",
        json={"idempotency_key": "wp5-stale"},
        headers=ORIGIN,
    )
    assert denied.status_code == 409


def test_financial_snapshot_is_a_mutable_working_projection_not_immutable_history(ctx):
    post(ctx, "/api/v1/financial/events", sale(ctx, "wp5-sale", "200.25"))
    first = post(ctx, "/api/v1/financial/calculations/recalculate")
    assert first["metrics"]["contribution"] == "UNKNOWN"
    post(ctx, "/api/v1/financial/events", {**sale(ctx, "wp5-fee", "20.05"), "event_type": "fee"})
    revised = post(ctx, "/api/v1/financial/calculations/recalculate")
    assert revised["id"] == first["id"]
    assert revised["metrics"]["fees"] == "20.05"
    assert revised["metrics"]["gross_sales"] == "200.25"
    assert revised["metrics"]["contribution"] == "UNKNOWN"
    assert revised["lineage"]["provenance_status"] == "SYNTHETIC"
    saved = ctx["client"].get("/api/v1/financial/calculations").json()
    assert len(saved) == 1 and saved[0]["metrics"] == revised["metrics"]


def test_mock_destination_never_creates_a_connected_marketplace_account(ctx):
    post(
        ctx,
        "/api/v1/publishing/destinations",
        {
            "name": "[QA SYNTHETIC] WP5 local",
            "connector_key": "mock_publisher_v1",
            "configuration": {"channel_name": "QA-WP5-LOCAL"},
        },
    )
    summary = ctx["client"].get("/api/v1/dashboard/summary").json()
    assert summary["metrics"]["active_destinations"] == 1
    account = ctx["client"].get("/api/v1/marketplaces/accounts").json()[0]
    assert account["enabled"] is False and account["credential_status"] == "missing"


def test_complete_rescan_retires_obsolete_financial_condition_with_system_audit(ctx):
    post(ctx, "/api/v1/financial/events", sale(ctx, "wp5-negative-sale", "200.25"))
    post(
        ctx,
        "/api/v1/financial/events",
        {**sale(ctx, "wp5-negative-fee", "20.05"), "event_type": "fee"},
    )
    post(
        ctx,
        "/api/v1/financial/costs",
        {
            "product_id": ctx["product"]["id"],
            "cost_key": "wp5-cost",
            "cost_type": "acquisition",
            "amount": "300.00",
            "source_type": "synthetic_fixture",
            "evidence_status": "reported",
        },
    )
    post(ctx, "/api/v1/financial/calculations/recalculate")
    post(ctx, ACTION + "/scan")
    original = next(
        row
        for row in ctx["client"].get(ACTION).json()["signals"]
        if row["signal_type"] == "negative_contribution"
    )
    post(ctx, "/api/v1/financial/events", sale(ctx, "wp5-additional-sale", "500.00"))
    post(ctx, "/api/v1/financial/calculations/recalculate")
    post(ctx, ACTION + "/scan")
    assert not any(
        row["id"] == original["id"] for row in ctx["client"].get(ACTION).json()["signals"]
    )
    detail = ctx["client"].get(ACTION + "/signals/" + original["id"]).json()
    assert detail["signal"]["status"] == "STALE"
    assert detail["history"][0]["actor_type"] == "SYSTEM"
    assert detail["signal"]["evidence"]["metrics"]["contribution"] == "-119.80"


def test_business_agent_owned_empty_state_is_not_a_failed_resource_read(ctx):
    client = ctx["client"]
    goal = post(
        ctx,
        "/api/v1/intelligence/business-agent/goals",
        {
            "raw_goal": "[QA SYNTHETIC] Research one product for Amazon India with INR 300000.",
            "idempotency_key": "wp5-empty-goal",
        },
    )
    for suffix in ["plan", "runs/latest"]:
        route = f"/api/v1/intelligence/business-agent/goals/{goal['id']}/{suffix}"
        assert client.get(route).status_code == 404
        response = client.get(route, params={"allow_missing": "true"})
        assert response.status_code == 200 and response.json() is None
        assert (
            client.get(
                f"/api/v1/intelligence/business-agent/goals/{uuid.uuid4()}/{suffix}",
                params={"allow_missing": "true"},
            ).status_code
            == 404
        )
