from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from statistics import median, quantiles
from time import perf_counter
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt
from vayujit_api.audit.models import AuditEvent
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def run_worker(worker_id: str, limit: int = 100) -> int:
    assert test_ai_integration.factory is not None
    from vayujit_api.ai.studio_worker import run_ai_jobs_once

    with test_ai_integration.factory() as db:
        return run_ai_jobs_once(db, worker_id, limit=limit)


def make_retries_due() -> None:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        for job in db.scalars(select(AIStudioJob).where(AIStudioJob.state == "retry_wait")):
            job.available_at = utcnow()
        db.commit()


def create_products(client: Any, first: dict[str, Any], count: int) -> list[str]:
    ids = [str(first["id"])]
    for index in range(1, count):
        response = client.post(
            "/api/v1/products",
            json={
                "name": f"Bulk Trail Bottle {index}",
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


def bulk_payload(product_ids: list[str], key: str) -> dict[str, Any]:
    return {
        "product_ids": product_ids,
        "video_types": ["youtube_video"],
        "targets": ["youtube", "instagram", "facebook"],
        "duration_seconds": 2,
        "resolution": "320x240",
        "idempotency_key": key,
    }


def test_bulk_normal_15_output_e2e_has_exact_durable_lineage(client: Any) -> None:
    context = setup_context(client)
    products = create_products(client, context["product"], 5)
    payload = bulk_payload(products, "bulk-15-normal")

    preview = client.post("/api/v1/ai/video/bulk/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready"] is True
    assert preview.json()["total_outputs"] == 15

    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    duplicate = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    assert duplicate.status_code in {200, 202}, duplicate.text
    assert duplicate.json()["id"] == queued.json()["id"]
    bulk_id = queued.json()["id"]

    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(VideoBulkOperation)) == 1
        assert db.scalar(select(func.count()).select_from(VideoBulkChild)) == 15
        assert db.scalar(select(func.count()).select_from(VideoGeneration)) == 15
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 15
        assert db.scalar(select(func.count()).select_from(AIStudioJob)) == 15

    assert run_worker("bulk-15-worker") == 15
    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["status"] == "succeeded"
    assert body["succeeded_count"] == 15
    assert body["progress_percentage"] == 100
    assert len(body["children"]) == 15
    assert len({item["id"] for item in body["children"]}) == 15
    assert len({item["generation_id"] for item in body["children"]}) == 15
    assert len({item["job_id"] for item in body["children"]}) == 15
    assert len({item["output_id"] for item in body["children"]}) == 15

    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 15
        assert db.scalar(select(func.count()).select_from(AIStudioJobAttempt)) == 15
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoOutput)
                .where(VideoOutput.media_id.is_not(None))
            )
            == 15
        )


def test_bulk_partial_failure_retry_and_cancel_isolates_siblings(client: Any) -> None:
    context = setup_context(client)
    products = create_products(client, context["product"], 4)
    payload = {
        **bulk_payload(products, "bulk-partial-isolation"),
        "targets": ["youtube"],
        "failure_scenarios": {
            "2": "provider_unavailable",
            "3": "unsupported_operation",
            "4": "invalid_video",
        },
    }
    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]

    # Exhaust the bounded transient retry while permanent siblings remain isolated.
    for index in range(4):
        run_worker(f"bulk-partial-worker-{index}")
        make_retries_due()
    first = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN).json()
    assert first["succeeded_count"] == 1
    assert first["failed_count"] >= 2, first
    assert first["counts"].get("retry_wait", 0) == 0
    failed = [item for item in first["children"] if item["status"] == "failed"]
    assert len(failed) >= 2
    retryable = [item for item in failed if item["retryable"]]
    assert retryable

    retried = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/retry-failed",
        json={"child_ids": [retryable[0]["id"]], "idempotency_key": "partial-retry"},
        headers=ORIGIN,
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["retried_count"] == 1
    repeated = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/retry-failed",
        json={"child_ids": [retryable[0]["id"]], "idempotency_key": "partial-retry"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["retried_count"] == 0
    assert repeated.json()["idempotent_reuse"] is True

    cancelled = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/cancel",
        json={"child_ids": [first["children"][0]["id"]]},
        headers=ORIGIN,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancelled_count"] == 0


def test_bulk_concurrent_creation_reuses_one_parent_and_child_set(client: Any) -> None:
    context = setup_context(client)
    payload = bulk_payload([context["product"]["id"]], "bulk-concurrent-create")

    def create() -> tuple[int, dict[str, Any]]:
        response = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert all(status in {200, 202} for status, _ in results), results
    assert len({str(body["id"]) for _, body in results}) == 1
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(VideoBulkOperation)) == 1
        assert db.scalar(select(func.count()).select_from(VideoBulkChild)) == 3
        assert db.scalar(select(func.count()).select_from(VideoGeneration)) == 3
        assert db.scalar(select(func.count()).select_from(AIStudioJob)) == 3


