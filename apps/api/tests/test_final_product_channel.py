from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration_fixture
from test_ads_media_e2e import _image, _video
from test_social_integration import _account as social_account

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _assert_safe(body: str) -> None:
    lowered = body.lower()
    assert all(marker not in lowered for marker in ("traceback", "postgresql://", "file://"))


def test_unified_product_channel_and_action_contract(client: Any) -> None:
    context = integration_fixture.setup_context(client)
    product_id = context["product"]["id"]
    content = client.post("/api/v1/ai/generations", json={"product_id": product_id}, headers=ORIGIN)
    assert content.status_code == 201, content.text
    artifact_id = content.json()["artifact_id"]
    assert (
        client.post(f"/api/v1/ai/artifacts/{artifact_id}/approve", headers=ORIGIN).status_code
        == 200
    )
    _image(client, context, "final-channel-image")
    video = _video(client, context, "final-channel-video")
    social_account_row = social_account(client, "youtube")
    social = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": product_id,
            "account_id": social_account_row["id"],
            "platform": "youtube",
            "content_type": "youtube_video",
            "content_artifact_id": artifact_id,
            "content_artifact_version": 1,
            "video_generation_id": video["generation_id"],
            "video_output_id": video["output_id"],
            "video_version": 1,
            "caption": "Final Product Channel",
            "title": "Final Product Channel",
            "idempotency_key": "final-product-channel-social",
        },
        headers=ORIGIN,
    )
    assert social.status_code == 201, social.text

    projections = {
        "content": client.get(f"/api/v1/ai/seo/products/{product_id}/channels", headers=ORIGIN),
        "image": client.get(f"/api/v1/ai/images/products/{product_id}/outputs", headers=ORIGIN),
        "video": client.get(f"/api/v1/ai/video/channels/products/{product_id}", headers=ORIGIN),
        "social": client.get(f"/api/v1/social/products/{product_id}/channel", headers=ORIGIN),
        "marketplace": client.get(
            f"/api/v1/marketplaces/video/product/{product_id}", headers=ORIGIN
        ),
        "campaign": client.get(
            f"/api/v1/campaigns/video/products/{product_id}/channel", headers=ORIGIN
        ),
        "ads": client.get(f"/api/v1/ads/product-channel/{product_id}", headers=ORIGIN),
        "marketing": client.get(
            f"/api/v1/ads/marketing/product-channel/{product_id}", headers=ORIGIN
        ),
    }
    for name, response in projections.items():
        assert response.status_code == 200, f"{name}: {response.text}"
        _assert_safe(response.text)

    assert projections["content"].json()
    assert (
        projections["image"].json() and projections["image"].json()[0]["product_id"] == product_id
    )
    for name in ("video", "social", "marketplace", "campaign", "ads", "marketing"):
        body = projections[name].json()
        if isinstance(body, dict):
            assert str(body.get("product_id", product_id)) == product_id
        elif body:
            first = body[0]
            if isinstance(first, dict) and "product_id" in first:
                assert str(first["product_id"]) == product_id

    advertised = set()
    for response in projections.values():
        body = response.json()
        if isinstance(body, dict):
            advertised.update(body.get("actions", []))
        elif isinstance(body, list):
            for row in body:
                if isinstance(row, dict):
                    advertised.update(row.get("actions", []))
    executable = {
        "open",
        "open_campaign",
        "open_calendar",
        "open_analytics",
        "open_recovery",
        "preview_update",
        "preview_video_update",
        "preview_video_attachment",
        "reconcile",
        "create_ad",
        "preview_ad",
        "pause",
        "resume",
        "retry_channel",
        "cancel_channel",
        "create_marketing_plan",
    }
    assert advertised <= executable
    assert advertised <= executable
    assert "update_available" in projections["social"].json()
