from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from fastapi.testclient import TestClient
from helpers import marketplace_video_fixture
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import CampaignActivity, CampaignScheduleLink
from vayujit_api.commerce.marketplace_video import (
    MarketplaceVideoJob,
    MarketplaceVideoMapping,
    fake_video_connector_state,
)
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialPost
from vayujit_api.video.models import VideoGeneration, VideoOutput

client = ai_fixture.client
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _factory() -> Session:
    assert ai_fixture.factory is not None
    return ai_fixture.factory()


def _campaign(client: TestClient, context: dict[str, Any]) -> dict[str, Any]:
    start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=5)
    response = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": context["brand"]["id"],
            "name": "Campaign Video execution",
            "timezone_name": "UTC",
            "local_start_at": start.replace(tzinfo=None).isoformat(),
            "local_end_at": (start + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            "scheduling_policy": "allow_with_confirmation",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _approved_lineage(
    client: TestClient,
    context: dict[str, Any],
    video_channel: str,
    platform: str,
    *,
    key: str | None = None,
) -> dict[str, Any]:
    generation_id = video_fixture._video(  # type: ignore[no-untyped-call]
        client,
        context,
        key=key or f"campaign-video-{video_channel}",
        video_type=video_channel,
        target=platform,
    )
    with _factory() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation.id))
        artifact = db.scalar(
            select(GeneratedArtifact)
            .where(
                GeneratedArtifact.product_id == generation.product_id,
                GeneratedArtifact.status == "approved",
            )
            .order_by(GeneratedArtifact.version_number.desc())
        )
        assert output is not None and output.media_id is not None and artifact is not None
        return {
            "generation_id": str(generation.id),
            "output_id": str(output.id),
            "media_id": str(output.media_id),
            "video_version": 1,
            "artifact_id": str(artifact.id),
            "artifact_version": artifact.version_number,
        }


def _request(
    context: dict[str, Any], lineage: dict[str, Any], account_id: str, video_channel: str
) -> dict[str, Any]:
    return {
        "product_id": context["product"]["id"],
        "video_generation_id": lineage["generation_id"],
        "video_output_id": lineage["output_id"],
        "video_media_id": lineage["media_id"],
        "video_version": lineage["video_version"],
        "video_channel": video_channel,
        "name": f"Publish {video_channel} campaign video",
        "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
        .replace(tzinfo=None)
        .isoformat(),
        "timezone_name": "UTC",
        "target_account_id": account_id,
        "metadata_artifact_id": lineage["artifact_id"],
        "metadata_artifact_version": lineage["artifact_version"],
        "metadata": {"title": "Campaign Video", "locale": "en-IN"},
        "idempotency_key": f"campaign-video-{video_channel}-activity",
    }


