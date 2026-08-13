from __future__ import annotations

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.media.models import MediaAsset
from vayujit_api.video.models import VideoGeneration, VideoOutput, VideoUsage

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def queue(client, context, **overrides):
    payload = {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "video_type": "product_showcase",
        "target_channel": "youtube",
        "resolution": "320x240",
        "duration_seconds": 2,
        "idempotency_key": "video-integration-1",
    }
    payload.update(overrides)
    return client.post("/api/v1/ai/video/queue", json=payload, headers=ORIGIN)


def test_video_preview_queue_worker_review_and_diagnostics(client) -> None:
    context = setup_context(client)
    preview = client.post(
        "/api/v1/ai/video/preview",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "resolution": "320x240",
            "duration_seconds": 2,
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200
    assert preview.json()["provider"] == "deterministic_video_local"
    assert preview.json()["cost_status"] == "unavailable"
    queued = queue(client, context)
    assert queued.status_code == 202
    generation_id = queued.json()["id"]
    with db_session() as db:
        assert run_ai_jobs_once(db, "video-integration-worker", limit=1) == 1
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None and generation.status == "succeeded"
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation_id))
        assert output is not None and output.media_id is not None
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
                select(func.count()).select_from(MediaAsset).where(MediaAsset.id == output.media_id)
            )
            == 1
        )
        usage = db.scalar(select(VideoUsage).where(VideoUsage.generation_id == generation_id))
        assert usage is not None and usage.cost_status == "unavailable"
    approved = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200
    assert approved.json()["output_media_id"] is not None
    diagnostics = client.get("/api/v1/ai/video/diagnostics", headers=ORIGIN)
    assert diagnostics.status_code == 200
    assert diagnostics.json()["live_provider_supported"] is False


def test_video_idempotency_and_safe_invalid_source(client) -> None:
    context = setup_context(client)
    first = queue(client, context)
    second = queue(client, context)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    invalid = queue(
        client, context, idempotency_key="invalid-video", failure_scenario="invalid_video"
    )
    assert invalid.status_code == 202
    with db_session() as db:
        run_ai_jobs_once(db, "video-invalid-worker", limit=4)
        row = db.scalar(select(VideoGeneration).where(VideoGeneration.id == invalid.json()["id"]))
        assert row is not None
