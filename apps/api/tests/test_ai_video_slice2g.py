from __future__ import annotations

import hashlib
import pathlib
import uuid

import pytest
import test_ai_integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.core.config import get_settings
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import storage_path
from vayujit_api.video.inspection import inspect_video
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def queue(
    client,
    context,
    *,
    video_type: str,
    resolution: str,
    duration: int,
    key: str,
    **overrides,
):
    payload = {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "video_type": video_type,
        "target_channel": "youtube",
        "resolution": resolution,
        "duration_seconds": duration,
        "idempotency_key": key,
    }
    payload.update(overrides)
    response = client.post("/api/v1/ai/video/queue", json=payload, headers=ORIGIN)
    assert response.status_code == 202, response.text
    return response.json()


def complete(client, context, **kwargs):
    result = queue(client, context, **kwargs)
    with session() as db:
        assert run_ai_jobs_once(db, f"slice2g-{kwargs['key']}", limit=1) == 1
    return result


def output_for(generation_id: str):
    with session() as db:
        generation = db.get(VideoGeneration, uuid.UUID(generation_id))
        assert generation is not None
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation.id))
        assert output is not None and output.media_id is not None
        media = db.get(MediaAsset, output.media_id)
        assert media is not None
        data = storage_path(media.storage_key).read_bytes()
        return generation, output, media, data


def test_product_showcase_dedicated_lineage_and_review(client):
    context = setup_context(client)
    script = client.post(
        "/api/v1/ai/video/scripts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "name": "Showcase",
            "hook": "Carry better",
            "introduction": "Insulated for every trip",
            "narration": "A durable bottle.",
            "on_screen_text": "Reusable",
            "cta": "Shop now",
            "outro": "Built for the journey",
            "target_duration_seconds": 2,
        },
        headers=ORIGIN,
    )
    assert script.status_code == 201, script.text
    script_value = script.json()
    assert (
        client.post(
            f"/api/v1/ai/video/scripts/{script_value['id']}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
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
                    "scene_text": "Carry better",
                    "narration": "A durable bottle.",
                }
            ],
        },
        headers=ORIGIN,
    )
    assert storyboard.status_code == 201, storyboard.text
    board = storyboard.json()
    approved_board = client.post(
        f"/api/v1/ai/video/storyboards/{board['id']}/approve",
        json={"expected_row_version": board["row_version"]},
        headers=ORIGIN,
    )
    assert approved_board.status_code == 200, approved_board.text
    style = client.post(
        "/api/v1/ai/video/styles",
        json={
            "brand_id": context["brand"]["id"],
            "name": "Showcase Style",
            "config": {"motion_style": "steady", "pacing": "measured", "cta_style": "clear"},
            "is_default": True,
        },
        headers=ORIGIN,
    )
    assert style.status_code == 201, style.text
    style_value = style.json()
    preset = client.post(
        "/api/v1/ai/video/presets",
        json={
            "name": "Showcase Preset",
            "video_type": "product_showcase",
            "target_channel": "youtube",
            "resolution": "320x240",
            "target_duration_seconds": 2,
            "max_duration_seconds": 10,
            "style_id": style_value["id"],
        },
        headers=ORIGIN,
    )
    assert preset.status_code == 201, preset.text
    preset_value = preset.json()
    queued = complete(
        client,
        context,
        video_type="product_showcase",
        resolution="320x240",
        duration=2,
        key="slice2g-showcase",
        script_id=script_value["id"],
        script_version=script_value["version"],
        storyboard_id=board["id"],
        storyboard_version=board["version"],
        style_id=style_value["id"],
        style_version=style_value["version"],
        preset_id=preset_value["id"],
    )
    generation, output, media, data = output_for(queued["id"])
    assert generation.script_id == uuid.UUID(script_value["id"])
    assert generation.script_version == script_value["version"]
    assert generation.storyboard_id == uuid.UUID(board["id"])
    assert generation.storyboard_version == board["version"]
    assert generation.style_id == uuid.UUID(style_value["id"])
    assert generation.preset_id == uuid.UUID(preset_value["id"])
    inspected = inspect_video(data)
    assert output.mime_type == "video/mp4" and inspected.container == "mp4"
    assert output.checksum_sha256 == hashlib.sha256(data).hexdigest()
    approved = client.post(
        f"/api/v1/ai/video/generations/{queued['id']}/approve",
        json={"feedback": None},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    assert media.checksum_sha256 == hashlib.sha256(data).hexdigest()


def test_slideshow_and_short_form_dedicated_shapes(client):
    context = setup_context(client)
    slideshow = complete(
        client,
        context,
        video_type="slideshow",
        resolution="320x240",
        duration=3,
        key="slice2g-slideshow",
    )
    short = complete(
        client,
        context,
        video_type="youtube_short",
        resolution="240x320",
        duration=3,
        key="slice2g-short",
    )
    for value in (slideshow, short):
        generation, output, _media, data = output_for(value["id"])
        inspected = inspect_video(data)
        assert output.mime_type == "video/mp4"
        assert output.width == inspected.width and output.height == inspected.height
        assert output.duration_seconds == generation.duration_seconds == inspected.duration_seconds


def test_promotional_video_keeps_canonical_context_and_regeneration_lineage(client):
    context = setup_context(client)
    first = complete(
        client,
        context,
        video_type="promotional_video",
        resolution="320x240",
        duration=2,
        key="slice2g-promo",
    )
    first_generation, _output, _media, _data = output_for(first["id"])
    rejected = client.post(
        f"/api/v1/ai/video/generations/{first['id']}/reject",
        json={"feedback": "Tighten CTA"},
        headers=ORIGIN,
    )
    assert rejected.status_code == 200
    second = client.post(
        f"/api/v1/ai/video/generations/{first['id']}/regenerate",
        json={"reason": "rejected_feedback", "feedback": "Tighten CTA"},
        headers=ORIGIN,
    )
    assert second.status_code == 202
    with session() as db:
        child = db.get(VideoGeneration, uuid.UUID(second.json()["id"]))
        assert child is not None
        assert child.parent_generation_id == first_generation.id
        assert child.rejection_feedback == "Tighten CTA"
        assert child.product_id == first_generation.product_id
        assert child.brand_id == first_generation.brand_id


def test_cleanup_is_explicit_idempotent_and_confined(client):
    setup_context(client)
    safe = (
        pathlib.Path(get_settings().media_storage_directory) / "slice2g" / ("b" * 64 + ".mp4.tmp")
    )
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_bytes(b"temp")
    first = client.post("/api/v1/ai/video/cleanup", json={"paths": [str(safe)]}, headers=ORIGIN)
    assert first.status_code == 200 and first.json()["removed"] == 1
    second = client.post("/api/v1/ai/video/cleanup", json={"paths": [str(safe)]}, headers=ORIGIN)
    assert second.status_code == 200 and second.json()["removed"] == 0
    assert not safe.exists()
    outside = client.post(
        "/api/v1/ai/video/cleanup",
        json={"paths": [str(pathlib.Path.cwd() / "unsafe.tmp")]},
        headers=ORIGIN,
    )
    assert outside.status_code == 200 and outside.json()["skipped"] == 1
