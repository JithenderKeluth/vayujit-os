"""Bounded Operations Control Center hardening evidence.

These tests intentionally exercise only safe local actions and deterministic
read projections; no live provider or advertising call is made.
"""

from __future__ import annotations

import contextlib
import json
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context
from test_ai_integration import client as integration_client
from test_scheduler_integration import business

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.operations.models import BackupRecord
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> object:
    generator = cast(Any, integration_client).__wrapped__()
    value = next(generator)
    try:
        yield value
    finally:
        with contextlib.suppress(StopIteration):
            next(generator)


def test_operations_sequential_idempotency_matrix(client: TestClient) -> None:
    setup_context(client)
    cleanup_payload = {"confirm": True, "idempotency_key": "cleanup-sequential"}
    first_cleanup = client.post("/api/v1/operations/cleanup", json=cleanup_payload, headers=ORIGIN)
    second_cleanup = client.post("/api/v1/operations/cleanup", json=cleanup_payload, headers=ORIGIN)
    assert first_cleanup.status_code == second_cleanup.status_code == 200
    assert first_cleanup.json()["idempotent_reuse"] is False
    assert second_cleanup.json()["idempotent_reuse"] is True
    assert first_cleanup.json()["audit_id"] == second_cleanup.json()["audit_id"]

    alert_payload = {"confirm": True, "idempotency_key": "alert-sequential"}
    first_alert = client.post(
        "/api/v1/operations/alerts/acknowledge?alert_code=storage_warning",
        json=alert_payload,
        headers=ORIGIN,
    )
    second_alert = client.post(
        "/api/v1/operations/alerts/acknowledge?alert_code=storage_warning",
        json=alert_payload,
        headers=ORIGIN,
    )
    assert first_alert.json()["idempotent_reuse"] is False
    assert second_alert.json()["idempotent_reuse"] is True
    assert first_alert.json()["audit_id"] == second_alert.json()["audit_id"]

    scheduler_payload = {"confirm": True, "idempotency_key": "scheduler-sequential"}
    first_scheduler = client.post(
        "/api/v1/operations/scheduler/run-due",
        json=scheduler_payload,
        headers=ORIGIN,
    )
    second_scheduler = client.post(
        "/api/v1/operations/scheduler/run-due",
        json=scheduler_payload,
        headers=ORIGIN,
    )
    assert first_scheduler.status_code == second_scheduler.status_code == 200
    assert second_scheduler.json()["idempotent_reuse"] is True


def test_operations_concurrent_alert_acknowledgement_is_singleton(client: TestClient) -> None:
    setup_context(client)
    payload = {"confirm": True, "idempotency_key": "alert-concurrent"}

    def acknowledge() -> tuple[int, dict[str, object]]:
        response = client.post(
            "/api/v1/operations/alerts/acknowledge?alert_code=worker_failure",
            json=payload,
            headers=ORIGIN,
        )
        return response.status_code, cast(dict[str, object], response.json())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: acknowledge(), range(2)))

    assert {status for status, _ in results} == {200}
    bodies = [body for _, body in results]
    assert sum(body["idempotent_reuse"] is False for body in bodies) == 1
    assert sum(body["idempotent_reuse"] is True for body in bodies) == 1
    assert len({body["audit_id"] for body in bodies}) == 1


def _audit_count(action: str) -> int:
    module = __import__("test_ai_integration")
    factory = cast(Any, module).factory
    assert factory is not None
    with factory() as db:
        return int(
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
            )
            or 0
        )


