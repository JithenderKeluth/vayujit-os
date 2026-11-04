"""Migration-backed local Video/Ads service contracts; no workers or live providers."""

import uuid

import pytest

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


@pytest.fixture
def local(pr56_client):
    c = pr56_client

    def post(path, data):
        result = c.post("/api/v1/" + path, json=data, headers=ORIGIN)
        assert result.status_code < 300, result.text
        return result.json() if result.content else None

    post(
        "auth/setup-owner",
        {
            "full_name": "[QA SYNTHETIC] WP6A Owner",
            "email": "wp6a@example.com",
            "password": "SyntheticOnlyWP6A123!",
            "password_confirmation": "SyntheticOnlyWP6A123!",
        },
    )
    brand = post("brands", {"name": "[QA SYNTHETIC] WP6A Brand"})
    product = post(
        "products",
        {
            "brand_id": brand["id"],
            "name": "[QA SYNTHETIC] WP6A Product",
            "product_type": "physical",
            "description": "Synthetic QA description, not live evidence.",
            "price_amount": "150.25",
            "price_currency": "INR",
        },
    )
    post("products/" + product["id"] + "/activate", {})
    return c, post, brand, product


@pytest.mark.parametrize(
    "path",
    [
        "ai/video/generations",
        "ai/video/scripts",
        "ai/video/storyboards",
        "ai/video/styles",
        "ads/overview",
        "ads/campaigns",
        "ads/optimization/overview",
        "ads/anomalies",
        "ads/comparison",
    ],
)
def test_repaired_empty_reads_are_real_success_not_sql_error(local, path):
    client, *_ = local
    for _ in range(2):
        result = client.get("/api/v1/" + path)
        assert result.status_code == 200, result.text


def test_local_account_create_edit_preserves_disabled_unverified_state(local):
    client, post, _, _ = local
    account = post(
        "ads/accounts",
        {
            "provider": "meta",
            "environment": "local",
            "display_name": "[QA SYNTHETIC] WP6A local",
            "external_account_id": "qa-wp6a-test",
            "credentials": {},
        },
    )
    assert account["enabled"] is False and account["validated"] is False
    result = client.patch(
        "/api/v1/ads/accounts/" + account["id"],
        json={"display_name": "[QA SYNTHETIC] WP6A renamed"},
        headers=ORIGIN,
    )
    assert result.status_code == 200
    value = client.get("/api/v1/ads/accounts/" + account["id"]).json()
    assert value["display_name"].endswith("renamed") and value["enabled"] is False
    assert "encrypted_credentials" not in value
    assert client.get("/api/v1/ads/accounts/" + str(uuid.uuid4())).status_code == 404


def test_disabled_account_blocks_campaign_without_manufacturing_approval(local):
    client, post, brand, product = local
    account = post(
        "ads/accounts",
        {
            "provider": "meta",
            "environment": "local",
            "display_name": "[QA SYNTHETIC] WP6A disabled",
            "external_account_id": "qa-wp6a-disabled",
            "credentials": {},
        },
    )
    payload = {
        "provider": "meta",
        "account_id": account["id"],
        "brand_id": brand["id"],
        "product_id": product["id"],
        "name": "[QA SYNTHETIC] WP6A blocked",
        "budget": {"daily_amount": "25.55", "currency": "INR"},
        "idempotency_key": "wp6a-blocked",
    }
    response = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert response.status_code in {409, 422}
    assert client.get("/api/v1/ads/campaigns").json() == []
    assert client.get("/api/v1/ads/overview").json()["synthetic"] is True


def test_storyboard_create_edit_version_reload_and_stale_rejection(local):
    client, post, brand, product = local
    draft = post(
        "ai/video/storyboards",
        {
            "brand_id": brand["id"],
            "product_id": product["id"],
            "scenes": [
                {
                    "stable_key": "qa-scene",
                    "scene_order": 1,
                    "scene_text": "Synthetic local QA scene",
                }
            ],
        },
    )
    path = "/api/v1/ai/video/storyboards/" + draft["id"]
    result = client.put(
        path,
        json={
            "expected_row_version": draft["row_version"],
            "scenes": [
                {
                    "stable_key": "qa-scene",
                    "scene_order": 1,
                    "scene_text": "Synthetic revised local scene",
                }
            ],
        },
        headers=ORIGIN,
    )
    assert result.status_code == 200, result.text
    revised = result.json()
    assert revised["row_version"] > draft["row_version"]
    assert revised["state"] == "draft"
    loaded = client.get("/api/v1/ai/video/storyboards").json()
    assert any(r["id"] == revised["id"] for r in loaded)
    stale = client.put(
        "/api/v1/ai/video/storyboards/" + revised["id"],
        json={"expected_row_version": draft["row_version"], "scenes": []},
        headers=ORIGIN,
    )
    assert stale.status_code == 409


def test_empty_storyboard_approval_is_blocked_and_auth_is_required(local):
    client, post, brand, product = local
    draft = post(
        "ai/video/storyboards", {"brand_id": brand["id"], "product_id": product["id"], "scenes": []}
    )
    response = client.post(
        "/api/v1/ai/video/storyboards/" + draft["id"] + "/approve",
        json={"expected_row_version": draft["row_version"]},
        headers=ORIGIN,
    )
    assert response.status_code in {409, 422}
    post("auth/logout", {})
    assert client.get("/api/v1/ai/video/generations").status_code == 401
    assert client.get("/api/v1/ads/overview").status_code == 401
