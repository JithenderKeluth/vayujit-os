"""Durable bulk-generation orchestration layered on the existing AI worker."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import (
    AIStudioGeneration,
    AIStudioJob,
    AIStudioOutput,
    BrandVoice,
    GenerationPreset,
)
from vayujit_api.ai.studio_schemas import (
    StudioBulkOutputResponse,
    StudioBulkPreviewResponse,
    StudioBulkRequest,
    StudioBulkStatusResponse,
    StudioGenerateRequest,
)
from vayujit_api.ai.studio_service import _owned_product, generate_studio
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.products.models import Product

BULK_LIMITS = {
    "max_products": 50,
    "max_channels": 6,
    "max_content_types": 12,
    "max_outputs": 300,
    "max_instructions": 2000,
    "max_jobs": 300,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _instruction_fingerprint(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def _plan_key(data: StudioBulkRequest) -> str:
    payload = {
        "products": [str(item) for item in data.product_ids],
        "channels": list(data.channels),
        "content_types": list(data.content_types),
        "brand_voice_id": str(data.brand_voice_id) if data.brand_voice_id else None,
        "preset_id": str(data.preset_id) if data.preset_id else None,
        "locale": data.locale,
        "provider_key": data.provider_key,
        "model": data.model,
        "instructions": _instruction_fingerprint(data.user_instructions),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _preset_and_voice(
    db: Session, owner: User, data: StudioBulkRequest
) -> tuple[GenerationPreset | None, BrandVoice | None]:
    preset = None
    if data.preset_id:
        preset = db.scalar(
            select(GenerationPreset).where(
                GenerationPreset.id == data.preset_id,
                (GenerationPreset.owner_id == owner.id) | GenerationPreset.is_system.is_(True),
            )
        )
        if preset is None:
            raise HTTPException(404, "Preset not found.")
        if preset.archived:
            raise HTTPException(409, "Archived presets cannot be selected.")
    selected_voice_id = data.brand_voice_id or (preset.brand_voice_id if preset else None)
    voice = None
    if selected_voice_id:
        voice = db.scalar(
            select(BrandVoice).where(
                BrandVoice.id == selected_voice_id,
                BrandVoice.owner_id == owner.id,
                BrandVoice.archived.is_(False),
            )
        )
        if voice is None:
            raise HTTPException(404, "Brand Voice not found.")
    return preset, voice


def _validate_limits(data: StudioBulkRequest) -> None:
    total = len(data.product_ids) * len(data.channels) * len(data.content_types)
    if len(data.product_ids) > BULK_LIMITS["max_products"]:
        raise HTTPException(422, "Bulk generation exceeds the Product limit.")
    if len(data.channels) > BULK_LIMITS["max_channels"]:
        raise HTTPException(422, "Bulk generation exceeds the channel limit.")
    if len(data.content_types) > BULK_LIMITS["max_content_types"]:
        raise HTTPException(422, "Bulk generation exceeds the content-type limit.")
    if total > BULK_LIMITS["max_outputs"] or total > BULK_LIMITS["max_jobs"]:
        raise HTTPException(422, "Bulk generation exceeds the output limit.")
    if data.user_instructions and len(data.user_instructions) > BULK_LIMITS["max_instructions"]:
        raise HTTPException(422, "Bulk instructions exceed the safe size limit.")
    if "canonical" in data.channels and len(data.channels) > 1:
        raise HTTPException(422, "Canonical content must be generated separately.")
    if data.provider_key != "deterministic_mock_v1":
        raise HTTPException(409, "Bulk Studio currently requires the local deterministic provider.")


def preview_bulk(db: Session, owner: User, data: StudioBulkRequest) -> StudioBulkPreviewResponse:
    _validate_limits(data)
    preset, voice = _preset_and_voice(db, owner, data)
    products = []
    warnings: list[str] = []
    for product_id in data.product_ids:
        product, brand = _owned_product(db, owner.id, product_id)
        products.append(product)
        if product.status != "active":
            warnings.append(f"Product {product.name} is not active.")
        if voice and voice.brand_id and voice.brand_id != brand.id:
            raise HTTPException(409, "Brand Voice does not match every selected Product brand.")
    total = len(products) * len(data.channels) * len(data.content_types)
    return StudioBulkPreviewResponse(
        product_ids=list(data.product_ids),
        channels=list(data.channels),
        content_types=list(data.content_types),
        product_count=len(products),
        channel_count=len(data.channels),
        content_type_count=len(data.content_types),
        total_outputs=total,
        brand_voice_id=voice.id if voice else None,
        brand_voice_version=voice.version if voice else None,
        preset_id=preset.id if preset else None,
        preset_version=preset.version if preset else None,
        locale=data.locale,
        provider_key=data.provider_key,
        model=data.model
        or (
            preset.preferred_model
            if preset and preset.preferred_model
            else "studio-deterministic-v1"
        ),
        estimated_provider_calls=total,
        estimated_cost="unavailable",
        blockers=[],
        warnings=warnings,
        operation_limits=BULK_LIMITS,
    )


def _output_key(product_id: uuid.UUID, channel: str, content_type: str) -> str:
    return f"{product_id}:{channel}:{content_type}"


def create_bulk(db: Session, owner: User, data: StudioBulkRequest) -> AIStudioBulkOperation:
    _validate_limits(data)
    key = data.idempotency_key or f"bulk:{_plan_key(data)}"
    existing = db.scalar(
        select(AIStudioBulkOperation).where(
            AIStudioBulkOperation.owner_id == owner.id,
            AIStudioBulkOperation.idempotency_key == key,
        )
    )
    if existing:
        return existing
    preview = preview_bulk(db, owner, data)
    stamp = _now()
    operation = AIStudioBulkOperation(
        owner_id=owner.id,
        created_by=owner.id,
        idempotency_key=key,
        brand_voice_id=preview.brand_voice_id,
        brand_voice_version=preview.brand_voice_version,
        preset_id=preview.preset_id,
        preset_version=preview.preset_version,
        locale=preview.locale,
        provider_key=preview.provider_key,
        model=preview.model,
        instructions_fingerprint=_instruction_fingerprint(data.user_instructions),
        product_count=preview.product_count,
        channel_count=preview.channel_count,
        content_type_count=preview.content_type_count,
        total_outputs=preview.total_outputs,
        status="queued",
        correlation_id=uuid.uuid4().hex[:32],
        cancellation_requested=False,
        completion_summary_json={},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(operation)
    db.flush()
    generation = generate_studio(
        db,
        owner,
        StudioGenerateRequest(
            product_ids=list(data.product_ids),
            channels=list(data.channels),
            content_types=list(data.content_types),
            brand_voice_id=data.brand_voice_id,
            preset_id=data.preset_id,
            locale=data.locale,
            user_instructions=data.user_instructions,
            provider_key=data.provider_key,
            model=data.model,
            idempotency_key=f"{key}:generation",
            generation_reason="bulk",
        ),
    )
    generation_row = db.get(AIStudioGeneration, generation.id)
    if generation_row is None:
        raise HTTPException(500, "Bulk generation could not be queued safely.")
    jobs = {
        _output_key(job.product_id, job.channel, job.content_type): job
        for job in db.scalars(
            select(AIStudioJob).where(AIStudioJob.generation_id == generation_row.id)
        )
    }
    outputs = {
        _output_key(output.product_id, output.channel, output.content_type): output
        for output in db.scalars(
            select(AIStudioOutput).where(AIStudioOutput.generation_id == generation_row.id)
        )
    }
    output_index = 0
    for product_id in data.product_ids:
        for channel in data.channels:
            for content_type in data.content_types:
                key_name = _output_key(product_id, channel, content_type)
                output_index += 1
                job = jobs.get(key_name)
                output = outputs.get(key_name)
                if job is None or output is None:
                    raise HTTPException(500, "Bulk output planning was incomplete.")
                scenario = data.failure_scenarios.get(key_name) or data.failure_scenarios.get(
                    str(output_index)
                )
                if scenario:
                    payload = dict(job.payload_json or {})
                    payload["failure_scenario"] = scenario
                    job.payload_json = payload
                db.add(
                    AIStudioBulkOutput(
                        bulk_operation_id=operation.id,
                        owner_id=owner.id,
                        product_id=product_id,
                        generation_id=generation_row.id,
                        job_id=job.id,
                        artifact_id=output.artifact_id,
                        channel=channel,
                        content_type=content_type,
                        locale=data.locale,
                        status="queued",
                        retryable=False,
                        created_at=stamp,
                        updated_at=stamp,
                    )
                )
    record_event(
        db,
        actor_id=owner.id,
        action="ai.bulk_generation_started",
        entity_type="ai_studio_bulk_operation",
        entity_id=operation.id,
        metadata={
            "total_outputs": operation.total_outputs,
            "correlation_id": operation.correlation_id,
        },
    )
    db.commit()
    db.refresh(operation)
    return operation


def _sync_output(db: Session, output: AIStudioBulkOutput) -> None:
    job = db.get(AIStudioJob, output.job_id)
    if job is None:
        output.status = "failed"
        output.retryable = False
        output.failure_category = "unknown_permanent"
        output.safe_error_message = "The bulk output job is unavailable."
        return
    output.artifact_id = job.artifact_id
    output.retryable = job.retryable
    output.failure_category = job.failure_category
    output.safe_error_message = job.safe_error_message
    if output.cancellation_requested or job.state == "cancelled":
        output.status = "cancelled"
    elif job.state == "stale":
        output.status = "stale"
        output.stale_reason = job.safe_error_message
    elif job.state == "failed":
        output.status = "failed"
    elif job.state == "retry_wait":
        output.status = "retry_wait"
    elif job.state in {"generating", "validating"}:
        output.status = job.state
    elif job.state == "succeeded":
        artifact = db.get(GeneratedArtifact, job.artifact_id) if job.artifact_id else None
        output.status = (
            "needs_review" if artifact and artifact.status == "pending_review" else "succeeded"
        )
    else:
        output.status = "queued"
    output.updated_at = _now()


def _sync_operation(db: Session, operation: AIStudioBulkOperation) -> list[AIStudioBulkOutput]:
    outputs = list(
        db.scalars(
            select(AIStudioBulkOutput)
            .where(AIStudioBulkOutput.bulk_operation_id == operation.id)
            .order_by(AIStudioBulkOutput.created_at, AIStudioBulkOutput.id)
        )
    )
    for output in outputs:
        _sync_output(db, output)
    counts = Counter(item.status for item in outputs)
    terminal = sum(
        counts.get(value, 0)
        for value in {"succeeded", "needs_review", "failed", "cancelled", "stale"}
    )
    active = operation.total_outputs - terminal
    if operation.cancellation_requested:
        status = (
            "cancelled"
            if counts.get("cancelled", 0) == operation.total_outputs
            else "partially_cancelled"
        )
    elif active:
        status = "queued" if counts.get("queued", 0) == operation.total_outputs else "running"
    elif counts.get("failed", 0) or counts.get("stale", 0):
        status = (
            "partially_completed"
            if counts.get("succeeded", 0) + counts.get("needs_review", 0)
            else "failed"
        )
    else:
        status = "completed"
    operation.status = status
    operation.completion_summary_json = dict(counts)
    if counts and operation.started_at is None and any(value not in {"queued"} for value in counts):
        operation.started_at = operation.started_at or _now()
    if terminal >= operation.total_outputs and operation.completed_at is None:
        operation.completed_at = _now()
    operation.updated_at = _now()
    return outputs


def _output_response(db: Session, output: AIStudioBulkOutput) -> StudioBulkOutputResponse:
    product = db.get(Product, output.product_id)
    artifact = db.get(GeneratedArtifact, output.artifact_id) if output.artifact_id else None
    job = db.get(AIStudioJob, output.job_id)
    return StudioBulkOutputResponse(
        id=output.id,
        product_id=output.product_id,
        product_name=product.name if product else "Unknown Product",
        channel=output.channel,
        content_type=output.content_type,
        locale=output.locale,
        status=output.status,
        artifact_id=output.artifact_id,
        artifact_version=artifact.version_number if artifact else None,
        job_id=output.job_id,
        generation_id=output.generation_id,
        attempt_count=job.attempt_count if job else 0,
        failure_category=output.failure_category,
        safe_error_message=output.safe_error_message,
        retryable=output.retryable,
        retry_eligible=output.status in {"failed", "stale"} and output.retryable,
        updated_at=output.updated_at,
    )


def status_response(db: Session, operation: AIStudioBulkOperation) -> StudioBulkStatusResponse:
    outputs = _sync_operation(db, operation)
    db.commit()
    counts = cast(dict[str, int], dict(operation.completion_summary_json or {}))
    progress = round(
        100
        * sum(
            counts.get(value, 0)
            for value in {"succeeded", "needs_review", "failed", "cancelled", "stale"}
        )
        / max(1, operation.total_outputs),
        2,
    )
    return StudioBulkStatusResponse(
        id=operation.id,
        status=operation.status,
        total_outputs=operation.total_outputs,
        counts=counts,
        progress_percentage=progress,
        product_count=operation.product_count,
        channel_count=operation.channel_count,
        content_type_count=operation.content_type_count,
        locale=operation.locale,
        provider_key=operation.provider_key,
        model=operation.model,
        brand_voice_id=operation.brand_voice_id,
        brand_voice_version=operation.brand_voice_version,
        preset_id=operation.preset_id,
        preset_version=operation.preset_version,
        correlation_id=operation.correlation_id,
        created_at=operation.created_at,
        started_at=operation.started_at,
        completed_at=operation.completed_at,
        completion_summary=cast(dict[str, object], counts),
        cancellation_requested=operation.cancellation_requested,
        outputs=[_output_response(db, item) for item in outputs],
    )


def retry_outputs(
    db: Session, owner: User, operation: AIStudioBulkOperation, output_ids: list[uuid.UUID]
) -> tuple[int, int]:
    _sync_operation(db, operation)
    selected = set(output_ids)
    rows = list(
        db.scalars(
            select(AIStudioBulkOutput)
            .where(
                AIStudioBulkOutput.bulk_operation_id == operation.id,
                AIStudioBulkOutput.owner_id == owner.id,
            )
            .with_for_update()
        )
    )
    eligible = [
        item
        for item in rows
        if item.status in {"failed", "stale"}
        and item.retryable
        and (not selected or item.id in selected)
    ]
    rejected = len([item for item in rows if selected and item.id in selected]) - len(eligible)
    for item in eligible:
        job = db.get(AIStudioJob, item.job_id)
        if job is None:
            continue
        job.state = "retry_wait"
        job.available_at = _now()
        job.next_retry_at = job.available_at
        job.completed_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.last_error_code = None
        job.safe_error_message = None
        job.failure_category = None
        job.retryable = True
        job.context_refresh_required = False
        generation = db.get(AIStudioGeneration, job.generation_id)
        if generation:
            generation.status = "queued"
            generation.completed_at = None
            generation.failed_outputs = max(0, generation.failed_outputs - 1)
        item.status = "retry_wait"
        item.failure_category = None
        item.safe_error_message = None
        record_event(
            db,
            actor_id=owner.id,
            action="ai.bulk_output_retried",
            entity_type="ai_studio_bulk_output",
            entity_id=item.id,
            metadata={"correlation_id": operation.correlation_id},
        )
    db.commit()
    return len(eligible), max(0, rejected)


def cancel_outputs(
    db: Session, owner: User, operation: AIStudioBulkOperation, output_ids: list[uuid.UUID]
) -> int:
    selected = set(output_ids)
    rows = list(
        db.scalars(
            select(AIStudioBulkOutput)
            .where(
                AIStudioBulkOutput.bulk_operation_id == operation.id,
                AIStudioBulkOutput.owner_id == owner.id,
            )
            .with_for_update()
        )
    )
    cancelled = 0
    for item in rows:
        if selected and item.id not in selected:
            continue
        _sync_output(db, item)
        if item.status not in {"queued", "retry_wait", "generating", "validating"}:
            continue
        job = db.get(AIStudioJob, item.job_id)
        if job is None:
            continue
        if job.state != "cancelled":
            job.state = "cancelled"
        job.lease_owner = None
        job.lease_expires_at = None
        job.completed_at = _now()
        item.cancellation_requested = True
        item.status = "cancelled"
        generation_output = db.scalar(
            select(AIStudioOutput).where(
                AIStudioOutput.generation_id == item.generation_id,
                AIStudioOutput.product_id == item.product_id,
                AIStudioOutput.channel == item.channel,
                AIStudioOutput.content_type == item.content_type,
            )
        )
        if generation_output and generation_output.artifact_id is None:
            generation_output.status = "cancelled"
        record_event(
            db,
            actor_id=owner.id,
            action="ai.bulk_output_cancelled",
            entity_type="ai_studio_bulk_output",
            entity_id=item.id,
            metadata={"correlation_id": operation.correlation_id},
        )
        cancelled += 1
    operation.cancellation_requested = not selected
    db.commit()
    return cancelled
