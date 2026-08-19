from __future__ import annotations

from typing import Any

import pytest
from helpers.ads_acceptance import create_account, create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

from vayujit_api.ads.connectors import CONNECTORS, FakeAdsState

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _reset_connectors() -> None:
    for connector in CONNECTORS.values():
        connector.state = FakeAdsState()


def _publish(client: Any, context: dict[str, Any], provider: str, suffix: str) -> dict[str, Any]:
    account = create_account(client, provider, suffix)
    payload = {
        "provider": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": f"{provider} {suffix}",
        "objective": "awareness" if provider == "meta" else "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"{provider}-{suffix}",
    }
    preview = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    job = client.post(f"/api/v1/ads/jobs/{confirmed.json()['job']['id']}/run", headers=ORIGIN)
    assert job.status_code == 200 and job.json()["status"] == "succeeded", job.text
    detail = client.get(
        f"/api/v1/ads/campaigns/{confirmed.json()['campaign']['id']}", headers=ORIGIN
    )
    assert detail.status_code == 200, detail.text
    return detail.json()["campaign"]


def _create_ad(client: Any, campaign: dict[str, Any], key: str) -> dict[str, Any]:
    placement = "feed" if campaign["provider"] == "meta" else "search"
    creative = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives",
        json={
            "campaign_id": campaign["id"],
            "product_id": campaign["product_id"],
            "creative_type": "manual",
            "headline": "Exact version",
            "primary_text": "Safe product message",
            "cta": "shop_now",
            "destination_url": "https://example.com/product",
            "placements": [placement],
            "idempotency_key": f"{key}-creative",
        },
        headers=ORIGIN,
    )
    assert creative.status_code == 201, creative.text
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={"name": f"{key} group", "placements": [placement], "idempotency_key": f"{key}-group"},
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
            "idempotency_key": f"{key}-ad",
        },
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    run = client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN)
    assert run.status_code == 200 and run.json()["status"] == "succeeded", run.text
    return {"creative": creative.json(), "group": group.json(), "ad": ad.json()}


def test_account_disable_blocks_worker_before_connector(client: Any) -> None:
    _reset_connectors()
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="disabled-worker")
    account_id = campaign["account_id"]
    # The normal preview/confirmation path is used so disabling happens after a durable Job exists.
    payload = {
        "provider": campaign["provider"],
        "account_id": account_id,
        "brand_id": campaign["brand_id"],
        "product_id": campaign["product_id"],
        "name": campaign["name"],
        "objective": campaign["objective"],
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": "disabled-worker-confirm",
    }
    preview = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200
    confirmed = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200
    disabled = client.post(f"/api/v1/ads/accounts/{account_id}/disable", headers=ORIGIN)
    assert disabled.status_code == 200
    result = client.post(f"/api/v1/ads/jobs/{confirmed.json()['job']['id']}/run", headers=ORIGIN)
    assert result.status_code == 200 and result.json()["status"] == "failed"
    assert result.json()["failure_code"] == "ads.account_disabled"
    assert not CONNECTORS["meta"].state.calls and not CONNECTORS["google"].state.calls
    recovery = client.get("/api/v1/ads/recovery", headers=ORIGIN)
    assert recovery.status_code == 200 and any(
        row["failure_code"] == "ads.account_disabled" for row in recovery.json()
    )


def test_meta_google_provider_failures_are_isolated(client: Any) -> None:
    _reset_connectors()
    context = setup_ads_context(client)
    meta = _publish(client, context, "meta", "isolation-meta")
    google = _publish(client, context, "google", "isolation-google")
    meta_remote = meta["remote_campaign_id"]
    google_remote = google["remote_campaign_id"]
    CONNECTORS["meta"].state.failures["update_campaign"] = "throttled"
    paused = client.post(
        f"/api/v1/ads/campaigns/{meta['id']}/action",
        json={"action": "pause", "confirm": True},
        headers=ORIGIN,
    )
    assert paused.status_code == 200
    failed = client.post(f"/api/v1/ads/jobs/{paused.json()['job_id']}/run", headers=ORIGIN)
    assert failed.status_code == 200 and failed.json()["status"] == "retry_wait"
    assert CONNECTORS["google"].state.entities["campaign"][google_remote]["state"] == "active"
    assert CONNECTORS["meta"].state.entities["campaign"][meta_remote]["state"] == "active"
    CONNECTORS["meta"].state.failures.clear()
    CONNECTORS["google"].state.failures["update_campaign"] = "throttled"
    paused_google = client.post(
        f"/api/v1/ads/campaigns/{google['id']}/action",
        json={"action": "pause", "confirm": True},
        headers=ORIGIN,
    )
    assert paused_google.status_code == 200
    failed_google = client.post(
        f"/api/v1/ads/jobs/{paused_google.json()['job_id']}/run", headers=ORIGIN
    )
    assert failed_google.status_code == 200 and failed_google.json()["status"] == "retry_wait"
    assert CONNECTORS["meta"].state.entities["campaign"][meta_remote]["state"] == "active"


def test_meta_and_google_connector_payloads_are_private(client: Any) -> None:
    _reset_connectors()
    context = setup_ads_context(client)
    for provider in ("meta", "google"):
        campaign = _publish(client, context, provider, f"privacy-{provider}")
        _create_ad(client, campaign, f"privacy-{provider}")
        payload_text = " ".join(
            str(call.get("payload", {})) for call in CONNECTORS[provider].state.calls
        ).casefold()
        forbidden = (
            "buyer",
            "email",
            "phone",
            "address",
            "order",
            "payment",
            "settlement",
            "credential",
            "token",
            "dsn",
            "c:\\",
            "password",
        )
        assert all(value not in payload_text for value in forbidden)
