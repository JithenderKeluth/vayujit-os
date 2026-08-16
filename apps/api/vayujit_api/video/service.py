from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.failures import failure_spec
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.image_schemas import ImageGenerateRequest
from vayujit_api.ai.image_service import queue_generation
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import AIStudioGeneration, AIStudioJob
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product
from vayujit_api.video.models import (
    VideoApproval,
    VideoAudioAttachment,
    VideoCaptionTrack,
    VideoGeneration,
    VideoOutput,
    VideoPreset,
    VideoProject,
    VideoScene,
    VideoScript,
    VideoStoryboard,
    VideoStyle,
    VideoUsage,
)
from vayujit_api.video.provider import video_provider


def stamp() -> datetime:
    return datetime.now(UTC)


def _resolution(value: str) -> tuple[int, int]:
    try:
        width, height = (int(x) for x in value.lower().split("x"))
    except (ValueError, TypeError):
        raise HTTPException(422, "Video resolution is invalid.") from None
    if width < 240 or height < 240 or width > 3840 or height > 3840:
        raise HTTPException(422, "Video resolution is outside safe limits.")
    return width, height


def _owned(
    db: Session, owner: User, product_id: uuid.UUID, brand_id: uuid.UUID
) -> tuple[Product, Brand]:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    brand = db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == owner.id))
    if product is None or brand is None or product.brand_id != brand.id:
        raise HTTPException(404, "Product or Brand not found.")
    if (
        str(getattr(product.status, "value", product.status)) == "archived"
        or str(getattr(brand.status, "value", brand.status)) == "archived"
    ):
        raise HTTPException(409, "Archived Product or Brand cannot be used for Video generation.")
    return product, brand


def _fingerprint(value: object) -> str:
    return hashlib.sha256(repr(value).encode()).hexdigest()


def _artifact(
    db: Session,
    owner: User,
    product_id: uuid.UUID,
    artifact_id: uuid.UUID | None,
    version: int | None,
) -> GeneratedArtifact | None:
    if artifact_id is None:
        return None
    row = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == artifact_id,
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.product_id == product_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Source Artifact not found.")
    if row.status != "approved":
        raise HTTPException(409, "Only an approved source Artifact can be used.")
    if version is not None and row.version_number != version:
        raise HTTPException(409, "Source Artifact version is stale.")
    return row


def _media(db: Session, owner: User, ids: list[uuid.UUID]) -> list[MediaAsset]:
    result: list[MediaAsset] = []
    for media_id in ids:
        row = db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == media_id,
                MediaAsset.owner_id == owner.id,
                MediaAsset.status == "ready",
            )
        )
        if row is None:
            raise HTTPException(404, "Source Media item not found.")
        result.append(row)
    return result


def script_response(row: VideoScript) -> dict[str, object]:
    return {
        "id": row.id,
        "brand_id": row.brand_id,
        "product_id": row.product_id,
        "name": row.name,
        "version": row.version,
        "hook": row.hook,
        "introduction": row.introduction,
        "scenes": row.scenes,
        "narration": row.narration,
        "on_screen_text": row.on_screen_text,
        "cta": row.cta,
        "outro": row.outro,
        "target_duration_seconds": row.target_duration_seconds,
        "locale": row.locale,
        "status": row.status,
        "archived": row.archived,
        "approved_at": row.approved_at,
    }


