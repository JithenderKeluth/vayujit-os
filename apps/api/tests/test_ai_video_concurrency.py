from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent
from vayujit_api.media.models import MediaAsset
from vayujit_api.video.models import VideoApproval, VideoGeneration, VideoOutput

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def queue(client, context, key: str, **overrides):
    payload = {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "resolution": "320x240",
        "duration_seconds": 2,
        "idempotency_key": key,
        "failure_scenario": "success",
    }
    payload.update(overrides)
    return client.post("/api/v1/ai/video/queue", json=payload, headers=ORIGIN)


def _counts(db, generation_id):
    output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation_id))
    return {
        "jobs": db.scalar(
            select(func.count())
            .select_from(AIStudioJob)
            .where(
                AIStudioJob.correlation_id
                == db.scalar(
                    select(VideoGeneration.correlation_id).where(
                        VideoGeneration.id == generation_id
                    )
                )
            )
        ),
        "outputs": db.scalar(
            select(func.count())
            .select_from(VideoOutput)
            .where(VideoOutput.generation_id == generation_id)
        ),
        "media": (
            db.scalar(
                select(func.count()).select_from(MediaAsset).where(MediaAsset.id == output.media_id)
            )
            if output and output.media_id
            else 0
        ),
        "files": 1 if output and output.media_id else 0,
        "audit": db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "ai.video_generation_completed",
                AuditEvent.entity_id == generation_id,
            )
        ),
    }


def test_recovery_sequential_idempotency_and_counts(client):
    context = setup_context(client)
    queued = queue(
        client, context, "video-recovery-sequential", failure_scenario="provider_unavailable"
    )
    generation_id = queued.json()["id"]
    with db_session() as db:
        run_ai_jobs_once(db, "recovery-sequential-initial", limit=1)
    preview = client.get(
        f"/api/v1/ai/video/generations/{generation_id}/recovery", headers=ORIGIN
    ).json()
    payload = {
        "action": "retry_generation",
        "expected_failure_code": preview["failure_code"],
        "expected_status": "retry_wait",
        "idempotency_key": "recovery-sequential",
    }
    first = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/recovery", json=payload, headers=ORIGIN
    )
    second = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/recovery", json=payload, headers=ORIGIN
    )
    assert first.status_code == second.status_code == 200
    with db_session() as db:
        row = db.get(VideoGeneration, generation_id)
        assert row is not None
        job_count_before = db.scalar(
            select(func.count())
            .select_from(AIStudioJob)
            .where(AIStudioJob.correlation_id == row.correlation_id)
        )
        assert job_count_before == 1
        job = db.scalar(select(AIStudioJob).where(AIStudioJob.correlation_id == row.correlation_id))
        assert job is not None
        job.payload_json = {**job.payload_json, "failure_scenario": "success"}
        db.commit()
        run_ai_jobs_once(db, "recovery-sequential-final", limit=1)
        counts = _counts(db, generation_id)
        assert counts == {"jobs": 1, "outputs": 1, "media": 1, "files": 1, "audit": 1}


def test_recovery_concurrent_idempotency_and_invariants(client):
    context = setup_context(client)
    queued = queue(
        client, context, "video-recovery-concurrent", failure_scenario="provider_unavailable"
    )
    generation_id = queued.json()["id"]
    with db_session() as db:
        run_ai_jobs_once(db, "recovery-concurrent-initial", limit=1)
    preview = client.get(
        f"/api/v1/ai/video/generations/{generation_id}/recovery", headers=ORIGIN
    ).json()
    payload = {
        "action": "retry_generation",
        "expected_failure_code": preview["failure_code"],
        "expected_status": "retry_wait",
        "idempotency_key": "recovery-concurrent",
    }

    def call():
        return client.post(
            f"/api/v1/ai/video/generations/{generation_id}/recovery", json=payload, headers=ORIGIN
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: call(), range(2)))
    assert all(response.status_code in {200, 409} for response in responses)
    with db_session() as db:
        row = db.get(VideoGeneration, generation_id)
        assert row is not None
        job = db.scalar(select(AIStudioJob).where(AIStudioJob.correlation_id == row.correlation_id))
        assert job is not None
        job.payload_json = {**job.payload_json, "failure_scenario": "success"}
        db.commit()
        run_ai_jobs_once(db, "recovery-concurrent-final", limit=1)
        assert _counts(db, generation_id) == {
            "jobs": 1,
            "outputs": 1,
            "media": 1,
            "files": 1,
            "audit": 1,
        }


