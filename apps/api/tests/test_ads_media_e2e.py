from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN

from vayujit_api.ads.connectors import CONNECTORS, FakeAdsState
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.image_provider import deterministic_png
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.media.models import MediaAsset
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _image(client: Any, context: dict[str, Any], key: str) -> dict[str, str]:
    source = client.post(
        "/api/v1/media",
        files={"file": ("ads.png", deterministic_png(64, 64, key), "image/png")},
        headers=ORIGIN,
    )
    assert source.status_code == 201, source.text
    queued = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "source_media_ids": [source.json()["id"]],
            "operation": "marketplace_main_image",
            "channel": "canonical",
            "width": 64,
            "height": 64,
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert run_ai_jobs_once(db, f"ads-image-{key}") == 1
    generation = client.get(
        f"/api/v1/ai/images/generations/{queued.json()['generation_id']}", headers=ORIGIN
    )
    assert generation.status_code == 200, generation.text
    output_id = generation.json()["outputs"][0]["id"]
    approved = client.post(
        f"/api/v1/ai/images/outputs/{output_id}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text
    with test_ai_integration.factory() as db:
        output = db.get(AIImageOutput, output_id)
        assert output is not None and output.media_id is not None
        media = db.get(MediaAsset, output.media_id)
        assert media is not None
        return {
            "output_id": str(output.id),
            "media_id": str(output.media_id),
            "version": "1",
            "checksum": str(output.checksum_sha256),
            "size": str(output.size_bytes),
            "width": str(output.actual_width),
            "height": str(output.actual_height),
            "mime": str(media.mime_type),
        }


def _video(client: Any, context: dict[str, Any], key: str) -> dict[str, str]:
    queued = client.post(
        "/api/v1/ai/video/queue",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "video_type": "product_showcase",
            "target_channel": "youtube",
            "resolution": "320x240",
            "duration_seconds": 2,
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    generation_id = queued.json()["id"]
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert run_ai_jobs_once(db, f"ads-video-{key}") == 1
    approved = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/approve",
        json={"feedback": "approved for Ads"},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    with test_ai_integration.factory() as db:
        generation = db.get(VideoGeneration, generation_id)
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation_id))
        assert generation is not None and output is not None and output.media_id is not None
        media = db.get(MediaAsset, output.media_id)
        assert media is not None
        return {
            "generation_id": str(generation.id),
            "output_id": str(output.id),
            "media_id": str(output.media_id),
            "version": "1",
            "checksum": output.checksum_sha256,
            "size": str(output.size_bytes),
            "width": str(output.width),
            "height": str(output.height),
            "duration": str(output.duration_seconds),
            "aspect_ratio": output.aspect_ratio,
            "mime": media.mime_type,
        }


def _campaign(client: Any, context: dict[str, Any], provider: str, key: str) -> dict[str, Any]:
    account = create_account(client, provider, key)
    payload = {
        "provider": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": f"{provider} media {key}",
        "objective": "awareness" if provider == "meta" else "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"campaign-{key}",
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
    run = client.post(f"/api/v1/ads/jobs/{confirmed.json()['job']['id']}/run", headers=ORIGIN)
    assert run.status_code == 200 and run.json()["status"] == "succeeded", run.text
    return client.get(
        f"/api/v1/ads/campaigns/{confirmed.json()['campaign']['id']}", headers=ORIGIN
    ).json()["campaign"]


def _publish_media(
    client: Any, campaign: dict[str, Any], media: dict[str, str], media_type: str, key: str
) -> dict[str, Any]:
    placement = {
        "meta-image": "feed",
        "meta-video": "video",
        "google-image": "display",
        "google-video": "youtube",
    }.get(key, "video")
    request: dict[str, Any] = {
        "campaign_id": campaign["id"],
        "product_id": campaign["product_id"],
        "creative_type": media_type,
        "headline": "Media exact lineage",
        "primary_text": "Approved media",
        "cta": "shop_now" if campaign["provider"] == "meta" else None,
        "destination_url": "https://example.com/product",
        "placements": [placement],
        "idempotency_key": f"creative-{key}",
    }
    if media_type == "image":
        request.update(
            {
                "image_output_id": media["output_id"],
                "image_media_id": media["media_id"],
                "image_version": 1,
            }
        )
    else:
        request.update(
            {
                "video_generation_id": media["generation_id"],
                "video_output_id": media["output_id"],
                "video_media_id": media["media_id"],
                "video_version": 1,
            }
        )
    creative = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives", json=request, headers=ORIGIN
    )
    assert creative.status_code == 201, creative.text
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={"name": f"{key} group", "placements": [placement], "idempotency_key": f"group-{key}"},
        headers=ORIGIN,
    )
    assert group.status_code == 201, group.text
    assert (
        client.post(f"/api/v1/ads/jobs/{group.json()['job_id']}/run", headers=ORIGIN).json()[
            "status"
        ]
        == "succeeded"
    )
    ad = client.post(
        f"/api/v1/ads/groups/{group.json()['id']}/ads",
        json={
            "creative_id": creative.json()["id"],
            "placement": placement,
            "idempotency_key": f"ad-{key}",
        },
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    ad_run = client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN)
    assert ad_run.status_code == 200 and ad_run.json()["status"] == "succeeded", ad_run.text
    return {"creative": creative.json(), "group": group.json(), "ad": ad.json()}


@pytest.mark.parametrize(
    ("provider", "kind"),
    [("meta", "image"), ("meta", "video"), ("google", "image"), ("google", "video")],
)
def test_ads_media_e2e_preserves_exact_approved_lineage(
    client: Any, provider: str, kind: str
) -> None:
    for connector in CONNECTORS.values():
        connector.state = FakeAdsState()
    context = setup_ads_context(client)
    key = f"{provider}-{kind}"
    media = (
        _image(client, context, f"image-{key}")
        if kind == "image"
        else _video(client, context, f"video-{key}")
    )
    campaign_key = key if provider == "meta" else f"google-{kind}"
    campaign = _campaign(client, context, provider, campaign_key)
    published = _publish_media(client, campaign, media, kind, campaign_key)
    assert published["creative"]["exact_lineage"][f"{kind}_output_id"] == media["output_id"]
    assert published["creative"]["exact_lineage"][f"{kind}_version"] == 1
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200, channel.text
    row = next(
        item for item in channel.json()["providers"] if item["campaign"]["provider"] == provider
    )
    assert row["ads"][0]["creative_id"] == published["creative"]["id"]
    assert (
        row["creatives"][0]["readiness"]["exact_creative"][f"{kind}_output_id"]
        == media["output_id"]
    )
