from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import test_ai_integration as ai_fixture
from sqlalchemy import func, select
from test_campaign_video_execution import (
    ORIGIN,
    _approved_lineage,
    _campaign,
    _factory,
    _request,
)

from vayujit_api.campaigns.models import CampaignActivity, CampaignActivityDependency
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS

client = ai_fixture.client
pytestmark = pytest.mark.integration


def _activity_with_dependency(client):
    FAKE_CONNECTOR_CALLS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    lineage = _approved_lineage(client, context, "youtube_video", "youtube")
    account_id = __import__("test_ai_video_slice3_channels")._account(
        client, "youtube", "-dependency"
    )
    request = _request(context, lineage, account_id, "youtube_video")
    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=request,
        headers=ORIGIN,
    )
    assert preview.status_code == 200 and preview.json()["ready"] is True
    request.update({"preview_fingerprint": preview.json()["fingerprint"], "confirm": True})
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json=request,
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    activity = created.json()["activity"]
    scheduled = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=2)
    predecessor = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activities",
        json={
            "activity_type": "review_checkpoint",
            "name": "Video prerequisite",
            "sequence": 20,
            "scheduled_local_date": scheduled.date().isoformat(),
            "scheduled_local_time": scheduled.time().isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert predecessor.status_code == 201, predecessor.text
    dependency = client.post(
        f"/api/v1/campaigns/{campaign['id']}/dependencies",
        json={
            "predecessor_activity_id": predecessor.json()["id"],
            "successor_activity_id": activity["id"],
            "dependency_type": "success_required",
        },
        headers=ORIGIN,
    )
    assert dependency.status_code == 201, dependency.text
    return campaign, activity, predecessor.json(), preview.json()["fingerprint"]


def _materialize(client, campaign, activity, fingerprint):
    return client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/materialize",
        json={
            "preview_fingerprint": fingerprint,
            "expected_activity_row_version": activity["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )


def test_dependency_waits_without_job_then_same_activity_resumes_once(client) -> None:
    campaign, activity, predecessor, fingerprint = _activity_with_dependency(client)
    waiting = _materialize(client, campaign, activity, fingerprint)
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["status"] == "waiting_dependency"
    assert waiting.json()["job_id"] is None
    assert not FAKE_CONNECTOR_CALLS
    with _factory() as db:
        current = db.get(CampaignActivity, activity["id"])
        edge = db.scalar(select(CampaignActivityDependency))
        assert current is not None and str(current.id) == activity["id"]
        assert current.failure_code is None
        assert edge is not None
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 0
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
        required = db.get(CampaignActivity, predecessor["id"])
        assert required is not None
        required.status = "succeeded"
        required.completed_at = datetime.now(UTC)
        db.commit()
    resumed = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/dependencies/resume", headers=ORIGIN
    )
    assert resumed.status_code == 200 and resumed.json()["resumed"] == 1
    scheduled = _materialize(client, campaign, activity, fingerprint)
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["job_id"]
    repeated = _materialize(client, campaign, activity, fingerprint)
    assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    with _factory() as db:
        assert db.scalar(select(func.count()).select_from(CampaignActivity)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 1


def test_permanently_failed_dependency_blocks_without_connector_or_job(client) -> None:
    campaign, activity, predecessor, fingerprint = _activity_with_dependency(client)
    with _factory() as db:
        required = db.get(CampaignActivity, predecessor["id"])
        assert required is not None
        required.status = "failed"
        required.failure_code = "prerequisite_rejected"
        db.commit()
    blocked = _materialize(client, campaign, activity, fingerprint)
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["status"] == "failed"
    assert blocked.json()["failure_code"] == "campaign_video_dependency_invalid"
    assert not FAKE_CONNECTOR_CALLS
    with _factory() as db:
        current = db.get(CampaignActivity, activity["id"])
        assert current is not None and current.dependency_state == "failed"
        assert current.safe_failure_message == "A Campaign Video dependency is permanently invalid."
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 0
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
