from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from helpers.ads_acceptance import create_account, setup_ads_context
from test_ai_integration import ORIGIN, generate

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def listing(
    client: Any, context: dict[str, Any], account: dict[str, Any], provider: str, version: int = 1
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/ads/marketplace/listings",
        json={
            "account_id": account["id"],
            "product_id": context["product"]["id"],
            "marketplace": provider,
            "listing_id": f"{provider.upper()}-SKU-001",
            "version": version,
            "title": f"{provider.title()} local product",
            "sku": f"SKU-{version}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def payload(
    context: dict[str, Any], account: dict[str, Any], item: dict[str, Any], provider: str
) -> dict[str, Any]:
    return {
        "provider": provider,
        "marketplace": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "listing_id": item["listing_id"],
        "listing_version": item["version"],
        "listing_state": item["state"],
        "name": f"{provider.title()} Sponsored Product",
        "objective": "sales",
        "bidding_strategy": "dynamic_down_only" if provider == "amazon" else "manual_cpc",
        "targeting_summary": {
            "target_type": "keywords" if provider == "amazon" else "product",
            "positive_keywords": ["heritage"],
            "negative_keywords": ["clearance"],
            "match_type": "exact",
            "locale": "en-IN",
        },
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"{provider}-campaign-001",
    }


def test_marketplace_capabilities_and_meesho_boundary(client: Any) -> None:
    setup_ads_context(client)
    response = client.get("/api/v1/ads/marketplace/capabilities", headers=ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["amazon"]["status"] == "fake_certified"
    assert body["amazon"]["listing_required"] is True
    assert body["amazon"]["video_support"] is False
    assert body["flipkart"]["status"] == "fake_certified"
    assert body["meesho"]["status"] == "not_supported"
    assert "credentials" not in response.text.lower()


def test_amazon_local_e2e_listing_preview_confirm_worker_group_ad_metrics_reconcile(
    client: Any,
) -> None:
    context = setup_ads_context(client)
    account = create_account(client, "amazon", "marketplace")
    item = listing(client, context, account, "amazon")
    data = payload(context, account, item, "amazon")
    readiness = client.post(
        "/api/v1/ads/marketplace/campaigns/readiness", json=data, headers=ORIGIN
    )
    assert readiness.status_code == 200 and readiness.json()["ready"] is True
    preview = client.post("/api/v1/ads/marketplace/campaigns/preview", json=data, headers=ORIGIN)
    assert preview.status_code == 200 and preview.json()["mutates"] is False
    confirmed = client.post(
        "/api/v1/ads/marketplace/campaigns/confirm",
        json={
            "campaign": data,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    campaign = confirmed.json()["campaign"]
    job = client.post(f"/api/v1/ads/jobs/{confirmed.json()['job']['id']}/run", headers=ORIGIN)
    assert job.json()["status"] == "succeeded"
    assert job.json()["result"]["remote_id"].startswith("amz_campaign_")
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={
            "name": "Amazon keywords",
            "targeting": {"keywords": ["heritage"], "match_type": "exact"},
            "idempotency_key": "amazon-group-001",
        },
        headers=ORIGIN,
    )
    assert group.status_code == 201, group.text
    assert (
        client.post(f"/api/v1/ads/jobs/{group.json()['job_id']}/run", headers=ORIGIN).json()[
            "status"
        ]
        == "succeeded"
    )
    generated = generate(client, context["product"]["id"], "Amazon sponsored product copy")
    assert generated.status_code == 201
    artifact_id = generated.json()["artifact_id"]
    approved = client.post(f"/api/v1/ai/artifacts/{artifact_id}/approve", headers=ORIGIN)
    assert approved.status_code == 200
    creative = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives",
        json={
            "campaign_id": campaign["id"],
            "product_id": context["product"]["id"],
            "creative_type": "content",
            "artifact_id": artifact_id,
            "artifact_version": 1,
            "headline": "Heritage",
            "destination_url": "https://example.com/listing",
            "placements": ["search"],
            "idempotency_key": "amazon-creative-001",
        },
        headers=ORIGIN,
    )
    assert creative.status_code == 201, creative.text
    ad = client.post(
        f"/api/v1/ads/groups/{group.json()['id']}/ads",
        json={
            "creative_id": creative.json()["id"],
            "placement": "search",
            "idempotency_key": "amazon-ad-001",
        },
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    assert (
        client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN).json()["status"]
        == "succeeded"
    )
    metrics = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/metrics/import", headers=ORIGIN
    )
    assert metrics.status_code == 200 and {row["metric_key"] for row in metrics.json()} >= {
        "impressions",
        "clicks",
        "spend",
        "conversions",
        "sales",
    }
    conversion = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/conversions",
        json={
            "provider_event_id": "amazon-order-001",
            "conversion_type": "sale",
            "occurred_at": datetime.now(UTC).isoformat(),
            "value": "250",
            "currency": "INR",
        },
        headers=ORIGIN,
    )
    assert conversion.status_code == 201
    reconcile = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/reconcile", headers=ORIGIN
    )
    assert reconcile.status_code == 200 and reconcile.json()["reconciliation_state"] == "matched"


