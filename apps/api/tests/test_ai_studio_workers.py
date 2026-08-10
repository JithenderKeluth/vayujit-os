from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import AIStudioJob, AIStudioOutput, BrandVoice
from vayujit_api.ai.studio_worker import (
    LEGAL_TRANSITIONS,
    AIWorkerCrash,
    claim_ai_jobs,
    execute_ai_job,
    recover_expired_ai_jobs,
    run_ai_jobs_once,
    transition_state,
)
from vayujit_api.audit.models import AuditEvent
from vayujit_api.publishing.scheduler_time import utcnow

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def queue_payload(product_id: str, key: str, *, voice_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "product_ids": [product_id],
        "channels": ["amazon"],
        "content_types": ["product_title"],
        "idempotency_key": key,
    }
    if voice_id:
        payload["brand_voice_id"] = voice_id
    return payload


def test_ai_state_machine_allows_only_authorized_transitions() -> None:
    assert transition_state("queued", "generating") == "generating"
    assert transition_state("generating", "validating") == "validating"
    assert transition_state("validating", "needs_review") == "needs_review"
    assert transition_state("generating", "retry_wait") == "retry_wait"
    assert transition_state("retry_wait", "generating") == "generating"
    assert transition_state("failed", "retry_wait") == "retry_wait"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("succeeded", "generating"),
        ("succeeded", "queued"),
        ("cancelled", "succeeded"),
        ("cancelled", "generating"),
        ("stale", "succeeded"),
        ("failed", "succeeded"),
        ("needs_review", "generating"),
    ],
)
def test_ai_state_machine_rejects_illegal_transitions(current: str, target: str) -> None:
    with pytest.raises(ValueError, match="Illegal AI Studio job transition"):
        transition_state(current, target)


def test_ai_state_machine_declares_terminal_states() -> None:
    assert LEGAL_TRANSITIONS["succeeded"] == set()
    assert LEGAL_TRANSITIONS["cancelled"] == set()
    assert LEGAL_TRANSITIONS["stale"] == set()


def test_normal_durable_generation_and_api_contract(client: Any) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json=queue_payload(context["product"]["id"], "worker-normal"),
        headers=ORIGIN,
    )
    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["outputs"][0]["artifact_id"] is None
    with db_session() as db:
        assert run_ai_jobs_once(db, "normal-worker", limit=4) == 1
    completed = client.get(f"/api/v1/ai/studio/generations/{queued['id']}", headers=ORIGIN)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
        actions = list(db.scalars(select(AuditEvent.action)))
        assert actions.count("ai.content_queued") == 1
        assert actions.count("ai.content_started") == 1
        assert actions.count("ai.content_generated") == 1


def test_duplicate_request_reuses_job_and_artifact(client: Any) -> None:
    context = setup_context(client)
    payload = queue_payload(context["product"]["id"], "worker-duplicate")
    first = client.post("/api/v1/ai/studio/generate", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/ai/studio/generate", json=payload, headers=ORIGIN)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    with db_session() as db:
        run_ai_jobs_once(db, "duplicate-worker", limit=4)
        assert db.scalar(select(func.count()).select_from(AIStudioJob)) == 1
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
    with db_session() as db:
        run_ai_jobs_once(db, "duplicate-worker-2", limit=4)
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1


def test_crash_before_provider_recovers_with_one_call(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json=queue_payload(context["product"]["id"], "worker-crash-before"),
        headers=ORIGIN,
    )
    job_id = response.json()["outputs"][0]["id"]
    with db_session() as db:
        job = db.get(AIStudioOutput, job_id)
        assert job is not None
        claimed = claim_ai_jobs(db, "crash-before-a", 1, 1)
        assert claimed
        row = db.get(AIStudioJob, claimed[0])
        assert row is not None
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    calls = 0
    original = __import__(
        "vayujit_api.ai.studio_worker", fromlist=["_provider_call"]
    )._provider_call

    def counted(*args: Any, **kwargs: Any):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("vayujit_api.ai.studio_worker._provider_call", counted)
    with db_session() as db:
        assert recover_expired_ai_jobs(db) == 1
        run_ai_jobs_once(db, "crash-before-b", limit=1)
        assert calls == 1
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ai.content_generated")
            )
            == 1
        )
        row = db.scalar(select(AIStudioJob))
        assert row is not None
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    with db_session() as db:
        assert execute_ai_job(db, row.id, "crash-before-a") == "lease_lost"


