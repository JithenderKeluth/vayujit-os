from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence.sourcing_models import SourcingRecoveryRecord, SourcingWorkerJob
from vayujit_api.intelligence.sourcing_service import now

pytest_plugins = ["test_ai_integration"]

pytestmark = pytest.mark.integration


def _expire(job_id: str) -> None:
    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        job = db.get(SourcingWorkerJob, job_id)
        assert job is not None
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()


def _job(job_id: str) -> SourcingWorkerJob:
    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        job = db.get(SourcingWorkerJob, job_id)
        assert job is not None
        db.expunge(job)
        return job


def test_sourcing_crash_before_reuses_checkpoint_and_finishes_once(client: Any) -> None:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing/worker/jobs",
        json={
            "task": "cost_recalculation",
            "idempotency_key": "crash-before-1",
            "payload": {
                "unit_supplier_price": 10,
                "quantity": 2,
                "crash_after_stage": "before_calculation",
            },
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    with pytest.raises(RuntimeError, match="before calculation"):
        client.post(f"/api/v1/intelligence/sourcing/worker/jobs/{job_id}/run", headers=ORIGIN)
    crashed = _job(job_id)
    assert crashed.checkpoint_stage == "before_calculation"
    assert crashed.result == {}
    _expire(job_id)
    resumed = client.post(f"/api/v1/intelligence/sourcing/worker/jobs/{job_id}/run", headers=ORIGIN)
    assert resumed.status_code == 200, resumed.text
    result = resumed.json()
    assert result["status"] == "completed"
    assert result["checkpoint_stage"] == "finalized"
    assert result["attempt_count"] == 2
    assert result["result"]["calculation"]["landed_cost_per_unit"] == 5.0


def test_sourcing_crash_after_calculation_does_not_duplicate_result(client: Any) -> None:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing/worker/jobs",
        json={
            "task": "cost_recalculation",
            "idempotency_key": "crash-after-1",
            "payload": {
                "unit_supplier_price": 12,
                "quantity": 3,
                "crash_after_stage": "calculation_complete",
            },
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    with pytest.raises(RuntimeError, match="calculation checkpoint"):
        client.post(f"/api/v1/intelligence/sourcing/worker/jobs/{job_id}/run", headers=ORIGIN)
    crashed = _job(job_id)
    assert crashed.checkpoint_stage == "calculation_complete"
    calculation = crashed.result["calculation"]
    _expire(job_id)
    resumed = client.post(f"/api/v1/intelligence/sourcing/worker/jobs/{job_id}/run", headers=ORIGIN)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["checkpoint_stage"] == "finalized"
    assert resumed.json()["result"]["calculation"] == calculation
    assert resumed.json()["attempt_count"] == 2


def test_sourcing_recovery_matrix_is_safe_and_idempotent(client: Any) -> None:
    setup_context(client)
    job = client.post(
        "/api/v1/intelligence/sourcing/worker/jobs",
        json={"task": "scenario_generation", "idempotency_key": "recovery-job-1"},
        headers=ORIGIN,
    )
    assert job.status_code == 201, job.text
    payload = {
        "entity_type": "sourcing_worker_job",
        "entity_id": job.json()["id"],
        "action": "retry",
        "failure_code": "cost_calculation_failed",
        "idempotency_key": "recovery-1",
        "reason": "Disposable deterministic recovery test.",
    }
    first = client.post("/api/v1/intelligence/sourcing/recovery", json=payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    assert first.json()["allowed_actions"] == ["retry", "reconcile", "cancel"]
    assert first.json()["safe_message"]
    second = client.post("/api/v1/intelligence/sourcing/recovery", json=payload, headers=ORIGIN)
    assert second.status_code == 200, second.text
    assert second.json()["idempotent_reuse"] is True
    assert second.json()["id"] == first.json()["id"]
    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        assert db.scalar(select(func.count()).select_from(SourcingRecoveryRecord)) == 1


def test_sourcing_recovery_rejects_unadvertised_action(client: Any) -> None:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing/recovery",
        json={
            "entity_type": "sourcing_worker_job",
            "entity_id": "00000000-0000-4000-8000-000000000001",
            "action": "purchase_now",
            "failure_code": "checkpoint_invalid",
            "reason": "must remain disabled",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 422
    assert "not executable" in response.text


def test_sourcing_storage_inventory_is_exact_and_bounded(client: Any) -> None:
    setup_context(client)
    response = client.get("/api/v1/intelligence/sourcing/storage/inventory", headers=ORIGIN)
    assert response.status_code == 200, response.text
    tables = response.json()["tables"]
    assert len(tables) == 28
    assert len(set(tables)) == 28
    assert all(table.startswith("intelligence_") for table in tables)
