"""Durable AI Studio execution on the existing publishing worker runtime."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.ai.failures import (
    StudioProviderFailure,
    failure_spec,
    scenario_failure,
    validate_structured_output,
)
from vayujit_api.ai.image_models import AIImageOutput, AIImagePreset, AIImageStyle
from vayujit_api.ai.image_provider import image_provider
from vayujit_api.ai.models import AIGenerationRequest, GeneratedArtifact
from vayujit_api.ai.studio_models import (
    AIStudioGeneration,
    AIStudioJob,
    AIStudioJobAttempt,
    AIStudioOutput,
    BrandVoice,
)
from vayujit_api.ai.studio_service import (
    CHANNEL_RULES,
    _content,
    _context,
    _ensure_template,
    _quality,
)
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import image_dimensions
from vayujit_api.media.service import upload as upload_media
from vayujit_api.products.models import Product
from vayujit_api.publishing.scheduler_time import utcnow

MAX_IMAGE_CHECKPOINT_BYTES = 8_000_000

CLAIMABLE_STATES = {"queued", "retry_wait"}
AI_STATES = {
    "queued",
    "generating",
    "validating",
    "needs_review",
    "retry_wait",
    "succeeded",
    "failed",
    "cancelled",
    "stale",
}
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"generating", "cancelled", "stale"},
    "generating": {"validating", "retry_wait", "failed", "cancelled", "stale"},
    "validating": {
        "needs_review",
        "succeeded",
        "retry_wait",
        "failed",
        "cancelled",
        "stale",
    },
    "needs_review": {"retry_wait", "cancelled"},
    "retry_wait": {"generating", "cancelled", "stale"},
    "succeeded": set(),
    "failed": {"retry_wait", "cancelled"},
    "cancelled": set(),
    "stale": set(),
}
TERMINAL_STATES = {"succeeded", "failed", "cancelled", "stale"}
MAX_RETRY_DELAY_SECONDS = 300
MAX_RETRY_AFTER_SECONDS = 300


def parse_retry_after(value: object) -> float | None:
    try:
        parsed = float(cast(str | float | int, value)) if value is not None else None
    except (TypeError, ValueError):
        return None
    if parsed is None or parsed < 0 or parsed > MAX_RETRY_AFTER_SECONDS:
        return None
    return parsed


def calculate_backoff(
    attempt_number: int, retry_after: object = None, jitter: float = 0.0
) -> tuple[int, int]:
    calculated = min(MAX_RETRY_DELAY_SECONDS, 2 ** max(0, attempt_number - 1))
    remote = parse_retry_after(retry_after)
    jitter_factor = max(-0.25, min(0.25, jitter))
    applied = max(float(calculated), remote or 0.0) * (1.0 + jitter_factor)
    return calculated, max(0, min(MAX_RETRY_DELAY_SECONDS, int(round(applied))))


class AIProviderError(RuntimeError):
    """Safe provider failure retained for compatibility with worker adapters."""


class AIWorkerCrash(BaseException):
    """Controlled test-only crash that leaves a durable lease for recovery."""


def transition_state(current: str, target: str) -> str:
    if current not in AI_STATES or target not in AI_STATES:
        raise ValueError("Unknown AI Studio job state.")
    if target == current:
        return target
    if target not in LEGAL_TRANSITIONS[current]:
        raise ValueError(f"Illegal AI Studio job transition: {current} -> {target}.")
    return target


def _lease_valid(row: AIStudioJob, worker_id: str) -> bool:
    return (
        row.lease_owner == worker_id
        and row.lease_expires_at is not None
        and row.lease_expires_at > utcnow()
    )


def claim_ai_jobs(db: Session, worker_id: str, limit: int, lease_seconds: int) -> list[uuid.UUID]:
    now = utcnow()
    rows = list(
        db.scalars(
            select(AIStudioJob)
            .where(
                AIStudioJob.state.in_(CLAIMABLE_STATES),
                AIStudioJob.available_at <= now,
                or_(
                    AIStudioJob.lease_expires_at.is_(None),
                    AIStudioJob.lease_expires_at < now,
                ),
            )
            .order_by(AIStudioJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for row in rows:
        previous_state = row.state
        row.state = transition_state(row.state, "generating")
        row.lease_owner = worker_id
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.started_at = row.started_at or now
        row.attempt_count += 1
        if previous_state == "queued":
            row.failure_category = None
            row.retryable = False
        row.updated_at = now
        db.add(
            AIStudioJobAttempt(
                job_id=row.id,
                attempt_number=row.attempt_count,
                worker_id=worker_id,
                state="generating",
                correlation_id=row.correlation_id,
                created_at=now,
            )
        )
        record_event(
            db,
            actor_id=row.owner_id,
            action="ai.content_started",
            entity_type="ai_studio_job",
            entity_id=row.id,
            metadata={
                "attempt": row.attempt_count,
                "worker_id": worker_id,
                "retry": previous_state == "retry_wait",
                "correlation_id": row.correlation_id,
            },
        )
        if previous_state == "retry_wait":
            record_event(
                db,
                actor_id=row.owner_id,
                action="ai.content_retry_started",
                entity_type="ai_studio_job",
                entity_id=row.id,
                metadata={
                    "attempt": row.attempt_count,
                    "correlation_id": row.correlation_id,
                },
            )
    db.commit()
    return [row.id for row in rows]


def finish_ai_job(
    db: Session,
    job_id: uuid.UUID,
    worker_id: str,
    *,
    state: str,
    error_code: str | None = None,
    safe_message: str | None = None,
    failure_category: str | None = None,
    retryable: bool | None = None,
    calculated_delay: int | None = None,
    applied_delay: int | None = None,
    retry_after: int | None = None,
) -> bool:
    row = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id).with_for_update())
    if row is None or row.lease_owner != worker_id:
        db.rollback()
        return False
    now = utcnow()
    spec = failure_spec(failure_category or error_code or "unknown_permanent")
    row.state = transition_state(row.state, state)
    row.last_error_code = error_code
    if state != "succeeded":
        row.usage_metadata_json = {
            "provider": row.provider,
            "model": row.model,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cost_status": "unavailable",
            "cost": None,
            "success": False,
            "channel": row.channel,
            "content_type": row.content_type,
            "locale": row.locale,
        }
    row.safe_error_message = safe_message
    row.failure_category = failure_category or (error_code if error_code == spec.code else None)
    row.retryable = spec.retryable if retryable is None else retryable
    row.recovery_actions_json = list(spec.recovery_actions) if state != "succeeded" else []
    row.context_refresh_required = spec.context_refresh_required if state != "succeeded" else False
    row.retry_after_seconds = retry_after
    row.calculated_delay_seconds = calculated_delay
    row.applied_delay_seconds = applied_delay
    row.next_retry_at = (
        now + timedelta(seconds=applied_delay or 0) if state == "retry_wait" else None
    )
    row.available_at = row.next_retry_at or row.available_at
    row.completed_at = now if state in TERMINAL_STATES else None
    row.lease_owner = None
    row.lease_expires_at = None
    row.updated_at = now
    attempt = db.scalar(
        select(AIStudioJobAttempt).where(
            AIStudioJobAttempt.job_id == row.id,
            AIStudioJobAttempt.attempt_number == row.attempt_count,
        )
    )
    if attempt:
        attempt.state = state
        attempt.error_code = error_code
        attempt.safe_error_message = safe_message
        attempt.failure_category = failure_category or error_code
        attempt.retryable = row.retryable
        attempt.calculated_delay_seconds = calculated_delay
        attempt.applied_delay_seconds = applied_delay
        attempt.retry_after_seconds = retry_after
        attempt.checkpoint_fingerprint = row.provider_result_fingerprint
        attempt.correlation_id = row.correlation_id
        attempt.completed_at = now if state in TERMINAL_STATES else None
    generation = db.get(AIStudioGeneration, row.generation_id)
    if generation and state != "succeeded":
        generation.failure_category = failure_category or error_code
        generation.retryable = row.retryable
        generation.recovery_actions_json = list(spec.recovery_actions)
        generation.context_refresh_required = spec.context_refresh_required
        generation.error_code = error_code
        generation.safe_error_message = safe_message
    if state in {"failed", "cancelled", "stale"}:
        output = db.scalar(
            select(AIStudioOutput).where(
                AIStudioOutput.generation_id == row.generation_id,
                AIStudioOutput.product_id == row.product_id,
                AIStudioOutput.channel == row.channel,
                AIStudioOutput.content_type == row.content_type,
            )
        )
        if output and output.artifact_id is None and output.status not in TERMINAL_STATES:
            output.status = state
            output.error_code = error_code
            output.safe_error_message = safe_message
            if generation:
                generation.failed_outputs += 1
                if (
                    generation.completed_outputs + generation.failed_outputs
                    >= generation.total_outputs
                ):
                    generation.status = "completed" if generation.failed_outputs == 0 else state
                    generation.completed_at = now
        if state == "failed":
            record_event(
                db,
                actor_id=row.owner_id,
                action="ai.content_failed",
                entity_type="ai_studio_job",
                entity_id=row.id,
                metadata={
                    "error_code": error_code,
                    "failure_category": failure_category,
                    "attempt": row.attempt_count,
                    "correlation_id": row.correlation_id,
                },
            )
    elif state == "retry_wait":
        record_event(
            db,
            actor_id=row.owner_id,
            action="ai.content_retry_wait",
            entity_type="ai_studio_job",
            entity_id=row.id,
            metadata={
                "error_code": error_code,
                "failure_category": failure_category,
                "attempt": row.attempt_count,
                "calculated_delay_seconds": calculated_delay,
                "applied_delay_seconds": applied_delay,
                "retry_after_seconds": retry_after,
                "correlation_id": row.correlation_id,
            },
        )
    db.commit()
    return True


def _provider_call(
    context: dict[str, object],
    channel: str,
    content_type: str,
    instructions: str | None,
    voice: BrandVoice | None,
    keywords: list[str],
) -> tuple[dict[str, object], dict[str, object]]:
    content = _content(context, channel, content_type, instructions, voice, keywords)
    validation = _quality(content, channel, context, keywords)
    return content, validation


def _set_generation_outcome(
    db: Session, generation: AIStudioGeneration, output: AIStudioOutput, state: str
) -> None:
    output.status = state
    if state == "succeeded":
        generation.completed_outputs += 1
    elif state in {"failed", "cancelled", "stale"}:
        generation.failed_outputs += 1
    finished = generation.completed_outputs + generation.failed_outputs
    if finished >= generation.total_outputs:
        generation.status = "completed" if generation.failed_outputs == 0 else state
        generation.completed_at = utcnow()


def _mark_stale(db: Session, row: AIStudioJob, worker_id: str, message: str) -> str:
    finish_ai_job(
        db,
        row.id,
        worker_id,
        state="stale",
        error_code="stale_context",
        failure_category="stale_context",
        safe_message=message,
    )
    return "stale"


def _mark_retry(
    db: Session,
    row: AIStudioJob,
    worker_id: str,
    code: str,
    message: str,
    *,
    retry_after: object = None,
) -> str:
    spec = failure_spec(code)
    calculated, applied = calculate_backoff(row.attempt_count, retry_after)
    target = "retry_wait" if spec.retryable and row.attempt_count < row.max_attempts else "failed"
    retry_after_value = parse_retry_after(retry_after)
    finish_ai_job(
        db,
        row.id,
        worker_id,
        state=target,
        error_code=spec.code,
        failure_category=spec.code,
        safe_message=spec.safe_message if message == "" else message,
        retryable=spec.retryable,
        calculated_delay=calculated,
        applied_delay=applied,
        retry_after=(int(round(retry_after_value)) if retry_after_value is not None else None),
    )
    return target


def _scenario_content(
    content: dict[str, object], scenario: str, attempt_number: int
) -> dict[str, object]:
    mutated = dict(content)
    if scenario == "malformed_json_once" or scenario == "malformed_json_twice":
        return {"malformed": "provider output"}
    if scenario == "missing_required_field":
        mutated.pop("title", None)
    elif scenario == "wrong_field_type":
        mutated["bullets"] = "not-a-list"
    elif scenario == "truncated_output":
        return {"title": str(mutated.get("title") or "Generated title")}
    elif scenario == "oversized_output":
        mutated["description"] = "x" * 100_001
    return mutated


def _repair_content(
    content: dict[str, object],
    scenario: str,
    context: dict[str, object],
    channel: str,
    content_type: str,
    instructions: str,
    voice: BrandVoice | None,
    keywords: list[str],
) -> dict[str, object]:
    if scenario == "malformed_json_once":
        repaired, _ = _provider_call(context, channel, content_type, instructions, voice, keywords)
        return validate_structured_output(repaired, content_type=content_type)
    raise StudioProviderFailure("structured_validation_failed")


def execute_image_job(
    db: Session,
    job_id: uuid.UUID,
    worker_id: str,
    *,
    crash_after_checkpoint: bool = False,
) -> str:
    """Execute image work through the shared durable AI lease/checkpoint runtime."""
    row = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id).with_for_update())
    if row is None or not _lease_valid(row, worker_id):
        db.rollback()
        return "lease_lost"
    studio_output = db.scalar(
        select(AIStudioOutput)
        .where(
            AIStudioOutput.generation_id == row.generation_id,
            AIStudioOutput.product_id == row.product_id,
            AIStudioOutput.channel == row.channel,
            AIStudioOutput.content_type == "image",
        )
        .with_for_update()
    )
    output = db.scalar(
        select(AIImageOutput).where(AIImageOutput.job_id == row.id).with_for_update()
    )
    generation = db.get(AIStudioGeneration, row.generation_id)
    product = db.get(Product, row.product_id)
    from vayujit_api.identity.models import User

    owner = db.get(User, row.owner_id)
    if output is None or generation is None or product is None or owner is None:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unknown_transient", "")
    if output.media_id is not None:
        row.state = transition_state(row.state, "validating")
        row.state = transition_state(row.state, "succeeded")
        row.lease_owner = None
        row.lease_expires_at = None
        row.completed_at = utcnow()
        db.commit()
        return "succeeded"
    payload = row.payload_json
    brand = db.get(Brand, product.brand_id)
    if brand is None:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unknown_transient", "")
    if str(payload.get("scenario") or "") == "stale_source":
        db.rollback()
        return _mark_stale(
            db,
            row,
            worker_id,
            "The queued source Media or Product changed before execution.",
        )
    if payload.get("product_name") and payload.get("product_name") != product.name:
        db.rollback()
        return _mark_stale(db, row, worker_id, "Product context changed before image execution.")
    if payload.get("brand_name") and payload.get("brand_name") != brand.name:
        db.rollback()
        return _mark_stale(db, row, worker_id, "Brand context changed before image execution.")
    style_id = payload.get("style_id")
    if style_id:
        style = db.get(AIImageStyle, uuid.UUID(str(style_id)))
        if style is None or style.archived or style.version != payload.get("style_version"):
            db.rollback()
            return _mark_stale(
                db,
                row,
                worker_id,
                "The queued Image Style version is no longer current.",
            )
    preset_id = payload.get("preset_id")
    if preset_id:
        preset = db.get(AIImagePreset, uuid.UUID(str(preset_id)))
        if preset is None or preset.version != payload.get("preset_version"):
            db.rollback()
            return _mark_stale(
                db,
                row,
                worker_id,
                "The queued Image Preset version is no longer current.",
            )
    source_ids = [
        uuid.UUID(str(value)) for value in cast(list[object], payload.get("source_media_ids") or [])
    ]
    if source_ids:
        ready_count = (
            db.scalar(
                select(func.count())
                .select_from(MediaAsset)
                .where(
                    MediaAsset.owner_id == row.owner_id,
                    MediaAsset.id.in_(source_ids),
                    MediaAsset.status == "ready",
                )
            )
            or 0
        )
        if ready_count != len(set(source_ids)):
            db.rollback()
            return _mark_stale(
                db,
                row,
                worker_id,
                "A queued source Media asset is no longer available.",
            )
    try:
        if row.provider_result_json is None:
            image_bytes, metadata = image_provider.generate(
                operation=str(payload.get("operation")),
                width=cast(int, payload.get("width") or 1024),
                height=cast(int, payload.get("height") or 1024),
                seed=f"{row.context_fingerprint}:{row.id}",
                scenario=(
                    "throttle"
                    if str(payload.get("scenario") or "") == "throttle_once"
                    and row.attempt_count == 1
                    else (
                        "timeout"
                        if str(payload.get("scenario") or "") == "timeout_once"
                        and row.attempt_count == 1
                        else (
                            "unsupported_provider"
                            if str(payload.get("scenario") or "") == "permanent_provider_failure"
                            else str(payload.get("scenario") or "success")
                        )
                    )
                ),
            )
            checkpoint: dict[str, object] = {
                "image_base64": base64.b64encode(image_bytes).decode("ascii"),
                "metadata": metadata,
            }
            checkpoint_size = len(json.dumps(checkpoint, sort_keys=True).encode())
            if checkpoint_size > MAX_IMAGE_CHECKPOINT_BYTES:
                raise StudioProviderFailure("output_too_large")
            checkpoint_hash = hashlib.sha256(
                json.dumps(checkpoint, sort_keys=True).encode()
            ).hexdigest()
            row.provider_result_json = checkpoint
            row.provider_result_fingerprint = checkpoint_hash
            row.checkpoint_fingerprint = checkpoint_hash
            row.checkpoint_size_bytes = checkpoint_size
            row.provider_request_id = f"deterministic-image:{row.id}:{row.attempt_count}"
            row.provider_completed_at = utcnow()
            row.updated_at = utcnow()
            db.commit()
            if str(payload.get("scenario")) == "crash_after_result" or crash_after_checkpoint:
                raise AIWorkerCrash("simulated crash after image checkpoint")
        db.expire_all()
        row = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id).with_for_update())
        output = db.scalar(
            select(AIImageOutput).where(AIImageOutput.job_id == job_id).with_for_update()
        )
        if row is None or output is None or not _lease_valid(row, worker_id):
            db.rollback()
            return "lease_lost"
        saved_checkpoint: dict[str, object] = cast(
            dict[str, object], row.provider_result_json or {}
        )
        checkpoint_size = len(json.dumps(saved_checkpoint, sort_keys=True).encode())
        checkpoint_hash = hashlib.sha256(
            json.dumps(saved_checkpoint, sort_keys=True).encode()
        ).hexdigest()
        if (
            checkpoint_size > MAX_IMAGE_CHECKPOINT_BYTES
            or row.provider_result_fingerprint != checkpoint_hash
        ):
            raise StudioProviderFailure("checkpoint_invalid")
        try:
            image_bytes = base64.b64decode(
                str(saved_checkpoint.get("image_base64") or ""), validate=True
            )
        except (ValueError, binascii.Error) as exc:
            raise StudioProviderFailure("checkpoint_invalid") from exc
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n") or b"IEND" not in image_bytes[-32:]:
            raise StudioProviderFailure("checkpoint_invalid")
        metadata = cast(dict[str, object], saved_checkpoint.get("metadata") or {})
        if metadata.get("mime_type") not in {None, "image/png"}:
            raise StudioProviderFailure("checkpoint_invalid")
        if metadata.get("checksum_sha256") not in {
            None,
            hashlib.sha256(image_bytes).hexdigest(),
        }:
            raise StudioProviderFailure("checkpoint_invalid")
        if metadata.get("size_bytes") not in {None, len(image_bytes)}:
            raise StudioProviderFailure("checkpoint_invalid")
        try:
            width, height = image_dimensions(image_bytes, "image/png")
        except Exception as exc:
            raise StudioProviderFailure("checkpoint_invalid") from exc
        if metadata.get("width") not in {None, width} or metadata.get("height") not in {
            None,
            height,
        }:
            raise StudioProviderFailure("checkpoint_invalid")
        response = upload_media(db, owner, f"ai-image-{row.id}.png", "image/png", image_bytes)
        output.media_id = response.id
        output.actual_width = response.width
        output.actual_height = response.height
        output.mime_type = response.mime_type
        output.size_bytes = response.size_bytes
        output.checksum_sha256 = response.checksum_sha256
        output.provider_metadata_json = cast(
            dict[str, object], saved_checkpoint.get("metadata") or {}
        )
        output.status = "needs_review"
        if studio_output is not None:
            studio_output.status = "succeeded"
        row.state = transition_state(row.state, "validating")
        row.state = transition_state(row.state, "succeeded")
        row.lease_owner = None
        row.lease_expires_at = None
        row.completed_at = utcnow()
        generation.completed_outputs += 1
        generation.status = (
            "completed"
            if generation.completed_outputs + generation.failed_outputs >= generation.total_outputs
            else "running"
        )
        generation.completed_at = utcnow() if generation.status == "completed" else None
        record_event(
            db,
            actor_id=row.owner_id,
            action="ai.image_generated",
            entity_type="ai_image_output",
            entity_id=output.id,
            metadata={
                "media_id": str(output.media_id),
                "correlation_id": row.correlation_id,
            },
        )
        db.commit()
        return "succeeded"
    except AIWorkerCrash:
        raise
    except StudioProviderFailure as failure:
        db.rollback()
        if row is None:
            return "lease_lost"
        return _mark_retry(
            db, row, worker_id, failure.spec.code, "", retry_after=failure.retry_after
        )
    except Exception:
        db.rollback()
        if row is None:
            return "lease_lost"
        return _mark_retry(db, row, worker_id, "unknown_transient", "")


def execute_ai_job(
    db: Session,
    job_id: uuid.UUID,
    worker_id: str,
    *,
    crash_after_checkpoint: bool = False,
) -> str:
    existing = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id))
    if existing is not None and existing.job_type.startswith("ai_video_"):
        from vayujit_api.video.worker import execute_video_job

        return execute_video_job(
            db, job_id, worker_id, crash_after_checkpoint=crash_after_checkpoint
        )
    if existing is not None and existing.job_type.startswith("ai_image_"):
        return execute_image_job(
            db, job_id, worker_id, crash_after_checkpoint=crash_after_checkpoint
        )
    row = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id).with_for_update())
    if row is None or not _lease_valid(row, worker_id):
        db.rollback()
        return "lease_lost"
    if row.state == "cancelled":
        db.rollback()
        return "cancelled"
    generation = db.get(AIStudioGeneration, row.generation_id)
    product = db.get(Product, row.product_id)
    brand = db.get(Brand, product.brand_id) if product else None
    if generation is None or product is None or brand is None:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unknown_transient", "")
    try:
        current_context, current_fingerprint, voice = _context(
            db, row.owner_id, row.product_id, generation.brand_voice_id, row.locale
        )
    except Exception:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unknown_transient", "")
    if current_fingerprint != row.context_fingerprint:
        db.rollback()
        return _mark_stale(db, row, worker_id, "Product or Brand context changed before execution.")
    if (voice.version if voice else None) != row.brand_voice_version:
        db.rollback()
        return _mark_stale(
            db, row, worker_id, "The queued Brand Voice version is no longer current."
        )
    if row.channel not in CHANNEL_RULES:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unsupported_provider", "")
    payload = row.payload_json
    scenario = str(payload.get("failure_scenario") or "success")
    output = db.scalar(
        select(AIStudioOutput)
        .where(
            AIStudioOutput.generation_id == row.generation_id,
            AIStudioOutput.product_id == row.product_id,
            AIStudioOutput.channel == row.channel,
            AIStudioOutput.content_type == row.content_type,
        )
        .with_for_update()
    )
    if output is None:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unknown_transient", "")
    if output.artifact_id is not None:
        row.state = transition_state(row.state, "validating")
        db.commit()
        finish_ai_job(db, row.id, worker_id, state="succeeded")
        return "succeeded"
    row.state = transition_state(row.state, "validating")
    row.updated_at = utcnow()
    db.commit()
    if row.provider_result_json is None:
        try:
            current_size = len(json.dumps(current_context, default=str).encode())
            if scenario == "context_too_large" or current_size > 100_000:
                raise StudioProviderFailure("context_too_large")
            failure = scenario_failure(scenario, row.attempt_count)
            if failure is not None:
                raise failure
            instructions = str(
                payload.get("user_instructions") or generation.user_instructions or ""
            )
            raw_keywords = payload.get("keywords")
            keywords = [str(value) for value in cast(list[object], raw_keywords or [])]
            content, validation = _provider_call(
                current_context,
                row.channel,
                row.content_type,
                instructions,
                voice,
                keywords,
            )
            if scenario == "truncated_output":
                raise StudioProviderFailure("structured_validation_failed")
            if scenario in {
                "malformed_json_once",
                "malformed_json_twice",
                "missing_required_field",
                "wrong_field_type",
                "truncated_output",
                "oversized_output",
            }:
                content = _scenario_content(content, scenario, row.attempt_count)
            try:
                content = validate_structured_output(content, content_type=row.content_type)
            except StudioProviderFailure as validation_failure:
                record_event(
                    db,
                    actor_id=row.owner_id,
                    action="ai.content_validation_failed",
                    entity_type="ai_studio_job",
                    entity_id=row.id,
                    metadata={
                        "failure_category": validation_failure.spec.code,
                        "attempt": row.attempt_count,
                    },
                )
                if scenario == "malformed_json_once":
                    record_event(
                        db,
                        actor_id=row.owner_id,
                        action="ai.content_repair_started",
                        entity_type="ai_studio_job",
                        entity_id=row.id,
                        metadata={"attempt": row.attempt_count},
                    )
                    try:
                        content = _repair_content(
                            content,
                            scenario,
                            current_context,
                            row.channel,
                            row.content_type,
                            instructions,
                            voice,
                            keywords,
                        )
                        record_event(
                            db,
                            actor_id=row.owner_id,
                            action="ai.content_repair_succeeded",
                            entity_type="ai_studio_job",
                            entity_id=row.id,
                            metadata={"attempt": row.attempt_count},
                        )
                    except StudioProviderFailure:
                        record_event(
                            db,
                            actor_id=row.owner_id,
                            action="ai.content_repair_failed",
                            entity_type="ai_studio_job",
                            entity_id=row.id,
                            metadata={"attempt": row.attempt_count},
                        )
                        raise
                else:
                    raise
            checkpoint: dict[str, object] = {
                "content": content,
                "validation": validation,
                "provider": row.provider,
                "model": row.model,
            }
            checkpoint_fingerprint = hashlib.sha256(
                json.dumps(checkpoint, sort_keys=True, default=str).encode()
            ).hexdigest()
            locked = db.scalar(
                select(AIStudioJob).where(AIStudioJob.id == row.id).with_for_update()
            )
            if locked is None or not _lease_valid(locked, worker_id):
                db.rollback()
                return "lease_lost"
            locked.provider_result_json = checkpoint
            locked.provider_result_fingerprint = checkpoint_fingerprint
            locked.checkpoint_fingerprint = checkpoint_fingerprint
            locked.provider_request_id = f"deterministic:{locked.id}:{locked.attempt_count}"
            locked.provider_completed_at = utcnow()
            locked.usage_metadata_json = {
                "provider": row.provider,
                "model": row.model,
                "input_characters": len(
                    json.dumps(current_context, ensure_ascii=False, default=str)
                ),
                "output_characters": len(json.dumps(content, ensure_ascii=False, default=str)),
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "cost_status": "unavailable",
                "cost": None,
                "success": True,
                "channel": row.channel,
                "content_type": row.content_type,
                "locale": row.locale,
            }
            locked.updated_at = utcnow()
            db.commit()
            row = locked
            if crash_after_checkpoint:
                raise AIWorkerCrash("simulated crash after provider checkpoint")
        except AIWorkerCrash:
            raise
        except StudioProviderFailure as failure:
            db.rollback()
            return _mark_retry(
                db,
                row,
                worker_id,
                failure.spec.code,
                "",
                retry_after=failure.retry_after,
            )
        except Exception:
            db.rollback()
            return _mark_retry(db, row, worker_id, "unknown_transient", "")
    db.expire_all()
    row = db.scalar(select(AIStudioJob).where(AIStudioJob.id == job_id).with_for_update())
    if row is None or not _lease_valid(row, worker_id):
        db.rollback()
        return "lease_lost"
    output = db.scalar(
        select(AIStudioOutput)
        .where(
            AIStudioOutput.generation_id == row.generation_id,
            AIStudioOutput.product_id == row.product_id,
            AIStudioOutput.channel == row.channel,
            AIStudioOutput.content_type == row.content_type,
        )
        .with_for_update()
    )
    if output is None:
        db.rollback()
        return _mark_retry(db, row, worker_id, "unknown_transient", "")
    if row.state == "cancelled":
        db.rollback()
        return "cancelled"
    if output.artifact_id is not None:
        db.commit()
        finish_ai_job(db, row.id, worker_id, state="succeeded")
        return "succeeded"
    checkpoint = cast(dict[str, object], row.provider_result_json or {})
    content = validate_structured_output(
        checkpoint.get("content") or {}, content_type=row.content_type
    )
    validation = cast(dict[str, object], checkpoint.get("validation") or {})
    template = _ensure_template(db)
    stamp = utcnow()
    version = (
        db.scalar(
            select(func.max(GeneratedArtifact.version_number)).where(
                GeneratedArtifact.product_id == row.product_id
            )
        )
        or 0
    ) + 1
    request = AIGenerationRequest(
        owner_id=row.owner_id,
        brand_id=brand.id,
        product_id=product.id,
        prompt_template_id=template.id,
        provider_key=row.provider,
        status="completed",
        additional_instructions=str(
            payload.get("user_instructions") or generation.user_instructions or ""
        ),
        normalized_input_hash=row.context_fingerprint,
        created_at=stamp,
        updated_at=stamp,
        completed_at=stamp,
        selected_model=row.model,
        final_provider_key=row.provider,
        fallback_used=False,
        final_attempt_count=row.attempt_count,
        channel=row.channel,
        content_type=row.content_type,
        locale=row.locale,
        context_fingerprint=row.context_fingerprint,
        brand_voice_id=generation.brand_voice_id,
        preset_id=generation.preset_id,
        generation_reason=str(payload.get("generation_reason") or "worker"),
    )
    db.add(request)
    db.flush()
    source_artifact_id = payload.get("source_artifact_id")
    parent_artifact_id = None
    if source_artifact_id:
        try:
            parent_artifact_id = uuid.UUID(str(source_artifact_id))
        except (TypeError, ValueError):
            parent_artifact_id = None
    source_artifact_id = payload.get("source_artifact_id")
    parent_artifact_id = None
    if source_artifact_id:
        try:
            parent_artifact_id = uuid.UUID(str(source_artifact_id))
        except (TypeError, ValueError):
            parent_artifact_id = None
    source_version = payload.get("source_artifact_version")
    source_locale = payload.get("source_locale")
    source_context = payload.get("source_product_context")
    if parent_artifact_id and source_version is None:
        parent = db.get(GeneratedArtifact, parent_artifact_id)
        if parent is not None:
            source_version = parent.version_number
            source_locale = parent.locale
            source_context = {
                "product_id": str(parent.product_id),
                "source_locale": parent.locale,
            }

    artifact = GeneratedArtifact(
        owner_id=row.owner_id,
        brand_id=brand.id,
        product_id=product.id,
        generation_request_id=request.id,
        prompt_template_id=template.id,
        artifact_type=row.content_type,
        version_number=version,
        status="pending_review",
        content_json=content,
        validation_result=validation,
        provider_metadata={
            "provider": row.provider,
            "model": row.model,
            "deterministic": True,
            "brand_voice_version": row.brand_voice_version,
            "preset_version": row.preset_version,
        },
        channel=row.channel,
        content_type=row.content_type,
        locale=row.locale,
        context_fingerprint=row.context_fingerprint,
        brand_voice_id=generation.brand_voice_id,
        generation_reason=str(payload.get("generation_reason") or "worker"),
        parent_artifact_id=parent_artifact_id,
        source_artifact_version=(int(str(source_version)) if source_version is not None else None),
        source_locale=str(source_locale) if source_locale else None,
        source_product_context=(source_context if isinstance(source_context, dict) else None),
        source="ai_generated",
        user_instructions=str(
            payload.get("user_instructions") or generation.user_instructions or ""
        ),
        input_context_json=current_context,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(artifact)
    db.flush()
    output.artifact_id = artifact.id
    _set_generation_outcome(db, generation, output, "succeeded")
    row.artifact_id = artifact.id
    row.state = transition_state(row.state, "succeeded")
    row.completed_at = stamp
    row.lease_owner = None
    row.lease_expires_at = None
    row.updated_at = stamp
    attempt = db.scalar(
        select(AIStudioJobAttempt).where(
            AIStudioJobAttempt.job_id == row.id,
            AIStudioJobAttempt.attempt_number == row.attempt_count,
        )
    )
    if attempt:
        attempt.state = "succeeded"
        attempt.provider_request_id = row.provider_request_id
        attempt.checkpoint_fingerprint = row.provider_result_fingerprint
        attempt.completed_at = stamp
    record_event(
        db,
        actor_id=row.owner_id,
        action="ai.content_generated",
        entity_type="generated_artifact",
        entity_id=artifact.id,
        metadata={"job_id": str(row.id), "correlation_id": row.correlation_id},
    )
    generation_reason = str(payload.get("generation_reason") or "")
    if generation_reason in {"localization", "localized_generation"}:
        record_event(
            db,
            actor_id=row.owner_id,
            action="ai.localized_artifact_generated",
            entity_type="generated_artifact",
            entity_id=artifact.id,
            metadata=(
                {"parent_artifact_id": str(parent_artifact_id)} if parent_artifact_id else {}
            ),
        )
    if generation_reason == "translation":
        record_event(
            db,
            actor_id=row.owner_id,
            action="ai.translated_artifact_generated",
            entity_type="generated_artifact",
            entity_id=artifact.id,
            metadata={
                "parent_artifact_id": str(parent_artifact_id),
                "source_artifact_version": artifact.source_artifact_version,
                "source_locale": artifact.source_locale,
            },
        )
    if str(payload.get("generation_reason") or "") == "regeneration":
        record_event(
            db,
            actor_id=row.owner_id,
            action="ai.artifact_regenerated",
            entity_type="generated_artifact",
            entity_id=artifact.id,
            metadata=(
                {"parent_artifact_id": str(parent_artifact_id)} if parent_artifact_id else {}
            ),
        )
    db.commit()
    return "succeeded"


def recover_expired_ai_jobs(db: Session) -> int:
    now = utcnow()
    rows = list(
        db.scalars(
            select(AIStudioJob)
            .where(
                AIStudioJob.state.in_({"generating", "validating"}),
                AIStudioJob.lease_expires_at < now,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for row in rows:
        target = (
            "retry_wait"
            if row.attempt_count < row.max_attempts or row.provider_result_json
            else "failed"
        )
        row.state = transition_state(row.state, target)
        row.available_at = now
        row.next_retry_at = now if target == "retry_wait" else None
        row.lease_owner = None
        row.lease_expires_at = None
        row.last_error_code = "worker_lease_expired"
        row.failure_category = "unknown_transient"
        row.retryable = target == "retry_wait"
        row.safe_error_message = "AI worker lease expired; the job is safe to retry."
        row.updated_at = now
    db.commit()
    return len(rows)


def run_ai_jobs_once(db: Session, worker_id: str, limit: int = 4, lease_seconds: int = 120) -> int:
    recovered = recover_expired_ai_jobs(db)
    claimed = claim_ai_jobs(db, worker_id, limit, lease_seconds)
    for job_id in claimed:
        execute_ai_job(db, job_id, worker_id)
    # Keep bulk projections durable without introducing another worker path.
    from vayujit_api.ai.bulk_models import AIStudioBulkOperation
    from vayujit_api.ai.bulk_service import _sync_operation

    for operation in db.scalars(select(AIStudioBulkOperation)).all():
        _sync_operation(db, operation)
    db.commit()
    return recovered + len(claimed)


ProviderCallable = Callable[..., tuple[dict[str, object], dict[str, object]]]
