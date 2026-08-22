from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration_fixture
from sqlalchemy import select
from test_ads_media_e2e import _image, _video
from test_social_integration import _account as social_account

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.media.models import MediaAsset
from vayujit_api.social.models import SocialPost
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_application_wide_version_safety(client: Any) -> None:
    context = integration_fixture.setup_context(client)
    product_id = context["product"]["id"]

    content_v1 = client.post(
        "/api/v1/ai/generations", json={"product_id": product_id}, headers=ORIGIN
    )
    assert content_v1.status_code == 201, content_v1.text
    artifact_v1_id = content_v1.json()["artifact_id"]
    assert (
        client.post(f"/api/v1/ai/artifacts/{artifact_v1_id}/approve", headers=ORIGIN).status_code
        == 200
    )

    image_v1 = _image(client, context, "final-version-image-v1")
    video_v1 = _video(client, context, "final-version-video-v1")
    account = social_account(client, "youtube")
    social = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": product_id,
            "account_id": account["id"],
            "platform": "youtube",
            "content_type": "youtube_video",
            "content_artifact_id": artifact_v1_id,
            "content_artifact_version": 1,
            "caption": "Version safety",
            "title": "Version safety",
            "idempotency_key": "final-version-social-v1",
        },
        headers=ORIGIN,
    )
    assert social.status_code == 201, social.text
    social_id = social.json()["id"]

    # Create approved v2 records through the real deterministic workflows. No
    # replacement or downstream execution is requested in this test.
    content_v2 = client.post(
        "/api/v1/ai/generations",
        json={"product_id": product_id, "additional_instructions": "Version two"},
        headers=ORIGIN,
    )
    assert content_v2.status_code == 201, content_v2.text
    artifact_v2_id = content_v2.json()["artifact_id"]
    assert (
        client.post(f"/api/v1/ai/artifacts/{artifact_v2_id}/approve", headers=ORIGIN).status_code
        == 200
    )
    image_v2 = _image(client, context, "final-version-image-v2")
    video_v2 = _video(client, context, "final-version-video-v2")

    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        artifact_v1 = db.get(GeneratedArtifact, artifact_v1_id)
        artifact_v2 = db.get(GeneratedArtifact, artifact_v2_id)
        image_output_v1 = db.scalar(select(MediaAsset).where(MediaAsset.id == image_v1["media_id"]))
        image_output_v2 = db.scalar(select(MediaAsset).where(MediaAsset.id == image_v2["media_id"]))
        video_generation_v1 = db.get(VideoGeneration, video_v1["generation_id"])
        video_generation_v2 = db.get(VideoGeneration, video_v2["generation_id"])
        video_output_v1 = db.get(VideoOutput, video_v1["output_id"])
        video_output_v2 = db.get(VideoOutput, video_v2["output_id"])
        post = db.get(SocialPost, social_id)
        assert artifact_v1 is not None and artifact_v1.version_number == 1
        assert artifact_v2 is not None and artifact_v2.version_number == 2
        assert image_output_v1 is not None and image_output_v2 is not None
        assert video_generation_v1 is not None and video_generation_v2 is not None
        assert video_output_v1 is not None and video_output_v2 is not None
        assert post is not None
        assert str(post.content_artifact_id) == str(artifact_v1_id)
        assert post.content_artifact_version == 1
        assert image_output_v1.id != image_output_v2.id
        assert video_generation_v1.id != video_generation_v2.id
        assert video_output_v1.id != video_output_v2.id

    history = client.get(f"/api/v1/ai/generations?product_id={product_id}", headers=ORIGIN)
    assert history.status_code == 200
    assert {item["version_number"] for item in history.json()["items"]} >= {1, 2}
    channel = client.get(f"/api/v1/commerce/video/product/{product_id}", headers=ORIGIN)
    assert channel.status_code in {200, 404}
    ads_channel = client.get(f"/api/v1/ads/product-channel/{product_id}", headers=ORIGIN)
    assert ads_channel.status_code == 200
    assert ads_channel.json()["product_id"] == product_id
    for provider in ads_channel.json()["providers"]:
        assert "actions" in provider
    assert all(marker not in ads_channel.text.lower() for marker in ("traceback", "postgresql://"))
