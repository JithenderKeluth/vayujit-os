from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration_fixture
from test_ai_video_bulk_restart import _recreated_client

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.core.database import Base
from vayujit_api.video.models import VideoGeneration

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_api_and_worker_restart_preserve_durable_work(client: Any) -> None:
    context = integration_fixture.setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/queue",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "video_type": "product_showcase",
            "target_channel": "youtube",
            "resolution": "320x240",
            "duration_seconds": 2,
            "idempotency_key": "final-restart-durable-video",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    generation_id = queued.json()["id"]

    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None and generation.status == "queued"

    with _recreated_client(integration_fixture.factory, client) as restarted:
        health = restarted.get("/api/v1/health", headers=ORIGIN)
        assert health.status_code == 200, health.text
        persisted = restarted.get(f"/api/v1/ai/video/generations/{generation_id}", headers=ORIGIN)
        assert persisted.status_code == 200, persisted.text
        assert persisted.json()["status"] == "queued"

    with integration_fixture.factory() as db:
        assert run_ai_jobs_once(db, "final-restart-worker", limit=1) == 1
        assert run_ai_jobs_once(db, "final-restart-worker-replay", limit=1) == 0
        completed = db.get(VideoGeneration, generation_id)
        assert completed is not None and completed.status == "succeeded"

    with _recreated_client(integration_fixture.factory, client) as restarted:
        completed_response = restarted.get(
            f"/api/v1/ai/video/generations/{generation_id}", headers=ORIGIN
        )
        assert completed_response.status_code == 200, completed_response.text
        assert completed_response.json()["status"] == "succeeded"
        assert all(
            marker not in completed_response.text.lower()
            for marker in ("traceback", "postgresql://")
        )

    durable_tables = {
        "ai_studio_jobs",
        "ai_studio_job_attempts",
        "video_generations",
        "video_outputs",
        "publishing_jobs",
        "publishing_job_attempts",
        "publishing_executions",
        "campaign_activity_reschedules",
        "marketing_channel_executions",
        "ad_jobs",
    }
    assert durable_tables <= set(Base.metadata.tables)
