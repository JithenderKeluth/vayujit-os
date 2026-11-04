"""WP6B decimal policy and persisted projections on signed disposable PostgreSQL."""

import os
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_qa_phase3a_remediation import ORIGIN, adjust, cost, ctx, post, sale, summary
from vayujit_api.commerce.financial_models import FinancialCalculationSnapshot
from vayujit_api.commerce.financial_router import _money
from vayujit_api.commerce.models import MarketplaceFee, MarketplaceOrderEvent
from vayujit_api.commerce.money import allocate_money
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.economic_calculation_service import _money as landed_money
from vayujit_api.intelligence.product_opportunity_unit_economics_service import _fx_convert

pytestmark = pytest.mark.integration
__all__ = ["ctx"]


@pytest.mark.parametrize(
    "source,expected",
    [
        ("0", "0.00"),
        ("0.005", "0.01"),
        ("-0.005", "-0.01"),
        ("100.125", "100.13"),
        ("999999999999.994", "999999999999.99"),
        ("1.00499999", "1.00"),
        ("1.005", "1.01"),
    ],
)
def test_explicit_half_up_financial_boundary(source, expected):
    assert _money(source) == Decimal(expected)


@pytest.mark.parametrize("value", [None, "UNKNOWN", "NaN", "Infinity"])
def test_unknown_invalid_money_is_not_zero(value):
    with pytest.raises(HTTPException) as error:
        _money(value)
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "total,weights,expected",
    [
        ("0.01", ["1", "1"], ["0.01", "0.00"]),
        ("0.05", ["1", "1", "1"], ["0.02", "0.02", "0.01"]),
        ("-0.05", ["1", "1", "1"], ["-0.02", "-0.02", "-0.01"]),
        ("0", ["1", "2"], ["0", "0"]),
        ("1000000.01", ["0.000001", "999999"], ["0.00", "1000000.01"]),
    ],
)
def test_allocation_conserves_total_and_repeating_division(total, weights, expected):
    actual = allocate_money(Decimal(total), [Decimal(w) for w in weights])
    assert actual == [Decimal(e) for e in expected]
    assert sum(actual) == Decimal(total)
    assert allocate_money(Decimal(total), [Decimal(w) for w in weights]) == actual


@pytest.mark.parametrize("weights", [[], [Decimal("0")], [Decimal("-1")], [Decimal("NaN")]])
def test_unknown_or_contradictory_allocation_basis_is_not_invented(weights):
    with pytest.raises(ValueError):
        allocate_money(Decimal("0.01"), weights)


def test_landed_precision_small_units_large_quantity_fx_and_unknown():
    assert landed_money(Decimal("0.000001") * Decimal("1000000")) == Decimal("1.00000000")
    assert landed_money(Decimal("1") / Decimal("3")) == Decimal("0.33333333")
    assert landed_money(None) is None
    fx = [{"from_currency": "USD", "to_currency": "INR", "rate": "83.125"}]
    assert _fx_convert(Decimal("0.0015"), "USD", "INR", fx) == (Decimal("0.1246875"), None)
    converted, missing = _fx_convert(Decimal("1"), "EUR", "INR", fx)
    assert converted is None and missing == "explicit_fx:EUR/INR"
    assert landed_money(_fx_convert(Decimal("1"), "INR", "USD", fx)[0]) == Decimal("0.01203008")


@pytest.mark.parametrize(
    "fee,profit,margin",
    [("197.99", "2.01", "1.01"), ("200", "0.00", "0.00"), ("201", "-1.00", "-0.50")],
)
def test_profit_margin_persistence_unknown_and_recalculation(ctx, fee, profit, margin):
    post(ctx, "/api/v1/financial/events", sale(ctx, "wp6b-sale", "200"))
    post(ctx, "/api/v1/financial/events", {**sale(ctx, "wp6b-fee", fee), "event_type": "fee"})
    assert summary(ctx)["estimated_profit"] is None
    cost(ctx, "0", "2026-01-01T00:00:00Z", "wp6b-cost")
    value = summary(ctx)
    assert Decimal(value["estimated_profit"]) == Decimal(profit)
    assert Decimal(value["margin_percent"]) == Decimal(margin)
    assert value["provenance_status"] == "SYNTHETIC"
    a = post(ctx, "/api/v1/financial/calculations/recalculate")
    b = post(ctx, "/api/v1/financial/calculations/recalculate")
    assert a["id"] == b["id"] and a["metrics"] == b["metrics"]
    cost(ctx, None, "2026-01-02T00:00:00Z", "wp6b-cost")
    assert summary(ctx)["contribution"] == "UNKNOWN"
    assert (
        ctx["client"]
        .post("/api/v1/financial/events", json={**sale(ctx), "amount": "-1"}, headers=ORIGIN)
        .status_code
        == 422
    )


