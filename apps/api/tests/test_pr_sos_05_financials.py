"""Focused PR-SOS-05 financial evidence and reconciliation regressions."""

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
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceFee,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplaceRefund,
    MarketplaceSettlement,
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
def financial_context(
    pr56_client: TestClient,
) -> Generator[tuple[TestClient, uuid.UUID, uuid.UUID], None, None]:
    setup = pr56_client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Financial Owner",
            "email": "financial-owner@example.com",
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
            name="Financial Brand",
            normalized_name="financial-brand",
            slug="financial-brand",
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
            name="Financial Test Product",
            normalized_name="financial-test-product",
            slug="financial-test-product",
            sku="FIN-001",
            product_type="physical",
            status="active",
            category="Kids",
            created_at=stamp,
            updated_at=stamp,
        )
        account = MarketplaceAccount(
            owner_id=owner.id,
            marketplace="amazon",
            display_name="Synthetic Amazon",
            seller_account_id="synthetic-amazon",
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
        db.commit()
        yield pr56_client, account.id, product.id


def test_financial_event_idempotency_and_unknown_cost(financial_context) -> None:
    client, account_id, _product_id = financial_context
    payload = {
        "account_id": str(account_id),
        "source_event_id": "sale-1",
        "marketplace": "amazon",
        "event_type": "sale",
        "amount": "100.00",
        "source_type": "synthetic_fixture",
        "evidence_status": "reported",
    }
    first = client.post("/api/v1/financial/events", json=payload, headers=ORIGIN)
    assert first.status_code == 201, first.text
    replay = client.post("/api/v1/financial/events", json=payload, headers=ORIGIN)
    assert replay.status_code == 201 and replay.json()["idempotent"] is True
    fee = {**payload, "source_event_id": "fee-1", "event_type": "fee", "amount": "10.25"}
    assert client.post("/api/v1/financial/events", json=fee, headers=ORIGIN).status_code == 201
    summary = client.get("/api/v1/financial/summary", headers=ORIGIN)
    assert summary.status_code == 200, summary.text
    value = summary.json()
    assert value["gross_sales"] == "100.00"
    assert value["fees"] == "10.25"
    assert value["known_direct_costs"] == "UNKNOWN"
    assert value["contribution"] == "UNKNOWN"
    assert value["estimated_profit"] is None
    assert "product_cost_evidence" in value["missing_inputs"]
    alerts = client.get("/api/v1/financial/alerts", headers=ORIGIN)
    assert alerts.status_code == 200, alerts.text
    assert any(alert["code"] == "product_cost_evidence" for alert in alerts.json()["alerts"])
    unknown_cost = client.post(
        "/api/v1/financial/costs",
        json={
            "cost_key": "unknown-cost",
            "cost_type": "acquisition",
            "evidence_status": "unknown",
            "source_type": "seller_entered",
        },
        headers=ORIGIN,
    )
    assert unknown_cost.status_code == 201, unknown_cost.text
    assert unknown_cost.json()["amount"] is None


def test_financial_cost_qualifies_profitability_and_settlement_difference(
    financial_context,
) -> None:
    client, account_id, product_id = financial_context
    for event_id, event_type, amount in (("sale-2", "sale", "200.00"), ("fee-2", "fee", "20.00")):
        response = client.post(
            "/api/v1/financial/events",
            json={
                "account_id": str(account_id),
                "source_event_id": event_id,
                "marketplace": "amazon",
                "event_type": event_type,
                "amount": amount,
                "product_id": str(product_id),
                "source_type": "synthetic_fixture",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    cost = client.post(
        "/api/v1/financial/costs",
        json={
            "product_id": str(product_id),
            "cost_key": "kids-sku-cost",
            "cost_type": "acquisition",
            "amount": "120.00",
            "source_type": "seller_entered",
            "evidence_status": "observed",
        },
        headers=ORIGIN,
    )
    assert cost.status_code == 201, cost.text
    profitability = client.get("/api/v1/financial/profitability", headers=ORIGIN)
    assert profitability.status_code == 200
    assert profitability.json()["rows"][0]["estimated_profit"] == "60.00"
    reconcile = client.post(
        "/api/v1/financial/settlements/reconcile",
        json={
            "account_id": str(account_id),
            "settlement_key": "settlement-1",
            "marketplace": "amazon",
            "expected_amount": "180.00",
            "reported_amount": "175.00",
            "currency": "INR",
            "provenance": {"source_type": "synthetic_fixture"},
        },
        headers=ORIGIN,
    )
    assert reconcile.status_code == 201
    assert reconcile.json()["status"] == "mismatch"


def test_financial_currency_and_external_provider_boundaries(financial_context) -> None:
    client, account_id, _product_id = financial_context
    invalid_currency = client.post(
        "/api/v1/financial/events",
        json={
            "account_id": str(account_id),
            "source_event_id": "usd-1",
            "marketplace": "amazon",
            "event_type": "sale",
            "amount": "1.00",
            "currency": "USD",
        },
        headers=ORIGIN,
    )
    assert invalid_currency.status_code == 422
    external = client.post(
        "/api/v1/financial/events",
        json={
            "account_id": str(account_id),
            "source_event_id": "external-1",
            "marketplace": "amazon",
            "event_type": "sale",
            "amount": "1.00",
            "source_type": "live_provider",
        },
        headers=ORIGIN,
    )
    assert external.status_code == 422
    guidance = client.get("/api/v1/financial/business-agent", headers=ORIGIN)
    assert guidance.status_code == 200
    assert guidance.json()["authority"] == "read_only"
    assert guidance.json()["external_writes"] is False


def test_canonical_order_fee_refund_and_settlement_projection(financial_context) -> None:
    client, account_id, product_id = financial_context
    with _factory()() as db:
        owner = db.query(User).one()
        stamp = now()
        order = MarketplaceOrder(
            owner_id=owner.id,
            account_id=account_id,
            marketplace="amazon",
            remote_order_id="canonical-order-1",
            status="delivered",
            payment_status="paid",
            fulfilment_status="delivered",
            totals_json={"item_subtotal": "150.00", "total": "150.00"},
            ordered_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(order)
        db.flush()
        db.add(
            MarketplaceOrderItem(
                owner_id=owner.id,
                order_id=order.id,
                product_id=product_id,
                title_snapshot="Financial Test Product",
                quantity=1,
                unit_price="150.00",
                total_price="150.00",
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            MarketplaceFee(
                owner_id=owner.id,
                account_id=account_id,
                order_id=order.id,
                fee_type="commission",
                amount="15.00",
                currency="INR",
                occurred_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            MarketplaceRefund(
                owner_id=owner.id,
                order_id=order.id,
                amount="10.00",
                currency="INR",
                reason="partial return",
                status="reported",
                marketplace_reference="canonical-refund-1",
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            MarketplaceSettlement(
                owner_id=owner.id,
                account_id=account_id,
                marketplace="amazon",
                remote_settlement_id="canonical-settlement-1",
                period_start=stamp,
                period_end=stamp,
                gross_amount="150.00",
                fee_amount="15.00",
                refund_amount="10.00",
                tax_withholding_amount="0.00",
                net_amount="125.00",
                currency="INR",
                status="settled",
                other_adjustment_amount="0.00",
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()

    summary = client.get("/api/v1/financial/summary", headers=ORIGIN)
    assert summary.status_code == 200, summary.text
    assert summary.json()["gross_sales"] == "150.00"
    assert summary.json()["refunds"] == "10.00"
    assert summary.json()["fees"] == "15.00"
    assert summary.json()["canonical_order_fallback"] is True
    assert "product_cost_evidence" in summary.json()["missing_inputs"]
    product_profit = client.get("/api/v1/financial/profitability", headers=ORIGIN)
    assert product_profit.status_code == 200
    assert product_profit.json()["rows"][0]["gross_sales"] == "150.00"
    assert product_profit.json()["rows"][0]["known_direct_costs"] == "UNKNOWN"
    fees = client.get("/api/v1/financial/fees", headers=ORIGIN)
    assert fees.status_code == 200 and fees.json()["fees"]["fee"] == "15.00"
    sales = client.get("/api/v1/financial/sales", headers=ORIGIN)
    assert sales.status_code == 200 and len(sales.json()["canonical_orders"]) == 1
    settlements = client.get("/api/v1/financial/settlements", headers=ORIGIN)
    assert settlements.status_code == 200
    assert settlements.json()["rows"][0]["settlement_key"] == "canonical-settlement-1"
    assert client.get("/api/v1/financial/profitability/sku", headers=ORIGIN).status_code == 200
    order_profitability = client.get("/api/v1/financial/profitability/order", headers=ORIGIN)
    assert order_profitability.status_code == 200
    assert order_profitability.json()["rows"][0]["group_key"] == "canonical-order-1"
    trends = client.get("/api/v1/financial/revenue-trends", headers=ORIGIN)
    assert trends.status_code == 200 and trends.json()["rows"]
    comparison = client.get("/api/v1/financial/marketplace-comparison", headers=ORIGIN)
    assert comparison.status_code == 200
    assert comparison.json()["rows"][0]["marketplace"] == "amazon"
    refund_impact = client.get("/api/v1/financial/refund-impact", headers=ORIGIN)
    assert refund_impact.status_code == 200 and refund_impact.json()["total_refunds"] == "10.00"
    missing_costs = client.get("/api/v1/financial/missing-costs", headers=ORIGIN)
    assert missing_costs.status_code == 200 and missing_costs.json()["count"] == 1
    snapshot = client.post("/api/v1/financial/calculations/recalculate", headers=ORIGIN)
    assert snapshot.status_code == 201, snapshot.text
    replay = client.post("/api/v1/financial/calculations/recalculate", headers=ORIGIN)
    assert replay.status_code == 201 and replay.json()["id"] == snapshot.json()["id"]
    calculations = client.get("/api/v1/financial/calculations", headers=ORIGIN)
    assert calculations.status_code == 200 and len(calculations.json()) == 1


def _post_event(
    client: TestClient,
    account_id: uuid.UUID,
    source_event_id: str,
    event_type: str,
    amount: str,
    product_id: uuid.UUID | None = None,
    effective_at: str | None = None,
) -> dict:
    payload = {
        "account_id": str(account_id),
        "source_event_id": source_event_id,
        "marketplace": "amazon",
        "event_type": event_type,
        "amount": amount,
        "source_type": "synthetic_fixture",
        "evidence_status": "reported",
    }
    if product_id is not None:
        payload["product_id"] = str(product_id)
    if effective_at is not None:
        payload["effective_at"] = effective_at
    response = client.post("/api/v1/financial/events", json=payload, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


def test_financial_rounding_refunds_lineage_and_warning_states(financial_context) -> None:
    client, account_id, product_id = financial_context
    effective = "2026-01-15T00:00:00Z"
    sale = _post_event(client, account_id, "matrix-sale", "sale", "10.005", product_id, effective)
    assert sale["event"]["amount"] == "10.01"
    duplicate_sale = _post_event(
        client, account_id, "matrix-sale", "sale", "10.005", product_id, effective
    )
    assert duplicate_sale["idempotent"] is True
    _post_event(client, account_id, "matrix-discount", "discount", "0.005", product_id, effective)
    _post_event(client, account_id, "matrix-fee", "fee", "2.005", product_id, effective)
    _post_event(client, account_id, "matrix-refund", "refund", "1.005", product_id, effective)
    duplicate_refund = _post_event(
        client, account_id, "matrix-refund", "refund", "1.005", product_id, effective
    )
    assert duplicate_refund["idempotent"] is True
    cost = client.post(
        "/api/v1/financial/costs",
        json={
            "product_id": str(product_id),
            "cost_key": "matrix-cost",
            "cost_type": "acquisition",
            "amount": "3.005",
            "effective_from": effective,
            "source_type": "seller_entered",
            "evidence_status": "observed",
        },
        headers=ORIGIN,
    )
    assert cost.status_code == 201, cost.text
    assert cost.json()["amount"] == "3.01"
    summary = client.get("/api/v1/financial/summary", headers=ORIGIN).json()
    assert summary["gross_sales"] == "10.01"
    assert summary["discounts"] == "0.01"
    assert summary["refunds"] == "1.01"
    assert summary["net_sales"] == "8.99"
    assert summary["fees"] == "2.01"
    assert summary["known_direct_costs"] == "3.01"
    assert summary["contribution"] == "3.97"
    assert summary["calculation_version"] == "pr-sos-05-v1"
    events = client.get("/api/v1/financial/events", headers=ORIGIN).json()
    assert len(events) == 4
    assert [row["source_event_id"] for row in events] == [
        "matrix-discount",
        "matrix-fee",
        "matrix-refund",
        "matrix-sale",
    ]
    refund_impact = client.get("/api/v1/financial/refund-impact", headers=ORIGIN).json()
    assert refund_impact["total_refunds"] == "1.01"

    # A complete contribution must not produce a negative-contribution alert.
    blank = client.get("/api/v1/financial/alerts", headers=ORIGIN)
    assert blank.status_code == 200, blank.text


def test_financial_effective_cost_rules_negative_contribution_and_reconciliation(
    financial_context,
) -> None:
    client, account_id, product_id = financial_context
    january = "2026-01-15T00:00:00Z"
    march = "2026-03-01T00:00:00Z"
    _post_event(client, account_id, "dated-sale", "sale", "100.00", product_id, january)
    _post_event(client, account_id, "dated-fee", "fee", "2.00", product_id, january)
    for key, amount, effective in (
        ("dated-cost", "10.00", "2026-01-01T00:00:00Z"),
        ("dated-cost", "50.00", "2026-02-01T00:00:00Z"),
        ("dated-cost", "200.00", march),
    ):
        response = client.post(
            "/api/v1/financial/costs",
            json={
                "product_id": str(product_id),
                "cost_key": key,
                "cost_type": "acquisition",
                "amount": amount,
                "effective_from": effective,
                "source_type": "seller_entered",
                "evidence_status": "observed",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    january_profit = client.get(
        "/api/v1/financial/profitability",
        params={"date_to": "2026-01-31T23:59:59Z"},
        headers=ORIGIN,
    ).json()
    assert january_profit["rows"][0]["known_direct_costs"] == "10.00"
    assert january_profit["rows"][0]["contribution"] == "88.00"
    march_profit = client.get(
        "/api/v1/financial/profitability",
        params={"date_to": "2026-03-31T23:59:59Z"},
        headers=ORIGIN,
    ).json()
    assert march_profit["rows"][0]["known_direct_costs"] == "200.00"
    assert march_profit["rows"][0]["contribution"] == "-102.00"
    alert_response = client.get("/api/v1/financial/alerts", headers=ORIGIN)
    assert alert_response.status_code == 200, alert_response.text
    assert any(
        alert["code"] == "negative_contribution" for alert in alert_response.json()["alerts"]
    )

    for rule_key, rate, effective in (
        ("amazon-kids-commission", "5.1250", "2026-01-01T00:00:00Z"),
        ("amazon-kids-commission", "6.2500", "2026-02-01T00:00:00Z"),
    ):
        rule = client.post(
            "/api/v1/financial/fee-rules",
            json={
                "marketplace": "amazon",
                "category": "Kids",
                "rule_key": rule_key,
                "fee_type": "commission",
                "rate_percent": rate,
                "effective_from": effective,
                "source_type": "synthetic_fixture",
            },
            headers=ORIGIN,
        )
        assert rule.status_code == 201, rule.text
    rules = client.get(
        "/api/v1/financial/fee-rules",
        params={"marketplace": "amazon", "category": "Kids", "as_of": "2026-02-15T00:00:00Z"},
        headers=ORIGIN,
    )
    assert rules.status_code == 200, rules.text
    assert [row["rate_percent"] for row in rules.json()] == ["6.2500", "5.1250"]
    assert all(row["source_type"] == "synthetic_fixture" for row in rules.json())

    match = client.post(
        "/api/v1/financial/settlements/reconcile",
        json={
            "account_id": str(account_id),
            "settlement_key": "matrix-match",
            "marketplace": "amazon",
            "expected_amount": "98.00",
            "reported_amount": "98.00",
            "currency": "INR",
            "provenance": {"source_type": "synthetic_fixture"},
        },
        headers=ORIGIN,
    )
    assert match.status_code == 201 and match.json()["status"] == "matched"
    mismatch = client.post(
        "/api/v1/financial/settlements/reconcile",
        json={
            "account_id": str(account_id),
            "settlement_key": "matrix-mismatch",
            "marketplace": "amazon",
            "expected_amount": "98.00",
            "reported_amount": "95.50",
            "currency": "INR",
            "provenance": {"source_type": "synthetic_fixture"},
        },
        headers=ORIGIN,
    )
    assert mismatch.status_code == 201
    assert mismatch.json()["difference_amount"] == "-2.50"
    unknown = client.post(
        "/api/v1/financial/settlements/reconcile",
        json={
            "account_id": str(account_id),
            "settlement_key": "matrix-unknown",
            "marketplace": "amazon",
            "currency": "INR",
            "provenance": {"source_type": "synthetic_fixture"},
        },
        headers=ORIGIN,
    )
    assert unknown.status_code == 201
    assert unknown.json()["status"] == "unknown"
    assert unknown.json()["evidence_status"] == "unknown"


def test_financial_owner_account_currency_and_snapshot_boundaries(financial_context) -> None:
    client, account_id, product_id = financial_context
    _post_event(client, account_id, "boundary-sale", "sale", "37.50", product_id)
    invalid_currency = client.post(
        "/api/v1/financial/events",
        json={
            "account_id": str(account_id),
            "source_event_id": "boundary-usd",
            "marketplace": "amazon",
            "event_type": "sale",
            "amount": "1.00",
            "currency": "USD",
            "source_type": "synthetic_fixture",
        },
        headers=ORIGIN,
    )
    assert invalid_currency.status_code == 422
    unknown_account = client.get(
        "/api/v1/financial/events",
        params={"marketplace": "amazon"},
        headers=ORIGIN,
    )
    assert unknown_account.status_code == 200
    assert all(row["account_id"] == str(account_id) for row in unknown_account.json())
    private_account = client.post(
        "/api/v1/financial/events",
        json={
            "account_id": str(uuid.uuid4()),
            "source_event_id": "cross-account",
            "marketplace": "amazon",
            "event_type": "sale",
            "amount": "1.00",
            "source_type": "synthetic_fixture",
        },
        headers=ORIGIN,
    )
    assert private_account.status_code == 404
    snapshot = client.post(
        "/api/v1/financial/calculations/recalculate",
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201
    replay = client.post(
        "/api/v1/financial/calculations/recalculate",
        headers=ORIGIN,
    )
    assert replay.status_code == 201 and replay.json()["id"] == snapshot.json()["id"]
    assert replay.json()["lineage"]["event_ids"]
    assert (
        client.get("/api/v1/financial/business-agent", headers=ORIGIN).json()["external_writes"]
        is False
    )