def test_bulk_concurrent_retry_reuses_one_child_attempt(client: Any) -> None:
    context = setup_context(client)
    payload = {
        **bulk_payload([context["product"]["id"]], "bulk-concurrent-retry"),
        "targets": ["youtube"],
        "failure_scenario": "provider_unavailable",
    }
    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    for index in range(4):
        run_worker(f"bulk-retry-exhaust-{index}")
        make_retries_due()
    body = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN).json()
    child = body["children"][0]
    assert child["status"] == "failed" and child["retryable"] is True

    def retry() -> tuple[int, dict[str, Any]]:
        response = client.post(
            f"/api/v1/ai/video/bulk/{bulk_id}/retry-failed",
            json={"child_ids": [child["id"]], "idempotency_key": "concurrent-retry"},
            headers=ORIGIN,
        )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: retry(), range(2)))
    assert all(status == 200 for status, _ in results), results
    assert sum(int(result["retried_count"]) for _, result in results) == 1
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(VideoGeneration)) == 1
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 1
        assert db.scalar(select(func.count()).select_from(AIStudioJob)) == 1
        child_row = db.get(VideoBulkChild, child["id"])
        assert child_row is not None and child_row.retry_count == 1


def test_bulk_performance_samples_are_recorded_with_local_provider(client: Any) -> None:
    context = setup_context(client)
    payload = bulk_payload([context["product"]["id"]], "bulk-performance-samples")
    preview_samples: list[float] = []
    status_samples: list[float] = []
    for _ in range(5):
        started = perf_counter()
        response = client.post("/api/v1/ai/video/bulk/preview", json=payload, headers=ORIGIN)
        preview_samples.append((perf_counter() - started) * 1000)
        assert response.status_code == 200, response.text
    queued_started = perf_counter()
    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    enqueue_ms = (perf_counter() - queued_started) * 1000
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    for _ in range(5):
        started = perf_counter()
        response = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
        status_samples.append((perf_counter() - started) * 1000)
        assert response.status_code == 200, response.text
    first_completion_started = perf_counter()
    assert run_worker("bulk-performance-worker") == 3
    first_completion_ms = (perf_counter() - first_completion_started) * 1000
    output_started = perf_counter()
    outputs = client.get(f"/api/v1/ai/video/bulk/{bulk_id}/outputs", headers=ORIGIN)
    output_ms = (perf_counter() - output_started) * 1000
    assert outputs.status_code == 200, outputs.text
    usage = client.get(f"/api/v1/ai/video/bulk/{bulk_id}/usage", headers=ORIGIN)
    diagnostics = client.get(f"/api/v1/ai/video/bulk/{bulk_id}/diagnostics", headers=ORIGIN)
    assert usage.status_code == diagnostics.status_code == 200
    p95_preview = quantiles(preview_samples, n=20, method="inclusive")[18]
    p95_status = quantiles(status_samples, n=20, method="inclusive")[18]
    print(
        "bulk performance: "
        f"preview_median_ms={median(preview_samples):.1f} "
        f"preview_p95_ms={p95_preview:.1f} "
        f"enqueue_ms={enqueue_ms:.1f} "
        f"status_median_ms={median(status_samples):.1f} "
        f"status_p95_ms={p95_status:.1f} "
        f"outputs_ms={output_ms:.1f} "
        f"time_to_first_completion_ms={first_completion_ms:.1f}"
    )


