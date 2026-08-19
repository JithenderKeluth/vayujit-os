from __future__ import annotations

import pytest
from helpers.ads_acceptance import create_account, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_google_search_e2e_uses_exact_keyword_set_and_product_channel(client) -> None:
    context = setup_ads_context(client)
    keywords = client.post(
        "/api/v1/ai/seo/keywords",
        json={
            "name": "Trail keywords",
            "product_id": context["product"]["id"],
            "brand_id": context["brand"]["id"],
            "locale": "en-IN",
            "primary": ["trail bottle"],
            "secondary": ["insulated bottle"],
            "campaign": ["buy trail bottle"],
        },
        headers=ORIGIN,
    )
    assert keywords.status_code == 201, keywords.text
    account = create_account(client, "google", "search-e2e")
    payload = {
        "provider": "google",
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": "Google Search acceptance",
        "objective": "traffic",
        "keyword_set_id": keywords.json()["id"],
        "targeting_summary": {"locale": "en-IN"},
        "bidding_strategy": "manual_cpc",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": "google-search-e2e-campaign",
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
    run = client.post(f"/api/v1/ads/jobs/{confirmation.json()['job']['id']}/run", headers=ORIGIN)
    assert run.status_code == 200 and run.json()["status"] == "succeeded"
    metrics = client.post(
        f"/api/v1/ads/campaigns/{confirmation.json()['campaign']['id']}/metrics/import",
        headers=ORIGIN,
    )
    assert metrics.status_code == 200
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200
    assert channel.json()["providers"][0]["campaign"]["provider"] == "google"
    assert "credentials" not in channel.text.lower()


@pytest.mark.parametrize(
    "campaign_type,creative_type",
    [("display", "image"), ("video", "video")],
)
def test_google_display_and_video_require_exact_approved_media(
    client, campaign_type: str, creative_type: str
) -> None:
    context = setup_ads_context(client)
    account = create_account(client, "google", f"{campaign_type}-readiness")
    payload = {
        "provider": "google",
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": f"Google {campaign_type}",
        "objective": "awareness",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"google-{campaign_type}-readiness",
    }
    campaign = client.post("/api/v1/ads/campaigns", json=payload, headers=ORIGIN)
    assert campaign.status_code == 201, campaign.text
    readiness = client.post(
        "/api/v1/ads/creatives/readiness",
        json={
            "campaign_id": campaign.json()["id"],
            "product_id": context["product"]["id"],
            "creative_type": creative_type,
            (
                "image_output_id" if creative_type == "image" else "video_generation_id"
            ): "00000000-0000-4000-8000-000000000001",
            (
                "image_media_id" if creative_type == "image" else "video_output_id"
            ): "00000000-0000-4000-8000-000000000002",
            "video_media_id": (
                "00000000-0000-4000-8000-000000000003" if creative_type == "video" else None
            ),
            "image_version" if creative_type == "image" else "video_version": 1,
            "idempotency_key": f"{campaign_type}-readiness",
        },
        headers=ORIGIN,
    )
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False
    assert "exact" in " ".join(readiness.json()["blockers"]).lower()