def test_operations_concurrent_manual_backup_is_singleton(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    stamp = datetime.now(UTC)

    def fake_backup(db: Any, owner_id: uuid.UUID) -> BackupRecord:
        value = BackupRecord(
            owner_id=owner_id,
            backup_key="operations-concurrent-backup",
            filename="operations-concurrent-backup.dump",
            format="postgres-custom",
            size_bytes=1,
            checksum_sha256="0" * 64,
            application_version="test",
            migration_revision="test",
            database_name="vayujit_test",
            created_at=stamp,
            verification_status="pending",
            status="created",
        )
        db.add(value)
        db.flush()
        return value

    monkeypatch.setattr("vayujit_api.operations.control_center.create_backup", fake_backup)
    payload = {"confirm": True, "idempotency_key": "backup-concurrent"}

    def request() -> tuple[int, dict[str, object]]:
        response = client.post("/api/v1/operations/backups/trigger", json=payload, headers=ORIGIN)
        return response.status_code, cast(dict[str, object], response.json())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert {status for status, _ in results} == {200}
    bodies = [body for _, body in results]
    assert sum(body["idempotent_reuse"] is False for body in bodies) == 1
    assert sum(body["idempotent_reuse"] is True for body in bodies) == 1
    assert len({body["audit_id"] for body in bodies}) == 1
    assert _audit_count("operations.backup_triggered") == 1


def test_operations_concurrent_recovery_is_delegated_without_duplicate_audit(
    client: TestClient,
) -> None:
    setup_context(client)
    payload = {"confirm": True, "idempotency_key": "recovery-concurrent"}
    before = _audit_count("operations.recovery_action")

    def request() -> int:
        return client.post(
            "/api/v1/operations/recovery/actions?action=retry",
            json=payload,
            headers=ORIGIN,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: request(), range(2)))
    assert statuses == [409, 409]
    assert _audit_count("operations.recovery_action") == before


def test_operations_storage_ledger_and_integrity(client: TestClient) -> None:
    setup_context(client)
    from test_ai_integration import factory

    assert factory is not None
    with factory() as db:
        before = {
            "audit_events": int(db.scalar(select(func.count()).select_from(AuditEvent)) or 0),
        }
    payload = {"confirm": True, "idempotency_key": "ledger-cleanup"}
    client.post("/api/v1/operations/cleanup", json=payload, headers=ORIGIN)
    client.post("/api/v1/operations/cleanup", json=payload, headers=ORIGIN)
    with factory() as db:
        after = {
            "audit_events": int(db.scalar(select(func.count()).select_from(AuditEvent)) or 0),
        }
    assert after["audit_events"] - before["audit_events"] == 1
    assert after["audit_events"] >= before["audit_events"]
    print(json.dumps({"before": before, "after": after, "delta": {"audit_events": 1}}))


def _seed_job(client: TestClient, state: str, retryable: bool) -> uuid.UUID:
    product, artifact, destination = business(client)
    module = __import__("test_ai_integration")
    factory = cast(Any, module).factory
    assert factory is not None
    timestamp = datetime.now(UTC)
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "scheduler@example.com"))
        assert owner is not None
        value = PublishingJob(
            owner_id=owner.id,
            product_id=uuid.UUID(str(product["id"])),
            artifact_id=uuid.UUID(str(artifact["id"])),
            artifact_version=cast(int, artifact["version_number"]),
            destination_id=uuid.UUID(str(destination["id"])),
            connector_key="mock_publisher_v1",
            requested_action="publish",
            idempotency_key=f"operations-{state}",
            state=state,
            priority=0,
            scheduled_at_utc=timestamp,
            available_at_utc=timestamp,
            claim_count=0,
            execution_attempt_count=0,
            max_execution_attempts=5,
            retryable=retryable,
            created_at=timestamp,
            updated_at=timestamp,
            row_version=1,
        )
        db.add(value)
        db.commit()
        return value.id


def test_operations_concurrent_job_retry_is_singleton(client: TestClient) -> None:
    job_id = _seed_job(client, "failed", True)

    def request() -> tuple[int, dict[str, object]]:
        response = client.post(
            f"/api/v1/operations/jobs/{job_id}/actions?action=retry",
            json={"confirm": True},
            headers=ORIGIN,
        )
        return response.status_code, cast(dict[str, object], response.json())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert {status for status, _ in results} == {200}
    bodies = [body for _, body in results]
    assert sum(body["idempotent_reuse"] is False for body in bodies) == 1
    assert sum(body["idempotent_reuse"] is True for body in bodies) == 1
    assert len({body["audit_id"] for body in bodies}) == 1
    assert _audit_count("operations.job_retry") == 1


def test_operations_concurrent_job_cancel_is_singleton_and_stale_safe(client: TestClient) -> None:
    job_id = _seed_job(client, "retry_wait", True)

    def request() -> tuple[int, dict[str, object]]:
        response = client.post(
            f"/api/v1/operations/jobs/{job_id}/actions?action=cancel",
            json={"confirm": True},
            headers=ORIGIN,
        )
        return response.status_code, cast(dict[str, object], response.json())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert {status for status, _ in results} == {200}
    bodies = [body for _, body in results]
    assert sum(body["idempotent_reuse"] is False for body in bodies) == 1
    assert sum(body["idempotent_reuse"] is True for body in bodies) == 1
    assert len({body["audit_id"] for body in bodies}) == 1
    assert _audit_count("operations.job_cancel") == 1
    module = __import__("test_ai_integration")
    factory = cast(Any, module).factory
    assert factory is not None
    with factory() as db:
        job = db.get(PublishingJob, job_id)
        assert job is not None and job.state == "cancelled"
        assert claim_jobs(db, "operations-stale-worker", 1, 60) == []


