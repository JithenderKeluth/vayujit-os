from __future__ import annotations

from datetime import timedelta

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt
from vayujit_api.ai.studio_worker import (
    AIWorkerCrash,
    claim_ai_jobs,
    execute_ai_job,
    recover_expired_ai_jobs,
)
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.video.bulk_models import VideoBulkChild
from vayujit_api.video.models import VideoGeneration, VideoOutput
from vayujit_api.video.provider import video_provider

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_bulk_worker_terminal_state_set_is_explicit():
    from vayujit_api.video.bulk import TERMINAL_CHILD_STATES

    assert {"succeeded", "failed", "stale", "cancelled"} == TERMINAL_CHILD_STATES


def test_bulk_crash_after_checkpoint_recovers_one_output_and_media(client):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "idempotency_key": "bulk-crash-after-checkpoint",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]

    with test_ai_integration.factory() as db:
        claimed = claim_ai_jobs(db, "bulk-crash-a", 1, 1)
        assert claimed
        with pytest.raises(AIWorkerCrash):
            execute_ai_job(db, claimed[0], "bulk-crash-a", crash_after_checkpoint=True)
        job = db.get(AIStudioJob, claimed[0])
        assert job is not None
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_ai_jobs(db) == 1
        assert claim_ai_jobs(db, "bulk-crash-b", 1, 120)
        execute_ai_job(db, claimed[0], "bulk-crash-b")
        child = db.scalar(select(VideoBulkChild).where(VideoBulkChild.bulk_id == bulk_id))
        assert child is not None
        assert child.generation_id is not None
        generation = db.get(VideoGeneration, child.generation_id)
        assert generation is not None and generation.status == "succeeded"
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation.id))
        assert output is not None and output.media_id is not None
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 1
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 1
        assert db.scalar(select(func.count()).select_from(AIStudioJobAttempt)) == 2

    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    assert status.json()["succeeded_count"] == 1


def test_bulk_crash_before_provider_recovers_without_duplicate_output(client):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "failure_scenario": "crash_before",
            "idempotency_key": "bulk-crash-before",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    with test_ai_integration.factory() as db:
        claimed = claim_ai_jobs(db, "bulk-crash-before-a", 1, 1)
        assert claimed
        with pytest.raises(AIWorkerCrash):
            execute_ai_job(db, claimed[0], "bulk-crash-before-a")
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 1
        job = db.get(AIStudioJob, claimed[0])
        assert job is not None
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_ai_jobs(db) == 1
        claimed_again = claim_ai_jobs(db, "bulk-crash-before-b", 1, 120)
        assert claimed_again == claimed
        job = db.get(AIStudioJob, claimed[0])
        assert job is not None
        job.payload_json = {**job.payload_json, "failure_scenario": "success"}
        db.commit()
        assert execute_ai_job(db, claimed[0], "bulk-crash-before-b") == "succeeded"
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 1
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 1
    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    assert status.json()["succeeded_count"] == 1


def test_bulk_invalid_checkpoint_is_safe_and_does_not_create_media(client):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "idempotency_key": "bulk-invalid-checkpoint",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    with test_ai_integration.factory() as db:
        claimed = claim_ai_jobs(db, "bulk-invalid-checkpoint-a", 1, 1)
        assert claimed
        with pytest.raises(AIWorkerCrash):
            execute_ai_job(db, claimed[0], "bulk-invalid-checkpoint-a", crash_after_checkpoint=True)
        generation = db.scalar(select(VideoGeneration))
        assert generation is not None and generation.checkpoint_json
        generation.checkpoint_json = {
            **generation.checkpoint_json,
            "path": "video-checkpoints/missing-checkpoint.mp4",
        }
        job = db.get(AIStudioJob, claimed[0])
        assert job is not None
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_ai_jobs(db) == 1
        assert claim_ai_jobs(db, "bulk-invalid-checkpoint-b", 1, 120) == claimed
        assert execute_ai_job(db, claimed[0], "bulk-invalid-checkpoint-b") == "retry_wait"
        refreshed = db.get(VideoGeneration, generation.id)
        assert refreshed is not None
        assert refreshed.failure_code == "ai.video.checkpoint_invalid"
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 1
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 0
    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    assert status.json()["failed_count"] == 0


