from __future__ import annotations

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _account(client, provider: str = "meta") -> dict[str, object]:
    response = client.post(
        "/api/v1/ads/accounts",
        json={
            "provider": provider,
            "external_account_id": f"local-{provider}-hard-closure",
            "display_name": f"{provider} hard closure",
            "credentials": {"opaque": "never-returned"},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    value = response.json()
    account_id = value["id"]
    assert (
        client.post(f"/api/v1/ads/accounts/{account_id}/validate", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/ads/accounts/{account_id}/enable", headers=ORIGIN).status_code == 200
    )
    return value


def _campaign(client, context: dict[str, dict[str, object]]) -> dict[str, object]:
    account = _account(client)
    response = client.post(
        "/api/v1/ads/campaigns",
        json={
            "provider": "meta",
            "account_id": account["id"],
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "name": "Hard closure campaign",
            "objective": "awareness",
            "budget": {"daily_amount": "25", "currency": "INR"},
            "idempotency_key": "hard-closure-campaign",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_audience_validation_failure_catalog_and_recovery_idempotency(client) -> None:
    context = setup_context(client)
    audience = client.post(
        "/api/v1/ads/audiences",
        json={
            "name": "Local abstract audience",
            "geography": ["IN"],
            "languages": ["en-IN"],
            "age_min": 25,
            "age_max": 45,
            "interests": ["home"],
            "exclusions": ["existing_customers"],
            "keyword_intent": {"positive": ["home decor"], "negative": ["free"]},
        },
        headers=ORIGIN,
    )
    assert audience.status_code == 201, audience.text
    audience_id = audience.json()["id"]
    validated = client.post(f"/api/v1/ads/audiences/{audience_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    assert validated.json()["validation_status"] == "valid"
    catalog = client.get("/api/v1/ads/failures/catalog", headers=ORIGIN)
    assert catalog.status_code == 200
    assert len(catalog.json()) == 16
    campaign = _campaign(client, context)
    payload = {
        "action": "reconcile",
        "entity_type": "campaign",
        "entity_id": campaign["id"],
        "confirm": True,
        "idempotency_key": "reconcile-hard-closure",
    }
    first = client.post("/api/v1/ads/recovery", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/ads/recovery", json=payload, headers=ORIGIN)
    assert first.status_code == second.status_code == 200
    assert second.json()["idempotent_reuse"] is True


def test_budget_confirmation_is_durable_and_analytics_are_explicit(client) -> None:
    context = setup_context(client)
    campaign = _campaign(client, context)
    preview = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/preview",
        json={"proposed": {"daily_amount": "40", "currency": "INR"}, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["mutates"] is False
    confirmed = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/budget/confirm",
        json={
            "proposed": {"daily_amount": "40", "currency": "INR"},
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": "budget-hard-closure",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["budget"]["version"] == 2
    analytics = client.get(f"/api/v1/ads/campaigns/{campaign['id']}/analytics", headers=ORIGIN)
    assert analytics.status_code == 200
    assert analytics.json()["roas"] is None
    assert analytics.json()["profitability"] == "Unavailable"
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200, channel.text
    assert channel.json()["providers"]


def test_ads_capability_and_ambiguous_connector_contract() -> None:
    from vayujit_api.ads.connectors import AdsConnectorError, FakeAdsState, FakeMetaAdsConnector
    from vayujit_api.ads.failure import ADS_FAILURE_TAXONOMY

    assert len(ADS_FAILURE_TAXONOMY) == 16
    assert "target_roas" in FakeMetaAdsConnector().capabilities()["bidding_strategies"]
    state = FakeAdsState()
    connector = FakeMetaAdsConnector(state)
    state.failures["create_campaign"] = "ambiguous"
    try:
        connector.create_campaign("local-campaign", {"objective": "awareness"})
    except AdsConnectorError as error:
        assert error.code == "ads.ambiguous_result"
        assert error.ambiguous is True
    else:
        raise AssertionError("ambiguous connector response was not raised")
    assert len(state.entities["campaign"]) == 1
    remote_id = next(iter(state.entities["campaign"]))
    assert connector.lookup("campaign", remote_id) is not None