def test_bulk_cancellation_is_idempotent_and_isolates_succeeded_siblings(client: Any) -> None:
    context = setup_context(client)
    products = create_products(client, context["product"], 3)
    payload = {
        **bulk_payload(products, "bulk-cancellation-proof"),
        "targets": ["youtube"],
        "failure_scenarios": {"2": "provider_unavailable"},
    }
    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    initial = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN).json()
    queued_child = initial["children"][0]["id"]
    first_cancel = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/cancel",
        json={"child_ids": [queued_child]},
        headers=ORIGIN,
    )
    assert first_cancel.status_code == 200, first_cancel.text
    assert first_cancel.json()["cancelled_count"] == 1
    repeated_cancel = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/cancel",
        json={"child_ids": [queued_child]},
        headers=ORIGIN,
    )
    assert repeated_cancel.status_code == 200, repeated_cancel.text
    assert repeated_cancel.json()["cancelled_count"] == 0

    assert run_worker("bulk-cancellation-worker") == 2
    after_worker = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN).json()
    retry_wait_child = next(
        child for child in after_worker["children"] if child["status"] == "retry_wait"
    )
    succeeded_child = next(
        child for child in after_worker["children"] if child["status"] == "succeeded"
    )
    retry_cancel = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/cancel",
        json={"child_ids": [retry_wait_child["id"]]},
        headers=ORIGIN,
    )
    assert retry_cancel.status_code == 200, retry_cancel.text
    assert retry_cancel.json()["cancelled_count"] == 1

    def cancel_retry_wait() -> dict[str, Any]:
        response = client.post(
            f"/api/v1/ai/video/bulk/{bulk_id}/cancel",
            json={"child_ids": [retry_wait_child["id"]]},
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
        return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(lambda _: cancel_retry_wait(), range(2)))
    assert sum(int(item["cancelled_count"]) for item in concurrent) == 0

    remaining = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/cancel-remaining",
        json={"child_ids": []},
        headers=ORIGIN,
    )
    repeated_remaining = client.post(
        f"/api/v1/ai/video/bulk/{bulk_id}/cancel-remaining",
        json={"child_ids": []},
        headers=ORIGIN,
    )
    assert remaining.status_code == repeated_remaining.status_code == 200
    assert remaining.json()["cancelled_count"] == repeated_remaining.json()["cancelled_count"] == 0
    assert run_worker("bulk-cancellation-after") == 0

    final = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN).json()
    assert final["succeeded_count"] == 1
    assert final["cancelled_count"] == 2
    assert {child["id"] for child in final["children"] if child["status"] == "succeeded"} == {
        succeeded_child["id"]
    }
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        child_rows = list(
            db.scalars(select(VideoBulkChild).where(VideoBulkChild.bulk_id == bulk_id))
        )
        generation_ids = [child.generation_id for child in child_rows if child.generation_id]
        outputs = list(
            db.scalars(select(VideoOutput).where(VideoOutput.generation_id.in_(generation_ids)))
        )
        media_ids = [output.media_id for output in outputs if output.media_id]
        assert len(outputs) == 3
        assert sum(output.media_id is not None for output in outputs) == 1
        assert (
            db.scalar(
                select(func.count()).select_from(MediaAsset).where(MediaAsset.id.in_(media_ids))
            )
            == 1
        )
        child_ids = [child.id for child in child_rows]
        child_cancel_events = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "video_bulk_child_cancelled",
                AuditEvent.entity_id.in_(child_ids),
            )
        )
        parent_cancel_events = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "video_bulk_cancel_remaining",
                AuditEvent.entity_id == bulk_id,
            )
        )
        assert child_cancel_events == 2
        assert parent_cancel_events == 1


