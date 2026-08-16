from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from helpers import marketplace_video_fixture
from sqlalchemy import func, select
from test_campaign_video_execution import ORIGIN, _approved_lineage, _campaign, _factory, _request

from vayujit_api.campaigns.models import CampaignActivity, CampaignScheduleLink
from vayujit_api.commerce.marketplace_video import (
    MarketplaceVideoMapping,
    fake_video_connector_state,
)
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialPost

client = ai_fixture.client
pytestmark = pytest.mark.integration


def _create_and_materialize(
    client: Any, campaign_id: str, request: dict[str, object]
) -> dict[str, object]:
    preview = client.post(
        f"/api/v1/campaigns/{campaign_id}/video/activities/preview",
        json=request,
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready"] is True
    request.update({"preview_fingerprint": preview.json()["fingerprint"], "confirm": True})
    created = client.post(
        f"/api/v1/campaigns/{campaign_id}/video/activities", json=request, headers=ORIGIN
    )
    assert created.status_code == 200, created.text
    activity = created.json()["activity"]
    materialized = client.post(
        f"/api/v1/campaigns/{campaign_id}/video/activities/{activity['id']}/materialize",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "expected_activity_row_version": activity["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert materialized.status_code == 200, materialized.text
    return {**activity, **materialized.json()}


def test_six_channel_campaign_executes_independently_and_projects_exact_usage(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    activities: list[dict[str, object]] = []

    social_specs = (
        ("youtube_video", "youtube"),
        ("instagram_reel", "instagram"),
        ("facebook_reel", "facebook"),
    )
    metadata_artifact_id = None
    metadata_artifact_version = None
    for channel, platform in social_specs:
        lineage = _approved_lineage(
            client, context, channel, platform, key=f"six-channel-{channel}"
        )
        metadata_artifact_id = metadata_artifact_id or lineage["artifact_id"]
        metadata_artifact_version = metadata_artifact_version or lineage["artifact_version"]
        account_id = video_fixture._account(client, platform, f"-six-{platform}")
        request = _request(context, lineage, account_id, channel)
        request["idempotency_key"] = f"six-channel-{channel}-activity"
        activities.append(_create_and_materialize(client, campaign["id"], request))

    marketplace_before = {
        key: int(cast(int, fake_video_connector_state()[key]["mutations"]))
        for key in ("amazon", "flipkart", "meesho")
    }
    for marketplace in ("amazon", "flipkart", "meesho"):
        scenario = marketplace_video_fixture.create_marketplace_video_scenario(
            client, marketplace, context
        )
        request = {
            "product_id": context["product"]["id"],
            "video_generation_id": scenario.generation_id,
            "video_output_id": scenario.output_id,
            "video_media_id": scenario.media_id,
            "video_version": scenario.version,
            "video_channel": marketplace,
            "name": f"Six-channel {marketplace} Video",
            "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
            .replace(tzinfo=None)
            .isoformat(),
            "timezone_name": "UTC",
            "target_account_id": scenario.account_id,
            "target_listing_id": scenario.listing_id,
            "metadata_artifact_id": metadata_artifact_id,
            "metadata_artifact_version": metadata_artifact_version,
            "metadata": {"title": f"Six-channel {marketplace} Video"},
            "idempotency_key": f"six-channel-{marketplace}-activity",
        }
        activities.append(_create_and_materialize(client, campaign["id"], request))

    assert not FAKE_CONNECTOR_CALLS
    assert len({str(item["id"]) for item in activities}) == 6
    assert len({str(item["schedule_id"]) for item in activities}) == 6
    assert len({str(item["job_id"]) for item in activities}) == 6
    with _factory() as db:
        assert db.scalar(select(func.count()).select_from(CampaignActivity)) == 6
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 6
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 6
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 6
        job_ids = claim_jobs(db, "six-channel-video-worker", 10, 60)
        assert len(job_ids) == 6

    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    for job_id in job_ids:
        execute_job(job_id, "six-channel-video-worker")

    assert sum(FAKE_CONNECTOR_CALLS.values()) == 3
    assert len(FAKE_REMOTE_PUBLICATIONS) == 3
    for marketplace, before in marketplace_before.items():
        assert int(cast(int, fake_video_connector_state()[marketplace]["mutations"])) == before + 1

    with _factory() as db:
        rows = list(db.scalars(select(CampaignActivity)))
        assert len(rows) == 6 and all(row.status == "succeeded" for row in rows)
        assert len({row.schedule_id for row in rows}) == 6
        assert len({row.job_id for row in rows}) == 6
        assert len({row.social_post_id for row in rows if row.social_post_id}) == 3
        assert (
            len({row.video_marketplace_job_id for row in rows if row.video_marketplace_job_id}) == 3
        )
        assert all(row.video_remote_id for row in rows)
        assert db.scalar(select(func.count()).select_from(SocialPost)) == 3
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)) == 3

    analytics = client.get(f"/api/v1/campaigns/{campaign['id']}/video/analytics")
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["total"] == 6
    assert analytics.json()["succeeded"] == 6
    assert set(analytics.json()["by_channel"]) == {
        "youtube_video",
        "instagram_reel",
        "facebook_reel",
        "amazon",
        "flipkart",
        "meesho",
    }
    channel = client.get(f"/api/v1/campaigns/video/products/{context['product']['id']}/channel")
    assert channel.status_code == 200, channel.text
    assert len(channel.json()["channels"]) == 6
    assert all("open_campaign" in item["actions"] for item in channel.json()["channels"])
    usage = client.get(f"/api/v1/campaigns/video/products/{context['product']['id']}/media-usage")
    assert usage.status_code == 200, usage.text
    assert len(usage.json()) == 6
    assert all(item["downstream_id"] and item["remote_id"] for item in usage.json())
    start = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    end = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    calendar = client.get(
        f"/api/v1/campaigns/{campaign['id']}/calendar", params={"start": start, "end": end}
    )
    assert calendar.status_code == 200, calendar.text
    assert len(calendar.json()) == 6
    assert all(
        item["video_output_id"] and item["dependency_state"] == "ready" for item in calendar.json()
    )
    history = client.get(f"/api/v1/campaigns/{campaign['id']}/video/history")
    assert history.status_code == 200, history.text
    assert sum(item["action"] == "campaign_video_completed" for item in history.json()) == 6
    for activity in activities:
        detail = client.get(
            f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/detail"
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["activity"]["video_remote_id"]
