from __future__ import annotations

from typing import Any

import pytest
from helpers.ads_acceptance import setup_ads_context
from test_ads_media_e2e import _campaign, _image, _publish_media, _video
from test_ai_integration import ORIGIN

from vayujit_api.ads.connectors import CONNECTORS, FakeAdsState

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("provider", "kind"), [("meta", "image"), ("meta", "video")])
def test_approved_media_v2_does_not_mutate_active_ad(client: Any, provider: str, kind: str) -> None:
    for connector in CONNECTORS.values():
        connector.state = FakeAdsState()
    context = setup_ads_context(client)
    key = f"version-{provider}-{kind}"
    first_media = (
        _image(client, context, f"first-{key}")
        if kind == "image"
        else _video(client, context, f"first-{key}")
    )
    campaign = _campaign(client, context, provider, key)
    first = _publish_media(client, campaign, first_media, kind, key)
    current_ad_id = first["ad"]["id"]
    current_creative_id = first["creative"]["id"]
    remote_before = [dict(call) for call in CONNECTORS[provider].state.calls]
    second_media = (
        _image(client, context, f"second-{key}")
        if kind == "image"
        else _video(client, context, f"second-{key}")
    )
    placement = "feed" if provider == "meta" else "youtube"
    request: dict[str, Any] = {
        "campaign_id": campaign["id"],
        "product_id": campaign["product_id"],
        "creative_type": kind,
        "headline": "Version two",
        "primary_text": "New approved version",
        "destination_url": "https://example.com/product-v2",
        "placements": [placement],
        "idempotency_key": f"second-{key}-creative",
    }
    if kind == "image":
        request.update(
            {
                "image_output_id": second_media["output_id"],
                "image_media_id": second_media["media_id"],
                "image_version": 2,
            }
        )
    else:
        request.update(
            {
                "video_generation_id": second_media["generation_id"],
                "video_output_id": second_media["output_id"],
                "video_media_id": second_media["media_id"],
                "video_version": 2,
            }
        )
    second = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives", json=request, headers=ORIGIN
    )
    assert second.status_code == 201, second.text
    assert [dict(call) for call in CONNECTORS[provider].state.calls] == remote_before
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200
    row = next(
        value for value in channel.json()["providers"] if value["campaign"]["provider"] == provider
    )
    assert row["ads"][0]["id"] == current_ad_id
    assert row["ads"][0]["creative_id"] == current_creative_id
    assert row["update_available"] is True
    assert any(value["id"] == second.json()["id"] for value in row["creatives"])