def _approval_race(client, context, key, action_a, action_b):
    queued = queue(client, context, key)
    generation_id = queued.json()["id"]
    with db_session() as db:
        run_ai_jobs_once(db, f"approval-{key}", limit=1)

    def call(action):
        return client.post(
            f"/api/v1/ai/video/generations/{generation_id}/{action}",
            json={"feedback": "safe"},
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(call, (action_a, action_b)))
    with db_session() as db:
        generation = db.get(VideoGeneration, generation_id)
        approval = db.scalar(
            select(VideoApproval).where(VideoApproval.generation_id == generation_id)
        )
        assert generation is not None and approval is not None
        audit_action = (
            "ai.video_approved"
            if generation_output_status(db, generation_id) == "approved"
            else "ai.video_rejected"
        )
        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == audit_action, AuditEvent.entity_id == generation_id)
        )
        assert audit_count == 1
        assert approval.state in {"approved", "rejected"}
    assert all(result.status_code in {200, 409} for result in results)
    return generation_id, approval.state


def generation_output_status(db, generation_id):
    return db.scalar(select(VideoOutput.status).where(VideoOutput.generation_id == generation_id))


def test_approve_approve_concurrency(client):
    context = setup_context(client)
    generation_id, state = _approval_race(
        client, context, "approval-approve-approve", "approve", "approve"
    )
    assert state == "approved"
    with db_session() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoApproval)
                .where(VideoApproval.generation_id == generation_id)
            )
            == 1
        )


def test_approve_reject_race(client):
    context = setup_context(client)
    _, state = _approval_race(client, context, "approval-approve-reject", "approve", "reject")
    assert state in {"approved", "rejected"}


def test_reject_reject_concurrency_and_sequential_idempotency(client):
    context = setup_context(client)
    generation_id, state = _approval_race(
        client, context, "approval-reject-reject", "reject", "reject"
    )
    assert state == "rejected"
    repeated = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/reject",
        json={"feedback": "same"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 200
    with db_session() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.action == "ai.video_rejected", AuditEvent.entity_id == generation_id
                )
            )
            == 1
        )


def test_stale_recovery_confirmation_is_rejected(client):
    context = setup_context(client)
    queued = queue(
        client, context, "recovery-stale-confirmation", failure_scenario="provider_unavailable"
    )
    generation_id = queued.json()["id"]
    with db_session() as db:
        run_ai_jobs_once(db, "recovery-stale-initial", limit=1)
    preview = client.get(
        f"/api/v1/ai/video/generations/{generation_id}/recovery", headers=ORIGIN
    ).json()
    with db_session() as db:
        row = db.get(VideoGeneration, generation_id)
        assert row is not None
        row.status = "failed"
        row.failure_code = "ai.video.invalid_output"
        db.commit()
    response = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/recovery",
        json={
            "action": "retry_generation",
            "expected_failure_code": preview["failure_code"],
            "expected_status": "retry_wait",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 409
    with db_session() as db:
        row = db.get(VideoGeneration, generation_id)
        assert row is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoOutput)
                .where(VideoOutput.generation_id == generation_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(MediaAsset)
                .join(VideoOutput, MediaAsset.id == VideoOutput.media_id)
                .where(VideoOutput.generation_id == generation_id)
            )
            == 0
        )