def test_bulk_exact_version_lineage_survives_new_context_versions_and_retry(client: Any) -> None:
    context = setup_context(client)
    script_payload = {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": "Bulk Exact Script",
        "hook": "Carry better",
        "introduction": "Insulated for every trip",
        "narration": "A durable bottle.",
        "on_screen_text": "Reusable",
        "cta": "Shop now",
        "outro": "Built for the journey",
        "target_duration_seconds": 2,
    }
    script_v1 = client.post("/api/v1/ai/video/scripts", json=script_payload, headers=ORIGIN)
    assert script_v1.status_code == 201, script_v1.text
    script_v1_body = script_v1.json()
    assert (
        client.post(
            f"/api/v1/ai/video/scripts/{script_v1_body['id']}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    storyboard_v1 = client.post(
        "/api/v1/ai/video/storyboards",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "scenes": [
                {
                    "stable_key": "hook",
                    "scene_order": 1,
                    "duration_seconds": 2,
                    "scene_text": "Carry better",
                }
            ],
        },
        headers=ORIGIN,
    )
    assert storyboard_v1.status_code == 201, storyboard_v1.text
    storyboard_v1_body = storyboard_v1.json()
    assert (
        client.post(
            f"/api/v1/ai/video/storyboards/{storyboard_v1_body['id']}/approve",
            json={"expected_row_version": storyboard_v1_body["row_version"]},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    style_v1 = client.post(
        "/api/v1/ai/video/styles",
        json={
            "brand_id": context["brand"]["id"],
            "name": "Bulk Exact Style",
            "config": {"motion_style": "steady", "pacing": "measured"},
        },
        headers=ORIGIN,
    )
    assert style_v1.status_code == 201, style_v1.text
    style_v1_body = style_v1.json()
    preset_v1 = client.post(
        "/api/v1/ai/video/presets",
        json={
            "name": "Bulk Exact Preset",
            "video_type": "youtube_video",
            "target_channel": "youtube",
            "resolution": "320x240",
            "target_duration_seconds": 2,
            "max_duration_seconds": 10,
            "style_id": style_v1_body["id"],
        },
        headers=ORIGIN,
    )
    assert preset_v1.status_code == 201, preset_v1.text
    preset_v1_body = preset_v1.json()
    base_context = {
        "script_id": script_v1_body["id"],
        "script_version": script_v1_body["version"],
        "storyboard_id": storyboard_v1_body["id"],
        "storyboard_version": storyboard_v1_body["version"],
        "style_id": style_v1_body["id"],
        "style_version": style_v1_body["version"],
        "preset_id": preset_v1_body["id"],
        "preset_version": preset_v1_body["version"],
    }
    success_payload = {
        **bulk_payload([context["product"]["id"]], "bulk-exact-version-success"),
        **base_context,
    }
    success_payload["targets"] = ["youtube"]
    queued = client.post("/api/v1/ai/video/bulk", json=success_payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text

    script_v2 = client.post(
        "/api/v1/ai/video/scripts",
        json={**script_payload, "hook": "Carry further"},
        headers=ORIGIN,
    )
    assert script_v2.status_code == 201 and script_v2.json()["version"] == 2
    assert (
        client.post(
            f"/api/v1/ai/video/scripts/{script_v2.json()['id']}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    storyboard_v2 = client.post(
        "/api/v1/ai/video/storyboards",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "scenes": [
                {
                    "stable_key": "hook",
                    "scene_order": 1,
                    "duration_seconds": 2,
                    "scene_text": "Carry further",
                }
            ],
        },
        headers=ORIGIN,
    )
    assert storyboard_v2.status_code == 201 and storyboard_v2.json()["version"] == 2
    assert (
        client.post(
            f"/api/v1/ai/video/storyboards/{storyboard_v2.json()['id']}/approve",
            json={"expected_row_version": storyboard_v2.json()["row_version"]},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    style_v2 = client.post(
        "/api/v1/ai/video/styles",
        json={
            "brand_id": context["brand"]["id"],
            "name": "Bulk Exact Style",
            "config": {"motion_style": "dynamic", "pacing": "fast"},
        },
        headers=ORIGIN,
    )
    assert style_v2.status_code == 201 and style_v2.json()["version"] == 2
    preset_v2 = client.post(
        "/api/v1/ai/video/presets",
        json={
            "name": "Bulk Exact Preset",
            "video_type": "youtube_video",
            "target_channel": "youtube",
            "resolution": "320x240",
            "target_duration_seconds": 2,
            "max_duration_seconds": 10,
            "style_id": style_v2.json()["id"],
        },
        headers=ORIGIN,
    )
    assert preset_v2.status_code == 201 and preset_v2.json()["version"] == 2
    assert run_worker("bulk-exact-version-success") == 1
    success_body = client.get(f"/api/v1/ai/video/bulk/{queued.json()['id']}", headers=ORIGIN).json()
    assert success_body["succeeded_count"] == 1

    retry_payload = {
        **bulk_payload([context["product"]["id"]], "bulk-exact-version-retry"),
        **base_context,
        "failure_scenario": "provider_unavailable",
    }
    retry_payload["targets"] = ["youtube"]
    retry_queued = client.post("/api/v1/ai/video/bulk", json=retry_payload, headers=ORIGIN)
    assert retry_queued.status_code == 202, retry_queued.text
    for index in range(4):
        run_worker(f"bulk-exact-version-failure-{index}")
        make_retries_due()
    failed = client.get(
        f"/api/v1/ai/video/bulk/{retry_queued.json()['id']}", headers=ORIGIN
    ).json()["children"][0]
    assert failed["status"] == "failed" and failed["retryable"] is True
    retried = client.post(
        f"/api/v1/ai/video/bulk/{retry_queued.json()['id']}/retry-failed",
        json={"child_ids": [failed["id"]], "idempotency_key": "bulk-exact-version-retry-1"},
        headers=ORIGIN,
    )
    assert retried.status_code == 200 and retried.json()["retried_count"] == 1
    db_factory = test_ai_integration.factory
    assert db_factory is not None
    with db_factory() as db:
        retry_job = db.get(AIStudioJob, failed["job_id"])
        assert retry_job is not None
        retry_job.payload_json = {**retry_job.payload_json, "failure_scenario": "success"}
        db.commit()
    assert run_worker("bulk-exact-version-retry-worker") == 1
    with db_factory() as db:
        retry_child = db.get(VideoBulkChild, failed["id"])
        assert retry_child is not None and retry_child.generation_id is not None
        generation = db.get(VideoGeneration, retry_child.generation_id)
        assert generation is not None and generation.status == "succeeded"
        assert generation.script_version == 1
        assert generation.storyboard_version == 1
        assert generation.style_version == 1
        assert generation.preset_version == 1