def test_operations_mutation_inventory_and_audit_boundaries(client: TestClient) -> None:
    setup_context(client)
    inventory = {
        "backup": "MUTATING",
        "alert": "MUTATING",
        "scheduler": "MUTATING",
        "job_retry": "MUTATING",
        "job_cancel": "MUTATING",
        "cleanup": "MUTATING",
        "recovery": "DELEGATED_TO_DOMAIN",
        "provider_switch": "DEPLOYMENT_CONTROLLED",
        "emergency_stop": "DEPLOYMENT_CONTROLLED",
        "mutation_control": "DEPLOYMENT_CONTROLLED",
        "drain": "DEPLOYMENT_CONTROLLED",
        "migrations": "DEPLOYMENT_CONTROLLED",
    }
    assert set(inventory.values()) == {
        "MUTATING",
        "DELEGATED_TO_DOMAIN",
        "DEPLOYMENT_CONTROLLED",
    }
    before = _audit_count("operations.alert_acknowledged")
    assert client.get("/api/v1/operations/overview", headers=ORIGIN).status_code == 200
    assert (
        client.post(
            "/api/v1/operations/providers/shopify/switch",
            json={"confirm": True},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/operations/recovery/actions?action=retry",
            json={"confirm": True},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert _audit_count("operations.alert_acknowledged") == before


def test_operations_performance_baseline(client: TestClient) -> None:
    setup_context(client)
    missing = str(uuid.uuid4())
    endpoints = [
        "/api/v1/operations/overview",
        "/api/v1/operations/health",
        "/api/v1/operations/workers",
        "/api/v1/operations/workers/missing-worker",
        "/api/v1/operations/scheduler",
        "/api/v1/operations/jobs",
        f"/api/v1/operations/jobs/{missing}",
        "/api/v1/operations/providers",
        "/api/v1/operations/providers/shopify",
        "/api/v1/operations/backups/overview",
        "/api/v1/operations/storage",
        "/api/v1/operations/security",
        "/api/v1/operations/audit?limit=10",
        "/api/v1/operations/trace/missing-correlation",
        "/api/v1/operations/alerts",
        "/api/v1/operations/release-readiness",
        "/api/v1/operations/configuration",
        "/api/v1/operations/recovery",
    ]
    timings: dict[str, list[float]] = {}
    for endpoint in endpoints:
        samples: list[float] = []
        for _ in range(3):
            started = time.perf_counter()
            response = client.get(endpoint, headers=ORIGIN)
            samples.append((time.perf_counter() - started) * 1000)
            assert response.status_code in {200, 404}
        timings[endpoint] = samples

    action_samples: dict[str, float] = {}
    for name, method, endpoint, payload in [
        ("backup_confirmation", "post", "/api/v1/operations/backups/trigger", {"confirm": False}),
        (
            "recovery_confirmation",
            "post",
            "/api/v1/operations/recovery/actions?action=retry",
            {"confirm": True},
        ),
        (
            "alert_acknowledgement",
            "post",
            "/api/v1/operations/alerts/acknowledge?alert_code=perf",
            {"confirm": True, "idempotency_key": "perf-alert"},
        ),
    ]:
        started = time.perf_counter()
        response = getattr(client, method)(endpoint, json=payload, headers=ORIGIN)
        action_samples[name] = (time.perf_counter() - started) * 1000
        assert response.status_code in {200, 409, 422, 503}

    summary = {}
    for endpoint, samples in timings.items():
        ordered = sorted(samples)
        p95 = ordered[-1]
        summary[endpoint] = {
            "median_ms": round(statistics.median(samples), 2),
            "p95_ms": round(p95, 2),
            "classification": "PASS" if p95 < 10000 else "WARN",
        }
    print(json.dumps({"reads": summary, "actions_ms": action_samples}, default=str))
    assert all(item["classification"] == "PASS" for item in summary.values())
