"""Persisted Phase 3B classification and filtering; disposable fixtures only."""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from test_qa_phase3a_remediation import ACTION, ORIGIN, adjust, ctx, post, sale, signal
from vayujit_api.commerce.financial_models import FinancialEvent
from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceOrder, MarketplaceRefund
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now

pytestmark = pytest.mark.integration
# Reuse canonical API fixture, not a new owner or authorization mechanism.
__all__ = ["ctx"]


@pytest.mark.parametrize("kind", ["fake", "sandbox", "reported", "missing", "contradictory"])
def test_persisted_source_classification_and_reload(ctx: dict[str, Any], kind: str) -> None:
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    # Normal ORM domain fixtures model legacy/ingestion contracts, never real acquisition.
    with Session(engine) as db:
        account = db.get(MarketplaceAccount, uuid.UUID(ctx["account"]["id"]))
        assert account is not None
        account.environment = "sandbox" if kind == "sandbox" else "production"
        account.capabilities_json = {}
        db.commit()
        owner = db.scalar(select(User))
        assert owner is not None
        if kind in {"reported", "contradictory"}:
            # A declared 'verified' type is not independent verification authority.
            data = sale(ctx, amount="100")
            data["source_type"] = "verified"
            response = post(ctx, "/api/v1/financial/events", data)
            event = db.get(FinancialEvent, uuid.UUID(response["event"]["id"]))
            assert event is not None
            event.payload_json = {"fake_provider": True} if kind == "contradictory" else {}
        else:
            db.add(
                MarketplaceOrder(
                    owner_id=owner.id,
                    account_id=account.id,
                    marketplace="amazon",
                    remote_order_id="[QA SYNTHETIC CONTRACT] " + kind,
                    status="pending",
                    totals_json={
                        "total": "100.00",
                        "currency": "INR",
                        **({"fake_provider": True} if kind == "fake" else {}),
                    },
                    ordered_at=now(),
                    created_at=now(),
                    updated_at=now(),
                )
            )
        db.commit()
    expected = (
        "SYNTHETIC"
        if kind in {"fake", "sandbox", "contradictory"}
        else "REPORTED" if kind == "reported" else "UNKNOWN"
    )
    for _ in range(2):
        value = ctx["client"].get("/api/v1/financial/summary", headers=ORIGIN).json()
        assert value["provenance_status"] == expected
        assert value["synthetic_provider"] == (expected == "SYNTHETIC")
        assert value["gross_sales"] == "100.00"
        assert value["contribution"] == "UNKNOWN"  # Missing costs/fees are not invented.
        assert value["provenance_sources"] and "VERIFIED" not in value["provenance_status"]
    snapshot = post(ctx, "/api/v1/financial/calculations/recalculate")
    assert snapshot["lineage"]["provenance_status"] == expected
    assert snapshot["metrics"]["synthetic_provider"] == (expected == "SYNTHETIC")
    engine.dispose()


def test_fake_order_refund_ancestry_and_snapshot(ctx: dict[str, Any]) -> None:
    item = adjust(ctx, 2, 1, "qa3b-receipt")
    post(
        ctx,
        "/api/v1/inventory/mappings",
        {
            "account_id": ctx["account"]["id"],
            "inventory_item_id": item["id"],
            "external_sku": "QA3B",
            "idempotency_key": "qa3b-mapping",
        },
    )
    order = post(
        ctx,
        "/api/v1/orders/fake/events",
        {
            "account_id": ctx["account"]["id"],
            "external_order_id": "QA3B-ORDER",
            "event_id": "qa3b-order",
            "event_type": "new_order",
            "lines": [{"external_sku": "QA3B", "quantity": 1, "unit_price": "100"}],
        },
    )
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    with Session(engine) as db:
        parent = db.get(MarketplaceOrder, uuid.UUID(order["id"]))
        assert parent is not None
        account = db.get(MarketplaceAccount, parent.account_id)
        assert account is not None
        account.environment = "production"  # Persisted fake marker must still dominate.
        db.add(
            MarketplaceRefund(
                owner_id=parent.owner_id,
                order_id=parent.id,
                amount=5,
                currency="INR",
                status="reported",
                created_at=now(),
                updated_at=now(),
            )
        )
        db.commit()
    refunds = ctx["client"].get("/api/v1/financial/refund-impact", headers=ORIGIN).json()
    assert refunds["synthetic_provider"] is True and refunds["total_refunds"] == "5.00"
    sales = ctx["client"].get("/api/v1/financial/sales", headers=ORIGIN).json()
    assert sales["canonical_orders"][0]["provenance_status"] == "SYNTHETIC"
    assert sales["canonical_orders"][0]["evidence_status"] != "verified"
    engine.dispose()


def test_empty_provenance_does_not_claim_real(ctx: dict[str, Any]) -> None:
    value = ctx["client"].get("/api/v1/financial/summary", headers=ORIGIN).json()
    assert value["provenance_status"] == "UNKNOWN" and value["provenance_unknown"]
    assert value["provenance_sources"] == []