def create_script(db: Session, owner: User, data: Any) -> dict[str, object]:
    product, brand = _owned(db, owner, data.product_id, data.brand_id)
    latest = (
        db.scalar(
            select(VideoScript.version)
            .where(
                VideoScript.owner_id == owner.id,
                VideoScript.product_id == product.id,
                VideoScript.name == data.name,
            )
            .order_by(VideoScript.version.desc())
            .limit(1)
        )
        or 0
    )
    now = stamp()
    row = VideoScript(
        owner_id=owner.id,
        brand_id=brand.id,
        product_id=product.id,
        version=latest + 1,
        status="draft",
        archived=False,
        created_at=now,
        updated_at=now,
        **data.model_dump(exclude={"brand_id", "product_id"}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return script_response(row)


def edit_script(db: Session, owner: User, script_id: uuid.UUID, data: Any) -> dict[str, object]:
    row = db.scalar(
        select(VideoScript).where(VideoScript.id == script_id, VideoScript.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Script not found.")
    if row.status != "draft" or row.archived:
        raise HTTPException(409, "Only active draft Video Scripts may be edited.")
    for key, value in data.model_dump(exclude={"brand_id", "product_id"}).items():
        setattr(row, key, value)
    row.updated_at = stamp()
    db.commit()
    db.refresh(row)
    return script_response(row)


def compare_scripts(
    db: Session, owner: User, script_id: uuid.UUID, other_script_id: uuid.UUID
) -> dict[str, object]:
    rows = db.scalars(
        select(VideoScript).where(
            VideoScript.id.in_([script_id, other_script_id]), VideoScript.owner_id == owner.id
        )
    ).all()
    if len(rows) != 2:
        raise HTTPException(404, "Video Script not found.")
    return {
        "left": script_response(next(row for row in rows if row.id == script_id)),
        "right": script_response(next(row for row in rows if row.id == other_script_id)),
    }


def decide_script(
    db: Session, owner: User, script_id: uuid.UUID, target: str, reason: str | None = None
) -> dict[str, object]:
    row = db.scalar(
        select(VideoScript)
        .where(VideoScript.id == script_id, VideoScript.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Video Script not found.")
    if target == "approved" and row.status == "approved":
        return script_response(row)
    if target == "rejected" and row.status == "rejected":
        return script_response(row)
    if row.status != "draft":
        raise HTTPException(409, "Only draft Video Scripts may be reviewed.")
    row.status = target
    row.rejection_reason = reason if target == "rejected" else None
    row.approved_by = owner.id if target == "approved" else None
    row.approved_at = stamp() if target == "approved" else None
    row.updated_at = stamp()
    record_event(
        db,
        actor_id=owner.id,
        action=f"ai.video_script_{target}",
        entity_type="video_script",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    return script_response(row)


def validate_preset(db: Session, owner: User, data: Any, brand: Brand) -> VideoPreset | None:
    if not getattr(data, "preset_id", None):
        return None
    preset = db.scalar(
        select(VideoPreset).where(
            VideoPreset.id == data.preset_id, VideoPreset.owner_id == owner.id
        )
    )
    if preset is None or preset.archived:
        raise HTTPException(409, "Video Preset is archived or unavailable.")
    checks = {
        "video type": preset.video_type == data.video_type,
        "target": preset.target_channel == data.target_channel,
        "resolution": preset.resolution == data.resolution,
        "aspect ratio": preset.aspect_ratio == data.aspect_ratio,
        "duration": data.duration_seconds <= preset.max_duration_seconds,
        "provider": preset.provider == video_provider.key,
        "model": preset.model == video_provider.model,
    }
    if not all(checks.values()):
        failed = next(label for label, valid in checks.items() if not valid)
        raise HTTPException(409, f"Video Preset is incompatible with {failed}.")
    if preset.style_id:
        style = db.scalar(
            select(VideoStyle).where(
                VideoStyle.id == preset.style_id,
                VideoStyle.owner_id == owner.id,
                VideoStyle.brand_id == brand.id,
                VideoStyle.archived.is_(False),
            )
        )
        if style is None:
            raise HTTPException(409, "Video Preset Style is archived or unavailable.")
    return preset


def _audio(db: Session, owner: User, data: Any) -> tuple[MediaAsset | None, dict[str, object]]:
    mode = getattr(data, "audio_mode", "none")
    if mode == "none":
        return None, {"mode": mode, "source_type": "none"}
    if mode in {"deterministic_narration_placeholder", "future_provider_voice"}:
        if getattr(data, "audio_media_id", None):
            raise HTTPException(422, "Audio Media is not valid for this audio mode.")
        return None, {"mode": mode, "source_type": "generated"}
    media_id = getattr(data, "audio_media_id", None)
    if not media_id:
        raise HTTPException(422, "Audio Media is required.")
    audio = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == media_id, MediaAsset.owner_id == owner.id, MediaAsset.status == "ready"
        )
    )
    if audio is None:
        raise HTTPException(404, "Audio Media item not found.")
    if audio.mime_type not in {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"}:
        raise HTTPException(422, "Audio MIME type is unsupported.")
    if audio.size_bytes <= 0 or audio.size_bytes > get_settings().media_max_size_bytes:
        raise HTTPException(413, "Audio file exceeds the configured upload limit.")
    return audio, {
        "mode": mode,
        "media_id": str(audio.id),
        "checksum": audio.checksum_sha256,
        "mime_type": audio.mime_type,
        "source_type": "uploaded",
    }


def preview(db: Session, owner: User, data: Any) -> dict[str, object]:
    product, brand = _owned(db, owner, data.product_id, data.brand_id)
    width, height = _resolution(data.resolution)
    validate_preset(db, owner, data, brand)
    audio, audio_plan = _audio(db, owner, data)
    artifact = _artifact(
        db, owner, product.id, data.source_artifact_id, data.source_artifact_version
    )
    media = _media(db, owner, list(data.source_media_ids))
    script = None
    if getattr(data, "script_id", None):
        script = db.scalar(
            select(VideoScript).where(
                VideoScript.id == data.script_id,
                VideoScript.owner_id == owner.id,
                VideoScript.product_id == product.id,
            )
        )
        if script is None or script.archived or script.status != "approved":
            raise HTTPException(409, "Video Script must be an approved, active version.")
        if data.script_version is not None and script.version != data.script_version:
            raise HTTPException(409, "Video Script version is stale.")
    storyboard = None
    if getattr(data, "storyboard_id", None):
        storyboard = db.scalar(
            select(VideoStoryboard).where(
                VideoStoryboard.id == data.storyboard_id,
                VideoStoryboard.owner_id == owner.id,
                VideoStoryboard.product_id == product.id,
            )
        )
        if storyboard is None or (
            data.storyboard_version is not None and storyboard.version != data.storyboard_version
        ):
            raise HTTPException(409, "Storyboard version is stale or unavailable.")
        if storyboard.state != "approved":
            raise HTTPException(409, "Storyboard must be approved before Video generation.")
    style = None
    if getattr(data, "style_id", None):
        style = db.scalar(
            select(VideoStyle).where(
                VideoStyle.id == data.style_id,
                VideoStyle.owner_id == owner.id,
                VideoStyle.brand_id == brand.id,
            )
        )
        if (
            style is None
            or style.archived
            or (data.style_version is not None and style.version != data.style_version)
        ):
            raise HTTPException(409, "Video Style is stale, archived, or unavailable.")
    blockers: list[str] = []
    warnings = [
        "Local deterministic workflow simulates transitions; visual quality is not certified.",
        "Cost is unavailable because no live provider is configured.",
    ]
    if not media:
        warnings.append(
            "No source images selected; the local provider will render deterministic cards."
        )
    fingerprint = _fingerprint(
        (
            str(product.id),
            str(artifact.id) if artifact else None,
            artifact.version_number if artifact else None,
            str(script.id) if script else None,
            script.version if script else None,
            str(storyboard.id) if storyboard else None,
            storyboard.version if storyboard else None,
            [str(x.id) for x in media],
            str(style.id) if style else None,
            style.version if style else None,
            data.aspect_ratio,
            data.resolution,
            data.duration_seconds,
            data.target_channel,
        )
    )
    return {
        "product_id": str(product.id),
        "brand_id": str(brand.id),
        "video_type": data.video_type,
        "target_channel": data.target_channel,
        "source_artifact_id": str(artifact.id) if artifact else None,
        "source_artifact_version": artifact.version_number if artifact else None,
        "script_id": str(script.id) if script else None,
        "script_version": script.version if script else None,
        "source_media_ids": [str(x.id) for x in media],
        "storyboard_id": str(storyboard.id) if storyboard else None,
        "storyboard_version": storyboard.version if storyboard else None,
        "style_id": str(style.id) if style else None,
        "style_version": style.version if style else None,
        "aspect_ratio": data.aspect_ratio,
        "resolution": data.resolution,
        "width": width,
        "height": height,
        "duration_seconds": data.duration_seconds,
        "provider": video_provider.key,
        "model": video_provider.model,
        "capabilities": video_provider.health(),
        "estimated_provider_calls": 1,
        "cost_status": "unavailable",
        "blockers": blockers,
        "warnings": warnings,
        "audio": audio_plan,
        "context_fingerprint": fingerprint,
    }


def _response(db: Session, row: VideoGeneration) -> dict[str, object]:
    output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == row.id))
    version = 1
    parent = row.parent_generation_id
    while parent is not None:
        version += 1
        parent_row = db.get(VideoGeneration, parent)
        parent = parent_row.parent_generation_id if parent_row else None
    return {
        "id": row.id,
        "project_id": row.project_id,
        "brand_id": row.brand_id,
        "product_id": row.product_id,
        "status": row.status,
        "video_version": version,
        "video_type": row.video_type,
        "target_channel": row.target_channel,
        "aspect_ratio": row.aspect_ratio,
        "resolution": row.resolution,
        "frame_rate": row.frame_rate,
        "duration_seconds": row.duration_seconds,
        "provider_key": row.provider_key,
        "model": row.model,
        "source_artifact_id": row.source_artifact_id,
        "source_artifact_version": row.source_artifact_version,
        "script_id": row.script_id,
        "script_version": row.script_version,
        "source_media_ids": list(row.source_media_ids or []),
        "audio_mode": row.audio_mode,
        "audio_media_id": row.audio_media_id,
        "thumbnail_image_output_id": row.thumbnail_image_output_id,
        "thumbnail_media_id": row.thumbnail_media_id,
        "thumbnail_version": row.thumbnail_version,
        "storyboard_id": row.storyboard_id,
        "storyboard_version": row.storyboard_version,
        "style_id": row.style_id,
        "style_version": row.style_version,
        "context_fingerprint": row.context_fingerprint,
        "parent_generation_id": row.parent_generation_id,
        "regeneration_reason": row.regeneration_reason,
        "output_id": output.id if output else None,
        "output_media_id": output.media_id if output else None,
        "output_checksum": output.checksum_sha256 if output else None,
        "output_size_bytes": output.size_bytes if output else None,
        "output_mime_type": output.mime_type if output else None,
        "output_width": output.width if output else None,
        "output_height": output.height if output else None,
        "output_status": output.status if output else None,
        "failure_code": row.failure_code,
        "safe_error_message": row.safe_error_message,
        "created_at": row.created_at,
        "completed_at": row.completed_at,
    }


def queue(db: Session, owner: User, data: Any) -> dict[str, object]:
    plan = preview(db, owner, data)
    audio, audio_plan = _audio(db, owner, data)
    artifact_version = plan["source_artifact_version"]
    storyboard_version = plan["storyboard_version"]
    idem = data.idempotency_key or (
        f"video:{owner.id}:{data.product_id}:{data.video_type}:{data.target_channel}:"
        f"{artifact_version}:{plan.get('script_version')}:{storyboard_version}"
    )
    existing = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.owner_id == owner.id,
            VideoGeneration.idempotency_key == idem,
        )
    )
    if existing:
        return _response(db, existing)
    now = stamp()
    project = VideoProject(
        owner_id=owner.id,
        brand_id=data.brand_id,
        product_id=data.product_id,
        name=f"{data.video_type} project",
        script_artifact_id=data.source_artifact_id,
        script_artifact_version=plan["source_artifact_version"],
        script_id=data.script_id,
        script_version=plan.get("script_version"),
        status="queued",
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    preset = (
        db.scalar(
            select(VideoPreset).where(
                VideoPreset.id == data.preset_id,
                VideoPreset.owner_id == owner.id,
                VideoPreset.archived.is_(False),
            )
        )
        if data.preset_id
        else None
    )
    if data.preset_id and preset is None:
        raise HTTPException(404, "Video Preset not found.")
    generation = VideoGeneration(
        owner_id=owner.id,
        project_id=project.id,
        brand_id=data.brand_id,
        product_id=data.product_id,
        source_artifact_id=data.source_artifact_id,
        source_artifact_version=plan["source_artifact_version"],
        script_id=data.script_id,
        script_version=plan.get("script_version"),
        preset_id=preset.id if preset else None,
        preset_version=preset.version if preset else None,
        storyboard_id=data.storyboard_id,
        storyboard_version=data.storyboard_version,
        style_id=data.style_id,
        style_version=data.style_version,
        video_type=data.video_type,
        target_channel=data.target_channel,
        aspect_ratio=data.aspect_ratio,
        resolution=data.resolution,
        frame_rate=24,
        duration_seconds=data.duration_seconds,
        provider_key=video_provider.key,
        model=video_provider.model,
        status="queued",
        idempotency_key=idem,
        correlation_id=uuid.uuid4().hex[:32],
        source_media_ids=plan["source_media_ids"],
        storyboard_json=data.storyboard,
        audio_mode=getattr(data, "audio_mode", "none"),
        audio_media_id=audio.id if audio else None,
        audio_checksum=audio.checksum_sha256 if audio else None,
        audio_mime_type=audio.mime_type if audio else None,
        audio_source_type=audio_plan.get("source_type"),
        audio_lineage_created_at=now if audio else None,
        thumbnail_image_output_id=getattr(data, "thumbnail_image_output_id", None),
        thumbnail_media_id=getattr(data, "thumbnail_media_id", None),
        thumbnail_version=getattr(data, "thumbnail_version", None),
        thumbnail_attached_at=now if getattr(data, "thumbnail_media_id", None) else None,
        context_fingerprint=plan["context_fingerprint"],
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(generation)
    db.flush()
    if data.audio_mode != "none":
        db.add(
            VideoAudioAttachment(
                generation_id=generation.id,
                owner_id=owner.id,
                mode=data.audio_mode,
                media_id=audio.id if audio else None,
                checksum_sha256=audio.checksum_sha256 if audio else None,
                mime_type=audio.mime_type if audio else None,
                source_type=str(audio_plan.get("source_type", "generated")),
                lineage_reference=str(audio.id) if audio else None,
                created_at=now,
            )
        )
    studio = AIStudioGeneration(
        owner_id=owner.id,
        product_ids_json=[str(data.product_id)],
        channels_json=[data.target_channel],
        content_types_json=["video"],
        locale="en-IN",
        provider_key=video_provider.key,
        model=video_provider.model,
        context_fingerprint=plan["context_fingerprint"],
        idempotency_key=f"video-studio:{idem}",
        status="queued",
        total_outputs=1,
        completed_outputs=0,
        failed_outputs=0,
        created_at=now,
    )
    db.add(studio)
    db.flush()
    db.add(
        AIStudioJob(
            owner_id=owner.id,
            generation_id=studio.id,
            product_id=data.product_id,
            job_type="ai_video_generate",
            channel=data.target_channel,
            content_type="video",
            locale="en-IN",
            context_fingerprint=plan["context_fingerprint"],
            provider=video_provider.key,
            model=video_provider.model,
            user_instruction_fingerprint=plan["context_fingerprint"],
            idempotency_key=f"video-job:{idem}",
            correlation_id=generation.correlation_id,
            state="queued",
            payload_json={
                "video_generation_id": str(generation.id),
                "failure_scenario": data.failure_scenario,
                "width": plan["width"],
                "height": plan["height"],
                "duration_seconds": data.duration_seconds,
                "seed": idem,
                "context_fingerprint": plan["context_fingerprint"],
            },
            max_attempts=3,
            available_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        VideoApproval(
            generation_id=generation.id,
            owner_id=owner.id,
            state="pending_review",
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        VideoUsage(
            generation_id=generation.id,
            modality="video",
            provider_calls=0,
            output_bytes=0,
            cost_status="unavailable",
            created_at=now,
        )
    )
    db.add(
        VideoOutput(
            generation_id=generation.id,
            owner_id=owner.id,
            checksum_sha256="pending",
            mime_type="video/mp4",
            size_bytes=1,
            duration_seconds=data.duration_seconds,
            width=plan["width"],
            height=plan["height"],
            status="pending_review",
            created_at=now,
        )
    )
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_generation_queued",
        entity_type="video_generation",
        entity_id=generation.id,
        metadata={"correlation_id": generation.correlation_id, "provider": video_provider.key},
    )
    db.commit()
    db.refresh(generation)
    return _response(db, generation)


def approve(
    db: Session, owner: User, generation_id: uuid.UUID, approved: bool, feedback: str | None
) -> dict[str, object]:
    row = db.scalar(
        select(VideoGeneration)
        .where(VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id)
        .with_for_update()
    )
    out = db.scalar(
        select(VideoOutput).where(VideoOutput.generation_id == generation_id).with_for_update()
    )
    if (
        row is None
        or out is None
        or row.status != "succeeded"
        or out.media_id is None
        or out.checksum_sha256 == "pending"
    ):
        raise HTTPException(409, "Video is not eligible for review.")
    target = "approved" if approved else "rejected"
    approval = db.scalar(
        select(VideoApproval)
        .where(VideoApproval.generation_id == generation_id, VideoApproval.owner_id == owner.id)
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(409, "Video approval record is unavailable.")
    if out.status == target or approval.state == target:
        return _response(db, row)
    if approval.state != "pending_review":
        raise HTTPException(409, "Video review already has a conflicting decision.")
    out.status = target
    approval.state = target
    approval.feedback = feedback
    approval.updated_at = stamp()
    if not approved:
        row.rejection_feedback = feedback
    record_event(
        db,
        actor_id=owner.id,
        action=f"ai.video_{'approved' if approved else 'rejected'}",
        entity_type="video_generation",
        entity_id=row.id,
        metadata={"feedback": feedback},
    )
    db.commit()
    return _response(db, row)


def create_storyboard(db: Session, owner: User, data: Any) -> dict[str, object]:
    product, brand = _owned(db, owner, data.product_id, data.brand_id)
    artifact = _artifact(
        db, owner, product.id, data.source_artifact_id, data.source_artifact_version
    )
    count = (
        db.scalar(
            select(VideoStoryboard.version)
            .where(VideoStoryboard.owner_id == owner.id, VideoStoryboard.product_id == product.id)
            .order_by(VideoStoryboard.version.desc())
            .limit(1)
        )
        or 0
    )
    now = stamp()
    row = VideoStoryboard(
        owner_id=owner.id,
        brand_id=brand.id,
        product_id=product.id,
        source_artifact_id=artifact.id if artifact else None,
        source_artifact_version=artifact.version_number if artifact else None,
        video_type=data.video_type,
        target_channel=data.target_channel,
        locale=data.locale,
        aspect_ratio=data.aspect_ratio,
        resolution=data.resolution,
        version=count + 1,
        state="draft",
        context_fingerprint=_fingerprint(
            (
                str(product.id),
                str(artifact.id) if artifact else None,
                artifact.version_number if artifact else None,
                data.aspect_ratio,
                data.resolution,
            )
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    for scene in data.scenes:
        db.add(
            VideoScene(
                storyboard_id=row.id,
                stable_key=scene.stable_key,
                scene_order=scene.scene_order,
                duration_seconds=scene.duration_seconds,
                source_media_id=scene.source_media_id,
                scene_text=scene.scene_text,
                narration=scene.narration,
                transition=scene.transition,
                visual_guidance=scene.visual_guidance,
                background=scene.background,
                cta=scene.cta,
                locale=scene.locale,
                version=1,
                status="draft",
            )
        )
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_storyboard_created",
        entity_type="video_storyboard",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    return storyboard_response(db, row)


def storyboard_response(db: Session, row: VideoStoryboard) -> dict[str, object]:
    scenes = db.scalars(
        select(VideoScene)
        .where(VideoScene.storyboard_id == row.id)
        .order_by(VideoScene.scene_order)
    ).all()
    total = sum(scene.duration_seconds for scene in scenes)
    return {
        "id": row.id,
        "product_id": row.product_id,
        "brand_id": row.brand_id,
        "source_artifact_id": row.source_artifact_id,
        "source_artifact_version": row.source_artifact_version,
        "video_type": row.video_type,
        "target_channel": row.target_channel,
        "locale": row.locale,
        "aspect_ratio": row.aspect_ratio,
        "resolution": row.resolution,
        "version": row.version,
        "state": row.state,
        "row_version": row.row_version,
        "total_duration_seconds": total,
        "ready": bool(scenes)
        and len({s.scene_order for s in scenes}) == len(scenes)
        and total <= 60,
        "scenes": [
            {
                "id": s.id,
                "stable_key": s.stable_key,
                "scene_order": s.scene_order,
                "duration_seconds": s.duration_seconds,
                "source_media_id": s.source_media_id,
                "scene_text": s.scene_text,
                "narration": s.narration,
                "transition": s.transition,
                "visual_guidance": s.visual_guidance,
                "background": s.background,
                "cta": s.cta,
                "locale": s.locale,
            }
            for s in scenes
        ],
    }


def update_storyboard(
    db: Session, owner: User, storyboard_id: uuid.UUID, data: Any
) -> dict[str, object]:
    row = db.scalar(
        select(VideoStoryboard)
        .where(VideoStoryboard.id == storyboard_id, VideoStoryboard.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Storyboard not found.")
    if row.row_version != data.expected_row_version:
        raise HTTPException(409, "Storyboard changed; refresh before editing.")
    target = row
    if row.state == "approved":
        now = stamp()
        target = VideoStoryboard(
            owner_id=row.owner_id,
            brand_id=row.brand_id,
            product_id=row.product_id,
            source_artifact_id=row.source_artifact_id,
            source_artifact_version=row.source_artifact_version,
            video_type=row.video_type,
            target_channel=row.target_channel,
            locale=row.locale,
            aspect_ratio=row.aspect_ratio,
            resolution=row.resolution,
            version=(
                db.scalar(
                    select(VideoStoryboard.version)
                    .where(
                        VideoStoryboard.owner_id == owner.id,
                        VideoStoryboard.product_id == row.product_id,
                    )
                    .order_by(VideoStoryboard.version.desc())
                    .limit(1)
                )
                or row.version
            )
            + 1,
            state="draft",
            context_fingerprint=row.context_fingerprint,
            row_version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(target)
        db.flush()
    else:
        db.query(VideoScene).filter(VideoScene.storyboard_id == row.id).delete(
            synchronize_session=False
        )
        target.updated_at = stamp()
        target.row_version += 1
    for scene in data.scenes:
        db.add(
            VideoScene(
                storyboard_id=target.id,
                stable_key=scene.stable_key,
                scene_order=scene.scene_order,
                duration_seconds=scene.duration_seconds,
                source_media_id=scene.source_media_id,
                scene_text=scene.scene_text,
                narration=scene.narration,
                transition=scene.transition,
                visual_guidance=scene.visual_guidance,
                background=scene.background,
                cta=scene.cta,
                locale=scene.locale,
                version=target.version,
                status="draft",
            )
        )
    row = target
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_storyboard_updated",
        entity_type="video_storyboard",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    return storyboard_response(db, row)


def approve_storyboard(
    db: Session, owner: User, storyboard_id: uuid.UUID, expected_row_version: int
) -> dict[str, object]:
    row = db.scalar(
        select(VideoStoryboard)
        .where(VideoStoryboard.id == storyboard_id, VideoStoryboard.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Storyboard not found.")
    if row.row_version != expected_row_version:
        raise HTTPException(409, "Storyboard changed; refresh before approval.")
    result = storyboard_response(db, row)
    if not result["ready"]:
        raise HTTPException(409, "Storyboard has readiness blockers.")
    if row.state == "approved":
        return result
    row.state = "approved"
    row.approved_by = owner.id
    row.approved_at = stamp()
    row.updated_at = stamp()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_storyboard_approved",
        entity_type="video_storyboard",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    return storyboard_response(db, row)


def create_style(
    db: Session,
    owner: User,
    brand_id: uuid.UUID,
    name: str,
    config: dict[str, object],
    is_default: bool = False,
) -> VideoStyle:
    (
        _owned(db, owner, uuid.UUID(int=0), brand_id)
        if db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == owner.id)) is None
        else None
    )
    version = (
        db.scalar(
            select(VideoStyle.version)
            .where(
                VideoStyle.owner_id == owner.id,
                VideoStyle.brand_id == brand_id,
                VideoStyle.name == name,
            )
            .order_by(VideoStyle.version.desc())
            .limit(1)
        )
        or 0
    )
    if is_default:
        db.query(VideoStyle).filter(
            VideoStyle.owner_id == owner.id, VideoStyle.brand_id == brand_id
        ).update({VideoStyle.is_default: False})
    now = stamp()
    row = VideoStyle(
        owner_id=owner.id,
        brand_id=brand_id,
        name=name,
        version=version + 1,
        config_json=config,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def regenerate(db: Session, owner: User, generation_id: uuid.UUID, data: Any) -> dict[str, object]:
    parent = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    if parent is None:
        raise HTTPException(404, "Video generation not found.")
    feedback_hash = hashlib.sha256((data.feedback or "").encode()).hexdigest()[:12]
    idem = data.idempotency_key or f"regenerate:{parent.id}:{data.reason}:{feedback_hash}"
    existing = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.owner_id == owner.id, VideoGeneration.idempotency_key == idem
        )
    )
    if existing:
        return _response(db, existing)
    payload = type(
        "Request",
        (),
        {
            "product_id": parent.product_id,
            "brand_id": parent.brand_id,
            "video_type": parent.video_type,
            "target_channel": parent.target_channel,
            "source_artifact_id": parent.source_artifact_id,
            "source_artifact_version": parent.source_artifact_version,
            "script_id": parent.script_id,
            "script_version": parent.script_version,
            "source_media_ids": [uuid.UUID(x) for x in parent.source_media_ids],
            "storyboard_id": data.storyboard_id or parent.storyboard_id,
            "storyboard_version": parent.storyboard_version,
            "style_id": data.style_id or parent.style_id,
            "style_version": parent.style_version,
            "aspect_ratio": parent.aspect_ratio,
            "resolution": parent.resolution,
            "duration_seconds": parent.duration_seconds,
            "preset_id": data.preset_id or parent.preset_id,
            "failure_scenario": "success",
            "idempotency_key": idem,
            "storyboard": parent.storyboard_json,
            "audio_mode": parent.audio_mode,
            "audio_media_id": parent.audio_media_id,
            "thumbnail_image_output_id": parent.thumbnail_image_output_id,
            "thumbnail_media_id": parent.thumbnail_media_id,
            "thumbnail_version": parent.thumbnail_version,
        },
    )()
    result = queue(db, owner, payload)
    child = db.scalar(select(VideoGeneration).where(VideoGeneration.id == result["id"]))
    if child is None:
        raise HTTPException(500, "Regeneration could not be queued.")
    child.parent_generation_id = parent.id
    child.regeneration_reason = data.reason
    child.rejection_feedback = data.feedback
    db.commit()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_regeneration_requested",
        entity_type="video_generation",
        entity_id=child.id,
        metadata={"parent_generation_id": str(parent.id), "reason": data.reason},
    )
    return _response(db, child)


def validate_caption_timing(timing: list[dict[str, object]], duration: int) -> None:
    previous_end = 0.0
    for cue in timing:
        try:
            start = float(str(cue.get("start", -1)))
            end = float(str(cue.get("end", -1)))
        except (TypeError, ValueError):
            raise HTTPException(422, "Caption timing is invalid.") from None
        if start < 0 or end <= start or end > duration or start < previous_end:
            raise HTTPException(422, "Caption timing is invalid or overlapping.")
        text = cue.get("text")
        if isinstance(text, str) and (
            len(text) > 1000 or "<script" in text.lower() or "onerror=" in text.lower()
        ):
            raise HTTPException(422, "Caption text contains unsafe markup.")
        previous_end = end


def decide_caption(
    db: Session, owner: User, caption_id: uuid.UUID, target: str
) -> dict[str, object]:
    row = db.scalar(
        select(VideoCaptionTrack)
        .join(VideoGeneration, VideoGeneration.id == VideoCaptionTrack.generation_id)
        .where(VideoCaptionTrack.id == caption_id, VideoGeneration.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Caption track not found.")
    if row.approval_state not in {"pending_review", target}:
        raise HTTPException(409, "Caption track is no longer reviewable.")
    row.approval_state = target
    db.commit()
    return {"id": row.id, "approval_state": row.approval_state, "version": row.version}


def generate_thumbnail_candidate(
    db: Session, owner: User, generation_id: uuid.UUID, data: Any
) -> dict[str, object]:
    generation = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    if generation is None:
        raise HTTPException(404, "Video generation not found.")
    request = ImageGenerateRequest(
        brand_id=generation.brand_id,
        product_id=generation.product_id,
        operation="thumbnail",
        channel="canonical",
        width=1280,
        height=720,
        aspect_ratio=generation.aspect_ratio,
        instructions=data.instructions,
        idempotency_key=data.idempotency_key or f"video-thumbnail:{generation.id}",
        content_artifact_id=generation.source_artifact_id,
        content_artifact_version=generation.source_artifact_version,
        output_count=1,
    )
    result = queue_generation(db, owner, request)
    return {
        "video_generation_id": generation.id,
        "image_generation": result,
        "auto_attached": False,
    }


def cleanup_video_temp_files(paths: list[str], *, dry_run: bool = False) -> dict[str, int | bool]:
    """Safely remove explicitly supplied Video temp files under the media root."""
    from pathlib import Path

    root = Path(get_settings().media_storage_directory).resolve()
    removed = 0
    skipped = 0
    for raw_path in paths:
        candidate = Path(raw_path).resolve()
        if root not in candidate.parents or candidate.suffix != ".tmp":
            skipped += 1
            continue
        if candidate.is_file():
            if not dry_run:
                candidate.unlink(missing_ok=True)
            removed += 1
    return {"removed": removed, "skipped": skipped, "dry_run": dry_run}


def recovery_projection(db: Session, owner: User, generation_id: uuid.UUID) -> dict[str, object]:
    row = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Video generation not found.")
    spec = failure_spec(row.failure_code or "unknown_permanent")
    job = db.scalar(
        select(AIStudioJob).where(
            AIStudioJob.correlation_id == row.correlation_id, AIStudioJob.owner_id == owner.id
        )
    )
    return {
        "failure_code": row.failure_code,
        "safe_message": row.safe_error_message or spec.safe_message,
        "retryable": spec.retryable,
        "correlation_id": row.correlation_id,
        "generation_id": row.id,
        "job_id": job.id if job else None,
        "eligible_actions": list(spec.recovery_actions),
    }


def execute_recovery_action(
    db: Session, owner: User, generation_id: uuid.UUID, data: Any
) -> dict[str, object]:
    projection = recovery_projection(db, owner, generation_id)
    if data.idempotency_key is not None:
        current_job = db.scalar(
            select(AIStudioJob).where(
                AIStudioJob.correlation_id == projection["correlation_id"],
                AIStudioJob.owner_id == owner.id,
            )
        )
        if current_job is not None:
            payload_json = current_job.payload_json
            if (
                isinstance(payload_json, dict)
                and payload_json.get("recovery_idempotency_key") == data.idempotency_key
            ):
                existing_row = db.get(VideoGeneration, generation_id)
                if existing_row is not None:
                    return _response(db, existing_row)
    if (
        data.expected_failure_code is not None
        and data.expected_failure_code != projection["failure_code"]
    ):
        raise HTTPException(409, "Video recovery state changed; refresh before confirming.")
    if data.expected_status is not None:
        current = db.scalar(
            select(VideoGeneration.status).where(
                VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
            )
        )
        if current != data.expected_status:
            raise HTTPException(409, "Video recovery state changed; refresh before confirming.")
    if data.action == "review_failure":
        return projection
    if data.action == "remove_audio":
        row = db.scalar(
            select(VideoGeneration)
            .where(VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id)
            .with_for_update()
        )
        if row is None:
            raise HTTPException(404, "Video generation not found.")
        row.audio_mode = "none"
        row.audio_media_id = None
        row.audio_checksum = None
        row.audio_mime_type = None
        db.commit()
        return _response(db, row)
    eligible = projection.get("eligible_actions", [])
    if not isinstance(eligible, list) or data.action not in eligible:
        raise HTTPException(409, "Recovery action is not eligible for this Video failure.")
    if data.action == "retry_generation":
        row = db.scalar(
            select(VideoGeneration)
            .where(VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id)
            .with_for_update()
        )
        job = (
            db.scalar(
                select(AIStudioJob)
                .where(
                    AIStudioJob.correlation_id == row.correlation_id,
                    AIStudioJob.owner_id == owner.id,
                )
                .with_for_update()
            )
            if row
            else None
        )
        if row is None or job is None:
            raise HTTPException(404, "Video recovery job not found.")
        if row.status == "succeeded":
            return _response(db, row)
        row.status = "queued"
        row.failure_code = None
        row.safe_error_message = None
        job.payload_json = {
            **(job.payload_json or {}),
            "recovery_idempotency_key": data.idempotency_key,
        }
        job.state = "queued"
        job.failure_category = None
        job.retryable = False
        job.available_at = stamp()
        db.commit()
        return _response(db, row)
    return projection


def attach_thumbnail(
    db: Session, owner: User, generation_id: uuid.UUID, data: Any
) -> dict[str, object]:
    generation = db.scalar(
        select(VideoGeneration)
        .where(VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id)
        .with_for_update()
    )
    if generation is None:
        raise HTTPException(404, "Video generation not found.")
    output = db.scalar(
        select(AIImageOutput).where(
            AIImageOutput.id == data.image_output_id,
            AIImageOutput.owner_id == owner.id,
            AIImageOutput.product_id == generation.product_id,
        )
    )
    if output is None or output.status != "approved" or output.media_id != data.media_id:
        raise HTTPException(
            409, "Thumbnail must be an approved Image Output with the exact Media asset."
        )
    generation.thumbnail_image_output_id = output.id
    generation.thumbnail_media_id = output.media_id
    generation.thumbnail_version = data.image_version
    generation.thumbnail_attached_at = stamp()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_thumbnail_attached",
        entity_type="video_generation",
        entity_id=generation.id,
        metadata={
            "image_output_id": str(output.id),
            "media_id": str(output.media_id),
            "image_version": data.image_version,
        },
    )
    db.commit()
    return _response(db, generation)


def add_caption(db: Session, owner: User, generation_id: uuid.UUID, data: Any) -> dict[str, object]:
    generation = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    if generation is None:
        raise HTTPException(404, "Video generation not found.")
    if any(
        token in data.caption_text.lower()
        for token in ("<script", "onerror=", "javascript:", "<svg")
    ):
        raise HTTPException(422, "Caption text contains unsafe markup.")
    validate_caption_timing(data.timing, generation.duration_seconds)
    artifact = _artifact(
        db, owner, generation.product_id, data.source_artifact_id, data.source_artifact_version
    )
    track = VideoCaptionTrack(
        generation_id=generation.id,
        locale=data.locale,
        caption_text=data.caption_text,
        format="webvtt",
        source_artifact_id=artifact.id if artifact else generation.source_artifact_id,
        source_artifact_version=(
            artifact.version_number if artifact else generation.source_artifact_version
        ),
        version=1,
        timing_json=data.timing,
        approval_state="pending_review",
    )
    db.add(track)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.video_caption_generated",
        entity_type="video_caption_track",
        entity_id=track.id,
        metadata={"locale": data.locale},
    )
    db.commit()
    db.refresh(track)
    return {
        "id": track.id,
        "generation_id": track.generation_id,
        "locale": track.locale,
        "format": track.format,
        "caption_text": track.caption_text,
        "timing": track.timing_json,
        "approval_state": track.approval_state,
        "version": track.version,
    }
