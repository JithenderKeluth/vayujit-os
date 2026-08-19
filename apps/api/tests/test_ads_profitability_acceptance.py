from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import test_ai_integration
from helpers.ads_acceptance import create_campaign, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN

from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceFee,
    MarketplaceOrder,
    MarketplaceOrderItem,
)
from vayujit_api.identity.models import User
from vayujit_api.products.models import Product

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _commerce_fixture(
    context: dict[str, Any], *, currency: str = "INR", include_cost: bool = True
) -> None:
    assert test_ai_integration.factory is not None
    stamp = datetime.now(UTC)
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        product = db.get(Product, context["product"]["id"])
        assert owner is not None and product is not None
        product.cost_amount = Decimal("10.00") if include_cost else None
        product.price_currency = currency
        account = MarketplaceAccount(
            owner_id=owner.id,
            marketplace="amazon",
            display_name="Ads profitability commerce",
            seller_account_id="ads-profitability-seller",
            environment="sandbox",
            enabled=True,
            credential_status="configured",
            encrypted_credentials="test-only",
            validation_status="valid",
            capabilities_json={},
            configuration_json={},
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(account)
        db.flush()
        order = MarketplaceOrder(
            owner_id=owner.id,
            account_id=account.id,
            marketplace="amazon",
            remote_order_id=f"ads-profit-order-{currency}",
            status="confirmed",
            payment_status="paid",
            fulfilment_status="delivered",
            buyer_snapshot_json={},
            totals_json={"currency": currency, "gross": "200.00"},
            tax_amount=Decimal("0"),
            shipping_amount=Decimal("0"),
            discount_amount=Decimal("0"),
            ordered_at=stamp,
            remote_raw_status="confirmed",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(order)
        db.flush()
        db.add(
            MarketplaceOrderItem(
                owner_id=owner.id,
                order_id=order.id,
                product_id=product.id,
                title_snapshot=product.name,
                quantity=1,
                unit_price=Decimal("200.00"),
                total_price=Decimal("200.00"),
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            MarketplaceFee(
                owner_id=owner.id,
                account_id=account.id,
                order_id=order.id,
                fee_type="commission",
                amount=Decimal("20.00"),
                currency=currency,
                description="local acceptance fee",
                occurred_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()


def _analytics(client: Any, context: dict[str, Any], suffix: str) -> dict[str, Any]:
    campaign = create_campaign(client, context, suffix=suffix)
    recovery = client.post(
        "/api/v1/ads/recovery",
        json={
            "action": "retry",
            "entity_type": "campaign",
            "entity_id": campaign["id"],
            "failure_code": "ads.throttled",
            "confirm": True,
            "idempotency_key": f"publish-for-analytics:{suffix}",
        },
        headers=ORIGIN,
    )
    assert recovery.status_code == 200, recovery.text
    published = client.post(f"/api/v1/ads/jobs/{recovery.json()['job_id']}/run", headers=ORIGIN)
    assert published.status_code == 200 and published.json()["status"] == "succeeded"
    imported = client.post(f"/api/v1/ads/campaigns/{campaign['id']}/metrics/import", headers=ORIGIN)
    assert imported.status_code == 200, imported.text
    return client.get(f"/api/v1/ads/campaigns/{campaign['id']}/analytics", headers=ORIGIN).json()


def test_ads_profitability_uses_revenue_cogs_fees_and_ad_spend(client: Any) -> None:
    context = setup_ads_context(client)
    _commerce_fixture(context)
    body = _analytics(client, context, "profitability-complete")
    assert body["profitability"] == pytest.approx(45.0)
    assert body["profit_status"] == "available"
    assert body["cogs"] == pytest.approx(10.0)
    assert body["marketplace_fees"] == pytest.approx(20.0)


def test_ads_profitability_is_unavailable_without_required_commerce_value(client: Any) -> None:
    context = setup_ads_context(client)
    _commerce_fixture(context, include_cost=False)
    body = _analytics(client, context, "profitability-missing-cogs")
    assert body["profitability"] == "Unavailable"
    assert body["profit_status"] == "unavailable"


def test_ads_profitability_is_unavailable_for_currency_mismatch(client: Any) -> None:
    context = setup_ads_context(client)
    _commerce_fixture(context, currency="USD")
    body = _analytics(client, context, "profitability-currency-mismatch")
    assert body["profitability"] == "Unavailable"
    assert body["currency_compatible"] is False


def test_ads_roas_requires_positive_same_currency_spend_and_revenue(client: Any) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="roas-acceptance")
    recovery = client.post(
        "/api/v1/ads/recovery",
        json={
            "action": "retry",
            "entity_type": "campaign",
            "entity_id": campaign["id"],
            "failure_code": "ads.throttled",
            "confirm": True,
            "idempotency_key": "publish-for-roas",
        },
        headers=ORIGIN,
    )
    assert recovery.status_code == 200, recovery.text
    published = client.post(f"/api/v1/ads/jobs/{recovery.json()['job_id']}/run", headers=ORIGIN)
    assert published.status_code == 200 and published.json()["status"] == "succeeded"
    imported = client.post(f"/api/v1/ads/campaigns/{campaign['id']}/metrics/import", headers=ORIGIN)
    assert imported.status_code == 200
    conversion = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/conversions",
        json={
            "provider_event_id": "ads-roas-acceptance",
            "conversion_type": "purchase",
            "occurred_at": "2026-08-18T00:00:00Z",
            "value": "250.00",
            "currency": "INR",
            "attribution_type": "click_through",
            "attribution_window": "7d",
        },
        headers=ORIGIN,
    )
    assert conversion.status_code == 201, conversion.text
    body = client.get(f"/api/v1/ads/campaigns/{campaign['id']}/analytics", headers=ORIGIN).json()
    assert body["roas"] == pytest.approx(2.0)
    assert body["currency_compatible"] is True
    assert body["profitability"] == "Unavailable"