def test_crash_after_provider_checkpoint_resumes_without_second_call(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json=queue_payload(context["product"]["id"], "worker-crash-after"),
        headers=ORIGIN,
    )
    output_id = response.json()["outputs"][0]["id"]
    with db_session() as db:
        output = db.get(AIStudioOutput, output_id)
        assert output is not None
        job = db.scalar(
            select(AIStudioJob).where(AIStudioJob.idempotency_key.like("worker-crash-after:%"))
        )
        assert job is not None
        assert claim_ai_jobs(db, "crash-after-a", 1, 30) == [job.id]
    calls = 0
    original = __import__(
        "vayujit_api.ai.studio_worker", fromlist=["_provider_call"]
    )._provider_call

    def counted(*args: Any, **kwargs: Any):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("vayujit_api.ai.studio_worker._provider_call", counted)
    with db_session() as db:
        with pytest.raises(AIWorkerCrash):
            execute_ai_job(db, job.id, "crash-after-a", crash_after_checkpoint=True)
        checkpointed = db.get(AIStudioJob, job.id)
        assert checkpointed is not None and checkpointed.provider_result_json is not None
        checkpointed.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    with db_session() as db:
        assert recover_expired_ai_jobs(db) == 1
        run_ai_jobs_once(db, "crash-after-b", limit=1)
        assert calls == 1
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIStudioOutput)
                .where(AIStudioOutput.artifact_id.is_not(None))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ai.content_generated")
            )
            == 1
        )


def test_stale_product_never_invokes_provider(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json=queue_payload(context["product"]["id"], "worker-stale-product"),
        headers=ORIGIN,
    )
    with db_session() as db:
        from vayujit_api.products.models import Product

        product = db.get(Product, context["product"]["id"])
        assert product is not None
        product.description = "Changed after enqueue"
        db.commit()
        monkeypatch.setattr(
            "vayujit_api.ai.studio_worker._provider_call",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider called")),
        )
        run_ai_jobs_once(db, "stale-product-worker", limit=1)
        job = db.scalar(
            select(AIStudioJob).where(AIStudioJob.generation_id == response.json()["id"])
        )
        assert job is not None and job.state == "stale"
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 0


def test_stale_brand_voice_never_uses_new_version(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_context(client)
    voice = client.post(
        "/api/v1/ai/studio/brand-voices",
        json={"name": "Queued voice", "brand_id": context["brand"]["id"]},
        headers=ORIGIN,
    ).json()
    response = client.post(
        "/api/v1/ai/studio/generate",
        json=queue_payload(context["product"]["id"], "worker-stale-voice", voice_id=voice["id"]),
        headers=ORIGIN,
    )
    with db_session() as db:
        row = db.get(BrandVoice, voice["id"])
        assert row is not None
        row.version = 4
        db.commit()
        monkeypatch.setattr(
            "vayujit_api.ai.studio_worker._provider_call",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider called")),
        )
        run_ai_jobs_once(db, "stale-voice-worker", limit=1)
        job = db.scalar(
            select(AIStudioJob).where(AIStudioJob.generation_id == response.json()["id"])
        )
        assert job is not None and job.state == "stale"
        assert job.brand_voice_version == 1
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 0


def test_queued_cancellation_prevents_provider_execution(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json=queue_payload(context["product"]["id"], "worker-cancel"),
        headers=ORIGIN,
    )
    job_id = response.json()["outputs"][0]["job_id"]
    jobs = client.get("/api/v1/ai/studio/jobs", headers=ORIGIN).json()
    durable_job = next(item for item in jobs if item["id"] == job_id)
    cancelled = client.post(f"/api/v1/ai/studio/jobs/{durable_job['id']}/cancel", headers=ORIGIN)
    assert cancelled.status_code == 200 and cancelled.json()["cancelled"] is True
    monkeypatch.setattr(
        "vayujit_api.ai.studio_worker._provider_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider called")),
    )
    with db_session() as db:
        assert run_ai_jobs_once(db, "cancel-worker", limit=1) == 0
        job = db.get(AIStudioJob, durable_job["id"])
        assert job is not None and job.state == "cancelled"
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 0
