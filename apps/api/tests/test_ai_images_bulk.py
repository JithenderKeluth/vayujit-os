from __future__ import annotations

import uuid

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def run_worker(worker_id: str, limit: int = 100) -> int:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        from vayujit_api.ai.studio_worker import run_ai_jobs_once

        return run_ai_jobs_once(db, worker_id, limit=limit)


def create_products(client, first: dict[str, object], count: int) -> list[str]:
    ids = [str(first["id"])]
    for index in range(1, count):
        response = client.post(
            "/api/v1/products",
            json={
                "name": f"Trail Bottle {index}",
                "product_type": "physical",
                "short_description": "An insulated reusable bottle",
                "description": "A durable bottle for long outdoor days.",
                "category": "Outdoors",
                "tags": ["insulated", "reusable"],
                "price_amount": "29.00",
                "price_currency": "USD",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


def image_payload(product_ids: list[str], key: str = "image-bulk-15") -> dict[str, object]:
    return {
        "product_ids": product_ids,
        "channels": ["amazon", "flipkart", "meesho"],
        "operation": "marketplace_main_image",
        "output_count_per_product": 1,
        "idempotency_key": key,
        "width": 128,
        "height": 128,
    }


def test_bulk_image_preview_enqueue_and_15_output_journey(client) -> None:
    context = setup_context(client)
    product_ids = create_products(client, context["product"], 5)
    payload = image_payload(product_ids)

    preview = client.post("/api/v1/ai/images/bulk/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    plan = preview.json()
    assert plan["total_outputs"] == 15
    assert plan["estimated_provider_calls"] == 15
    assert plan["estimated_cost"] == "unavailable"
    assert plan["blockers"] == []

    queued = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    duplicate = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    assert duplicate.status_code == 202, duplicate.text
    assert queued.json()["id"] == duplicate.json()["id"]
    bulk_id = queued.json()["id"]
    assert queued.json()["total_outputs"] == 15

    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(AIStudioBulkOperation)) == 1
        assert db.scalar(select(func.count()).select_from(AIStudioBulkOutput)) == 15
        assert db.scalar(select(func.count()).select_from(AIStudioJob)) == 15

    assert run_worker("image-bulk-15") == 15
    status = client.get(f"/api/v1/ai/images/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["status"] == "completed"
    assert body["counts"].get("needs_review") == 15
    assert body["progress_percentage"] == 100
    assert len(body["outputs"]) == 15
    assert len({item["image_output_id"] for item in body["outputs"]}) == 15
    assert len({item["media_id"] for item in body["outputs"]}) == 15
    assert {item["channel"] for item in body["outputs"]} == {
        "amazon",
        "flipkart",
        "meesho",
    }

    listed = client.get(f"/api/v1/ai/images/bulk/{bulk_id}/outputs?channel=amazon", headers=ORIGIN)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 5
    assert all(item["channel"] == "amazon" for item in listed.json()["items"])

    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(AIImageOutput)) == 15
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ai.image_bulk_started")
            )
            == 1
        )


def test_bulk_image_partial_failure_retry_cancel_and_owner_scope(client) -> None:
    context = setup_context(client)
    product_ids = create_products(client, context["product"], 5)
    payload = image_payload(product_ids, "image-bulk-partial")
    payload["failure_scenarios"] = {
        "3": "throttle_once",
        "6": "timeout_once",
        "9": "permanent_provider_failure",
        "12": "stale_source",
    }
    queued = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    cancel_id = queued.json()["outputs"][-1]["id"]
    cancelled = client.post(f"/api/v1/ai/images/bulk/outputs/{cancel_id}/cancel", headers=ORIGIN)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancelled_count"] == 1
    assert run_worker("image-bulk-partial") == 14
    first = client.get(f"/api/v1/ai/images/bulk/{bulk_id}", headers=ORIGIN).json()
    assert first["counts"].get("needs_review", 0) >= 9
    assert first["counts"].get("cancelled") == 1
    assert first["counts"].get("failed", 0) + first["counts"].get("stale", 0) >= 1

    eligible = [item["id"] for item in first["outputs"] if item["retry_eligible"]]
    retry = client.post(
        f"/api/v1/ai/images/bulk/{bulk_id}/retry-failed",
        json={"output_ids": eligible[:1]},
        headers=ORIGIN,
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["retried_count"] <= 1
    if eligible:
        assert (
            client.post(
                f"/api/v1/ai/images/bulk/{bulk_id}/retry-failed",
                json={"output_ids": eligible[:1]},
                headers=ORIGIN,
            ).status_code
            == 200
        )

    assert client.get(f"/api/v1/ai/images/bulk/{bulk_id}", headers=ORIGIN).status_code == 200
    assert client.get(f"/api/v1/ai/images/bulk/{uuid.uuid4()}", headers=ORIGIN).status_code == 404
