from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as slice3
from sqlalchemy import func, select

from vayujit_api.audit.models import AuditEvent
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialPost

client = ai_fixture.client

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _factory():
    assert ai_fixture.factory is not None
    return ai_fixture.factory()


def _handoff(client, context: dict[str, Any], *, scenario: str = "success") -> tuple[str, str]:
    generation_id = slice3._video(
        client, context, key=f"durable-{scenario}", video_type="youtube_short", target="youtube"
    )
    account_response = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": "youtube",
            "display_name": f"YouTube {scenario}",
            "remote_account_id": f"youtube-{scenario}",
            "capabilities": {"scenario": scenario, "supported_content_types": ["youtube_short"]},
        },
        headers=ORIGIN,
    )
    assert account_response.status_code == 201, account_response.text
    account_id = account_response.json()["id"]
    validated = client.post(f"/api/v1/social/accounts/{account_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    prepared = client.post(
        "/api/v1/ai/video/channels/prepare",
        json={
            "video_generation_id": generation_id,
            "channel": "youtube",
            "target_id": account_id,
            "idempotency_key": f"durable-handoff-{scenario}",
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
    with _factory() as db:
        post = db.scalar(select(SocialPost).where(SocialPost.video_generation_id == generation_id))
        assert post is not None
        post_id = str(post.id)
    approved = client.post(f"/api/v1/social/posts/{post_id}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    return generation_id, post_id


def _schedule(client, post_id: str) -> dict[str, Any]:
    preview = client.get(f"/api/v1/social/posts/{post_id}/preview", headers=ORIGIN)
    assert preview.status_code == 200, preview.text
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
    return response.json()


def _materialize_and_claim() -> tuple[Any, list[Any]]:
    with _factory() as db:
        assert materialize_due_schedules(db) >= 1
        claimed = claim_jobs(db, "durable-worker-a", 10, 60)
        jobs = list(db.scalars(select(PublishingJob).where(PublishingJob.id.in_(claimed))))
    return jobs[0].id, jobs


def test_video_http_confirm_does_not_call_connector_and_pins_context(client, monkeypatch):
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    _, post_id = _handoff(client, context)
    _schedule(client, post_id)
    assert not FAKE_CONNECTOR_CALLS
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None
        schedule = db.get(PublishingSchedule, post.schedule_id)
        assert schedule is not None
        assert schedule.context_json["social_post_id"] == post_id
        assert schedule.context_json["video_output_id"] == str(post.video_output_id)
        assert schedule.context_json["video_version"] == post.video_version
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
    job_id, _ = _materialize_and_claim()
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "durable-worker-a")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None and post.lifecycle_status == "published"
        job = db.get(PublishingJob, job_id)
        assert job is not None and job.context_json["video_output_id"] == str(post.video_output_id)


def test_video_remote_checkpoint_is_normalized_and_secret_free(client, monkeypatch):
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    _, post_id = _handoff(client, context)
    _schedule(client, post_id)
    job_id, _ = _materialize_and_claim()
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "durable-worker-a")
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None
        checkpoint = post.remote_checkpoint_json
        assert checkpoint is not None
        assert checkpoint["state"] == "remote_succeeded"
        assert checkpoint["social_post_id"] == post_id
        assert checkpoint["video_output_id"] == str(post.video_output_id)
        assert checkpoint["video_media_id"] == str(post.video_media_id)
        assert checkpoint["platform"] == post.platform
        assert checkpoint["format"] == post.content_type
        assert "credentials" not in checkpoint
        assert "token" not in checkpoint
        assert "password" not in checkpoint
        assert "database_url" not in checkpoint
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "social.post_checkpointed" in actions


def test_video_crash_after_checkpoint_recovers_without_second_connector_call(client, monkeypatch):
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    _, post_id = _handoff(client, context)
    _schedule(client, post_id)
    job_id, _ = _materialize_and_claim()
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    import vayujit_api.social.worker as social_worker

    original = social_worker.record_event

    def crash_checkpoint(*args, **kwargs):
        if kwargs.get("action") == "social.post_checkpointed":
            raise RuntimeError("simulated local crash")
        return original(*args, **kwargs)

    monkeypatch.setattr(social_worker, "record_event", crash_checkpoint)
    execute_job(job_id, "durable-worker-a")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    monkeypatch.setattr(social_worker, "record_event", original)
    with _factory() as db:
        job = db.get(PublishingJob, job_id)
        assert job is not None
        job.state = "pending"
        job.available_at_utc = datetime.now(UTC) - timedelta(seconds=1)
        job.lease_owner = None
        job.lease_expires_at = None
        db.commit()
        claimed = claim_jobs(db, "durable-worker-b", 1, 60)
    assert claimed == [job_id]
    execute_job(job_id, "durable-worker-b")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None and post.lifecycle_status == "published"


def test_video_ambiguous_publication_reconciles_without_republish(client, monkeypatch):
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    _, post_id = _handoff(client, context, scenario="ambiguous_result")
    _schedule(client, post_id)
    job_id, _ = _materialize_and_claim()
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "durable-worker-a")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None
        assert post.failure_code == "social.video.ambiguous_publication"
        remote_id = post.remote_publication_id
    recovery = client.post(
        "/api/v1/social/recovery/actions",
        json={
            "action": "reconcile",
            "post_id": post_id,
            "confirm": True,
            "idempotency_key": "ambiguous-reconcile-1",
        },
        headers=ORIGIN,
    )
    assert recovery.status_code == 200, recovery.text
    assert recovery.json()["result"]["status"] == "published"
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None and post.remote_publication_id == remote_id
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "social.post_ambiguous" in actions
        assert "social.post_reconcile" in actions


