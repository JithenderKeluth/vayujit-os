from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration as ai_fixture
from helpers.ads_acceptance import create_campaign
from sqlalchemy import func, select
from test_ads_media_e2e import _image, _video
from test_ai_video_bulk_cross_channel_acceptance import marketplace_target
from test_marketing_plan_slice4_acceptance import (
    _confirm_plan,
    _enable_six_channel_accounts,
    _six_channel_payload,
)
from test_social_integration import _account as social_account
from test_social_integration import _artifact as social_artifact

from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.worker import run_next_ads_job
from vayujit_api.ai.image_provider import deterministic_png
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.core.database import Base
from vayujit_api.media.service import storage_root
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _table_counts(factory: Any) -> dict[str, int]:
    with factory() as db:
        return {
            table.name: int(db.scalar(select(func.count()).select_from(table)) or 0)
            for table in Base.metadata.sorted_tables
        }


def _filesystem_counts() -> dict[str, int]:
    root = storage_root()
    files = [path for path in root.rglob("*") if path.is_file()]
    return {"files": len(files), "bytes": sum(path.stat().st_size for path in files)}


def test_whole_product_local_deterministic_journey(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the owner-scoped local product path without contacting live providers."""
    context = ai_fixture.setup_context(client)
    product_id = context["product"]["id"]
    assert ai_fixture.factory is not None
    before_tables = _table_counts(ai_fixture.factory)
    before_files = _filesystem_counts()

    media = client.post(
        "/api/v1/media",
        files={
            "file": (
                "certification.png",
                deterministic_png(64, 64, "final-certification"),
                "image/png",
            )
        },
        headers=ORIGIN,
    )
    assert media.status_code == 201, media.text

    content = client.post("/api/v1/ai/generations", json={"product_id": product_id}, headers=ORIGIN)
    assert content.status_code == 201, content.text
    content_id = content.json()["artifact_id"]
    approved_content = client.post(f"/api/v1/ai/artifacts/{content_id}/approve", headers=ORIGIN)
    assert approved_content.status_code == 200, approved_content.text

    image = _image(client, context, "final-certification-image")
    video = _video(client, context, "final-certification-video")
    assert image["version"] == "1" and video["version"] == "1"

    account_id, listing_id = marketplace_target(client, context, "amazon")
    marketplace_payload = {
        "listing_id": listing_id,
        "account_id": account_id,
        "video_generation_id": video["generation_id"],
        "video_output_id": video["output_id"],
        "video_media_id": video["media_id"],
        "video_version": 1,
        "correlation_id": "final-local-certification-marketplace",
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
            "idempotency_key": "final-local-certification-marketplace",
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    marketplace_run = client.post(
        f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
    )
    assert marketplace_run.status_code == 200, marketplace_run.text

    social = social_artifact(client, product_id, "final-local-certification-social")
    social_account_row = social_account(client, "youtube")
    social_post = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": product_id,
            "account_id": social_account_row["id"],
            "platform": "youtube",
            "content_type": "youtube_video",
            "content_artifact_id": social["id"],
            "content_artifact_version": social["version_number"],
            "caption": "Final local certification",
            "title": "Final local certification",
            "idempotency_key": "final-local-certification-social",
        },
        headers=ORIGIN,
    )
    assert social_post.status_code == 201, social_post.text
    post_id = social_post.json()["id"]
    social_preview = client.get(f"/api/v1/social/posts/{post_id}/preview", headers=ORIGIN)
    assert social_preview.status_code == 200, social_preview.text
    assert client.post(f"/api/v1/social/posts/{post_id}/approve", headers=ORIGIN).status_code == 200
    publish = client.post(
        f"/api/v1/social/posts/{post_id}/publish-now",
        json={
            "preview_fingerprint": social_preview.json()["fingerprint"],
            "local_scheduled_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert publish.status_code == 200, publish.text
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    with ai_fixture.factory() as db:
        assert materialize_due_schedules(db) >= 1
        claimed = claim_jobs(db, "final-local-certification-social", 1, 60)
    assert len(claimed) == 1
    execute_job(claimed[0], "final-local-certification-social")

    ads_campaign = create_campaign(client, context, suffix="final-local-certification")
    _enable_six_channel_accounts(client, context)
    _confirm_plan(client, _six_channel_payload(context, "final-local-certification"))
    with ai_fixture.factory() as db:
        for index in range(6):
            assert run_next_ads_job(db, worker_id=f"final-local-certification-{index}") is not None
    analytics = client.get(f"/api/v1/ads/campaigns/{ads_campaign['id']}/analytics", headers=ORIGIN)
    assert analytics.status_code == 200, analytics.text
    optimization = client.post(
        f"/api/v1/ads/optimization/evaluate?campaign_id={ads_campaign['id']}", headers=ORIGIN
    )
    assert optimization.status_code == 200, optimization.text

    # Exercise one certified deterministic failure and Recovery cycle. The
    # deterministic Ads connector is throttled before the queued mutation,
    # then cleared before retry. Recovery must resume the same logical
    # operation without a duplicate provider mutation.
    connector = connector_for("meta")
    calls_before_recovery = sum(
        call["operation"] == "create_campaign" for call in connector.state.calls
    )
    connector.state.failures["create_campaign"] = "throttled"
    failed_recovery = client.post(
        "/api/v1/ads/recovery",
        json={
            "action": "retry",
            "entity_type": "campaign",
            "entity_id": ads_campaign["id"],
            "failure_code": "ads.throttled",
            "confirm": True,
            "idempotency_key": "final-local-certification-failure",
            "correlation_id": "final-local-certification-recovery",
        },
        headers=ORIGIN,
    )
    assert failed_recovery.status_code == 200, failed_recovery.text
    failed_job_id = failed_recovery.json()["job_id"]
    failed_job = client.post(f"/api/v1/ads/jobs/{failed_job_id}/run", headers=ORIGIN)
    assert failed_job.status_code == 200, failed_job.text
    assert failed_job.json()["status"] == "retry_wait"
    assert failed_job.json()["failure_code"] == "ads.throttled"
    assert "traceback" not in failed_job.text.lower()

    connector.state.failures.pop("create_campaign", None)
    recovered = client.post(
        "/api/v1/ads/recovery",
        json={
            "action": "retry",
            "entity_type": "campaign",
            "entity_id": ads_campaign["id"],
            "failure_code": "ads.throttled",
            "confirm": True,
            "idempotency_key": "final-local-certification-recovery",
            "correlation_id": "final-local-certification-recovery",
        },
        headers=ORIGIN,
    )
    assert recovered.status_code == 200, recovered.text
    recovered_job_id = recovered.json()["job_id"]
    assert recovered_job_id != failed_job_id
    recovered_job = client.post(f"/api/v1/ads/jobs/{recovered_job_id}/run", headers=ORIGIN)
    assert recovered_job.status_code == 200, recovered_job.text
    assert recovered_job.json()["status"] == "succeeded"
    assert recovered_job.json()["failure_code"] is None
    assert recovered.json()["correlation_id"] == "final-local-certification-recovery"
    recovery_projection = client.get("/api/v1/ads/recovery", headers=ORIGIN)
    assert recovery_projection.status_code == 200, recovery_projection.text
    throttled = next(
        item for item in recovery_projection.json() if item["failure_code"] == "ads.throttled"
    )
    assert throttled["safe_message"] and throttled["observed"] is True
    assert (
        sum(call["operation"] == "create_campaign" for call in connector.state.calls)
        == calls_before_recovery + 1
    )
    history = client.get("/api/v1/ads/history", headers=ORIGIN)
    assert history.status_code == 200, history.text
    assert {item["action"] for item in history.json()} >= {
        "ads.recovery_recorded",
    }
    campaign_start = datetime.now(UTC).replace(microsecond=0)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": context["brand"]["id"],
            "name": "Final local certification campaign",
            "timezone_name": "UTC",
            "local_start_at": campaign_start.replace(tzinfo=None).isoformat(),
            "local_end_at": (campaign_start + timedelta(days=1)).replace(tzinfo=None).isoformat(),
        },
        headers=ORIGIN,
    )
    assert campaign.status_code == 201, campaign.text
    calendar = client.get(
        "/api/v1/campaigns/calendar",
        params={
            "start": (campaign_start - timedelta(hours=1)).isoformat(),
            "end": (campaign_start + timedelta(days=1)).isoformat(),
            "view": "agenda",
        },
        headers=ORIGIN,
    )
    assert calendar.status_code == 200, calendar.text
    calendar_body = calendar.json()
    assert calendar_body["view"] == "agenda" and isinstance(calendar_body["days"], list)

    product_channel = client.get(f"/api/v1/ads/product-channel/{product_id}", headers=ORIGIN)
    assert product_channel.status_code == 200, product_channel.text
    channel_body = product_channel.json()
    assert isinstance(channel_body.get("providers"), list)
    for path in (
        f"/api/v1/ai/seo/products/{product_id}/channels",
        f"/api/v1/ai/video/channels/products/{product_id}",
        f"/api/v1/marketplaces/video/product/{product_id}",
        f"/api/v1/ads/product-channel/{product_id}",
        "/api/v1/operations/history",
    ):
        response = client.get(path, headers=ORIGIN)
        assert response.status_code == 200, f"{path}: {response.text}"

    with ai_fixture.factory() as db:
        assert run_ai_jobs_once(db, "final-local-certification-replay", limit=20) == 0
    after_tables = _table_counts(ai_fixture.factory)
    after_files = _filesystem_counts()
    print(
        "STORAGE_LEDGER="
        + json.dumps({"before": before_tables, "after": after_tables}, sort_keys=True)
    )
    print(
        "FILESYSTEM_LEDGER="
        + json.dumps({"before": before_files, "after": after_files}, sort_keys=True)
    )
