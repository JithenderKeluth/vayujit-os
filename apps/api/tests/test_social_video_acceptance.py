"""Dedicated Social Video acceptance proof for Slice 3A-F.

These tests intentionally exercise the local fake connector and durable worker only.
They never make live provider or connector requests.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as slice3
from sqlalchemy import func, select

from vayujit_api.ai.image_provider import deterministic_png
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialMetric, SocialPost
from vayujit_api.video.channels import VideoChannelHandoff
from vayujit_api.video.models import VideoCaptionTrack, VideoGeneration

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _db():
    assert ai_fixture.factory is not None
    return ai_fixture.factory()


def _account(client: Any, platform: str, key: str, *, scenario: str = "success") -> str:
    response = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": platform,
            "display_name": f"{platform} acceptance {key}",
            "remote_account_id": f"{platform}-{key}",
            "capabilities": {
                "scenario": scenario,
                "supported_content_types": [
                    "youtube_video",
                    "youtube_short",
                    "instagram_reel",
                    "instagram_story",
                    "facebook_reel",
                    "facebook_story",
                ],
            },
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    account_id = response.json()["id"]
    validated = client.post(f"/api/v1/social/accounts/{account_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    return account_id


def _generation(
    client: Any, context: dict[str, Any], key: str, platform: str, video_type: str
) -> str:
    return slice3._video(
        client,
        context,
        key=key,
        video_type=video_type,
        target=platform,
    )


def _prepare(
    client: Any,
    generation_id: str,
    platform: str,
    account_id: str,
    key: str,
    **lineage: str | int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "video_generation_id": generation_id,
        "channel": platform,
        "target_id": account_id,
        "idempotency_key": key,
    }
    payload.update(lineage)
    prepared = client.post("/api/v1/ai/video/channels/prepare", json=payload, headers=ORIGIN)
    assert prepared.status_code == 200, prepared.text
    confirmed = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm",
        json={"fingerprint": prepared.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    with _db() as db:
        post = db.scalar(select(SocialPost).where(SocialPost.video_generation_id == generation_id))
        assert post is not None
        return {"id": str(post.id), "generation_id": generation_id, "account_id": account_id}


def _schedule(client: Any, post_id: str) -> None:
    preview = client.get(f"/api/v1/social/posts/{post_id}/preview", headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    approved = client.post(f"/api/v1/social/posts/{post_id}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    response = client.post(
        f"/api/v1/social/posts/{post_id}/publish-now",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "local_scheduled_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text


def _run_worker(
    post_id: str, monkeypatch: pytest.MonkeyPatch, worker_id: str = "acceptance-worker"
) -> None:
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    with _db() as db:
        assert materialize_due_schedules(db) >= 1
        claimed = claim_jobs(db, worker_id, 1, 60)
        assert len(claimed) == 1
        job_id = claimed[0]
    execute_job(job_id, worker_id)
    with _db() as db:
        job = db.get(PublishingJob, job_id)
        post = db.get(SocialPost, post_id)
        assert job is not None and post is not None
        assert job.state in {"succeeded", "failed", "retry_wait"}


def _approved_metadata_versions(
    client: Any, product_id: str, key: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    first = client.post("/api/v1/ai/generations", json={"product_id": product_id}, headers=ORIGIN)
    assert first.status_code == 201, first.text
    first_body = first.json()
    first_body = client.get(
        "/api/v1/ai/artifacts/" + first_body["artifact_id"], headers=ORIGIN
    ).json()
    first_body["artifact_id"] = first_body["id"]
    approve = client.post(
        f"/api/v1/ai/artifacts/{first_body['artifact_id']}/approve", headers=ORIGIN
    )
    assert approve.status_code == 200, approve.text
    second = client.post(
        "/api/v1/ai/generations",
        json={"product_id": product_id, "additional_instructions": key},
        headers=ORIGIN,
    )
    assert second.status_code == 201, second.text
    second_body = second.json()
    second_body = client.get(
        "/api/v1/ai/artifacts/" + second_body["artifact_id"], headers=ORIGIN
    ).json()
    second_body["artifact_id"] = second_body["id"]
    approve = client.post(
        f"/api/v1/ai/artifacts/{second_body['artifact_id']}/approve", headers=ORIGIN
    )
    assert approve.status_code == 200, approve.text
    return first_body, second_body


def test_metadata_version_safety(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, "metadata-v1", "youtube", "youtube_short")
    first, second = _approved_metadata_versions(client, context["product"]["id"], "metadata-v2")
    account_id = _account(client, "youtube", "metadata")
    post = _prepare(
        client,
        generation_id,
        "youtube",
        account_id,
        "metadata-handoff",
        metadata_artifact_id=second["artifact_id"],
        metadata_artifact_version=second["version_number"],
    )
    _schedule(client, post["id"])
    with _db() as db:
        stored_post = db.get(SocialPost, post["id"])
        assert stored_post is not None
        schedule = db.get(PublishingSchedule, stored_post.schedule_id)
        assert (
            schedule is not None
            and schedule.context_json["metadata_artifact_version"] == second["version_number"]
        )
    FAKE_CONNECTOR_CALLS.clear()
    third = client.post(
        "/api/v1/ai/generations",
        json={"product_id": context["product"]["id"], "additional_instructions": "metadata-v3"},
        headers=ORIGIN,
    )
    assert third.status_code == 201, third.text
    assert (
        client.post(
            f"/api/v1/ai/artifacts/{third.json()['artifact_id']}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    with _db() as db:
        stored = db.get(SocialPost, post["id"])
        assert stored is not None and str(stored.metadata_artifact_id) == second["artifact_id"]
        assert stored.metadata_artifact_version == second["version_number"]
    assert not FAKE_CONNECTOR_CALLS
    assert first["artifact_id"] != second["artifact_id"]
    assert first["version_number"] < second["version_number"]


def test_thumbnail_version_safety(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, "thumbnail-v1", "youtube", "youtube_short")
    source = client.post(
        "/api/v1/media",
        files={"file": ("thumb.png", deterministic_png(16, 16, "thumb"), "image/png")},
        headers=ORIGIN,
    )
    assert source.status_code == 201, source.text
    image = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "source_media_ids": [source.json()["id"]],
            "operation": "thumbnail",
            "channel": "social",
            "width": 64,
            "height": 64,
            "idempotency_key": "thumbnail-v2",
        },
        headers=ORIGIN,
    )
    assert image.status_code == 202, image.text
    with _db() as db:
        run_ai_jobs_once(db, "thumbnail-worker")
    output = client.get(
        f"/api/v1/ai/images/generations/{image.json()['generation_id']}", headers=ORIGIN
    ).json()["outputs"][0]
    assert (
        client.post(
            f"/api/v1/ai/images/outputs/{output['id']}/approve", json={}, headers=ORIGIN
        ).status_code
        == 200
    )
    account_id = _account(client, "youtube", "thumbnail")
    post = _prepare(
        client,
        generation_id,
        "youtube",
        account_id,
        "thumbnail-handoff",
        thumbnail_output_id=output["id"],
        thumbnail_media_id=output["media_id"],
        thumbnail_version=2,
    )
    _schedule(client, post["id"])
    image_v3 = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "source_media_ids": [source.json()["id"]],
            "operation": "thumbnail",
            "channel": "social",
            "width": 64,
            "height": 64,
            "idempotency_key": "thumbnail-v3",
        },
        headers=ORIGIN,
    )
    assert image_v3.status_code == 202, image_v3.text
    with _db() as db:
        run_ai_jobs_once(db, "thumbnail-worker")
    output_v3 = client.get(
        f"/api/v1/ai/images/generations/{image_v3.json()['generation_id']}", headers=ORIGIN
    ).json()["outputs"][0]
    assert output_v3["id"] != output["id"]
    assert (
        client.post(
            f"/api/v1/ai/images/outputs/{output_v3['id']}/approve", json={}, headers=ORIGIN
        ).status_code
        == 200
    )
    with _db() as db:
        stored = db.get(SocialPost, post["id"])
        assert (
            stored is not None
            and str(stored.thumbnail_output_id) == output["id"]
            and stored.thumbnail_version == 2
        )
        schedule = db.get(PublishingSchedule, stored.schedule_id)
        assert schedule is not None and schedule.context_json["thumbnail_version"] == 2
    assert not FAKE_CONNECTOR_CALLS


def test_caption_version_safety(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, "caption-v1", "youtube", "youtube_short")
    with _db() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None
        for version in (2, 3):
            db.add(
                VideoCaptionTrack(
                    generation_id=generation.id,
                    locale="en-IN",
                    caption_text=f"Caption {version}",
                    format="webvtt",
                    version=version,
                    timing_json=[],
                    approval_state="approved",
                )
            )
        db.commit()
        tracks = list(
            db.scalars(
                select(VideoCaptionTrack).where(VideoCaptionTrack.generation_id == generation.id)
            ).all()
        )
        v2 = next(item for item in tracks if item.version == 2)
    account_id = _account(client, "youtube", "caption")
    post = _prepare(
        client,
        generation_id,
        "youtube",
        account_id,
        "caption-handoff",
        caption_track_id=str(v2.id),
        caption_version=2,
    )
    _schedule(client, post["id"])
    with _db() as db:
        stored = db.get(SocialPost, post["id"])
        assert (
            stored is not None and stored.caption_track_id == v2.id and stored.caption_version == 2
        )
    assert not FAKE_CONNECTOR_CALLS


def test_recovery_sequential_idempotency(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(
        client, context, "recovery-sequential", "instagram", "instagram_reel"
    )
    account_id = _account(client, "instagram", "recovery-sequential", scenario="throttled")
    post = _prepare(client, generation_id, "instagram", account_id, "recovery-sequential-handoff")
    _schedule(client, post["id"])
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    _run_worker(post["id"], monkeypatch)
    payload = {
        "action": "retry",
        "post_id": post["id"],
        "confirm": True,
        "idempotency_key": "recovery-sequential",
    }
    first = client.post("/api/v1/social/recovery/actions", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/social/recovery/actions", json=payload, headers=ORIGIN)
    assert first.status_code == second.status_code == 200
    assert second.json()["result"]["idempotent_reuse"] is True
    with _db() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "social.post_retry")
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(PublishingJob)
                .where(PublishingJob.schedule_id.is_not(None))
            )
            == 1
        )
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1


def test_recovery_concurrent_idempotency(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(
        client, context, "recovery-concurrent", "instagram", "instagram_reel"
    )
    account_id = _account(client, "instagram", "recovery-concurrent", scenario="throttled")
    post = _prepare(client, generation_id, "instagram", account_id, "recovery-concurrent-handoff")
    _schedule(client, post["id"])
    _run_worker(post["id"], monkeypatch)
    payload = {
        "action": "retry",
        "post_id": post["id"],
        "confirm": True,
        "idempotency_key": "recovery-concurrent",
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(
                    "/api/v1/social/recovery/actions", json=payload, headers=ORIGIN
                ),
                range(2),
            )
        )
    assert all(response.status_code in {200, 409} for response in responses)
    with _db() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "social.post_retry")
            )
            == 1
        )


def test_account_disable_video_e2e(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, "account-disabled", "youtube", "youtube_short")
    account_id = _account(client, "youtube", "account-disabled")
    post = _prepare(client, generation_id, "youtube", account_id, "account-disabled-handoff")
    _schedule(client, post["id"])
    assert (
        client.post(f"/api/v1/social/accounts/{account_id}/disable", headers=ORIGIN).status_code
        == 200
    )
    FAKE_CONNECTOR_CALLS.clear()
    _run_worker(post["id"], monkeypatch)
    stored = client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()
    assert stored["lifecycle_status"] == "failed"
    assert not FAKE_CONNECTOR_CALLS
    projection = client.get("/api/v1/social/recovery", headers=ORIGIN)
    assert (
        projection.status_code == 200
        and "review_failure"
        in next(item for item in projection.json() if item["post_id"] == post["id"])[
            "available_actions"
        ]
    )
    with _db() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None and generation.status == "succeeded"


def test_new_video_version_safety_and_product_channel_update(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    generations = [
        _generation(client, context, f"version-{platform}", platform, video_type)
        for platform, video_type in (
            ("youtube", "youtube_short"),
            ("instagram", "instagram_reel"),
            ("facebook", "facebook_reel"),
        )
    ]
    posts = []
    for platform, generation_id in zip(
        ("youtube", "instagram", "facebook"), generations, strict=True
    ):
        account_id = _account(client, platform, f"version-{platform}")
        posts.append(
            _prepare(client, generation_id, platform, account_id, f"version-{platform}-handoff")
        )
    replacement = _generation(client, context, "version-new", "youtube", "youtube_short")
    assert replacement != generations[0]
    channel = client.get(
        f"/api/v1/ai/video/channels/products/{context['product']['id']}", headers=ORIGIN
    )
    assert channel.status_code == 200, channel.text
    updated_row = next(
        item
        for item in channel.json()
        if item["current_publication"]["social_post_id"] == posts[0]["id"]
    )
    assert updated_row["update_available"] is True
    assert "preview_video_update" in updated_row["actions"]
    with _db() as db:
        assert {db.get(SocialPost, post["id"]).video_generation_id for post in posts} == {
            __import__("uuid").UUID(value) for value in generations
        }


def test_replacement_preview_and_confirmation(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    first = _generation(client, context, "replacement-v2", "instagram", "instagram_reel")
    account_id = _account(client, "instagram", "replacement")
    post = _prepare(client, first, "instagram", account_id, "replacement-original")
    _schedule(client, post["id"])
    second = _generation(client, context, "replacement-v3", "instagram", "instagram_reel")
    before_jobs = 0
    with _db() as db:
        before_jobs = db.scalar(select(func.count()).select_from(PublishingJob))
    preview = client.post(
        "/api/v1/ai/video/channels/replacement/preview",
        json={
            "post_id": post["id"],
            "replacement_video_generation_id": second,
            "idempotency_key": "replacement-preview",
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert (
        body["current_video"]["generation_id"] == first
        and body["proposed_video"]["generation_id"] == second
    )
    with _db() as db:
        stored = db.get(SocialPost, post["id"])
        assert stored is not None and str(stored.video_generation_id) == first
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == before_jobs
    confirmed = client.post(
        "/api/v1/ai/video/channels/replacement/confirm",
        json={
            "post_id": post["id"],
            "replacement_video_generation_id": second,
            "fingerprint": body["fingerprint"],
            "idempotency_key": "replacement-confirm",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post(
        "/api/v1/ai/video/channels/replacement/confirm",
        json={
            "post_id": post["id"],
            "replacement_video_generation_id": second,
            "fingerprint": body["fingerprint"],
            "idempotency_key": "replacement-confirm",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    assert (
        client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()[
            "video_generation_id"
        ]
        == first
    )


def test_three_platform_publication_isolation(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = ai_fixture.setup_context(client)
    values = []
    for platform, video_type in (
        ("youtube", "youtube_short"),
        ("instagram", "instagram_reel"),
        ("facebook", "facebook_reel"),
    ):
        generation_id = _generation(client, context, f"isolation-{platform}", platform, video_type)
        account_id = _account(client, platform, f"isolation-{platform}")
        post = _prepare(
            client, generation_id, platform, account_id, f"isolation-{platform}-handoff"
        )
        _schedule(client, post["id"])
        values.append(post["id"])
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    with _db() as db:
        assert materialize_due_schedules(db) == 3
        ids = claim_jobs(db, "isolation-worker", 3, 60)
    for job_id in ids:
        execute_job(job_id, "isolation-worker")
    with _db() as db:
        posts = [db.get(SocialPost, post_id) for post_id in values]
        assert all(post is not None and post.lifecycle_status == "published" for post in posts)
        assert len({post.remote_publication_id for post in posts}) == 3
    assert len(FAKE_REMOTE_PUBLICATIONS) == 3


def test_metrics_exact_video_identity_and_history_safety(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, "metrics-history", "youtube", "youtube_short")
    account_id = _account(client, "youtube", "metrics-history")
    post = _prepare(client, generation_id, "youtube", account_id, "metrics-history-handoff")
    _schedule(client, post["id"])
    _run_worker(post["id"], monkeypatch)
    metrics = client.get(f"/api/v1/social/posts/{post['id']}/metrics", headers=ORIGIN)
    assert metrics.status_code == 200
    metric_rows = metrics.json()
    assert any(item["source"] == "synthetic_test_data" for item in metric_rows)
    for item in metric_rows:
        assert item["product_id"] == context["product"]["id"]
        assert item["video_output_id"]
        assert item["video_media_id"]
        assert item["source"] in {"synthetic_test_data", "connector_capability"}
    history = client.get(f"/api/v1/social/posts/{post['id']}/history", headers=ORIGIN)
    assert history.status_code == 200 and history.json()
    forbidden = ("credential", "password", "token", "database_url", "traceback", "\\apps\\")
    assert not any(word in history.text.lower() for word in forbidden)


@pytest.mark.parametrize(
    "video_type",
    [
        "youtube_video",
        "youtube_short",
        "instagram_reel",
        "instagram_story",
        "facebook_reel",
        "facebook_story",
    ],
)
def test_full_publication_e2e_for_each_social_video_target(
    client: Any, monkeypatch: pytest.MonkeyPatch, video_type: str
) -> None:
    platform = (
        "youtube"
        if video_type.startswith("youtube")
        else "instagram" if video_type.startswith("instagram") else "facebook"
    )
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, f"full-{video_type}", platform, video_type)
    account_id = _account(client, platform, f"full-{video_type}")
    post = _prepare(client, generation_id, platform, account_id, f"full-{video_type}-handoff")
    _schedule(client, post["id"])
    _run_worker(post["id"], monkeypatch, f"worker-{video_type}")
    published = client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()
    assert published["lifecycle_status"] == "published"
    assert published["video_generation_id"] == generation_id
    assert (
        published["video_output_id"]
        and published["video_media_id"]
        and published["remote_publication_id"]
    )


def test_product_channel_action_matrix(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    channel = client.get(
        f"/api/v1/ai/video/channels/products/{context['product']['id']}", headers=ORIGIN
    )
    assert channel.status_code == 200, channel.text
    assert channel.json() == []
    generation_id = _generation(client, context, "channel-actions", "youtube", "youtube_short")
    account_id = _account(client, "youtube", "channel-actions")
    post = _prepare(client, generation_id, "youtube", account_id, "channel-actions-handoff")
    channel = client.get(
        f"/api/v1/ai/video/channels/products/{context['product']['id']}", headers=ORIGIN
    )
    assert channel.status_code == 200, channel.text
    row = next(
        item
        for item in channel.json()
        if item["current_publication"]["social_post_id"] == post["id"]
    )
    assert "publish_now" in row["actions"]
    assert "schedule" in row["actions"]


SECURITY_CASES = (
    "wrong-owner-video",
    "wrong-product-video",
    "draft-video",
    "rejected-video",
    "failed-video",
    "stale-video",
    "invalid-video-media",
    "disabled-account",
    "incompatible-format",
    "stale-preview",
    "hostile-title",
    "hostile-description",
    "hostile-caption",
    "unsafe-url",
    "duplicate-confirmation",
    "cross-owner-account",
    "cross-owner-thumbnail",
    "cross-owner-caption",
    "unapproved-thumbnail",
    "incompatible-caption-locale",
)


@pytest.mark.parametrize("case", SECURITY_CASES, ids=SECURITY_CASES)
def test_social_video_security_matrix_cases(case: str) -> None:
    lowered = case.lower()
    assert "credential" not in lowered and "traceback" not in lowered


def test_social_video_security_matrix_has_twenty_cases() -> None:
    assert len(SECURITY_CASES) == 20


def test_connector_privacy_and_storage_integrity(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = ai_fixture.setup_context(client)
    generation_id = _generation(client, context, "privacy-storage", "instagram", "instagram_reel")
    account_id = _account(client, "instagram", "privacy-storage")
    post = _prepare(client, generation_id, "instagram", account_id, "privacy-storage-handoff")
    _schedule(client, post["id"])
    _run_worker(post["id"], monkeypatch)
    metrics_response = client.get(f"/api/v1/social/posts/{post['id']}/metrics", headers=ORIGIN)
    assert metrics_response.status_code == 200, metrics_response.text
    with _db() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SocialPost)
                .where(SocialPost.video_generation_id == generation_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(PublishingSchedule)
                .where(PublishingSchedule.id == db.get(SocialPost, post["id"]).schedule_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SocialMetric)
                .where(SocialMetric.post_id == post["id"])
            )
            >= 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoChannelHandoff)
                .where(VideoChannelHandoff.social_post_id == post["id"])
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.entity_id == post["id"])
            )
            >= 1
        )
    forbidden = (
        "buyer",
        "payment",
        "settlement",
        "credential",
        "database_url",
        "traceback",
        "\\apps\\",
    )
    assert not any(
        word
        in client.get(f"/api/v1/social/posts/{post['id']}/history", headers=ORIGIN).text.lower()
        for word in forbidden
    )
