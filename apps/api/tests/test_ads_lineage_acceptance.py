from __future__ import annotations

from typing import Any

import pytest
from helpers.ads_acceptance import create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _manual_ad(client: Any, campaign: dict[str, Any]) -> dict[str, Any]:
    creative = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives",
        json={
            "campaign_id": campaign["id"],
            "product_id": campaign["product_id"],
            "creative_type": "manual",
            "headline": "Lineage v1",
            "primary_text": "Exact creative",
            "cta": "shop_now" if campaign["provider"] == "meta" else None,
            "destination_url": "https://example.com/lineage",
            "placements": ["feed" if campaign["provider"] == "meta" else "search"],
            "idempotency_key": f"lineage-{campaign['provider']}-creative",
        },
        headers=ORIGIN,
    )
    assert creative.status_code == 201, creative.text
    placement = "feed" if campaign["provider"] == "meta" else "search"
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={
            "name": "Lineage group",
            "placements": [placement],
            "idempotency_key": f"lineage-{campaign['provider']}-group",
        },
        headers=ORIGIN,
    )
    assert group.status_code == 201, group.text
    group_run = client.post(f"/api/v1/ads/jobs/{group.json()['job_id']}/run", headers=ORIGIN)
    assert group_run.status_code == 200 and group_run.json()["status"] == "succeeded"
    ad = client.post(
        f"/api/v1/ads/groups/{group.json()['id']}/ads",
        json={
            "creative_id": creative.json()["id"],
            "placement": placement,
            "idempotency_key": f"lineage-{campaign['provider']}-ad",
        },
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    ad_run = client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN)
    assert ad_run.status_code == 200 and ad_run.json()["status"] == "succeeded"
    return {"creative": creative.json(), "group": group.json(), "ad": ad.json()}


def test_campaign_calendar_and_storage_preserve_exact_ads_lineage(client: Any) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(
        client,
        context,
        provider="meta",
        suffix="calendar-lineage",
        start_at="2026-08-19T10:00:00+00:00",
        end_at="2026-08-19T11:00:00+00:00",
    )
    published = client.post(
        "/api/v1/ads/campaigns/preview",
        json={
            "provider": "meta",
            "account_id": campaign["account_id"],
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "name": "calendar-lineage-published",
            "objective": "awareness",
            "budget": {"daily_amount": "25", "currency": "INR"},
            "start_at": "2026-08-19T10:00:00+00:00",
            "end_at": "2026-08-19T11:00:00+00:00",
            "idempotency_key": "calendar-lineage-published",
        },
        headers=ORIGIN,
    )
    assert published.status_code == 200, published.text
    confirm = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            "campaign": {
                "provider": "meta",
                "account_id": campaign["account_id"],
                "brand_id": context["brand"]["id"],
                "product_id": context["product"]["id"],
                "name": "calendar-lineage-published",
                "objective": "awareness",
                "budget": {"daily_amount": "25", "currency": "INR"},
                "start_at": "2026-08-19T10:00:00+00:00",
                "end_at": "2026-08-19T11:00:00+00:00",
                "idempotency_key": "calendar-lineage-published",
            },
            "preview_fingerprint": published.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirm.status_code == 200, confirm.text
    campaign_id = confirm.json()["campaign"]["id"]
    run = client.post(f"/api/v1/ads/jobs/{confirm.json()['job']['id']}/run", headers=ORIGIN)
    assert run.status_code == 200 and run.json()["status"] == "succeeded"
    detail = client.get(f"/api/v1/ads/campaigns/{campaign_id}", headers=ORIGIN).json()["campaign"]
    lineage = _manual_ad(client, detail)
    schedule = client.post(
        f"/api/v1/ads/campaigns/{campaign_id}/schedule",
        json={
            "start_at": "2026-08-19T10:00:00Z",
            "end_at": "2026-08-19T11:00:00Z",
            "timezone": "UTC",
            "state": "scheduled",
        },
        headers=ORIGIN,
    )
    assert schedule.status_code == 201, schedule.text
    calendar = client.get("/api/v1/ads/calendar", headers=ORIGIN)
    assert calendar.status_code == 200, calendar.text
    row = next(item for item in calendar.json() if str(item["campaign_id"]) == campaign_id)
    assert str(lineage["group"]["id"]) in {str(value) for value in row["group_ids"]}
    assert str(lineage["ad"]["id"]) in {str(value) for value in row["ad_ids"]}
    assert str(lineage["creative"]["id"]) in {str(value) for value in row["creative_ids"]}
    assert row["creative_versions"] == [None]
    assert row["budget_version"] == 1
    assert row["timezone"] == "UTC" and row["state"] == "scheduled"
    storage = client.get("/api/v1/ads/storage/integrity", headers=ORIGIN)
    assert storage.status_code == 200, storage.text
    body = storage.json()
    assert body["safe"] is True
    assert all(value == 0 for value in body["duplicates"].values())
    assert all(value == 0 for value in body["orphans"].values())
    assert all(value == 0 for value in body["lineage"].values())
    assert body["isolation"] == {"cross_owner": 0, "cross_provider": 0}
