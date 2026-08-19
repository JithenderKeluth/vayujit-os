from __future__ import annotations

from typing import Any

import pytest
from helpers.ads_acceptance import create_account, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _campaign(client, context: dict[str, Any], provider: str = "meta") -> dict[str, object]:
    account = create_account(client, provider, "e2e")
    payload = {
        "provider": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": f"{provider} durable E2E",
        "objective": "awareness" if provider == "meta" else "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"{provider}-e2e-campaign",
    }
    preview = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    confirmation = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmation.status_code == 200, confirmation.text
    campaign = confirmation.json()["campaign"]
    job = client.post(f"/api/v1/ads/jobs/{confirmation.json()['job']['id']}/run", headers=ORIGIN)
    assert job.status_code == 200 and job.json()["status"] == "succeeded"
    return campaign


def test_meta_durable_campaign_group_ad_metrics_conversion_and_channel(client) -> None:
    context = setup_ads_context(client)
    campaign = _campaign(client, context)
    creative = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives",
        json={
            "campaign_id": campaign["id"],
            "product_id": context["product"]["id"],
            "creative_type": "manual",
            "headline": "Trail Bottle",
            "primary_text": "Built for the journey.",
            "cta": "shop_now",
            "destination_url": "https://example.com/trail-bottle",
            "placements": ["feed", "story"],
            "idempotency_key": "meta-e2e-creative",
        },
        headers=ORIGIN,
    )
    assert creative.status_code == 201, creative.text
    assert creative.json()["readiness"]["ready"] is True
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={"name": "Meta ad set", "placements": ["feed"], "idempotency_key": "meta-e2e-group"},
        headers=ORIGIN,
    )
    assert group.status_code == 201, group.text
    group_run = client.post(f"/api/v1/ads/jobs/{group.json()['job_id']}/run", headers=ORIGIN)
    assert group_run.json()["status"] == "succeeded"
    ad = client.post(
        f"/api/v1/ads/groups/{group.json()['id']}/ads",
        json={
            "creative_id": creative.json()["id"],
            "placement": "feed",
            "idempotency_key": "meta-e2e-ad",
        },
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    ad_run = client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN)
    assert ad_run.json()["status"] == "succeeded"
    metrics = client.post(f"/api/v1/ads/campaigns/{campaign['id']}/metrics/import", headers=ORIGIN)
    assert metrics.status_code == 200
    conversion = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/conversions",
        json={
            "provider_event_id": "meta-e2e-purchase",
            "conversion_type": "purchase",
            "occurred_at": "2026-08-18T00:00:00Z",
            "value": "99.00",
            "currency": "INR",
            "attribution_type": "click_through",
            "attribution_window": "7d",
        },
        headers=ORIGIN,
    )
    assert conversion.status_code == 201, conversion.text
    analytics = client.get(f"/api/v1/ads/campaigns/{campaign['id']}/analytics", headers=ORIGIN)
    assert analytics.status_code == 200
    assert analytics.json()["currency_compatible"] is True
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200
    body = channel.json()["providers"][0]
    assert body["campaign"]["provider"] == "meta"
    assert body["ads"][0]["remote_id"]
    assert "never-returned" not in channel.text
