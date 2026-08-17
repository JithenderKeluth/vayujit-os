from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
import test_ai_integration as ai_fixture
from sqlalchemy import select
from test_ai_video_bulk_cross_channel_acceptance import bulk_video as create_bulk_video
from test_ai_video_bulk_cross_channel_acceptance import marketplace_target, social_account

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.commerce.marketplace_video import MarketplaceVideoMapping
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingSchedule
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialPost
from vayujit_api.video.models import VideoOutput

client = ai_fixture.client
pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def db_factory():
    assert ai_fixture.factory is not None
    return ai_fixture.factory()


def test_bulk_final_video_version_safety_preserves_v1_across_channels(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import test_campaign_video_cross_channel as campaign_fixture
    import test_campaign_video_execution as execution_fixture

    context = ai_fixture.setup_context(client)
    lineage = create_bulk_video(client, context, "bulk-final-version-v1")

    social_payload = {
        "video_generation_id": lineage["generation_id"],
        "channel": "youtube",
        "target_id": social_account(client),
        "idempotency_key": "bulk-final-version-social",
    }
    prepared = client.post("/api/v1/ai/video/channels/prepare", json=social_payload, headers=ORIGIN)
    assert prepared.status_code == 200, prepared.text
    confirmed = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm",
        json={"fingerprint": prepared.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    with db_factory() as db:
        post = db.scalar(
            select(SocialPost).where(SocialPost.video_generation_id == lineage["generation_id"])
        )
        assert post is not None
        post_id = str(post.id)
    assert client.post(f"/api/v1/social/posts/{post_id}/approve", headers=ORIGIN).status_code == 200
    preview = client.get(f"/api/v1/social/posts/{post_id}/preview", headers=ORIGIN)
    publish = client.post(
        f"/api/v1/social/posts/{post_id}/publish-now",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "local_scheduled_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert publish.status_code == 200, publish.text
    with db_factory() as db:
        assert materialize_due_schedules(db) == 1
        claimed = claim_jobs(db, "bulk-final-version-social", 1, 60)
    assert len(claimed) == 1
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(claimed[0], "bulk-final-version-social")

    account_id, listing_id = marketplace_target(client, context, "amazon")
    marketplace_payload = {
        "listing_id": listing_id,
        "account_id": account_id,
        "video_generation_id": lineage["generation_id"],
        "video_output_id": lineage["output_id"],
        "video_media_id": lineage["media_id"],
        "video_version": 1,
        "correlation_id": "bulk-final-version-marketplace",
    }
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=marketplace_payload, headers=ORIGIN
    )
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/marketplaces/video/confirm",
        json={
            **marketplace_payload,
            "fingerprint": preview.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "bulk-final-version-marketplace",
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    completed = client.post(
        f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
    )
    assert completed.status_code == 200, completed.text

    campaign = execution_fixture._campaign(client, context)
    campaign_request = {
        "product_id": context["product"]["id"],
        "video_generation_id": lineage["generation_id"],
        "video_output_id": lineage["output_id"],
        "video_media_id": lineage["media_id"],
        "video_version": 1,
        "video_channel": "youtube_video",
        "name": "Bulk final version campaign",
        "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
        .replace(tzinfo=None)
        .isoformat(),
        "timezone_name": "UTC",
        "target_account_id": campaign_fixture.video_fixture._account(
            client, "youtube", "-bulk-final-version"
        ),
        "metadata_artifact_id": lineage["artifact_id"],
        "metadata_artifact_version": int(lineage["artifact_version"]),
        "metadata": {"title": "Bulk final version campaign"},
        "idempotency_key": "bulk-final-version-campaign",
    }
    campaign_preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=campaign_request,
        headers=ORIGIN,
    )
    assert campaign_preview.status_code == 200, campaign_preview.text
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json={
            **campaign_request,
            "preview_fingerprint": campaign_preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    activity = created.json()["activity"]
    materialized = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/materialize",
        json={
            "preview_fingerprint": campaign_preview.json()["fingerprint"],
            "expected_activity_row_version": activity["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert materialized.status_code == 200, materialized.text
    with db_factory() as db:
        activity_row = db.get(CampaignActivity, UUID(str(activity["id"])))
        assert activity_row is not None
        schedule = db.get(PublishingSchedule, activity_row.schedule_id)
        assert schedule is not None
        schedule.enabled = True
        schedule.paused = False
        schedule.archived = False
        schedule.max_occurrences = max(schedule.max_occurrences, 1)
        schedule.materialized_occurrence_count = 0
        schedule.next_run_at_utc = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        materialize_due_schedules(db)
        claimed = claim_jobs(db, "bulk-final-version-campaign", 1, 60)
    assert len(claimed) == 1
    execute_job(claimed[0], "bulk-final-version-campaign")

    before_calls = (dict(FAKE_CONNECTOR_CALLS), list(FAKE_REMOTE_PUBLICATIONS))
    regenerated = client.post(
        f"/api/v1/ai/video/generations/{lineage['generation_id']}/regenerate",
        json={"reason": "pacing", "idempotency_key": "bulk-final-version-v2"},
        headers=ORIGIN,
    )
    assert regenerated.status_code == 202, regenerated.text
    generation_v2 = str(regenerated.json()["id"])
    with db_factory() as db:
        assert run_ai_jobs_once(db, "bulk-final-version-v2", limit=1) == 1
        output_v2 = db.scalar(
            select(VideoOutput).where(VideoOutput.generation_id == UUID(generation_v2))
        )
        assert output_v2 is not None and output_v2.status == "pending_review"
    approved = client.post(
        f"/api/v1/ai/video/generations/{generation_v2}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text
    assert (dict(FAKE_CONNECTOR_CALLS), list(FAKE_REMOTE_PUBLICATIONS)) == before_calls

    social_projection = client.get(
        f"/api/v1/ai/video/channels/products/{context['product']['id']}", headers=ORIGIN
    )
    assert social_projection.status_code == 200, social_projection.text
    social_row = next(row for row in social_projection.json() if row["channel"] == "youtube")
    assert social_row["current_video_version"] == 1
    assert social_row["latest_approved_video_version"] == 2
    assert social_row["update_available"] is True

    marketplace_projection = client.get(
        f"/api/v1/marketplaces/video/product/{context['product']['id']}", headers=ORIGIN
    )
    assert marketplace_projection.status_code == 200, marketplace_projection.text
    amazon = next(
        row for row in marketplace_projection.json()["channels"] if row["marketplace"] == "amazon"
    )
    assert amazon["current"]["video_version"] == 1
    assert amazon["latest_approved_video"]["video_version"] == 2
    assert amazon["update_available"] is True

    campaign_projection = client.get(
        f"/api/v1/campaigns/video/products/{context['product']['id']}/channel", headers=ORIGIN
    )
    assert campaign_projection.status_code == 200, campaign_projection.text
    campaign_row = campaign_projection.json()["channels"][0]
    assert campaign_row["current_video_version"] == 1
    assert campaign_row["update_available"] is True

    with db_factory() as db:
        activity_row = db.get(CampaignActivity, UUID(str(activity["id"])))
        mapping = db.scalar(
            select(MarketplaceVideoMapping).where(
                MarketplaceVideoMapping.listing_id == UUID(listing_id)
            )
        )
        post_row = db.get(SocialPost, UUID(post_id))
        assert activity_row is not None and activity_row.video_version == 1
        assert mapping is not None and mapping.video_version == 1
        assert post_row is not None and post_row.video_version == 1
