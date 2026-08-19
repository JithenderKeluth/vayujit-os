from __future__ import annotations

import pytest
from helpers.ads_acceptance import create_account, create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_budget_v1_to_v2_is_preview_safe_and_exactly_confirmed(client) -> None:
    context = setup_ads_context(client)
    account = create_account(client, "meta", "budget-version")
    payload = {
        "provider": "meta",
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": "budget version",
        "objective": "awareness",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": "budget-version-campaign",
    }
    preview_campaign = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview_campaign.status_code == 200, preview_campaign.text
    created = client.post("/api/v1/ads/campaigns", json=payload, headers=ORIGIN)
    assert created.status_code == 201, created.text
    campaign = created.json()
    confirmed_campaign = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview_campaign.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed_campaign.status_code == 200, confirmed_campaign.text
    job_id = confirmed_campaign.json()["job"]["id"]
    assert (
        client.post(f"/api/v1/ads/jobs/{job_id}/run", headers=ORIGIN).json()["status"]
        == "succeeded"
    )
    published = client.get(f"/api/v1/ads/campaigns/{campaign['id']}", headers=ORIGIN).json()[
        "campaign"
    ]
    assert published["budget"]["version"] == 1
    assert published["remote_campaign_id"]

    preview = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/preview",
        json={"proposed": {"daily_amount": "40", "currency": "INR"}, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["mutates"] is False
    assert preview.json()["proposed_budget_version"] == 2
    before = client.get(f"/api/v1/ads/campaigns/{campaign['id']}", headers=ORIGIN).json()
    assert before["campaign"]["budget"]["version"] == 1

    confirmed = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/confirm",
        json={
            "proposed": {"daily_amount": "40", "currency": "INR"},
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": "budget-version-v2",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["budget"]["version"] == 2
    assert confirmed.json()["job"]["status"] == "queued"
    after_confirm = client.get(f"/api/v1/ads/campaigns/{campaign['id']}", headers=ORIGIN).json()
    assert after_confirm["campaign"]["budget"]["version"] == 2

    stale = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/confirm",
        json={
            "proposed": {"daily_amount": "45", "currency": "INR"},
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": "budget-version-stale",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409


def test_budget_confirm_requires_exact_fingerprint(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="budget-fingerprint")
    preview = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/preview",
        json={"proposed": {"daily_amount": "40", "currency": "INR"}, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200
    response = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/confirm",
        json={
            "proposed": {"daily_amount": "40", "currency": "INR"},
            "expected_version": 1,
            "preview_fingerprint": "0" * 64,
            "idempotency_key": "budget-wrong-fingerprint",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 409
