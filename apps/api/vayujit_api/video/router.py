from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.video.models import (
    VideoCaptionTrack,
    VideoGeneration,
    VideoPreset,
    VideoScript,
    VideoStoryboard,
    VideoStyle,
)
from vayujit_api.video.provider import video_provider
from vayujit_api.video.schemas import (
    CaptionRequest,
    RecoveryActionRequest,
    RegenerateRequest,
    StoryboardApprovalRequest,
    StoryboardCreateRequest,
    StoryboardUpdateRequest,
    ThumbnailAttachRequest,
    ThumbnailCandidateRequest,
    VideoApprovalRequest,
    VideoPresetPayload,
    VideoPreviewRequest,
    VideoQueueRequest,
    VideoScriptPayload,
    VideoStylePayload,
)
from vayujit_api.video.service import (
    _response,
    add_caption,
    approve,
    approve_storyboard,
    attach_thumbnail,
    cleanup_video_temp_files,
    compare_scripts,
    create_script,
    create_storyboard,
    create_style,
    decide_caption,
    decide_script,
    edit_script,
    execute_recovery_action,
    generate_thumbnail_candidate,
    preview,
    queue,
    recovery_projection,
    regenerate,
    storyboard_response,
    update_storyboard,
)

router = APIRouter(prefix="/api/v1/ai/video", tags=["ai-video"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/cleanup")
def cleanup_video(data: dict[str, object], owner: Owner) -> dict[str, int | bool]:
    paths = data.get("paths", [])
    if not isinstance(paths, list) or not all(isinstance(value, str) for value in paths):
        raise HTTPException(422, "Cleanup paths must be a list of strings.")
    return cleanup_video_temp_files(paths)


@router.get("/diagnostics")
def diagnostics() -> dict[str, object]:
    return video_provider.health()


@router.post("/preview")
def generation_preview(data: VideoPreviewRequest, db: DB, owner: Owner) -> dict[str, object]:
    return preview(db, owner, data)


@router.post("/generate", status_code=202)
@router.post("/queue", status_code=202)
def queue_generation(data: VideoQueueRequest, db: DB, owner: Owner) -> dict[str, object]:
    return queue(db, owner, data)


@router.get("/generations")
def list_generations(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        _response(db, row)
        for row in db.scalars(
            select(VideoGeneration)
            .where(VideoGeneration.owner_id == owner.id)
            .order_by(VideoGeneration.created_at.desc())
            .limit(100)
        )
    ]


@router.get("/generations/{generation_id}")
def get_generation(generation_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Video generation not found.")
    return _response(db, row)


@router.get("/generations/{generation_id}/history")
def generation_history(generation_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    row = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id,
            VideoGeneration.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Video generation not found.")
    from vayujit_api.audit.models import AuditEvent

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_id == generation_id)
        .order_by(AuditEvent.occurred_at)
    ).all()
    return [
        {
            "action": event.action,
            "timestamp": event.occurred_at,
            "actor_id": event.actor_id,
            "correlation_id": event.correlation_id or row.correlation_id,
        }
        for event in events
    ]


@router.post("/generations/{generation_id}/approve")
def approve_generation(
    generation_id: uuid.UUID, data: VideoApprovalRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return approve(db, owner, generation_id, True, data.feedback)


@router.post("/generations/{generation_id}/reject")
def reject_generation(
    generation_id: uuid.UUID, data: VideoApprovalRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return approve(db, owner, generation_id, False, data.feedback)


@router.post("/generations/{generation_id}/regenerate", status_code=202)
def regenerate_generation(
    generation_id: uuid.UUID, data: RegenerateRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return regenerate(db, owner, generation_id, data)


@router.get("/generations/{generation_id}/compare/{other_generation_id}")
def compare_generations(
    generation_id: uuid.UUID, other_generation_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    rows = db.scalars(
        select(VideoGeneration).where(
            VideoGeneration.id.in_([generation_id, other_generation_id]),
            VideoGeneration.owner_id == owner.id,
        )
    ).all()
    if len(rows) != 2:
        raise HTTPException(404, "Video generation not found.")
    return {
        "left": _response(db, next(x for x in rows if x.id == generation_id)),
        "right": _response(db, next(x for x in rows if x.id == other_generation_id)),
        "perceptual_quality_score": None,
    }


@router.get("/scripts")
def list_scripts(db: DB, owner: Owner) -> list[dict[str, object]]:
    from vayujit_api.video.service import script_response

    return [
        script_response(row)
        for row in db.scalars(
            select(VideoScript)
            .where(VideoScript.owner_id == owner.id)
            .order_by(VideoScript.created_at.desc())
        )
    ]


@router.post("/scripts", status_code=201)
def add_script(data: VideoScriptPayload, db: DB, owner: Owner) -> dict[str, object]:
    return create_script(db, owner, data)


@router.get("/scripts/{script_id}")
def get_script(script_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.video.service import script_response

    row = db.scalar(
        select(VideoScript).where(VideoScript.id == script_id, VideoScript.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Script not found.")
    return script_response(row)


@router.put("/scripts/{script_id}")
def update_script(
    script_id: uuid.UUID, data: VideoScriptPayload, db: DB, owner: Owner
) -> dict[str, object]:
    return edit_script(db, owner, script_id, data)


@router.get("/scripts/{script_id}/compare/{other_script_id}")
def compare_script_versions(
    script_id: uuid.UUID, other_script_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return compare_scripts(db, owner, script_id, other_script_id)


@router.post("/scripts/{script_id}/regenerate", status_code=201)
def regenerate_script(script_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoScript).where(VideoScript.id == script_id, VideoScript.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Script not found.")
    payload = {
        "brand_id": row.brand_id,
        "product_id": row.product_id,
        "name": row.name,
        "hook": row.hook,
        "introduction": row.introduction,
        "scenes": row.scenes,
        "narration": row.narration,
        "on_screen_text": row.on_screen_text,
        "cta": row.cta,
        "outro": row.outro,
        "target_duration_seconds": row.target_duration_seconds,
        "locale": row.locale,
    }
    return create_script(
        db, owner, type("ScriptRequest", (), {"model_dump": lambda self, **_: payload, **payload})()
    )


@router.post("/scripts/{script_id}/approve")
def approve_script(script_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return decide_script(db, owner, script_id, "approved")


@router.post("/scripts/{script_id}/reject")
def reject_script(
    script_id: uuid.UUID, data: VideoApprovalRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return decide_script(db, owner, script_id, "rejected", data.feedback)


@router.post("/scripts/{script_id}/archive")
def archive_script(script_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoScript)
        .where(VideoScript.id == script_id, VideoScript.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Video Script not found.")
    row.archived = True
    row.updated_at = __import__("vayujit_api.video.service", fromlist=["stamp"]).stamp()
    db.commit()
    from vayujit_api.video.service import script_response

    return script_response(row)


@router.get("/storyboards")
def list_storyboards(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        storyboard_response(db, row)
        for row in db.scalars(
            select(VideoStoryboard)
            .where(VideoStoryboard.owner_id == owner.id)
            .order_by(VideoStoryboard.created_at.desc())
            .limit(100)
        )
    ]


@router.post("/storyboards", status_code=201)
def add_storyboard(data: StoryboardCreateRequest, db: DB, owner: Owner) -> dict[str, object]:
    return create_storyboard(db, owner, data)


@router.get("/storyboards/{storyboard_id}")
def get_storyboard(storyboard_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStoryboard).where(
            VideoStoryboard.id == storyboard_id, VideoStoryboard.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Storyboard not found.")
    return storyboard_response(db, row)


@router.put("/storyboards/{storyboard_id}")
def edit_storyboard(
    storyboard_id: uuid.UUID, data: StoryboardUpdateRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return update_storyboard(db, owner, storyboard_id, data)


@router.post("/storyboards/{storyboard_id}/approve")
def approve_storyboard_route(
    storyboard_id: uuid.UUID, data: StoryboardApprovalRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return approve_storyboard(db, owner, storyboard_id, data.expected_row_version)


@router.get("/storyboards/{storyboard_id}/preview")
def preview_storyboard(storyboard_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStoryboard).where(
            VideoStoryboard.id == storyboard_id, VideoStoryboard.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Storyboard not found.")
    return storyboard_response(db, row)


@router.get("/presets")
def list_presets(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "id": r.id,
            "name": r.name,
            "version": r.version,
            "video_type": r.video_type,
            "target_channel": r.target_channel,
            "aspect_ratio": r.aspect_ratio,
            "resolution": r.resolution,
            "target_duration_seconds": r.target_duration_seconds,
            "max_duration_seconds": r.max_duration_seconds,
            "scene_limit": r.scene_limit,
            "caption_defaults": r.caption_defaults,
            "audio_defaults": r.audio_defaults,
            "thumbnail_required": r.thumbnail_required,
            "style_id": r.style_id,
            "provider": r.provider,
            "model": r.model,
            "guidance": r.guidance,
            "archived": r.archived,
            "is_default": r.is_default,
        }
        for r in db.scalars(
            select(VideoPreset)
            .where(VideoPreset.owner_id == owner.id)
            .order_by(VideoPreset.name, VideoPreset.version)
        )
    ]


@router.post("/presets", status_code=201)
def add_preset(data: VideoPresetPayload, db: DB, owner: Owner) -> dict[str, object]:
    version = (
        db.scalar(
            select(VideoPreset.version)
            .where(VideoPreset.owner_id == owner.id, VideoPreset.name == data.name)
            .order_by(VideoPreset.version.desc())
            .limit(1)
        )
        or 0
    )
    if data.is_default:
        db.query(VideoPreset).filter(VideoPreset.owner_id == owner.id).update(
            {VideoPreset.is_default: False}
        )
    from vayujit_api.video.service import stamp

    timestamp = stamp()
    row = VideoPreset(
        owner_id=owner.id,
        version=version + 1,
        created_at=timestamp,
        updated_at=timestamp,
        **data.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "video_type": row.video_type,
        "target_channel": row.target_channel,
        "aspect_ratio": row.aspect_ratio,
        "resolution": row.resolution,
        "target_duration_seconds": row.target_duration_seconds,
        "max_duration_seconds": row.max_duration_seconds,
        "scene_limit": row.scene_limit,
        "caption_defaults": row.caption_defaults,
        "audio_defaults": row.audio_defaults,
        "thumbnail_required": row.thumbnail_required,
        "style_id": row.style_id,
        "provider": row.provider,
        "model": row.model,
        "guidance": row.guidance,
        "archived": row.archived,
        "is_default": row.is_default,
    }


@router.post("/styles", status_code=201)
def add_style(data: VideoStylePayload, db: DB, owner: Owner) -> dict[str, object]:
    row = create_style(db, owner, data.brand_id, data.name, data.config, data.is_default)
    return {
        "id": row.id,
        "brand_id": row.brand_id,
        "name": row.name,
        "version": row.version,
        "config": row.config_json,
        "archived": row.archived,
        "is_default": row.is_default,
    }


@router.get("/styles")
def list_styles(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "id": row.id,
            "brand_id": row.brand_id,
            "name": row.name,
            "version": row.version,
            "config": row.config_json,
            "archived": row.archived,
            "is_default": row.is_default,
        }
        for row in db.scalars(
            select(VideoStyle)
            .where(VideoStyle.owner_id == owner.id)
            .order_by(VideoStyle.name, VideoStyle.version)
        )
    ]


def _preset_response(row: VideoPreset) -> dict[str, object]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "name",
            "version",
            "video_type",
            "target_channel",
            "aspect_ratio",
            "resolution",
            "target_duration_seconds",
            "max_duration_seconds",
            "scene_limit",
            "caption_defaults",
            "audio_defaults",
            "thumbnail_required",
            "style_id",
            "provider",
            "model",
            "guidance",
            "archived",
            "is_default",
        )
    }


@router.get("/presets/{preset_id}")
def get_preset(preset_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoPreset).where(VideoPreset.id == preset_id, VideoPreset.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Preset not found.")
    return _preset_response(row)


@router.post("/presets/{preset_id}/archive")
def archive_preset(preset_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoPreset)
        .where(VideoPreset.id == preset_id, VideoPreset.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Video Preset not found.")
    row.archived = True
    if row.is_default:
        row.is_default = False
    db.commit()
    return _preset_response(row)


@router.post("/presets/{preset_id}/restore")
def restore_preset(preset_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoPreset)
        .where(VideoPreset.id == preset_id, VideoPreset.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Video Preset not found.")
    row.archived = False
    db.commit()
    return _preset_response(row)


@router.post("/presets/{preset_id}/duplicate", status_code=201)
def duplicate_preset(preset_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoPreset).where(VideoPreset.id == preset_id, VideoPreset.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Preset not found.")
    payload = {
        key: getattr(row, key)
        for key in (
            "name",
            "video_type",
            "target_channel",
            "aspect_ratio",
            "resolution",
            "target_duration_seconds",
            "max_duration_seconds",
            "scene_limit",
            "caption_defaults",
            "audio_defaults",
            "thumbnail_required",
            "style_id",
            "provider",
            "model",
            "guidance",
        )
    }
    payload["name"] = f"{row.name} copy"
    value = VideoPreset(owner_id=owner.id, version=1, **payload)
    db.add(value)
    db.commit()
    db.refresh(value)
    return _preset_response(value)


@router.get("/styles/{style_id}")
def get_style(style_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStyle).where(VideoStyle.id == style_id, VideoStyle.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Style not found.")
    return {
        "id": row.id,
        "brand_id": row.brand_id,
        "name": row.name,
        "version": row.version,
        "config": row.config_json,
        "archived": row.archived,
        "is_default": row.is_default,
    }


@router.post("/styles/{style_id}/archive")
def archive_style(style_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStyle)
        .where(VideoStyle.id == style_id, VideoStyle.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Video Style not found.")
    row.archived = True
    row.is_default = False
    db.commit()
    return get_style(style_id, db, owner)


@router.post("/styles/{style_id}/restore")
def restore_style(style_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStyle)
        .where(VideoStyle.id == style_id, VideoStyle.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Video Style not found.")
    row.archived = False
    db.commit()
    return get_style(style_id, db, owner)


@router.post("/styles/{style_id}/duplicate", status_code=201)
def duplicate_style(style_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStyle).where(VideoStyle.id == style_id, VideoStyle.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Video Style not found.")
    value = create_style(db, owner, row.brand_id, f"{row.name} copy", dict(row.config_json), False)
    return {
        "id": value.id,
        "brand_id": value.brand_id,
        "name": value.name,
        "version": value.version,
        "config": value.config_json,
        "archived": value.archived,
        "is_default": value.is_default,
    }


@router.post("/styles/{style_id}/default")
def default_style(style_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoStyle)
        .where(VideoStyle.id == style_id, VideoStyle.owner_id == owner.id)
        .with_for_update()
    )
    if row is None or row.archived:
        raise HTTPException(409, "Only an active Video Style can be default.")
    db.query(VideoStyle).filter(
        VideoStyle.owner_id == owner.id, VideoStyle.brand_id == row.brand_id
    ).update({VideoStyle.is_default: False})
    row.is_default = True
    db.commit()
    return get_style(style_id, db, owner)


@router.get("/styles/{style_id}/preview")
def preview_style(style_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return get_style(style_id, db, owner)


@router.post("/generations/{generation_id}/thumbnail-candidate", status_code=202)
def thumbnail_candidate(
    generation_id: uuid.UUID, data: ThumbnailCandidateRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return generate_thumbnail_candidate(db, owner, generation_id, data)


@router.get("/generations/{generation_id}/recovery")
def generation_recovery(generation_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return recovery_projection(db, owner, generation_id)


@router.post("/generations/{generation_id}/recovery")
def generation_recovery_action(
    generation_id: uuid.UUID, data: RecoveryActionRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return execute_recovery_action(db, owner, generation_id, data)


@router.post("/generations/{generation_id}/thumbnail")
def attach_generation_thumbnail(
    generation_id: uuid.UUID, data: ThumbnailAttachRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return attach_thumbnail(db, owner, generation_id, data)


@router.post("/generations/{generation_id}/captions", status_code=201)
def create_caption(
    generation_id: uuid.UUID, data: CaptionRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return add_caption(db, owner, generation_id, data)


@router.get("/generations/{generation_id}/captions")
def list_captions(generation_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    if (
        db.scalar(
            select(VideoGeneration.id).where(
                VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
            )
        )
        is None
    ):
        raise HTTPException(404, "Video generation not found.")
    return [
        {
            "id": row.id,
            "generation_id": row.generation_id,
            "locale": row.locale,
            "format": row.format,
            "caption_text": row.caption_text,
            "timing": row.timing_json,
            "approval_state": row.approval_state,
            "version": row.version,
        }
        for row in db.scalars(
            select(VideoCaptionTrack)
            .where(VideoCaptionTrack.generation_id == generation_id)
            .order_by(VideoCaptionTrack.locale, VideoCaptionTrack.version)
        )
    ]


@router.post("/captions/{caption_id}/approve")
def approve_caption(caption_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(VideoCaptionTrack)
        .join(VideoGeneration, VideoGeneration.id == VideoCaptionTrack.generation_id)
        .where(VideoCaptionTrack.id == caption_id, VideoGeneration.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Caption track not found.")
    return decide_caption(db, owner, caption_id, "approved")


@router.post("/captions/{caption_id}/reject")
def reject_caption(caption_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return decide_caption(db, owner, caption_id, "rejected")


@router.get("/captions/{caption_id}/export")
def export_caption(caption_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, str]:
    row = db.scalar(
        select(VideoCaptionTrack)
        .join(VideoGeneration, VideoGeneration.id == VideoCaptionTrack.generation_id)
        .where(VideoCaptionTrack.id == caption_id, VideoGeneration.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Caption track not found.")
    return {"format": "webvtt", "content": "WEBVTT\n\n" + row.caption_text}
