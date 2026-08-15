from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.ai.studio_worker import AIWorkerCrash, _lease_valid, _mark_retry, transition_state
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.media.service import storage_root, upload_generated_video
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.video.inspection import VideoInspectionError, inspect_video
from vayujit_api.video.models import VideoGeneration, VideoOutput
from vayujit_api.video.provider import video_provider


def _int_value(value: object, default: int) -> int:
    try:
        return int(value) if isinstance(value, (int, float, str)) else default
    except (TypeError, ValueError):
        return default


MAX_VIDEO_BYTES = 8_000_000


def execute_video_job(
    db: Session, job_id: Any, worker_id: str, *, crash_after_checkpoint: bool = False
) -> str:
    job = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id).with_for_update())
    if job is None or not _lease_valid(job, worker_id):
        db.rollback()
        return "lease_lost"
    raw = job.payload_json or {}
    generation_id = raw.get("video_generation_id")
    try:
        generation = db.get(VideoGeneration, generation_id) if generation_id else None
    except (TypeError, ValueError):
        generation = None
    output = (
        db.scalar(
            select(VideoOutput).where(VideoOutput.generation_id == generation.id).with_for_update()
        )
        if generation
        else None
    )
    owner = db.get(User, job.owner_id)
    if generation is None or output is None or owner is None:
        db.rollback()
        return _mark_retry(db, job, worker_id, "unknown_transient", "")
    expected_context = raw.get("context_fingerprint")
    if (
        expected_context
        and generation.context_fingerprint
        and expected_context != generation.context_fingerprint
    ):
        db.rollback()
        generation.status = "failed"
        generation.failure_code = "ai.video.source_changed"
        generation.safe_error_message = "The Video source context changed before execution."
        return _mark_retry(
            db,
            job,
            worker_id,
            "ai.video.source_changed",
            "The Video source context changed before execution.",
        )
    checkpoint = generation.checkpoint_json or {}
    checkpoint_path = checkpoint.get("path") if isinstance(checkpoint, dict) else None
    if not checkpoint_path:
        scenario = str(raw.get("failure_scenario") or "success")
        if scenario == "crash_before":
            raise AIWorkerCrash("simulated crash before provider execution")
        try:
            data, metadata = video_provider.generate(
                seed=str(raw.get("seed") or generation.id),
                width=_int_value(raw.get("width"), 1280),
                height=_int_value(raw.get("height"), 720),
                duration=_int_value(raw.get("duration_seconds"), 10),
                scenario=scenario,
            )
        except (RuntimeError, ValueError, TimeoutError):
            db.rollback()
            code = (
                "ai.video.unsupported_operation"
                if scenario == "unsupported_operation"
                else "ai.video.provider_unavailable"
            )
            message = (
                "The requested Video operation is unsupported."
                if scenario == "unsupported_operation"
                else "The local video provider is temporarily unavailable."
            )
            refreshed = db.get(VideoGeneration, generation.id)
            if refreshed is not None:
                refreshed.status = "retry_wait"
                refreshed.failure_code = code
                refreshed.safe_error_message = message
            return _mark_retry(db, job, worker_id, code, message)
        try:
            inspection = inspect_video(data)
            if inspection.size_bytes > MAX_VIDEO_BYTES:
                raise VideoInspectionError("Video output exceeds the safe size limit.")
        except VideoInspectionError:
            db.rollback()
            return _mark_retry(
                db,
                job,
                worker_id,
                "ai.video.invalid_output",
                "The deterministic video output failed validation.",
            )
        relative = Path("video-checkpoints") / owner.id.hex[:12] / f"{generation.id}.mp4"
        target = storage_root() / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        checksum = hashlib.sha256(data).hexdigest()
        generation.checkpoint_json = {
            "path": str(relative).replace("\\", "/"),
            "checksum": checksum,
            "size_bytes": len(data),
            "container": inspection.container,
            "mime_type": inspection.mime_type,
            "video_stream_count": inspection.video_stream_count,
            "audio_stream_count": inspection.audio_stream_count,
            "duration_seconds": inspection.duration_seconds,
            "width": inspection.width,
            "height": inspection.height,
            "frame_rate": inspection.frame_rate,
            "aspect_ratio": f"{inspection.width}:{inspection.height}",
            **metadata,
        }
        job.provider_result_json = {"checksum": checksum, "size_bytes": len(data), **metadata}
        job.provider_result_fingerprint = checksum
        job.checkpoint_fingerprint = checksum
        job.checkpoint_size_bytes = len(data)
        job.provider_completed_at = utcnow()
        generation.status = "validating"
        db.commit()
        if crash_after_checkpoint or scenario == "crash_after_checkpoint":
            raise AIWorkerCrash("simulated crash after provider checkpoint")
        checkpoint_path = str(relative).replace("\\", "/")
    target = storage_root() / str(checkpoint_path)
    data = target.read_bytes()
    checkpoint_data = generation.checkpoint_json or {}
    try:
        inspection = inspect_video(data)
        valid_checkpoint = (
            hashlib.sha256(data).hexdigest() == str(checkpoint_data.get("checksum"))
            and inspection.size_bytes == _int_value(checkpoint_data.get("size_bytes"), -1)
            and inspection.width == _int_value(checkpoint_data.get("width"), -1)
            and inspection.height == _int_value(checkpoint_data.get("height"), -1)
            and inspection.container == str(checkpoint_data.get("container"))
        )
    except (OSError, VideoInspectionError):
        valid_checkpoint = False
    if not valid_checkpoint:
        db.rollback()
        return _mark_retry(
            db,
            job,
            worker_id,
            "ai.video.checkpoint_invalid",
            "The stored video checkpoint is invalid.",
        )
    media = upload_generated_video(
        db,
        owner,
        f"video-{generation.id}.mp4",
        data,
        width=_int_value(checkpoint_data.get("width"), 1280),
        height=_int_value(checkpoint_data.get("height"), 720),
    )
    if job.state == "generating":
        job.state = transition_state(job.state, "validating")
    output.media_id = media.id
    output.checksum_sha256 = media.checksum_sha256
    output.size_bytes = media.size_bytes
    output.width = media.width
    output.height = media.height
    output.container = inspection.container
    output.video_stream_count = inspection.video_stream_count
    output.audio_stream_count = inspection.audio_stream_count
    output.frame_rate = inspection.frame_rate
    output.aspect_ratio = f"{inspection.width}:{inspection.height}"
    output.duration_seconds = round(inspection.duration_seconds)
    output.mime_type = inspection.mime_type
    output.status = "pending_review"
    generation.status = "succeeded"
    generation.completed_at = utcnow()
    generation.lease_owner = None
    generation.lease_expires_at = None
    job.artifact_id = None
    job.state = transition_state(job.state, "succeeded")
    job.lease_owner = None
    job.lease_expires_at = None
    job.completed_at = utcnow()
    job.updated_at = utcnow()
    db.commit()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_generation_completed",
        entity_type="video_generation",
        entity_id=generation.id,
        metadata={"media_id": str(media.id), "checksum": media.checksum_sha256},
    )
    return "succeeded"
