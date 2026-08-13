from __future__ import annotations

import pytest
import test_ai_integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.video.models import VideoGeneration

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def queue_payload(context: dict[str, dict[str, str]], **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "video_type": "product_showcase",
        "target_channel": "youtube",
        "resolution": "320x240",
        "duration_seconds": 2,
        "idempotency_key": "video-acceptance-1",
    }
    payload.update(overrides)
    return payload


def test_storyboard_versioned_editor_approval_and_exact_generation_lineage(client) -> None:
    context = setup_context(client)
    storyboard = client.post(
        "/api/v1/ai/video/storyboards",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "scenes": [
                {
                    "stable_key": "hook",
                    "scene_order": 1,
                    "duration_seconds": 2,
                    "scene_text": "Hook",
                }
            ],
        },
        headers=ORIGIN,
    )
    assert storyboard.status_code == 201, storyboard.text
    row = storyboard.json()
    assert row["version"] == 1 and row["ready"] is True
    edited = client.put(
        f"/api/v1/ai/video/storyboards/{row['id']}",
        json={
            "expected_row_version": row["row_version"],
            "scenes": [
                {
                    "stable_key": "hook",
                    "scene_order": 1,
                    "duration_seconds": 2,
                    "scene_text": "Updated",
                },
                {"stable_key": "cta", "scene_order": 2, "duration_seconds": 2, "cta": "Learn more"},
            ],
        },
        headers=ORIGIN,
    )
    assert edited.status_code == 200, edited.text
    approved = client.post(
        f"/api/v1/ai/video/storyboards/{row['id']}/approve",
        json={"expected_row_version": edited.json()["row_version"]},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    queued = client.post(
        "/api/v1/ai/video/queue",
        json=queue_payload(context, storyboard_id=row["id"], storyboard_version=1),
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    with db_session() as db:
        generation = db.get(VideoGeneration, queued.json()["id"])
        assert generation is not None
        assert str(generation.storyboard_id) == row["id"] and generation.storyboard_version == 1
        assert generation.context_fingerprint


def test_regeneration_captions_compare_and_exact_version_safety(client) -> None:
    context = setup_context(client)
    queued = client.post("/api/v1/ai/video/queue", json=queue_payload(context), headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    generation_id = queued.json()["id"]
    with db_session() as db:
        assert run_ai_jobs_once(db, "video-acceptance-worker", limit=1) == 1
    rejected = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/reject",
        json={"feedback": "pacing"},
        headers=ORIGIN,
    )
    assert rejected.status_code == 200, rejected.text
    regenerated = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/regenerate",
        json={"reason": "rejected_feedback", "feedback": "Please tighten pacing."},
        headers=ORIGIN,
    )
    assert regenerated.status_code == 202, regenerated.text
    child_id = regenerated.json()["id"]
    assert child_id != generation_id
    with db_session() as db:
        child = db.get(VideoGeneration, child_id)
        parent = db.get(VideoGeneration, generation_id)
        assert child is not None and parent is not None
        assert child.parent_generation_id == parent.id
        assert child.rejection_feedback == "Please tighten pacing."
    caption = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/captions",
        json={"locale": "en-IN", "caption_text": "Hello", "timing": [{"start": 0, "end": 1}]},
        headers=ORIGIN,
    )
    assert caption.status_code == 201, caption.text
    caption_id = caption.json()["id"]
    approved_caption = client.post(
        f"/api/v1/ai/video/captions/{caption_id}/approve", headers=ORIGIN
    )
    assert approved_caption.status_code == 200
    exported = client.get(f"/api/v1/ai/video/captions/{caption_id}/export", headers=ORIGIN)
    assert exported.status_code == 200 and exported.json()["content"].startswith("WEBVTT")
    comparison = client.get(
        f"/api/v1/ai/video/generations/{generation_id}/compare/{child_id}", headers=ORIGIN
    )
    assert comparison.status_code == 200 and comparison.json()["perceptual_quality_score"] is None


def test_unapproved_exact_artifact_is_rejected(client) -> None:
    context = setup_context(client)
    generated = client.post(
        "/api/v1/ai/generations",
        json={"product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert generated.status_code == 201, generated.text
    artifact_id = generated.json()["artifact_id"]
    with db_session() as db:
        artifact = db.get(GeneratedArtifact, artifact_id)
        assert artifact is not None
        artifact.status = "pending_review"
        version = artifact.version_number
        db.commit()
    response = client.post(
        "/api/v1/ai/video/queue",
        json=queue_payload(
            context,
            idempotency_key="video-unapproved-artifact",
            source_artifact_id=artifact_id,
            source_artifact_version=version,
        ),
        headers=ORIGIN,
    )
    assert response.status_code == 409 and "approved" in response.text.lower()


def test_stale_context_is_rejected_before_provider_execution(client) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/queue",
        json=queue_payload(context, idempotency_key="video-stale-context"),
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    generation_id = queued.json()["id"]
    with db_session() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None
        generation.context_fingerprint = "changed-context"
        db.commit()
        assert run_ai_jobs_once(db, "video-stale-worker", limit=1) == 1
        job = db.scalar(
            select(AIStudioJob).where(
                AIStudioJob.idempotency_key == "video-job:video-stale-context"
            )
        )
        assert job is not None and job.failure_category == "ai.video.source_changed"
        assert generation.status in {"retry_wait", "failed"}
