"""WP7A-2 canonical offline workflow/concurrency regressions on signed PostgreSQL."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select
from test_pr_sos_04_inventory_orders import _factory
from test_seller_wp7a import local as local
from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.models import AdJob, AdRecoveryRecord
from vayujit_api.ads.service import run_job
from vayujit_api.ai import studio_worker
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.audit.models import AuditEvent
from vayujit_api.video.models import VideoGeneration, VideoStoryboard
from vayujit_api.video.provider import video_provider
from vayujit_api.video.worker import execute_video_job

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def board_setup(local):
    c, post, brand, product, _ = local
    board = post(
        "ai/video/storyboards",
        {
            "brand_id": brand["id"],
            "product_id": product["id"],
            "scenes": [
                {
                    "stable_key": "one",
                    "scene_order": 1,
                    "duration_seconds": 2,
                    "scene_text": "[QA SYNTHETIC] original",
                }
            ],
        },
    )
    approved = post(
        "ai/video/storyboards/" + board["id"] + "/approve",
        {"expected_row_version": board["row_version"]},
    )
    body = {
        "expected_row_version": approved["row_version"],
        "scenes": [{**approved["scenes"][0], "scene_text": "[QA SYNTHETIC] cloned"}],
    }
    return c, post, approved, body


def test_approved_storyboard_duplicate_edit_clones_once_and_preserves_approval(local):
    c, post, original, body = board_setup(local)
    path = "ai/video/storyboards/" + original["id"]
    first = c.put("/api/v1/" + path, json=body, headers=ORIGIN).json()
    repeat = c.put("/api/v1/" + path, json=body, headers=ORIGIN).json()
    assert first["id"] == repeat["id"] and first["version"] == original["version"] + 1
    assert first["state"] == "draft" and c.get("/api/v1/" + path).json() == original
    with _factory()() as db:
        row = db.get(VideoStoryboard, uuid.UUID(first["id"]))
        assert row.approved_by is None and row.approved_at is None
        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == row.id, AuditEvent.action == "ai.video_storyboard_updated"
            )
        )
        assert event.metadata_json["source_storyboard_id"] == original["id"]
        assert event.metadata_json["approval_inherited"] is False


def test_concurrent_storyboard_clones_share_identity_and_draft_cannot_execute(local):
    c, post, original, body = board_setup(local)
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda _: c.put(
                    "/api/v1/ai/video/storyboards/" + original["id"], json=body, headers=ORIGIN
                ),
                range(2),
            )
        )
    assert all(r.status_code == 200 for r in results)
    clone = results[0].json()
    assert results[1].json()["id"] == clone["id"]
    assert (
        c.post(
            "/api/v1/ai/video/preview",
            json={
                "product_id": clone["product_id"],
                "brand_id": clone["brand_id"],
                "storyboard_id": clone["id"],
                "storyboard_version": clone["version"],
            },
            headers=ORIGIN,
        ).status_code
        == 409
    )


def video_failure(local):
    c, post, brand, product, _ = local
    generation = post(
        "ai/video/queue",
        {"brand_id": brand["id"], "product_id": product["id"], "idempotency_key": "wp7a2-video"},
    )
    with _factory()() as db:
        row = db.get(VideoGeneration, uuid.UUID(generation["id"]))
        job = db.scalar(select(AIStudioJob).where(AIStudioJob.correlation_id == row.correlation_id))
        for _ in range(3):
            with (
                patch.object(
                    studio_worker, "utcnow", return_value=max(datetime.now(UTC), job.available_at)
                ),
                patch.object(
                    video_provider,
                    "generate",
                    side_effect=RuntimeError("QA controlled provider failure"),
                ),
            ):
                assert studio_worker.claim_ai_jobs(db, "wp7a2-test", 1, 120) == [job.id]
                execute_video_job(db, job.id, "wp7a2-test")
            db.expire_all()
            if job.state == "failed":
                break
        assert job.state == "failed" and row.status == "failed"
        return c, row.id, job.id, job.attempt_count


def test_video_retry_clears_current_errors_and_keeps_history(local):
    c, identity, job_id, attempts = video_failure(local)
    response = c.post(
        f"/api/v1/ai/video/generations/{identity}/recovery",
        json={
            "action": "retry_generation",
            "expected_status": "failed",
            "expected_failure_code": "ai.video.provider_unavailable",
            "idempotency_key": "video-retry:test",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200 and response.json()["status"] == "queued"
    with _factory()() as db:
        job = db.get(AIStudioJob, job_id)
        assert job.attempt_count == attempts and job.state == "queued"
        assert job.last_error_code is None and job.safe_error_message is None
        assert job.next_retry_at is None and job.lease_owner is None and job.completed_at is None


def test_video_retry_concurrent_replay_is_one_audited_intent_and_stale_key_rejected(local):
    c, identity, job_id, _ = video_failure(local)
    body = {
        "action": "retry_generation",
        "expected_status": "failed",
        "expected_failure_code": "ai.video.provider_unavailable",
        "idempotency_key": "video-retry:test",
    }
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(
                lambda _: c.post(
                    f"/api/v1/ai/video/generations/{identity}/recovery", json=body, headers=ORIGIN
                ),
                range(2),
            )
        )
    assert all(r.status_code == 200 for r in responses)
    assert (
        c.post(
            f"/api/v1/ai/video/generations/{identity}/recovery",
            json={**body, "idempotency_key": "video-retry:stale"},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    with _factory()() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == identity, AuditEvent.action == "ai.video_recovery_requested"
            )
        ).all()
        assert len(events) == 1


def ads_failure(local):
    c, post, brand, product, _ = local
    account = post(
        "ads/accounts",
        {
            "provider": "meta",
            "environment": "local",
            "display_name": "[QA SYNTHETIC] WP7A2 local",
            "external_account_id": "qa-wp7a2-unit",
            "credentials": {"token": "QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL"},
        },
    )
    post("ads/accounts/" + account["id"] + "/validate", {})
    post("ads/accounts/" + account["id"] + "/enable", {})
    body = {
        "provider": "meta",
        "account_id": account["id"],
        "brand_id": brand["id"],
        "product_id": product["id"],
        "name": "[QA SYNTHETIC] WP7A2 campaign",
        "budget": {"currency": "INR", "daily_amount": "25.55"},
        "idempotency_key": "wp7a2-campaign",
    }
    preview = post("ads/campaigns/preview", body)
    prepared = post(
        "ads/campaigns/confirm",
        {
            "campaign": body,
            "preview_fingerprint": preview["fingerprint"],
            "confirm": True,
            "idempotency_key": "wp7a2-campaign-job",
        },
    )
    connector = connector_for("meta")
    with _factory()() as db:
        job = db.get(AdJob, uuid.UUID(prepared["job"]["id"]))
        connector.state.failures["create_campaign"] = "unavailable"
        try:
            run_job(db, job)
        finally:
            connector.state.failures.clear()
        assert job.status == "retry_wait"
    recovery = {
        "action": "retry",
        "entity_type": "campaign",
        "entity_id": prepared["campaign"]["id"],
        "failure_code": "ads.connector_unavailable",
        "confirm": True,
        "idempotency_key": "ads-recovery-retry-test",
    }
    return c, post, prepared["campaign"], recovery


def test_ads_recovery_replay_binds_exact_intent_and_rejects_different_target(local):
    c, post, campaign, body = ads_failure(local)
    first = post("ads/recovery", body)
    assert post("ads/recovery", body)["job_id"] == first["job_id"]
    conflict = c.post(
        "/api/v1/ads/recovery", json={**body, "entity_id": str(uuid.uuid4())}, headers=ORIGIN
    )
    assert conflict.status_code == 409


def test_ads_stale_recovery_cannot_queue_a_second_intent_without_another_failure(local):
    c, post, _, body = ads_failure(local)
    post("ads/recovery", body)
    assert (
        c.post(
            "/api/v1/ads/recovery",
            json={**body, "idempotency_key": "ads-recovery-retry-stale"},
            headers=ORIGIN,
        ).status_code
        == 409
    )


def test_ads_concurrent_retry_is_one_persisted_job_and_record(local):
    c, _, campaign, body = ads_failure(local)
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(lambda _: c.post("/api/v1/ads/recovery", json=body, headers=ORIGIN), range(2))
        )
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json()["job_id"] == responses[1].json()["job_id"]
    with _factory()() as db:
        rows = db.scalars(
            select(AdRecoveryRecord).where(AdRecoveryRecord.entity_id == uuid.UUID(campaign["id"]))
        ).all()
        assert len(rows) == 1


def test_changed_research_goal_never_reuses_old_category_or_approvals(local):
    c, post, *_ = local
    results = []
    for category in ("Home & Kitchen", "Travel Accessories"):
        goal = post(
            "intelligence/business-agent/goals",
            {
                "raw_goal": (
                    f"[QA SYNTHETIC] Find products in {category} category for Amazon India."
                ),
                "idempotency_key": "wp7a2-" + category,
            },
        )
        post(f"intelligence/business-agent/goals/{goal['id']}/plan", {})
        run = post(
            f"intelligence/business-agent/goals/{goal['id']}/runs",
            {"idempotency_key": "wp7a2-" + category, "max_steps": 20},
        )
        result = post(f"intelligence/business-agent/runs/{run['id']}/start", {})
        assert result["candidates"] and all(r["category"] == category for r in result["candidates"])
        results.append((goal, result))
    current = c.get(
        "/api/v1/intelligence/product-opportunities/research-results",
        params={"goal_id": results[1][0]["id"]},
    ).json()
    assert results[0][1]["id"] not in current["active_run_ids"]
    old_ids = {c["id"] for c in results[0][1]["candidates"]}
    assert not old_ids.intersection(c["id"] for c in results[1][1]["candidates"])
