from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from sqlalchemy import func, select
from test_campaign_video_execution import ORIGIN, _approved_lineage, _campaign, _factory, _request

from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialAccount, SocialPost

client = ai_fixture.client
pytestmark = pytest.mark.integration


def test_ambiguous_social_result_reconciles_once_without_republishing(client, monkeypatch) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    lineage = _approved_lineage(
        client, context, "youtube_video", "youtube", key="campaign-video-ambiguous"
    )
    account_id = video_fixture._account(client, "youtube", "-ambiguous")
    with _factory() as db:
        account = db.get(SocialAccount, uuid.UUID(account_id))
        assert account is not None
        account.capabilities_json = {**account.capabilities_json, "scenario": "ambiguous_result"}
        db.commit()
    request = _request(context, lineage, account_id, "youtube_video")
    request["idempotency_key"] = "campaign-video-ambiguous-activity"
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
    job_id = uuid.UUID(materialized.json()["job_id"])
    with _factory() as db:
        assert claim_jobs(db, "ambiguous-video-worker", 1, 60) == [job_id]
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "ambiguous-video-worker")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1

    with _factory() as db:
        current = db.get(CampaignActivity, uuid.UUID(activity["id"]))
        assert current is not None
        post = db.get(SocialPost, current.social_post_id)
        job = db.get(PublishingJob, job_id)
        assert current.status == "reconciliation_required"
        assert current.failure_code == "social.video.ambiguous_publication"
        assert post is not None and post.remote_publication_id
        assert job is not None and job.state == "failed"

    recovery_payload = {
        "action": "reconcile_activity",
        "campaign_id": campaign["id"],
        "activity_id": activity["id"],
        "reason": "Reconcile the exact Campaign Video downstream checkpoint.",
        "confirm": True,
    }

    def reconcile(_: int) -> Any:
        return client.post(
            "/api/v1/campaigns/recovery/actions", json=recovery_payload, headers=ORIGIN
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        recovery_responses = list(pool.map(reconcile, range(2)))
    assert all(response.status_code == 200 for response in recovery_responses), [
        response.text for response in recovery_responses
    ]
    assert (
        sum(
            response.json()["result"]["idempotent_reuse"] is False
            for response in recovery_responses
        )
        == 1
    )
    repeated = reconcile(2)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["result"]["idempotent_reuse"] is True
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        current = db.get(CampaignActivity, uuid.UUID(activity["id"]))
        assert current is not None and current.status == "succeeded"
        assert current.video_remote_id
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == current.id,
                    AuditEvent.action == "campaign_video_reconciled",
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == current.id,
                    AuditEvent.action == "campaign_video_recovered",
                )
            )
            == 1
        )