def test_bulk_stale_context_fingerprint_stops_before_provider(client):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "idempotency_key": "bulk-stale-context",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    with test_ai_integration.factory() as db:
        child = db.scalar(select(VideoBulkChild))
        assert child is not None and child.generation_id is not None
        generation = db.get(VideoGeneration, child.generation_id)
        assert generation is not None
        generation.context_fingerprint = "stale-context-fingerprint"
        db.commit()
        claimed = claim_ai_jobs(db, "bulk-stale-context-worker", 1, 120)
        assert claimed
        assert execute_ai_job(db, claimed[0], "bulk-stale-context-worker") == "stale"
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 0
    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    assert status.json()["stale_count"] == 1


def test_bulk_stale_product_stops_only_changed_sibling(client, monkeypatch):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    second = client.post(
        "/api/v1/products",
        json={
            "name": "Bulk Stale Product B",
            "product_type": "physical",
            "short_description": "A second product",
            "description": "An unchanged sibling product.",
            "category": "Outdoors",
            "tags": ["sibling"],
            "price_amount": "29.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    )
    assert second.status_code == 201, second.text
    product_ids = [context["product"]["id"], second.json()["id"]]
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": product_ids,
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "idempotency_key": "bulk-stale-product-sibling",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    changed = client.patch(
        f"/api/v1/products/{product_ids[0]}",
        json={"description": "Product context changed before execution."},
        headers=ORIGIN,
    )
    assert changed.status_code == 200, changed.text
    calls: list[str] = []
    original_generate = video_provider.generate

    def counted_generate(**kwargs):
        calls.append(str(kwargs.get("seed")))
        return original_generate(**kwargs)

    monkeypatch.setattr(video_provider, "generate", counted_generate)
    with test_ai_integration.factory() as db:
        claimed = claim_ai_jobs(db, "bulk-stale-product-worker", 2, 120)
        assert len(claimed) == 2
        results = [execute_ai_job(db, job_id, "bulk-stale-product-worker") for job_id in claimed]
        assert sorted(results) == ["stale", "succeeded"]
        children = list(db.scalars(select(VideoBulkChild).where(VideoBulkChild.bulk_id == bulk_id)))
        assert len(children) == 2
        generations = [db.get(VideoGeneration, child.generation_id) for child in children]
        assert all(generation is not None for generation in generations)
        assert sorted(
            generation.status for generation in generations if generation is not None
        ) == ["stale", "succeeded"]
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoOutput)
                .where(VideoOutput.media_id.is_not(None))
            )
            == 1
        )
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 1
    assert len(calls) == 1
    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["stale_count"] == 1 and body["succeeded_count"] == 1


def test_bulk_stale_worker_cannot_resume_cancelled_child(client):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "video_types": ["youtube_video"],
            "targets": ["youtube"],
            "duration_seconds": 2,
            "resolution": "320x240",
            "idempotency_key": "bulk-stale-worker-cancelled",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    with test_ai_integration.factory() as db:
        claimed = claim_ai_jobs(db, "bulk-stale-cancel-worker", 1, 120)
        assert claimed
        child = db.scalar(select(VideoBulkChild).where(VideoBulkChild.bulk_id == bulk_id))
        assert child is not None
        cancelled = client.post(
            f"/api/v1/ai/video/bulk/{bulk_id}/cancel",
            json={"child_ids": [str(child.id)]},
            headers=ORIGIN,
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["cancelled_count"] == 1
        db.expire_all()
        assert execute_ai_job(db, claimed[0], "bulk-stale-cancel-worker") == "cancelled"
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 0
        refreshed = db.get(VideoBulkChild, child.id)
        assert refreshed is not None and refreshed.status == "cancelled"
