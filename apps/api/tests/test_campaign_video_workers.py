from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_campaign_video_execution import ORIGIN, _approved_lineage, _campaign, _factory, _request

from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import (
    CampaignActivity,
    CampaignActivityReschedule,
    CampaignScheduleLink,
)
from vayujit_api.publishing.job_queue import claim_jobs, recover_expired_leases
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialPost
from vayujit_api.social.worker import execute_social_job

client = ai_fixture.client
pytestmark = pytest.mark.integration


def _materialized_social(client) -> tuple[dict[str, object], dict[str, object]]:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    lineage = _approved_lineage(client, context, "youtube_video", "youtube")
    account_id = video_fixture._account(client, "youtube", "-worker")
    request = _request(context, lineage, account_id, "youtube_video")
    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=request,
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    request.update({"preview_fingerprint": preview.json()["fingerprint"], "confirm": True})
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json=request,
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    activity = created.json()["activity"]
    materialized = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/materialize",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "expected_activity_row_version": activity["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert materialized.status_code == 200, materialized.text
    return campaign, {**activity, **materialized.json()}


def test_cancelled_campaign_video_refuses_stale_job_without_connector(client, monkeypatch) -> None:
    campaign, activity = _materialized_social(client)
    job_id = uuid.UUID(str(activity["job_id"]))
    cancelled = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activities/{activity['id']}/cancel",
        headers=ORIGIN,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert not FAKE_CONNECTOR_CALLS

    with _factory() as db:
        schedule = db.get(PublishingSchedule, activity["schedule_id"])
        job = db.get(PublishingJob, job_id)
        post = db.scalar(select(SocialPost))
        assert schedule is not None and schedule.archived and not schedule.enabled
        assert job is not None and job.state == "cancelled"
        assert post is not None and post.lifecycle_status == "cancelled"
        job.state = "claimed"
        job.lease_owner = "stale-video-worker"
        job.lease_expires_at = utcnow() + timedelta(minutes=1)
        db.commit()

    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "stale-video-worker")
    assert not FAKE_CONNECTOR_CALLS
    assert not FAKE_REMOTE_PUBLICATIONS
    with _factory() as db:
        current = db.get(CampaignActivity, activity["id"])
        job = db.get(PublishingJob, job_id)
        assert current is not None and current.status == "cancelled"
        assert job is not None and job.state == "cancelled"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == current.id,
                    AuditEvent.action == "campaign_video_cancelled",
                )
            )
            == 1
        )


def test_crash_before_connector_recovers_lease_and_executes_once(client, monkeypatch) -> None:
    _, activity = _materialized_social(client)
    job_id = uuid.UUID(str(activity["job_id"]))
    with _factory() as db:
        claimed = claim_jobs(db, "crashed-video-worker", 1, 60)
        assert claimed == [job_id]
        job = db.get(PublishingJob, job_id)
        assert job is not None
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert recover_expired_leases(db) == 1
        db.refresh(job)
        assert job.state == "retry_wait"
        job.available_at_utc = utcnow() - timedelta(seconds=1)
        db.commit()
        assert claim_jobs(db, "recovered-video-worker", 1, 60) == [job_id]

    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "recovered-video-worker")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        current = db.get(CampaignActivity, activity["id"])
        assert current is not None and current.status == "succeeded"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == current.id,
                    AuditEvent.action == "campaign_video_completed",
                )
            )
            == 1
        )


def test_crash_after_downstream_checkpoint_finalizes_without_republishing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, activity = _materialized_social(client)
    job_id = uuid.UUID(str(activity["job_id"]))
    with _factory() as db:
        assert claim_jobs(db, "campaign-video-crash-after", 1, 60) == [job_id]
        job = db.get(PublishingJob, job_id)
        assert job is not None
        result = execute_social_job(db, job)
        assert result.status == "succeeded"
        current = db.get(CampaignActivity, uuid.UUID(str(activity["id"])))
        post = db.scalar(select(SocialPost))
        assert current is not None and post is not None
        assert post.lifecycle_status == "published" and post.remote_publication_id
        current.status = "running"
        current.completed_at = None
        current.video_remote_id = None
        current.video_downstream_state = "running"
        db.commit()

    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "campaign-video-crash-after")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        current = db.get(CampaignActivity, uuid.UUID(str(activity["id"])))
        job = db.get(PublishingJob, job_id)
        assert current is not None and current.status == "succeeded"
        assert current.video_remote_id
        assert job is not None and job.state == "succeeded"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == current.id,
                    AuditEvent.action == "campaign_video_completed",
                )
            )
            == 1
        )


def test_campaign_video_reschedule_preserves_t1_and_one_active_t2(
    client: TestClient,
) -> None:
    campaign, activity = _materialized_social(client)
    proposed = (datetime.now(UTC) + timedelta(days=2)).replace(tzinfo=None, microsecond=0)
    with _factory() as db:
        current = db.get(CampaignActivity, uuid.UUID(str(activity["id"])))
        assert current is not None
        expected_row_version = current.row_version
        old_schedule_id = current.schedule_id
        old_job_id = current.job_id

    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/recovery/reschedule-activity/preview",
        json={
            "activity_id": activity["id"],
            "proposed_local_datetime": proposed.isoformat(),
            "proposed_timezone": "UTC",
            "reason": "Move the Campaign Video to the approved future slot.",
            "expected_activity_row_version": expected_row_version,
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    payload = {
        "action": "reschedule_activity",
        "campaign_id": campaign["id"],
        "activity_id": activity["id"],
        "proposed_local_datetime": proposed.isoformat(),
        "proposed_timezone": "UTC",
        "reason": "Move the Campaign Video to the approved future slot.",
        "expected_activity_row_version": expected_row_version,
        "preview_fingerprint": preview.json()["preview_fingerprint"],
        "confirm": True,
    }
    confirmed = client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["result"]["idempotent_reuse"] is True
    assert not FAKE_CONNECTOR_CALLS

    with _factory() as db:
        current = db.get(CampaignActivity, uuid.UUID(str(activity["id"])))
        old_schedule = db.get(PublishingSchedule, old_schedule_id)
        old_job = db.get(PublishingJob, old_job_id)
        assert current is not None and current.schedule_id != old_schedule_id
        assert current.job_id is not None and current.job_id != old_job_id
        assert current.status == "scheduled"
        assert old_schedule is not None and old_schedule.archived and not old_schedule.enabled
        assert old_job is not None and old_job.state == "cancelled"
        new_job = db.get(PublishingJob, current.job_id)
        assert new_job is not None and new_job.state == "scheduled"
        assert new_job.available_at_utc > datetime.now(UTC)
        assert (
            db.scalar(
                select(func.count())
                .select_from(PublishingSchedule)
                .where(PublishingSchedule.enabled, PublishingSchedule.archived.is_(False))
            )
            == 1
        )
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 2
        assert db.scalar(select(func.count()).select_from(CampaignActivityReschedule)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == current.id,
                    AuditEvent.action == "campaign_video_rescheduled",
                )
            )
            == 1
        )
