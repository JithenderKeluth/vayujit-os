from __future__ import annotations

import uuid

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.studio_models import AIStudioJob

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def run_worker(worker_id: str) -> int:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        from vayujit_api.ai.studio_worker import run_ai_jobs_once

        return run_ai_jobs_once(db, worker_id, limit=50)


def bulk_payload(product_id: str, key: str = "bulk-test") -> dict[str, object]:
    return {
        "product_ids": [product_id],
        "channels": ["amazon", "flipkart"],
        "content_types": ["marketplace_listing"],
        "idempotency_key": key,
    }


def test_bulk_preview_and_enqueue_are_durable_and_idempotent(client) -> None:
    context = setup_context(client)
    payload = bulk_payload(context["product"]["id"])
    preview = client.post("/api/v1/ai/studio/bulk/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    assert preview.json()["total_outputs"] == 2
    assert preview.json()["estimated_cost"] == "unavailable"
    first = client.post("/api/v1/ai/studio/bulk", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/ai/studio/bulk", json=payload, headers=ORIGIN)
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["total_outputs"] == 2
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(AIStudioBulkOperation)) == 1
        assert db.scalar(select(func.count()).select_from(AIStudioBulkOutput)) == 2
        assert db.scalar(select(func.count()).select_from(AIStudioJob)) == 2


def test_bulk_worker_progress_and_output_listing(client) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/bulk",
        json=bulk_payload(context["product"]["id"], "bulk-worker"),
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    assert run_worker("bulk-worker") == 2
    status = client.get(f"/api/v1/ai/studio/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["total_outputs"] == 2
    assert body["counts"].get("needs_review") == 2
    assert body["progress_percentage"] == 100
    outputs = client.get(f"/api/v1/ai/studio/bulk/{bulk_id}/outputs", headers=ORIGIN)
    assert outputs.status_code == 200, outputs.text
    assert len(outputs.json()["items"]) == 2
    assert all(item["artifact_id"] for item in outputs.json()["items"])


def test_bulk_single_output_cancellation_isolated(client) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/bulk",
        json=bulk_payload(context["product"]["id"], "bulk-cancel"),
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    output_id = queued.json()["outputs"][0]["id"]
    cancelled = client.post(f"/api/v1/ai/studio/bulk/outputs/{output_id}/cancel", headers=ORIGIN)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancelled_count"] == 1
    assert run_worker("bulk-cancel-worker") == 1
    body = client.get(f"/api/v1/ai/studio/bulk/{bulk_id}", headers=ORIGIN).json()
    assert body["counts"].get("cancelled") == 1
    assert body["counts"].get("needs_review") == 1


def test_bulk_partial_failure_and_retry_failed_only(client) -> None:
    context = setup_context(client)
    payload = bulk_payload(context["product"]["id"], "bulk-partial")
    payload["failure_scenarios"] = {"2": "invalid_credentials"}
    queued = client.post("/api/v1/ai/studio/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    assert run_worker("bulk-partial-worker") == 2
    first = client.get(f"/api/v1/ai/studio/bulk/{bulk_id}", headers=ORIGIN).json()
    assert first["counts"].get("needs_review") == 1
    assert first["counts"].get("failed") == 1
    retry = client.post(f"/api/v1/ai/studio/bulk/{bulk_id}/retry-failed", headers=ORIGIN)
    assert retry.status_code == 200, retry.text
    assert retry.json()["retried_count"] == 0


def test_bulk_owner_scope_and_limits(client) -> None:
    context = setup_context(client)
    too_many = bulk_payload(context["product"]["id"], "bulk-limit")
    too_many["product_ids"] = [str(uuid.uuid4()) for _ in range(51)]
    response = client.post("/api/v1/ai/studio/bulk/preview", json=too_many, headers=ORIGIN)
    assert response.status_code == 422
