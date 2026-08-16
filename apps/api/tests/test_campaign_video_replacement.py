from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_campaign_video_execution import ORIGIN, _approved_lineage, _campaign, _factory, _request

from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.video.models import VideoGeneration

client = ai_fixture.client
pytestmark = pytest.mark.integration


def test_replacement_preserves_history_and_materializes_one_new_execution(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    original_lineage = _approved_lineage(client, context, "youtube_video", "youtube")
    account_id = video_fixture._account(client, "youtube", "-replacement")
    original_request = _request(context, original_lineage, account_id, "youtube_video")
    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=original_request,
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    original_request.update({"preview_fingerprint": preview.json()["fingerprint"], "confirm": True})
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json=original_request,
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    original = created.json()["activity"]
    materialized = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{original['id']}/materialize",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "expected_activity_row_version": original["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert materialized.status_code == 200, materialized.text

    replacement_lineage = _approved_lineage(
        client, context, "youtube_video", "youtube", key="campaign-video-youtube-v2"
    )
    with _factory() as db:
        generation = db.get(VideoGeneration, uuid.UUID(replacement_lineage["generation_id"]))
        assert generation is not None
        generation.parent_generation_id = uuid.UUID(original_lineage["generation_id"])
        current = db.get(CampaignActivity, uuid.UUID(original["id"]))
        assert current is not None
        expected_row_version = current.row_version
        old_schedule_id = current.schedule_id
        old_job_id = current.job_id
        db.commit()

    replacement_request = _request(context, replacement_lineage, account_id, "youtube_video")
    replacement_request.update(
        {
            "activity_id": original["id"],
            "video_version": 2,
            "expected_activity_row_version": expected_row_version,
            "idempotency_key": "campaign-video-youtube-replacement-v2",
        }
    )
    replacement_preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{original['id']}/replacement/preview",
        json=replacement_request,
        headers=ORIGIN,
    )
    assert replacement_preview.status_code == 200, replacement_preview.text
    assert replacement_preview.json()["ready"] is True
    replacement_request.update(
        {
            "preview_fingerprint": replacement_preview.json()["fingerprint"],
            "confirm": True,
            "reason": "Use the exact approved replacement Video version.",
        }
    )

    def confirm_replacement(_: int) -> Any:
        return client.post(
            f"/api/v1/campaigns/{campaign['id']}/video/activities/{original['id']}/replacement",
            json=replacement_request,
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        confirmations = list(pool.map(confirm_replacement, range(2)))
    assert all(response.status_code == 200 for response in confirmations), [
        response.text for response in confirmations
    ]
    confirmed = next(
        response for response in confirmations if response.json()["idempotent_reuse"] is False
    )
    repeated = next(
        response for response in confirmations if response.json()["idempotent_reuse"] is True
    )
    sequential = confirm_replacement(2)
    assert sequential.status_code == 200, sequential.text
    assert sequential.json()["idempotent_reuse"] is True
    replacement = confirmed.json()["activity"]
    assert repeated.json()["activity"]["id"] == replacement["id"]

    new_materialized = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{replacement['id']}/materialize",
        json={
            "preview_fingerprint": replacement_preview.json()["fingerprint"],
            "expected_activity_row_version": replacement["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert new_materialized.status_code == 200, new_materialized.text
    assert not FAKE_CONNECTOR_CALLS
    new_job_id = uuid.UUID(new_materialized.json()["job_id"])
    with _factory() as db:
        historical = db.get(CampaignActivity, uuid.UUID(original["id"]))
        current = db.get(CampaignActivity, uuid.UUID(replacement["id"]))
        old_schedule = db.get(PublishingSchedule, old_schedule_id)
        old_job = db.get(PublishingJob, old_job_id)
        assert historical is not None and historical.video_replacement_state == "replaced"
        assert current is not None and current.video_version == 2
        assert historical.video_version == 1 and historical.replaced_by_activity_id == current.id
        assert current.replaces_activity_id == historical.id
        assert old_schedule is not None and old_schedule.archived and not old_schedule.enabled
        assert old_job is not None and old_job.state == "cancelled"
        assert (
            db.scalar(
                select(func.count())
                .select_from(PublishingSchedule)
                .where(PublishingSchedule.enabled)
            )
            == 1
        )
        assert claim_jobs(db, "replacement-video-worker", 1, 60) == [new_job_id]

    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(new_job_id, "replacement-video-worker")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with _factory() as db:
        historical = db.get(CampaignActivity, uuid.UUID(original["id"]))
        current = db.get(CampaignActivity, uuid.UUID(replacement["id"]))
        assert historical is not None and historical.video_version == 1
        assert current is not None and current.status == "succeeded"