def test_video_calendar_analytics_and_channel_projection_pin_identity(client):
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    first_generation, post_id = _handoff(client, context)
    _schedule(client, post_id)
    second_generation = slice3._video(
        client, context, key="durable-latest", video_type="youtube_short", target="youtube"
    )
    with _factory() as db:
        first = db.scalar(select(SocialPost).where(SocialPost.id == post_id))
        assert first is not None
        current_output_id = str(first.video_output_id)
    channel = client.get(
        f"/api/v1/social/products/{context['product']['id']}/channel", headers=ORIGIN
    )
    assert channel.status_code == 200, channel.text
    video_rows = channel.json()["video"]
    current = next(item for item in video_rows if item["post_id"] == post_id)
    assert current["current_video_output_id"] == current_output_id
    assert current["latest_approved_video_output_id"] != current_output_id
    assert current["update_available"] is True
    assert second_generation != first_generation
    calendar = client.get("/api/v1/social/calendar", headers=ORIGIN)
    assert calendar.status_code == 200, calendar.text
    event = next(item for item in calendar.json() if item["social_post_id"] == post_id)
    assert event["video_generation_id"] == first_generation
    assert event["video_output_id"] == current_output_id
    assert event["video_version"] == 1
    assert event["schedule_id"] is not None
    analytics = client.get("/api/v1/social/analytics/summary", headers=ORIGIN)
    assert analytics.status_code == 200, analytics.text
    breakdown = analytics.json()["video"]["breakdown"]
    assert any(item["video_output_id"] == current_output_id for item in breakdown)


def test_video_crash_before_connector_invocation_recovers_once(client, monkeypatch):
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    _, post_id = _handoff(client, context, scenario="crash-before")
    _schedule(client, post_id)
    job_id, _ = _materialize_and_claim()
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    import vayujit_api.social.worker as social_worker

    original_connector_for = social_worker.connector_for
    first_call = True

    class CrashBeforeConnector:
        def __init__(self, delegate):
            self.delegate = delegate

        def publish_post(self, *args, **kwargs):
            nonlocal first_call
            if first_call:
                first_call = False
                raise RuntimeError("simulated crash before connector mutation")
            return self.delegate.publish_post(*args, **kwargs)

        def fetch_publication_status(self, *args, **kwargs):
            return self.delegate.fetch_publication_status(*args, **kwargs)

    def crash_before_connector(platform, capabilities):
        return CrashBeforeConnector(original_connector_for(platform, capabilities))

    monkeypatch.setattr(social_worker, "connector_for", crash_before_connector)
    execute_job(job_id, "durable-worker-a")
    assert not FAKE_CONNECTOR_CALLS
    with _factory() as db:
        job = db.get(PublishingJob, job_id)
        assert job is not None
        job.state = "pending"
        job.available_at_utc = datetime.now(UTC) - timedelta(seconds=1)
        job.lease_owner = None
        job.lease_expires_at = None
        db.commit()
        claimed = claim_jobs(db, "durable-worker-b", 1, 60)
    assert claimed == [job_id]
    execute_job(job_id, "durable-worker-b")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None and post.lifecycle_status == "published"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.action == "social.post_published", AuditEvent.entity_id == post.id
                )
            )
            == 1
        )


@pytest.mark.parametrize(
    ("failure_code", "expected_actions"),
    [
        ("social.video.account_disabled", {"review_failure"}),
        ("social.video.invalid_credentials", {"review_failure"}),
        ("social.video.unsupported_format", {"review_failure"}),
        ("social.video.video_not_ready", {"review_failure"}),
        ("social.video.throttled", {"retry", "reschedule", "review_failure"}),
        ("social.video.timeout", {"retry", "reschedule", "review_failure"}),
        ("social.video.connector_unavailable", {"retry", "reschedule", "review_failure"}),
        ("social.video.ambiguous_publication", {"reconcile", "review_failure"}),
        ("social.video.stale_video", {"review_failure"}),
        ("social.video.stale_post", {"review_failure"}),
        ("social.video.scheduling_failure", {"retry", "reschedule", "review_failure"}),
        ("social.video.policy_rejection", {"review_failure"}),
    ],
)
def test_video_recovery_projection_matrix(client, failure_code, expected_actions):
    context = ai_fixture.setup_context(client)
    _, post_id = _handoff(client, context, scenario=failure_code.rsplit(".", 1)[-1])
    _schedule(client, post_id)
    with _factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None
        post.lifecycle_status = "failed"
        post.failure_code = failure_code
        post.safe_failure_message = "The Video publication requires safe owner review."
        db.commit()
    response = client.get("/api/v1/social/recovery", headers=ORIGIN)
    assert response.status_code == 200, response.text
    item = next(value for value in response.json() if value["post_id"] == post_id)
    assert item["failure_code"] == failure_code
    assert item["safe_failure_message"]
    assert item["correlation_id"]
    assert item["video_output_id"]
    assert item["schedule_id"]
    assert set(item["available_actions"]) == expected_actions
    assert "encrypted_credentials" not in response.text.lower()
    assert "database_url" not in response.text.lower()
    assert "traceback" not in response.text.lower()
