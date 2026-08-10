from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.failures import FAILURE_TAXONOMY, validate_failure_scenario
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent
from vayujit_api.publishing.scheduler_time import utcnow

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def payload(product_id: str, key: str, scenario: str) -> dict[str, Any]:
    return {
        "product_ids": [product_id],
        "channels": ["amazon"],
        "content_types": ["product_title"],
        "idempotency_key": key,
        "failure_scenario": scenario,
    }


def run_once_and_get_job(generation_id: str, worker: str) -> AIStudioJob:
    with db_session() as db:
        run_ai_jobs_once(db, worker, limit=1)
        job = db.scalar(select(AIStudioJob).where(AIStudioJob.generation_id == generation_id))
        assert job is not None
        return job


def make_retry_due(job_id: Any) -> None:
    with db_session() as db:
        row = db.get(AIStudioJob, job_id)
        assert row is not None
        row.available_at = utcnow() - timedelta(seconds=1)
        row.next_retry_at = row.available_at
        db.commit()


def test_failure_taxonomy_is_typed_and_complete() -> None:
    expected = {
        "provider_unavailable",
        "provider_timeout",
        "provider_throttled",
        "provider_5xx",
        "invalid_credentials",
        "unsupported_provider",
        "unsupported_model",
        "policy_refusal",
        "context_too_large",
        "malformed_output",
        "output_too_large",
        "structured_validation_failed",
        "unsafe_input",
        "stale_context",
        "cancelled",
        "unknown_transient",
        "unknown_permanent",
    }
    assert set(FAILURE_TAXONOMY) == expected
    assert all(spec.safe_message and spec.recovery_actions for spec in FAILURE_TAXONOMY.values())
    with pytest.raises(ValueError):
        validate_failure_scenario("not-a-real-scenario")


def test_throttle_once_retries_with_durable_delay_and_one_artifact(client: Any) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json=payload(context["product"]["id"], "failure-throttle-once", "throttle_once"),
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    generation_id = queued.json()["id"]
    job = run_once_and_get_job(generation_id, "failure-throttle-a")
    assert job.state == "retry_wait"
    assert job.failure_category == "provider_throttled"
    assert job.retry_after_seconds == 2
    assert job.applied_delay_seconds is not None
    make_retry_due(job.id)
    job = run_once_and_get_job(generation_id, "failure-throttle-b")
    assert job.state == "succeeded"
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
        assert db.scalar(select(func.count()).select_from(AIStudioJobAttempt)) == 2


def test_permanent_failure_is_safe_and_has_no_artifact(client: Any) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json=payload(
            context["product"]["id"], "failure-invalid-credentials", "invalid_credentials"
        ),
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    job = run_once_and_get_job(queued.json()["id"], "failure-permanent")
    assert job.state == "failed"
    assert job.failure_category == "invalid_credentials"
    assert "credentials" in (job.safe_error_message or "").lower()
    assert "sk-" not in (job.safe_error_message or "")
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ai.content_failed")
            )
            == 1
        )


@pytest.mark.parametrize("scenario", ["malformed_json_once", "malformed_json_twice"])
def test_malformed_output_has_one_repair_attempt(client: Any, scenario: str) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json=payload(context["product"]["id"], f"failure-{scenario}", scenario),
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    generation_id = queued.json()["id"]
    job = run_once_and_get_job(generation_id, f"failure-{scenario}")
    if scenario == "malformed_json_once":
        assert job.state == "succeeded"
        with db_session() as db:
            assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
            actions = set(db.scalars(select(AuditEvent.action)))
            assert "ai.content_repair_started" in actions
            assert "ai.content_repair_succeeded" in actions
    else:
        assert job.state == "failed"
        with db_session() as db:
            assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 0
            assert db.scalar(select(func.count()).select_from(AIStudioJobAttempt)) == 1


@pytest.mark.parametrize(
    "scenario",
    [
        "missing_required_field",
        "wrong_field_type",
        "truncated_output",
        "oversized_output",
        "context_too_large",
        "policy_refusal",
        "unsupported_model",
    ],
)
def test_structured_and_permanent_failures_do_not_create_artifacts(
    client: Any, scenario: str
) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json=payload(context["product"]["id"], f"failure-{scenario}", scenario),
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    job = run_once_and_get_job(queued.json()["id"], f"failure-{scenario}")
    if job.state == "retry_wait":
        make_retry_due(job.id)
        job = run_once_and_get_job(queued.json()["id"], f"failure-{scenario}-retry")
    assert job.state == "failed"
    assert job.failure_category
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 0


def test_retry_wait_cancellation_and_recovery_idempotency(client: Any) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json=payload(context["product"]["id"], "failure-cancel-recover", "timeout_twice"),
        headers=ORIGIN,
    )
    generation_id = queued.json()["id"]
    job = run_once_and_get_job(generation_id, "failure-cancel")
    assert job.state == "retry_wait"
    cancelled = client.post(f"/api/v1/ai/studio/jobs/{job.id}/cancel", headers=ORIGIN)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    recovery = client.post(
        "/api/v1/ai/studio/recovery/actions",
        json={"action": "retry_generation", "job_id": str(job.id)},
        headers=ORIGIN,
    )
    assert recovery.status_code == 409
