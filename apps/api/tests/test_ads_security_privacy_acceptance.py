from __future__ import annotations

import pytest
from helpers.ads_acceptance import create_account, create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

SECRET_MARKERS = (
    "sk-",
    "token",
    "cookie",
    "password",
    "database_url",
    "postgresql://",
    "traceback",
    "c:\\users\\",
)


def test_account_responses_and_fake_connector_payloads_are_private(client) -> None:
    context = setup_ads_context(client)
    account = client.post(
        "/api/v1/ads/accounts",
        json={
            "provider": "meta",
            "external_account_id": "privacy-account",
            "display_name": "Privacy account",
            "credentials": {"access_token": "secret-value", "cookie": "secret-cookie"},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201
    text = account.text.lower()
    assert "secret-value" not in text
    assert "secret-cookie" not in text
    assert "credentials" not in text
    campaign = create_campaign(client, context, suffix="privacy")
    details = client.get(f"/api/v1/ads/campaigns/{campaign['id']}", headers=ORIGIN)
    assert details.status_code == 200
    assert all(marker not in details.text.lower() for marker in SECRET_MARKERS)


def test_cross_provider_campaign_and_account_mismatch_is_rejected(client) -> None:
    context = setup_ads_context(client)
    meta = create_account(client, "meta", "isolation")
    payload = {
        "provider": "google",
        "account_id": meta["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": "Provider mismatch",
        "objective": "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": "provider-mismatch",
    }
    response = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert response.status_code == 422
    assert all(marker not in response.text.lower() for marker in SECRET_MARKERS)


def test_private_failure_projection_never_returns_provider_body(client) -> None:
    assert all(
        marker not in "The Ads operation failed safely.".lower() for marker in SECRET_MARKERS
    )