@pytest.mark.parametrize(
    ("video_channel", "platform"),
    (
        ("youtube_video", "youtube"),
        ("instagram_reel", "instagram"),
        ("facebook_reel", "facebook"),
    ),
)
def test_social_campaign_video_materializes_once_and_executes_only_in_worker(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, video_channel: str, platform: str
) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    lineage = _approved_lineage(client, context, video_channel, platform)
    account_id = video_fixture._account(client, platform, "-campaign")
    request = _request(context, lineage, account_id, video_channel)

    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=request,
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready"] is True
    assert not FAKE_CONNECTOR_CALLS

    request.update({"preview_fingerprint": preview.json()["fingerprint"], "confirm": True})
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json=request,
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    activity = created.json()["activity"]
    assert not FAKE_CONNECTOR_CALLS

    materialize_payload = {
        "preview_fingerprint": preview.json()["fingerprint"],
        "expected_activity_row_version": activity["row_version"],
        "confirm": True,
    }

    def materialize(_: int) -> Any:
        return client.post(
            f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/materialize",
            json=materialize_payload,
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(materialize, range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    first = next(response for response in responses if response.json()["idempotent_reuse"] is False)
    repeated = next(
        response for response in responses if response.json()["idempotent_reuse"] is True
    )
    assert repeated.json()["job_id"] == first.json()["job_id"]
    sequential = materialize(2)
    assert sequential.status_code == 200, sequential.text
    assert sequential.json()["idempotent_reuse"] is True
    assert not FAKE_CONNECTOR_CALLS

    with _factory() as db:
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 1
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 1
        post = db.scalar(select(SocialPost))
        assert post is not None
        assert str(post.video_output_id) == lineage["output_id"]
        assert post.video_version == lineage["video_version"]
        claimed = claim_jobs(db, "campaign-video-worker", 1, 60)
        assert [str(value) for value in claimed] == [first.json()["job_id"]]
        job_id = claimed[0]

    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, "campaign-video-worker")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1

    with _factory() as db:
        current = db.get(CampaignActivity, activity["id"])
        post = db.scalar(select(SocialPost))
        job = db.get(PublishingJob, job_id)
        assert current is not None and current.status == "succeeded"
        assert post is not None
        assert current.social_post_id == post.id
        assert current.video_remote_id == post.remote_publication_id
        assert current.video_downstream_state == "published"
        assert job is not None and job.state == "succeeded"
        actions = set(
            db.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == current.id))
        )
        assert {
            "campaign_video_created",
            "campaign_video_scheduled",
            "campaign_video_materialized",
            "campaign_video_started",
            "campaign_video_completed",
        } <= actions


@pytest.mark.parametrize("marketplace", ("amazon", "flipkart", "meesho"))
def test_marketplace_campaign_video_delegates_once_and_persists_mapping(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, marketplace: str
) -> None:
    scenario = marketplace_video_fixture.create_marketplace_video_scenario(client, marketplace)
    campaign = _campaign(client, scenario.context)
    artifact_created = client.post(
        "/api/v1/ai/generations",
        json={"product_id": scenario.context["product"]["id"]},
        headers=ORIGIN,
    )
    assert artifact_created.status_code == 201, artifact_created.text
    artifact = client.post(
        f"/api/v1/ai/artifacts/{artifact_created.json()['artifact_id']}/approve",
        headers=ORIGIN,
    )
    assert artifact.status_code == 200, artifact.text
    request = {
        "product_id": scenario.context["product"]["id"],
        "video_generation_id": scenario.generation_id,
        "video_output_id": scenario.output_id,
        "video_media_id": scenario.media_id,
        "video_version": scenario.version,
        "video_channel": marketplace,
        "name": f"Publish {marketplace} Campaign Video",
        "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
        .replace(tzinfo=None)
        .isoformat(),
        "timezone_name": "UTC",
        "target_account_id": scenario.account_id,
        "target_listing_id": scenario.listing_id,
        "metadata_artifact_id": artifact.json()["id"],
        "metadata_artifact_version": artifact.json()["version_number"],
        "metadata": {"title": f"{marketplace.title()} Campaign Video"},
        "idempotency_key": f"campaign-video-{marketplace}-activity",
    }
    before = cast(int, fake_video_connector_state()[marketplace]["mutations"])
    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=request,
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready"] is True
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
    assert cast(int, fake_video_connector_state()[marketplace]["mutations"]) == before
    with _factory() as db:
        claimed = claim_jobs(db, f"campaign-video-{marketplace}", 1, 60)
        assert [str(value) for value in claimed] == [materialized.json()["job_id"]]
        job_id = claimed[0]
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(job_id, f"campaign-video-{marketplace}")
    assert cast(int, fake_video_connector_state()[marketplace]["mutations"]) == before + 1
    with _factory() as db:
        current = db.get(CampaignActivity, activity["id"])
        assert current is not None
        downstream = db.get(MarketplaceVideoJob, current.video_marketplace_job_id)
        mapping = db.get(MarketplaceVideoMapping, current.video_mapping_id)
        assert current is not None and current.status == "succeeded"
        assert downstream is not None and downstream.state == "succeeded"
        assert mapping is not None and mapping.attachment_state == "active"
        assert current.video_remote_id == mapping.remote_video_id
        assert current.video_downstream_state == "succeeded"