@pytest.mark.parametrize("unit_price", ["100.125", "0"])
def test_subpaise_source_is_preserved_and_allocated_fee_reconciles(ctx, unit_price):
    adjust(ctx, 10, 1, "wp6b-stock")
    post(
        ctx,
        "/api/v1/inventory/mappings",
        {
            "inventory_item_id": ctx["item"]["id"],
            "account_id": ctx["account"]["id"],
            "external_sku": "QA3A",
            "idempotency_key": "wp6b-map",
        },
    )
    payload = {
        "account_id": ctx["account"]["id"],
        "external_order_id": "WP6B",
        "event_id": "wp6b-two-lines",
        "event_type": "new_order",
        "event_version": 1,
        "lines": [{"external_sku": "QA3A", "quantity": 1, "unit_price": unit_price}] * 2,
    }
    order = post(ctx, "/api/v1/orders/fake/events", payload)
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
    try:
        with Session(engine) as db:
            owner = db.scalar(select(User))
            event = db.scalar(
                select(MarketplaceOrderEvent).where(
                    MarketplaceOrderEvent.event_id == payload["event_id"]
                )
            )
            assert event.payload_json["lines"][0]["unit_price"] == unit_price
            db.add(
                MarketplaceFee(
                    owner_id=owner.id,
                    account_id=uuid.UUID(ctx["account"]["id"]),
                    order_id=uuid.UUID(order["id"]),
                    fee_type="commission",
                    amount=Decimal("0.01"),
                    currency="INR",
                    occurred_at=now(),
                    created_at=now(),
                    updated_at=now(),
                )
            )
            db.commit()
        rows = ctx["client"].get("/api/v1/financial/profitability").json()["rows"]
        assert sum(Decimal(r["deductions"]) for r in rows) == Decimal("0.01")
        if unit_price == "0":
            assert len(rows) == 1 and rows[0]["product_id"] is None
            assert "deduction_allocation_basis" in rows[0]["missing_inputs"]
            assert rows[0]["estimated_profit"] is None
        loaded = ctx["client"].get("/api/v1/orders/" + order["id"]).json()
        expected = Decimal("100.13") if unit_price == "100.125" else Decimal("0.00")
        assert all(Decimal(r["unit_price"]) == expected for r in loaded["lines"])
        assert ctx["client"].get("/api/v1/orders/" + order["id"]).json() == loaded
    finally:
        engine.dispose()


def test_new_projection_policy_preserves_prior_version_snapshot(ctx):
    engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
    try:
        with Session(engine) as db:
            owner = db.scalar(select(User))
            legacy = FinancialCalculationSnapshot(
                owner_id=owner.id,
                scope_key="all|open|open",
                scope_type="financial_summary",
                calculation_version="pr-sos-05-v1",
                evidence_status="unknown",
                metrics_json={"legacy_record": "preserve"},
                missing_inputs_json=[],
                lineage_json={"old_policy": True},
                created_at=now(),
            )
            db.add(legacy)
            db.commit()
            old_id = legacy.id
        a = post(ctx, "/api/v1/financial/calculations/recalculate")
        b = post(ctx, "/api/v1/financial/calculations/recalculate")
        assert a["id"] == b["id"] and a["id"] != str(old_id)
        assert a["calculation_version"] == "pr-sos-05-v2"
        with Session(engine) as db:
            old = db.get(FinancialCalculationSnapshot, old_id)
            assert old.metrics_json == {"legacy_record": "preserve"}
            assert old.lineage_json == {"old_policy": True}
    finally:
        engine.dispose()


def test_zero_net_sales_margin_is_undefined_not_zero(ctx):
    post(ctx, "/api/v1/financial/events", sale(ctx, "wp6b-zero-sale", "200"))
    post(
        ctx,
        "/api/v1/financial/events",
        {**sale(ctx, "wp6b-zero-discount", "200"), "event_type": "discount"},
    )
    post(ctx, "/api/v1/financial/events", {**sale(ctx, "wp6b-zero-fee", "0"), "event_type": "fee"})
    cost(ctx, "0", "2026-01-01T00:00:00Z", "wp6b-zero-cost")
    value = summary(ctx)
    assert value["missing_inputs"] == []
    assert Decimal(value["net_sales"]) == 0
    assert Decimal(value["estimated_profit"]) == 0
    assert value["margin_percent"] is None
