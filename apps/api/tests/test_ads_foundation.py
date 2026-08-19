import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)

pytestmark = pytest.mark.integration


def test_capabilities_are_server_driven_and_local_only(client) -> None:
    setup_context(client)
    response = client.get("/api/v1/ads/capabilities", headers=ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["status"] == "fake_certified"
    assert body["google"]["status"] == "fake_certified"
    assert "search" in body["google"]["campaign_types"]
    assert "instagram" in body["meta"]["platforms"]


def test_account_preview_confirm_worker_and_synthetic_metrics(client) -> None:
    context = setup_context(client)
    account = client.post(
        "/api/v1/ads/accounts",
        json={
            "provider": "meta",
            "external_account_id": "act_local_001",
            "display_name": "Meta local",
            "credentials": {"token": "never-returned"},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201, account.text
    assert "credentials" not in account.json()
    account_id = account.json()["id"]
    assert (
        client.post(f"/api/v1/ads/accounts/{account_id}/validate", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/ads/accounts/{account_id}/enable", headers=ORIGIN).status_code == 200
    )
    payload = {
        "provider": "meta",
        "account_id": account_id,
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": "Northstar local awareness",
        "objective": "awareness",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": "ads-campaign-001",
    }
    preview = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    assert preview.json()["mutates"] is False
    confirmed = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            **payload,
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    job_id = confirmed.json()["job"]["id"]
    assert (
        client.post(f"/api/v1/ads/jobs/{job_id}/run", headers=ORIGIN).json()["status"]
        == "succeeded"
    )
    campaign_id = confirmed.json()["campaign"]["id"]
    metrics = client.post(f"/api/v1/ads/campaigns/{campaign_id}/metrics/import", headers=ORIGIN)
    assert metrics.status_code == 200
    assert all(item["availability"] == "synthetic" for item in metrics.json())
    assert (
        client.post(f"/api/v1/ads/jobs/{job_id}/run", headers=ORIGIN).json()["status"]
        == "succeeded"
    )


def test_destination_and_account_disable_safety(client) -> None:
    context = setup_context(client)
    account = client.post(
        "/api/v1/ads/accounts",
        json={
            "provider": "google",
            "external_account_id": "customers/local",
            "display_name": "Google local",
            "credentials": {"key": "opaque"},
        },
        headers=ORIGIN,
    ).json()
    account_id = account["id"]
    client.post(f"/api/v1/ads/accounts/{account_id}/validate", headers=ORIGIN)
    client.post(f"/api/v1/ads/accounts/{account_id}/enable", headers=ORIGIN)
    payload = {
        "provider": "google",
        "account_id": account_id,
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": "Search local",
        "objective": "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": "google-local-001",
    }
    campaign = client.post("/api/v1/ads/campaigns", json=payload, headers=ORIGIN)
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["id"]
    unsafe = client.post(
        f"/api/v1/ads/campaigns/{campaign_id}/creatives",
        json={
            "campaign_id": campaign_id,
            "creative_type": "manual",
            "destination_url": "javascript:alert(1)",
            "idempotency_key": "unsafe-creative",
        },
        headers=ORIGIN,
    )
    assert unsafe.status_code == 422
    client.post(f"/api/v1/ads/accounts/{account_id}/disable", headers=ORIGIN)
    preview = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 422