def test_flipkart_isolation_and_listing_version_safety(client: Any) -> None:
    context = setup_ads_context(client)
    account = create_account(client, "flipkart", "marketplace")
    item = listing(client, context, account, "flipkart")
    data = payload(context, account, item, "flipkart")
    preview = client.post("/api/v1/ads/marketplace/campaigns/preview", json=data, headers=ORIGIN)
    assert preview.status_code == 200 and preview.json()["provider"] == "flipkart"
    confirmed = client.post(
        "/api/v1/ads/marketplace/campaigns/confirm",
        json={
            "campaign": data,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "flipkart-idempotent",
        },
        headers=ORIGIN,
    )
    repeated = client.post(
        "/api/v1/ads/marketplace/campaigns/confirm",
        json={
            "campaign": data,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "flipkart-idempotent",
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == repeated.status_code == 200
    assert confirmed.json()["campaign"]["id"] == repeated.json()["campaign"]["id"]
    item_v2 = listing(client, context, account, "flipkart", version=2)
    changed = dict(data, listing_version=item_v2["version"])
    changed_preview = client.post(
        "/api/v1/ads/marketplace/campaigns/preview", json=changed, headers=ORIGIN
    )
    assert changed_preview.status_code == 200 and changed_preview.json()["listing"]["version"] == 2
    assert confirmed.json()["campaign"]["listing_version"] == 1


def test_marketplace_account_disable_security_and_storage_integrity(client: Any) -> None:
    context = setup_ads_context(client)
    account = create_account(client, "amazon", "safety")
    item = listing(client, context, account, "amazon")
    data = payload(context, account, item, "amazon")
    preview = client.post("/api/v1/ads/marketplace/campaigns/preview", json=data, headers=ORIGIN)
    confirmed = client.post(
        "/api/v1/ads/marketplace/campaigns/confirm",
        json={
            "campaign": data,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "amazon-disable",
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200
    client.post(f"/api/v1/ads/accounts/{account['id']}/disable", headers=ORIGIN)
    job = client.post(f"/api/v1/ads/jobs/{confirmed.json()['job']['id']}/run", headers=ORIGIN)
    assert job.json()["status"] == "failed" and job.json()["failure_code"] == "ads.account_disabled"
    channel = client.get(
        f"/api/v1/ads/marketplace/product-channel/{context['product']['id']}", headers=ORIGIN
    )
    assert channel.status_code == 200 and "open_recovery" in channel.json()["actions"]
    integrity = client.get("/api/v1/ads/storage/integrity", headers=ORIGIN)
    assert integrity.status_code == 200 and integrity.json()["safe"] is True
    assert all(value == 0 for value in integrity.json()["duplicates"].values())
    assert all(value == 0 for value in integrity.json()["orphans"].values())
