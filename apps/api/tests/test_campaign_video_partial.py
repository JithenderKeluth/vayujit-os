from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from helpers import marketplace_video_fixture
from test_campaign_video_cross_channel import _create_and_materialize
from test_campaign_video_execution import _approved_lineage, _campaign, _factory, _request

from vayujit_api.campaigns.models import Campaign, CampaignActivity
from vayujit_api.commerce.marketplace_video import fake_video_connector_state
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialAccount

client = ai_fixture.client
pytestmark = pytest.mark.integration


def test_six_channel_partial_failure_is_isolated_and_summary_is_honest(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    activities: list[dict[str, object]] = []
    social_account_ids: dict[str, str] = {}
    lineage_by_channel: dict[str, dict[str, Any]] = {}
    for channel, platform in (
        ("youtube_video", "youtube"),
        ("instagram_reel", "instagram"),
        ("facebook_reel", "facebook"),
    ):
        lineage = _approved_lineage(
            client, context, channel, platform, key=f"campaign-video-partial-{channel}"
        )
        lineage_by_channel[channel] = lineage
        account_id = video_fixture._account(client, platform, f"-partial-{platform}")
        social_account_ids[channel] = account_id
        social_request = _request(context, lineage, account_id, channel)
        social_request["idempotency_key"] = f"campaign-video-partial-{channel}"
        activities.append(_create_and_materialize(client, str(campaign["id"]), social_request))

    metadata_lineage = lineage_by_channel["youtube_video"]
    marketplace_before = {
        marketplace: int(cast(int, fake_video_connector_state()[marketplace]["mutations"]))
        for marketplace in ("amazon", "flipkart", "meesho")
    }
    for marketplace in ("amazon", "flipkart", "meesho"):
        scenario = marketplace_video_fixture.create_marketplace_video_scenario(
            client, marketplace, context
        )
        marketplace_request: dict[str, object] = {
            "product_id": context["product"]["id"],
            "video_generation_id": scenario.generation_id,
            "video_output_id": scenario.output_id,
            "video_media_id": scenario.media_id,
            "video_version": scenario.version,
            "video_channel": marketplace,
            "name": f"Partial-state {marketplace} Campaign Video",
            "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
            .replace(tzinfo=None)
            .isoformat(),
            "timezone_name": "UTC",
            "target_account_id": scenario.account_id,
            "target_listing_id": scenario.listing_id,
            "metadata_artifact_id": metadata_lineage["artifact_id"],
            "metadata_artifact_version": metadata_lineage["artifact_version"],
            "metadata": {"title": f"Partial-state {marketplace} Campaign Video"},
            "idempotency_key": f"campaign-video-partial-{marketplace}",
        }
        activities.append(_create_and_materialize(client, str(campaign["id"]), marketplace_request))

    with _factory() as db:
        instagram = db.get(SocialAccount, social_account_ids["instagram_reel"])
        facebook = db.get(SocialAccount, social_account_ids["facebook_reel"])
        assert instagram is not None and facebook is not None
        instagram.capabilities_json = {**instagram.capabilities_json, "scenario": "throttled"}
        facebook.capabilities_json = {**facebook.capabilities_json, "scenario": "policy_failure"}
        db.commit()
        job_ids = claim_jobs(db, "campaign-video-partial-worker", 10, 60)
        assert len(job_ids) == 6

    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    for job_id in job_ids:
        execute_job(job_id, "campaign-video-partial-worker")

    with _factory() as db:
        rows = list(db.query(CampaignActivity).filter_by(campaign_id=campaign["id"]).all())
        states = {row.video_channel: row.status for row in rows}
        current_campaign = db.get(Campaign, campaign["id"])
        assert states == {
            "youtube_video": "succeeded",
            "instagram_reel": "retrying",
            "facebook_reel": "failed",
            "amazon": "succeeded",
            "flipkart": "succeeded",
            "meesho": "succeeded",
        }
        assert current_campaign is not None and current_campaign.status == "partially_completed"
        assert all(
            row.video_remote_id
            for row in rows
            if row.video_channel in {"youtube_video", "amazon", "flipkart", "meesho"}
        )
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 3
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    for marketplace, before in marketplace_before.items():
        assert int(cast(int, fake_video_connector_state()[marketplace]["mutations"])) == before + 1

    analytics = client.get(f"/api/v1/campaigns/{campaign['id']}/video/analytics")
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["total"] == 6
    assert analytics.json()["succeeded"] == 4
    assert analytics.json()["retry_wait"] == 1
    assert analytics.json()["failed"] == 1
    assert analytics.json()["mixed_state"] is True
