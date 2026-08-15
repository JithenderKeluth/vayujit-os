from __future__ import annotations

from typing import cast

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.social.models import SocialPost
from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
from vayujit_api.video.channels import SOCIAL_FORMATS
from vayujit_api.video.inspection import inspect_video
from vayujit_api.video.models import VideoGeneration
from vayujit_api.video.provider import video_provider

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def _video(client, context, *, key="slice3-video", video_type="youtube_video", target="youtube"):
    queued = client.post(
        "/api/v1/ai/video/queue",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "video_type": video_type,
            "target_channel": target,
            "resolution": (
                "240x426"
                if video_type
                in {
                    "youtube_short",
                    "instagram_reel",
                    "instagram_story",
                    "facebook_reel",
                    "facebook_story",
                }
                else "320x240"
            ),
            "duration_seconds": 2,
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    with db_session() as db:
        assert run_ai_jobs_once(db, "slice3-worker", limit=5) >= 1
    artifact = client.post(
        "/api/v1/ai/generations", json={"product_id": context["product"]["id"]}, headers=ORIGIN
    )
    assert artifact.status_code == 201, artifact.text
    artifact_id = artifact.json()["artifact_id"]
    approved_artifact = client.post(f"/api/v1/ai/artifacts/{artifact_id}/approve", headers=ORIGIN)
    assert approved_artifact.status_code == 200, approved_artifact.text
    approved = client.post(
        f"/api/v1/ai/video/generations/{queued.json()['id']}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text
    return queued.json()["id"]


def _account(client, platform: str, suffix: str = "") -> str:
    response = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": platform,
            "display_name": f"{platform} local",
            "remote_account_id": f"{platform}-local{suffix}",
            "capabilities": {
                "supported_content_types": [
                    f"{platform}_video",
                    f"{platform}_reel",
                    f"{platform}_story",
                    "youtube_short",
                ]
            },
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    account_id = response.json()["id"]
    validated = client.post(f"/api/v1/social/accounts/{account_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    return validated.json()["id"]


def test_deterministic_provider_supports_local_social_aspects() -> None:
    for width, height in ((1280, 720), (720, 1280), (1000, 1000)):
        data, metadata = video_provider.generate(
            seed=f"social-{width}x{height}", width=width, height=height, duration=7
        )
        inspection = inspect_video(data)
        assert inspection.width == width
        assert inspection.height == height
        assert inspection.duration_seconds == 7
        assert inspection.video_stream_count == 1
        assert inspection.mime_type == "video/mp4"
        assert inspection.checksum_sha256
        assert metadata["mime_type"] == "video/mp4"


def test_social_registry_covers_all_local_fake_certified_targets() -> None:
    assert set(SOCIAL_FORMATS) == {
        "youtube_video",
        "youtube_short",
        "instagram_reel",
        "instagram_story",
        "facebook_reel",
        "facebook_story",
    }
    for target, rule in SOCIAL_FORMATS.items():
        assert rule["channel"] in {"youtube", "instagram", "facebook"}
        assert rule["mime_types"] == ["video/mp4"]
        assert cast(int, rule["min_duration"]) < cast(int, rule["max_duration"])
        assert cast(int, rule["min_width"]) <= cast(int, rule["max_width"])
        assert cast(int, rule["min_height"]) <= cast(int, rule["max_height"])
        assert rule["caption_support"] is True
        assert rule["thumbnail_support"] is True
        assert rule["scheduling_support"] is True
        assert rule["supported_video_type"] == target


def test_youtube_video_handoff_preview_confirm_and_exact_social_lineage(client) -> None:
    context = setup_context(client)
    generation_id = _video(client, context)
    account_id = _account(client, "youtube")
    preview = client.post(
        "/api/v1/ai/video/channels/preview",
        json={
            "video_generation_id": generation_id,
            "channel": "youtube",
            "target_id": account_id,
            "idempotency_key": "yt-preview",
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["compatibility"] == "ready"
    prepared = client.post(
        "/api/v1/ai/video/channels/prepare",
        json={
            "video_generation_id": generation_id,
            "channel": "youtube",
            "target_id": account_id,
            "idempotency_key": "yt-handoff",
        },
        headers=ORIGIN,
    )
    assert prepared.status_code == 200, prepared.text
    confirmed = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm",
        json={"fingerprint": prepared.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    with db_session() as db:
        post = db.scalar(select(SocialPost).where(SocialPost.video_generation_id == generation_id))
        assert post is not None and str(post.video_media_id) == preview.json()["video_media_id"]
        assert post.lifecycle_status == "draft"
        assert post.metadata_artifact_id == post.content_artifact_id
        assert post.metadata_artifact_version == post.content_artifact_version
        assert post.thumbnail_output_id is None
        assert post.caption_track_id is None


def test_stale_preview_is_rejected_and_repeated_prepare_is_idempotent(client) -> None:
    context = setup_context(client)
    generation_id = _video(
        client, context, key="stale-video", video_type="youtube_video", target="youtube"
    )
    account_id = _account(client, "youtube")
    prepared = client.post(
        "/api/v1/ai/video/channels/prepare",
        json={
            "video_generation_id": generation_id,
            "channel": "youtube",
            "target_id": account_id,
            "idempotency_key": "stale-handoff",
        },
        headers=ORIGIN,
    )
    assert prepared.status_code == 200, prepared.text
    repeated = client.post(
        "/api/v1/ai/video/channels/prepare",
        json={
            "video_generation_id": generation_id,
            "channel": "youtube",
            "target_id": account_id,
            "idempotency_key": "stale-handoff",
        },
        headers=ORIGIN,
    )
    assert repeated.status_code in {200, 202} and repeated.json()["idempotent_reuse"] is True
    with db_session() as db:
        row = db.get(VideoGeneration, generation_id)
        assert row is not None
        row.updated_at = row.updated_at.replace(
            microsecond=(row.updated_at.microsecond + 1) % 999999
        )
        db.commit()
    stale = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm",
        json={"fingerprint": prepared.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert stale.status_code == 409 and "stale" in stale.text.lower()


def test_video_bulk_parent_children_and_owner_scoped_status(client) -> None:
    context = setup_context(client)
    payload = {
        "product_ids": [context["product"]["id"]],
        "video_types": ["youtube_video", "instagram_reel"],
        "targets": ["youtube", "instagram"],
        "duration_seconds": 2,
        "resolution": "320x240",
        "idempotency_key": "slice3-bulk-1",
    }
    preview = client.post("/api/v1/ai/video/bulk/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200 and preview.json()["total_outputs"] == 4
    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    repeated = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert repeated.status_code in {200, 202} and repeated.json()["idempotent_reuse"] is True
    bulk_id = queued.json()["id"]
    with db_session() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoBulkOperation)
                .where(VideoBulkOperation.id == bulk_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoBulkChild)
                .where(VideoBulkChild.bulk_id == bulk_id)
            )
            == 4
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoGeneration)
                .where(VideoGeneration.idempotency_key.like(f"video-bulk:{bulk_id}:%"))
            )
            == 4
        )


def test_wrong_channel_is_blocked_before_confirmation(client) -> None:
    context = setup_context(client)
    generation_id = _video(
        client, context, key="wrong-channel", video_type="youtube_video", target="youtube"
    )
    account_id = _account(client, "instagram")
    preview = client.post(
        "/api/v1/ai/video/channels/preview",
        json={
            "video_generation_id": generation_id,
            "channel": "instagram",
            "target_id": account_id,
            "idempotency_key": "wrong-channel-preview",
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200
    assert preview.json()["compatibility"] == "blocked"


def test_all_six_social_video_targets_create_independent_drafts(client) -> None:
    context = setup_context(client)
    targets = (
        ("youtube", "youtube_video", "youtube-landscape"),
        ("youtube", "youtube_short", "youtube-short"),
        ("instagram", "instagram_reel", "instagram-reel"),
        ("instagram", "instagram_story", "instagram-story"),
        ("facebook", "facebook_reel", "facebook-reel"),
        ("facebook", "facebook_story", "facebook-story"),
    )
    created_posts: list[str] = []
    for platform, video_type, key in targets:
        generation_id = _video(client, context, key=key, video_type=video_type, target=platform)
        account_id = _account(client, platform, f"-{key}")
        prepared = client.post(
            "/api/v1/ai/video/channels/prepare",
            json={
                "video_generation_id": generation_id,
                "channel": platform,
                "target_id": account_id,
                "idempotency_key": f"handoff-{key}",
            },
            headers=ORIGIN,
        )
        assert prepared.status_code == 200, prepared.text
        preview = prepared.json()["preview"]
        assert preview["compatibility"] == "ready"
        assert preview["video_generation_id"] == generation_id
        confirmed = client.post(
            f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm",
            json={"fingerprint": prepared.json()["fingerprint"], "confirm": True},
            headers=ORIGIN,
        )
        assert confirmed.status_code == 200, confirmed.text
        with db_session() as db:
            post = db.scalar(
                select(SocialPost).where(SocialPost.video_generation_id == generation_id)
            )
            assert post is not None
            assert post.platform == platform
            assert post.content_type == video_type
            created_posts.append(str(post.id))
    assert len(set(created_posts)) == 6
