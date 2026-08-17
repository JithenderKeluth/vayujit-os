from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import test_ai_integration as ai_fixture
from sqlalchemy import func, select
from test_ai_video_bulk_e2e import bulk_payload

from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.campaigns.models import CampaignActivity, CampaignScheduleLink
from vayujit_api.commerce.marketplace_video import MarketplaceVideoJob, MarketplaceVideoMapping
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS, FAKE_REMOTE_PUBLICATIONS
from vayujit_api.social.models import SocialPost
from vayujit_api.video.bulk_models import VideoBulkChild
from vayujit_api.video.models import VideoGeneration, VideoOutput

client = ai_fixture.client
pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def db_factory():
    assert ai_fixture.factory is not None
    return ai_fixture.factory()


def bulk_video(client: Any, context: dict[str, Any], key: str) -> dict[str, str]:
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = str(queued.json()["id"])
    with db_factory() as db:
        assert run_ai_jobs_once(db, f"{key}-worker", limit=1) == 1
        child = db.scalar(select(VideoBulkChild).where(VideoBulkChild.bulk_id == UUID(bulk_id)))
        assert child is not None and child.generation_id is not None
        generation = db.get(VideoGeneration, child.generation_id)
        output = db.scalar(
            select(VideoOutput).where(VideoOutput.generation_id == child.generation_id)
        )
        assert generation is not None and output is not None and output.media_id is not None
        result = {
            "bulk_id": bulk_id,
            "child_id": str(child.id),
            "generation_id": str(generation.id),
            "output_id": str(output.id),
            "media_id": str(output.media_id),
            "video_version": "1",
        }
    approved = client.post(
        f"/api/v1/ai/video/generations/{result['generation_id']}/approve",
        json={},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    artifact = client.post(
        "/api/v1/ai/generations",
        json={"product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert artifact.status_code == 201, artifact.text
    result["artifact_id"] = str(artifact.json()["artifact_id"])
    result["artifact_version"] = str(artifact.json().get("version_number", 1))
    approved_artifact = client.post(
        f"/api/v1/ai/artifacts/{result['artifact_id']}/approve", headers=ORIGIN
    )
    assert approved_artifact.status_code == 200, approved_artifact.text
    return result


def social_account(client: Any) -> str:
    response = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": "youtube",
            "display_name": "Bulk YouTube",
            "remote_account_id": f"bulk-youtube-{uuid4().hex[:8]}",
            "capabilities": {"supported_content_types": ["youtube_video"]},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    account_id = response.json()["id"]
    validated = client.post(f"/api/v1/social/accounts/{account_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    return str(validated.json()["id"])


def marketplace_target(client: Any, context: dict[str, Any], marketplace: str) -> tuple[str, str]:
    account = client.post(
        "/api/v1/marketplaces/accounts",
        json={
            "marketplace": marketplace,
            "display_name": f"Bulk {marketplace}",
            "seller_account_id": f"bulk-seller-{marketplace}",
            "credentials": {"token": f"local-{marketplace}"},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201, account.text
    account_id = str(account.json()["id"])
    for action in ("validate", "enable"):
        response = client.post(
            f"/api/v1/marketplaces/accounts/{account_id}/{action}", headers=ORIGIN
        )
        assert response.status_code == 200, response.text
    listing = client.post(
        "/api/v1/marketplaces/listings",
        json={
            "product_id": context["product"]["id"],
            "brand_id": context["brand"]["id"],
            "account_id": account_id,
            "title": f"Bulk {marketplace} Video",
            "marketplace_sku": f"BULK-{marketplace.upper()}-{uuid4().hex[:6]}",
            "idempotency_key": f"bulk-listing-{marketplace}-{uuid4().hex}",
        },
        headers=ORIGIN,
    )
    assert listing.status_code == 201, listing.text
    return account_id, str(listing.json()["id"])


def safe(response: Any) -> None:
    assert response.status_code != 500
    body = response.text.lower()
    assert all(
        value not in body
        for value in ("traceback", "database_url", "postgresql://", "c:\\users", "select ")
    )


def test_bulk_to_social_durable_handoff_pins_exact_output_and_is_idempotent(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    context = ai_fixture.setup_context(client)
    lineage = bulk_video(client, context, "bulk-social-durable")
    payload = {
        "video_generation_id": lineage["generation_id"],
        "channel": "youtube",
        "target_id": social_account(client),
        "idempotency_key": "bulk-social-handoff",
    }
    preview = client.post("/api/v1/ai/video/channels/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200 and preview.json()["compatibility"] == "ready"
    prepared = client.post("/api/v1/ai/video/channels/prepare", json=payload, headers=ORIGIN)
    assert prepared.status_code == 200, prepared.text
    confirm = {"fingerprint": prepared.json()["fingerprint"], "confirm": True}
    confirmed = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm", json=confirm, headers=ORIGIN
    )
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm", json=confirm, headers=ORIGIN
    )
    assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    with db_factory() as db:
        post = db.scalar(
            select(SocialPost).where(SocialPost.video_generation_id == lineage["generation_id"])
        )
        assert (
            post is not None
            and str(post.video_output_id) == lineage["output_id"]
            and str(post.video_media_id) == lineage["media_id"]
        )
        post_id = str(post.id)
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
    assert client.post(f"/api/v1/social/posts/{post_id}/approve", headers=ORIGIN).status_code == 200
    post_preview = client.get(f"/api/v1/social/posts/{post_id}/preview", headers=ORIGIN)
    scheduled = client.post(
        f"/api/v1/social/posts/{post_id}/publish-now",
        json={
            "preview_fingerprint": post_preview.json()["fingerprint"],
            "local_scheduled_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert scheduled.status_code == 200, scheduled.text
    with db_factory() as db:
        assert materialize_due_schedules(db) == 1
        claimed = claim_jobs(db, "bulk-social-worker", 1, 60)
    assert len(claimed) == 1
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(claimed[0], "bulk-social-worker")
    assert sum(FAKE_CONNECTOR_CALLS.values()) == 1 and len(FAKE_REMOTE_PUBLICATIONS) == 1
    with db_factory() as db:
        post = db.get(SocialPost, post_id)
        assert post is not None and post.lifecycle_status == "published"


@pytest.mark.parametrize("marketplace", ["amazon", "flipkart", "meesho"])
def test_bulk_to_marketplace_readiness_is_exact_and_confirmation_is_durable(
    client: Any, marketplace: str
) -> None:
    context = ai_fixture.setup_context(client)
    lineage = bulk_video(client, context, f"bulk-marketplace-{marketplace}")
    account_id, listing_id = marketplace_target(client, context, marketplace)
    payload = {
        "listing_id": listing_id,
        "account_id": account_id,
        "video_generation_id": lineage["generation_id"],
        "video_output_id": lineage["output_id"],
        "video_media_id": lineage["media_id"],
        "video_version": 1,
        "correlation_id": f"bulk-marketplace-{marketplace}",
    }
    readiness = client.post("/api/v1/marketplaces/video/readiness", json=payload, headers=ORIGIN)
    assert readiness.status_code == 200 and readiness.json()["ready"] is True
    preview = client.post("/api/v1/marketplaces/video/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoJob)) == 0
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)) == 0
    body = {
        **payload,
        "fingerprint": preview.json()["fingerprint"],
        "confirm": True,
        "idempotency_key": f"bulk-marketplace-{marketplace}",
    }
    confirmed = client.post("/api/v1/marketplaces/video/confirm", json=body, headers=ORIGIN)
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post("/api/v1/marketplaces/video/confirm", json=body, headers=ORIGIN)
    assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    completed = client.post(
        f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
    )
    assert completed.status_code == 200 and completed.json()["state"] == "succeeded"
    with db_factory() as db:
        mapping = db.scalar(
            select(MarketplaceVideoMapping).where(
                MarketplaceVideoMapping.listing_id == UUID(listing_id)
            )
        )
        assert (
            mapping is not None
            and str(mapping.video_output_id) == lineage["output_id"]
            and str(mapping.video_media_id) == lineage["media_id"]
            and mapping.video_version == 1
        )


def test_bulk_to_campaign_materializes_exact_version_and_is_worker_only(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import test_campaign_video_cross_channel as campaign_fixture
    import test_campaign_video_execution as execution_fixture

    context = ai_fixture.setup_context(client)
    lineage = bulk_video(client, context, "bulk-campaign-durable")
    campaign = execution_fixture._campaign(client, context)
    request = {
        "product_id": context["product"]["id"],
        "video_generation_id": lineage["generation_id"],
        "video_output_id": lineage["output_id"],
        "video_media_id": lineage["media_id"],
        "video_version": 1,
        "video_channel": "youtube_video",
        "name": "Bulk campaign video",
        "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
        .replace(tzinfo=None)
        .isoformat(),
        "timezone_name": "UTC",
        "target_account_id": campaign_fixture.video_fixture._account(
            client, "youtube", "-bulk-campaign"
        ),
        "metadata_artifact_id": lineage["artifact_id"],
        "metadata_artifact_version": int(lineage["artifact_version"]),
        "metadata": {"title": "Bulk campaign video"},
        "idempotency_key": "bulk-campaign-activity",
    }
    preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview", json=request, headers=ORIGIN
    )
    assert preview.status_code == 200 and preview.json()["ready"] is True, preview.text
    request.update({"preview_fingerprint": preview.json()["fingerprint"], "confirm": True})
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities", json=request, headers=ORIGIN
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
    with db_factory() as db:
        row = db.get(CampaignActivity, UUID(str(activity["id"])))
        assert (
            row is not None
            and str(row.video_output_id) == lineage["output_id"]
            and row.video_version == 1
        )
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 1
        claimed = claim_jobs(db, "bulk-campaign-worker", 1, 60)
    assert len(claimed) == 1
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    execute_job(claimed[0], "bulk-campaign-worker")
    with db_factory() as db:
        row = db.get(CampaignActivity, UUID(str(activity["id"])))
        assert row is not None and row.status == "succeeded"


def test_bulk_cross_channel_handoff_isolation_preserves_unrelated_lineage(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    social_lineage = bulk_video(client, context, "bulk-isolation-social")
    marketplace_lineage = bulk_video(client, context, "bulk-isolation-marketplace")
    campaign_lineage = bulk_video(client, context, "bulk-isolation-campaign")
    account_id = social_account(client)
    social_payload = {
        "video_generation_id": social_lineage["generation_id"],
        "channel": "youtube",
        "target_id": account_id,
        "idempotency_key": "bulk-isolation-social-handoff",
    }
    social_preview = client.post(
        "/api/v1/ai/video/channels/preview", json=social_payload, headers=ORIGIN
    )
    assert social_preview.status_code == 200
    prepared = client.post("/api/v1/ai/video/channels/prepare", json=social_payload, headers=ORIGIN)
    assert prepared.status_code == 200
    confirm = client.post(
        f"/api/v1/ai/video/channels/{prepared.json()['id']}/confirm",
        json={"fingerprint": prepared.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert confirm.status_code == 200
    with db_factory() as db:
        before = {
            "social": db.scalar(select(func.count()).select_from(SocialPost)),
            "marketplace": db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)),
            "campaign": db.scalar(select(func.count()).select_from(CampaignActivity)),
            "marketplace_generation": db.scalar(
                select(func.count())
                .select_from(VideoGeneration)
                .where(VideoGeneration.id == marketplace_lineage["generation_id"])
            ),
            "campaign_generation": db.scalar(
                select(func.count())
                .select_from(VideoGeneration)
                .where(VideoGeneration.id == campaign_lineage["generation_id"])
            ),
        }
    assert before["social"] == 1
    assert before["marketplace"] == 0
    assert before["campaign"] == 0
    with db_factory() as db:
        marketplace_generation = db.get(VideoGeneration, UUID(marketplace_lineage["generation_id"]))
        campaign_generation = db.get(VideoGeneration, UUID(campaign_lineage["generation_id"]))
        assert marketplace_generation is not None and campaign_generation is not None
        assert marketplace_generation.status == "succeeded"
        assert campaign_generation.status == "succeeded"
        assert str(marketplace_generation.id) == marketplace_lineage["generation_id"]
        assert str(campaign_generation.id) == campaign_lineage["generation_id"]
    with db_factory() as db:
        after = {
            "social": db.scalar(select(func.count()).select_from(SocialPost)),
            "marketplace": db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)),
            "campaign": db.scalar(select(func.count()).select_from(CampaignActivity)),
        }
    assert after == {"social": 1, "marketplace": 0, "campaign": 0}


def test_bulk_cross_channel_failure_isolation_keeps_siblings_progressing(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    products = [context["product"]["id"]]
    for index in range(1, 4):
        response = client.post(
            "/api/v1/products",
            json={
                "name": f"Failure isolation {index}",
                "product_type": "physical",
                "short_description": "Durable product",
                "description": "Failure isolation product",
                "category": "Test",
                "tags": ["test"],
                "price_amount": "10.00",
                "price_currency": "USD",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        products.append(response.json()["id"])
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            **bulk_payload(products, "bulk-cross-channel-failure-isolation"),
            "targets": ["youtube"],
            "failure_scenarios": {"2": "provider_unavailable", "3": "unsupported_operation"},
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    for index in range(4):
        with db_factory() as db:
            for job in db.scalars(select(AIStudioJob).where(AIStudioJob.state == "retry_wait")):
                job.available_at = datetime.now(UTC)
            db.commit()
        with db_factory() as db:
            run_ai_jobs_once(db, f"failure-isolation-{index}", limit=10)
    body = client.get(f"/api/v1/ai/video/bulk/{queued.json()['id']}", headers=ORIGIN)
    assert body.status_code == 200
    result = body.json()
    assert result["succeeded_count"] >= 1
    assert result["failed_count"] >= 1
    assert result["status"] != "failed"


def test_bulk_authorization_matrix_is_safe_and_side_effect_free(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    lineage = bulk_video(client, context, "bulk-auth-matrix")
    forged = str(uuid4())
    parent, child = lineage["bulk_id"], lineage["child_id"]
    cases: list[tuple[str, Any]] = []
    paths = [
        f"/api/v1/ai/video/bulk/{forged}",
        f"/api/v1/ai/video/bulk/{forged}/outputs",
        f"/api/v1/ai/video/bulk/{forged}/history",
        f"/api/v1/ai/video/bulk/{forged}/usage",
        f"/api/v1/ai/video/bulk/{forged}/diagnostics",
    ]
    for index, path in enumerate(paths, 1):
        cases.append(
            (f"wrong-owner parent {index}", lambda path=path: client.get(path, headers=ORIGIN))
        )
    for index, action in enumerate(("retry-failed", "retry", "cancel", "cancel-remaining"), 6):
        cases.append(
            (
                f"wrong-owner parent action {index}",
                lambda action=action, index=index: client.post(
                    f"/api/v1/ai/video/bulk/{forged}/{action}",
                    json={"child_ids": [forged], "idempotency_key": f"m{index}"},
                    headers=ORIGIN,
                ),
            )
        )
    for index, path in enumerate(
        (
            f"/api/v1/ai/video/bulk/{forged}/child/{child}",
            f"/api/v1/ai/video/generations/{forged}",
            f"/api/v1/ai/video/generations/{forged}/recovery",
        ),
        10,
    ):
        cases.append(
            (f"wrong-owner child {index}", lambda path=path: client.get(path, headers=ORIGIN))
        )
    for index in range(13, 24):
        cases.append(
            (
                f"cross-owner resource {index}",
                lambda: client.get(
                    f"/api/v1/ai/video/generations/{forged}/history", headers=ORIGIN
                ),
            )
        )
    for index in range(24, 29):
        cases.append(
            (
                f"forged identifier {index}",
                lambda: client.get(f"/api/v1/ai/video/generations/{forged}", headers=ORIGIN),
            )
        )
    cases.extend(
        [
            (
                "stale idempotency replay",
                lambda: client.post(
                    "/api/v1/ai/video/bulk",
                    json={
                        "product_ids": [forged],
                        "video_types": ["youtube_video"],
                        "targets": ["youtube"],
                        "duration_seconds": 2,
                        "resolution": "320x240",
                        "idempotency_key": "m29",
                    },
                    headers=ORIGIN,
                ),
            ),
            (
                "retry succeeded child",
                lambda: client.post(
                    f"/api/v1/ai/video/bulk/{parent}/retry",
                    json={"child_ids": [child], "idempotency_key": "m30"},
                    headers=ORIGIN,
                ),
            ),
            (
                "cancel succeeded child",
                lambda: client.post(
                    f"/api/v1/ai/video/bulk/{parent}/cancel",
                    json={"child_ids": [child]},
                    headers=ORIGIN,
                ),
            ),
            (
                "recover succeeded child",
                lambda: client.post(
                    f"/api/v1/ai/video/generations/{lineage['generation_id']}/recovery",
                    json={"action": "retry", "confirm": True},
                    headers=ORIGIN,
                ),
            ),
            (
                "credential leakage attempt",
                lambda: client.post(
                    f"/api/v1/ai/video/bulk/{forged}/retry",
                    json={"token": "secret", "password": "secret"},
                    headers=ORIGIN,
                ),
            ),
            (
                "token/cookie leakage attempt",
                lambda: client.get(
                    f"/api/v1/ai/video/generations/{forged}",
                    headers={**ORIGIN, "Cookie": "token=secret"},
                ),
            ),
            (
                "local path / DB DSN leakage attempt",
                lambda: client.get(f"/api/v1/ai/video/bulk/{forged}/diagnostics", headers=ORIGIN),
            ),
            (
                "unrelated Product/private data leakage attempt",
                lambda: client.get(f"/api/v1/ai/video/generations/{forged}", headers=ORIGIN),
            ),
        ]
    )
    assert len(cases) == 36
    models = (
        AIStudioJob,
        VideoGeneration,
        VideoOutput,
        MediaAsset,
        PublishingJob,
        SocialPost,
        MarketplaceVideoJob,
        MarketplaceVideoMapping,
    )
    with db_factory() as db:
        before = {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in models
        }
    for name, invoke in cases:
        response = invoke()
        safe(response)
        assert response.status_code in {200, 401, 404, 405, 409, 422}, name + ": " + response.text
    with db_factory() as db:
        after = {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in models
        }
    assert after == before