def test_mixed_sources_preserve_synthetic_warning(ctx: dict[str, Any]) -> None:
    post(ctx, "/api/v1/financial/events", sale(ctx))
    post(
        ctx,
        "/api/v1/financial/costs",
        {
            "product_id": ctx["product"]["id"],
            "cost_key": "qa3b-mixed-cost",
            "cost_type": "acquisition",
            "amount": "20",
            "source_type": "seller_entered",
        },
    )
    value = ctx["client"].get("/api/v1/financial/summary", headers=ORIGIN).json()
    assert value["provenance_status"] == "MIXED" and value["synthetic_provider"] is True
    assert {row["classification"] for row in value["provenance_sources"]} == {
        "SYNTHETIC",
        "REPORTED",
    }


def test_original_sandbox_origin_survives_later_account_configuration(ctx: dict[str, Any]) -> None:
    post(ctx, "/api/v1/financial/events", {**sale(ctx), "source_type": "marketplace_reported"})
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool)
    with Session(engine) as db:
        account = db.get(MarketplaceAccount, uuid.UUID(ctx["account"]["id"]))
        assert account is not None
        account.environment = "production"
        db.commit()
    for _ in range(2):
        value = ctx["client"].get("/api/v1/financial/summary", headers=ORIGIN).json()
        assert value["synthetic_provider"] is True and value["provenance_status"] == "SYNTHETIC"
    engine.dispose()


@pytest.mark.parametrize(
    "status", ["NEW", "ACKNOWLEDGED", "SNOOZED", "RESOLVED", "REOPENED", "STALE"]
)
def test_status_filters_transitions_and_reload(ctx: dict[str, Any], status: str) -> None:
    row = signal(ctx)
    route = ACTION + f"/signals/{row['id']}"
    if status == "STALE":
        adjust(ctx, 20, 1, "qa3b-recover")
    elif status != "NEW":
        target = {
            "ACKNOWLEDGED": "acknowledge",
            "SNOOZED": "snooze",
            "RESOLVED": "resolve",
            "REOPENED": "reopen",
        }[status]
        if status == "REOPENED":
            post(ctx, route + "/resolve", {"idempotency_key": "qa3b-before-reopen"})
        post(
            ctx,
            route + "/" + target,
            {
                "idempotency_key": "qa3b-transition",
                **({"until": "2099-01-01T00:00:00Z"} if status == "SNOOZED" else {}),
            },
        )
    for _ in range(2):
        result = (
            ctx["client"]
            .get(ACTION, params={"status": status, "category": "inventory"}, headers=ORIGIN)
            .json()
        )
        assert result["total"] == 1 and result["signals"][0]["id"] == row["id"]
        assert result["signals"][0]["status"] == status
        assert result["briefing"]["counts"]["resolved"] == (1 if status == "RESOLVED" else 0)
        assert result["briefing"]["counts"]["stale"] == (1 if status == "STALE" else 0)
    active = ctx["client"].get(ACTION, headers=ORIGIN).json()["signals"]
    assert any(r["id"] == row["id"] for r in active) == (status not in {"RESOLVED", "STALE"})
    empty = (
        ctx["client"]
        .get(ACTION, params={"status": status, "search": "absent-qa3b"}, headers=ORIGIN)
        .json()
    )
    assert empty["total"] == 0 and empty["signals"] == []


def test_filter_pagination_counts_sorting_and_auth(ctx: dict[str, Any]) -> None:
    for index in range(3):
        post(
            ctx,
            "/api/v1/inventory/items",
            {
                "product_id": ctx["product"]["id"],
                "internal_sku": f"QA3B-{index}",
                "opening_quantity": 0,
                "low_stock_threshold": 5,
                "idempotency_key": f"qa3b-opening-{index}",
            },
        )
    post(ctx, ACTION + "/scan")
    query = {"category": "inventory", "status": "NEW", "search": "QA3B"}
    all_rows = ctx["client"].get(ACTION, params=query, headers=ORIGIN).json()
    assert all_rows["total"] == 3
    first = ctx["client"].get(ACTION, params={**query, "limit": 2}, headers=ORIGIN).json()
    second = (
        ctx["client"].get(ACTION, params={**query, "limit": 2, "offset": 2}, headers=ORIGIN).json()
    )
    assert first["total"] == second["total"] == 3
    assert [r["id"] for r in first["signals"] + second["signals"]] == [
        r["id"] for r in all_rows["signals"]
    ]
    foreign = (
        ctx["client"]
        .get(ACTION, params={**query, "owner_id": str(uuid.uuid4())}, headers=ORIGIN)
        .json()
    )
    assert foreign["signals"] == all_rows["signals"]  # Cannot switch the authenticated owner.
    assert ctx["client"].get(ACTION + f"/signals/{uuid.uuid4()}", headers=ORIGIN).status_code == 404
    ctx["client"].cookies.clear()
    assert ctx["client"].get(ACTION, params=query, headers=ORIGIN).status_code == 401
