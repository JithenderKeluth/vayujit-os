from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.core.database import get_session
from vayujit_api.main import create_app
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def _products(client: TestClient, context: dict[str, Any]) -> list[str]:
    response = client.post(
        "/api/v1/products",
        json={
            "name": "Restart Product",
            "product_type": "physical",
            "short_description": "A second restart fixture product",
            "description": "A second restart fixture product.",
            "category": "Outdoors",
            "tags": ["restart"],
            "price_amount": "19.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return [context["product"]["id"], response.json()["id"]]


def _recreated_client(factory: sessionmaker[Session], source: TestClient) -> TestClient:
    def session():
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = session
    replacement = TestClient(app)
    replacement.cookies.update(source.cookies)
    return replacement


def _payload(product_ids: list[str], key: str) -> dict[str, Any]:
    return {
        "product_ids": product_ids,
        "video_types": ["youtube_video"],
        "targets": ["youtube", "instagram"],
        "duration_seconds": 2,
        "resolution": "320x240",
        "idempotency_key": key,
    }


def test_bulk_api_restart_preserves_mixed_parent_and_child_state(client: TestClient) -> None:
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    product_ids = _products(client, context)
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json=_payload(product_ids, "restart-api"),
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]

    with test_ai_integration.factory() as db:
        children = list(
            db.scalars(
                select(VideoBulkChild)
                .where(VideoBulkChild.bulk_id == bulk_id)
                .order_by(VideoBulkChild.output_ordinal)
            )
        )
        assert len(children) == 4
        for index, child in enumerate(children):
            generation = db.get(VideoGeneration, child.generation_id)
            job = db.get(AIStudioJob, child.job_id)
            assert generation is not None and job is not None
            if index == 0:
                child.status = "succeeded"
                generation.status = "succeeded"
                job.state = "succeeded"
                child.completed_at = generation.completed_at = job.completed_at = (
                    generation.updated_at
                )
            elif index == 1:
                child.status = "retry_wait"
                child.retryable = True
                child.retry_count = 2
                child.failure_code = "ai.video.provider_unavailable"
                child.recovery_state = "retry_scheduled"
                generation.status = "retry_wait"
                job.state = "retry_wait"
                job.retryable = True
                job.attempt_count = 2
            elif index == 2:
                child.status = "cancelled"
                child.cancellation_requested = True
                generation.status = "cancelled"
                job.state = "cancelled"
            child.updated_at = generation.updated_at = job.updated_at
        child_ids = [child.id for child in children]
        job_ids = [child.job_id for child in children]
        db.commit()

    with _recreated_client(test_ai_integration.factory, client) as restarted:
        status = restarted.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
        assert status.status_code == 200, status.text
        body = status.json()
        assert body["id"] == bulk_id
        assert body["child_count"] == 4
        assert body["succeeded_count"] == 1
        assert body["retry_wait_count"] == 1
        assert body["cancelled_count"] == 1
        assert {item["status"] for item in body["children"]} == {
            "succeeded",
            "retry_wait",
            "cancelled",
            "queued",
        }
        duplicate = restarted.post(
            "/api/v1/ai/video/bulk",
            json=_payload(product_ids, "restart-api"),
            headers=ORIGIN,
        )
        assert duplicate.status_code in {200, 202} and duplicate.json()["idempotent_reuse"] is True

    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(VideoBulkOperation)) == 1
        assert db.scalar(select(func.count()).select_from(VideoBulkChild)) == 4
        assert [
            child.id
            for child in db.scalars(select(VideoBulkChild).order_by(VideoBulkChild.output_ordinal))
        ] == child_ids
        assert [
            child.job_id
            for child in db.scalars(select(VideoBulkChild).order_by(VideoBulkChild.output_ordinal))
        ] == job_ids
        assert db.scalar(select(func.count()).select_from(VideoGeneration)) == 4
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 4
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 0


def test_bulk_worker_restart_executes_persisted_queued_child_once(client: TestClient) -> None:
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    product_ids = _products(client, context)
    queued = client.post(
        "/api/v1/ai/video/bulk", json=_payload(product_ids, "restart-worker"), headers=ORIGIN
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]

    from vayujit_api.ai.studio_worker import run_ai_jobs_once

    with test_ai_integration.factory() as db:
        first = run_ai_jobs_once(db, "worker-before-restart", limit=1)
        assert first == 1
        succeeded_generations = list(
            db.scalars(
                select(VideoGeneration)
                .join(VideoBulkChild, VideoBulkChild.generation_id == VideoGeneration.id)
                .where(VideoBulkChild.bulk_id == bulk_id, VideoGeneration.status == "succeeded")
            )
        )
        assert len(succeeded_generations) == 1
        succeeded_id = succeeded_generations[0].id
        succeeded_output_id = db.scalar(
            select(VideoOutput.id).where(VideoOutput.generation_id == succeeded_id)
        )
        children = list(
            db.scalars(
                select(VideoBulkChild)
                .where(VideoBulkChild.bulk_id == bulk_id)
                .order_by(VideoBulkChild.output_ordinal)
            )
        )
        retry_child = children[1]
        retry_generation = db.get(VideoGeneration, retry_child.generation_id)
        retry_job = db.get(AIStudioJob, retry_child.job_id)
        assert retry_generation is not None and retry_job is not None
        retry_child.status = "retry_wait"
        retry_child.retryable = True
        retry_child.recovery_state = "retry_scheduled"
        retry_generation.status = "retry_wait"
        retry_job.state = "retry_wait"
        retry_job.available_at = utcnow()
        retry_job.lease_owner = None
        retry_job.lease_expires_at = None
        cancelled_child = children[2]
        cancelled_generation = db.get(VideoGeneration, cancelled_child.generation_id)
        cancelled_job = db.get(AIStudioJob, cancelled_child.job_id)
        assert cancelled_generation is not None and cancelled_job is not None
        cancelled_child.status = "cancelled"
        cancelled_child.cancellation_requested = True
        cancelled_generation.status = "cancelled"
        cancelled_job.state = "cancelled"
        cancelled_job.lease_owner = None
        cancelled_job.lease_expires_at = None
        db.commit()

    with test_ai_integration.factory() as db:
        second = run_ai_jobs_once(db, "worker-after-restart", limit=10)
        assert second == 2
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 4
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 3
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIStudioJob)
                .where(AIStudioJob.state == "succeeded")
            )
            == 3
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIStudioJob)
                .where(AIStudioJob.state == "cancelled")
            )
            == 1
        )
        assert (
            db.scalar(select(VideoOutput.id).where(VideoOutput.generation_id == succeeded_id))
            == succeeded_output_id
        )

    status = client.get(f"/api/v1/ai/video/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200
    assert status.json()["succeeded_count"] == 3
    assert status.json()["cancelled_count"] == 1
    assert status.json()["completed_count"] == 4
