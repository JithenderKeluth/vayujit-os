from __future__ import annotations

import pytest
from helpers.ads_acceptance import create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _manual(client, campaign: dict[str, object], key: str, headline: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives",
        json={
            "campaign_id": campaign["id"],
            "product_id": campaign["product_id"],
            "creative_type": "manual",
            "headline": headline,
            "primary_text": "Trusted product content.",
            "cta": "shop_now",
            "destination_url": "https://example.com/product",
            "placements": ["feed"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_exact_creative_registration_is_non_mutating_and_update_visible(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="creative-versions")
    first = _manual(client, campaign, "creative-v1", "Version one")
    second = _manual(client, campaign, "creative-v2", "Version two")
    assert first["id"] != second["id"]
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200
    provider = channel.json()["providers"][0]
    assert provider["update_available"] is True
    assert {creative["id"] for creative in provider["creatives"]} == {
        first["id"],
        second["id"],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"destination_url": "http://example.com/product"},
        {"destination_url": "https://user:password@example.com/product"},
        {"placements": ["unsupported-placement"]},
    ],
)
def test_creative_readiness_rejects_unsafe_or_incompatible_inputs(client, payload) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="creative-safety")
    request = {
        "campaign_id": campaign["id"],
        "creative_type": "manual",
        "headline": "Safe headline",
        "cta": "shop_now",
        "destination_url": "https://example.com/product",
        "placements": ["feed"],
        "idempotency_key": "creative-safety",
    }
    request.update(payload)
    response = client.post("/api/v1/ads/creatives/readiness", json=request, headers=ORIGIN)
    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert "traceback" not in response.text.lower()


def test_creative_replacement_is_previewed_confirmed_and_idempotent(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="creative-replacement")
    first = _manual(client, campaign, "creative-replacement-v1", "Version one")
    second = _manual(client, campaign, "creative-replacement-v2", "Version two")
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={
            "name": "Replacement group",
            "placements": ["feed"],
            "idempotency_key": "replacement-group",
        },
        headers=ORIGIN,
    )
    assert group.status_code == 201, group.text
    group_run = client.post(f"/api/v1/ads/jobs/{group.json()['job_id']}/run", headers=ORIGIN)
    assert group_run.status_code == 200, group_run.text
    ad = client.post(
        f"/api/v1/ads/groups/{group.json()['id']}/ads",
        json={"creative_id": first["id"], "placement": "feed", "idempotency_key": "replacement-ad"},
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    ad_run = client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN)
    assert ad_run.status_code == 200, ad_run.text

    preview = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{ad.json()['id']}/creative/preview",
        json={"creative_id": second["id"]},
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["mutates"] is False
    replacement = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{ad.json()['id']}/creative/confirm",
        json={
            "creative_id": second["id"],
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": "replacement-confirm",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert replacement.status_code == 200, replacement.text
    run = client.post(f"/api/v1/ads/jobs/{replacement.json()['job_id']}/run", headers=ORIGIN)
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "succeeded"

    repeated = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{ad.json()['id']}/creative/confirm",
        json={
            "creative_id": second["id"],
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": "replacement-confirm",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["job_id"] == replacement.json()["job_id"]

    stale = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{ad.json()['id']}/creative/confirm",
        json={
            "creative_id": first["id"],
            "preview_fingerprint": "0" * 64,
            "idempotency_key": "replacement-stale",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200
    ads = channel.json()["providers"][0]["ads"]
    assert ads[0]["creative_id"] == second["id"]
