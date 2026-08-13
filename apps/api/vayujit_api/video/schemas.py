import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

VideoType = Literal[
    "product_showcase",
    "slideshow",
    "marketplace_product_video",
    "instagram_reel",
    "facebook_reel",
    "instagram_story",
    "facebook_story",
    "youtube_video",
    "youtube_short",
    "promotional_video",
    "explainer_video",
    "product_demo",
    "testimonial_style",
    "generic_social_video",
]
REGENERATION_REASONS = Literal[
    "pacing",
    "scene_order",
    "wrong_source_image",
    "wrong_text",
    "branding",
    "duration",
    "captions",
    "audio",
    "cta",
    "platform_readiness",
    "rejected_feedback",
    "custom",
]


class VideoPreviewRequest(BaseModel):
    product_id: uuid.UUID
    brand_id: uuid.UUID
    video_type: VideoType = "product_showcase"
    target_channel: str = "youtube"
    source_artifact_id: uuid.UUID | None = None
    source_artifact_version: int | None = Field(default=None, ge=1)
    script_id: uuid.UUID | None = None
    script_version: int | None = Field(default=None, ge=1)
    source_media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
    storyboard_id: uuid.UUID | None = None
    storyboard_version: int | None = Field(default=None, ge=1)
    style_id: uuid.UUID | None = None
    style_version: int | None = Field(default=None, ge=1)
    aspect_ratio: str = Field(default="16:9", pattern=r"^\d{1,4}:\d{1,4}$")
    resolution: str = "1280x720"
    duration_seconds: int = Field(default=10, ge=1, le=60)
    preset_id: uuid.UUID | None = None
    failure_scenario: str = "success"
    audio_mode: Literal[
        "none",
        "uploaded_audio",
        "background_music",
        "deterministic_narration_placeholder",
        "future_provider_voice",
    ] = "none"
    audio_media_id: uuid.UUID | None = None
    thumbnail_image_output_id: uuid.UUID | None = None
    thumbnail_media_id: uuid.UUID | None = None
    thumbnail_version: int | None = Field(default=None, ge=1)


class VideoQueueRequest(VideoPreviewRequest):
    idempotency_key: str | None = Field(default=None, max_length=180)
    storyboard: dict[str, object] = Field(default_factory=dict)


class VideoGenerationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    video_type: str
    target_channel: str
    source_artifact_id: uuid.UUID | None
    source_artifact_version: int | None
    script_id: uuid.UUID | None = None
    script_version: int | None = None
    source_media_ids: list[str]
    audio_mode: str = "none"
    audio_media_id: uuid.UUID | None = None
    thumbnail_image_output_id: uuid.UUID | None = None
    thumbnail_media_id: uuid.UUID | None = None
    thumbnail_version: int | None = None
    provider_key: str
    model: str
    output_media_id: uuid.UUID | None = None
    output_checksum: str | None = None
    failure_code: str | None = None
    safe_error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None


class VideoScriptPayload(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    hook: str = Field(min_length=1, max_length=2000)
    introduction: str = Field(min_length=1, max_length=4000)
    scenes: list[dict[str, object]] = Field(default_factory=list, max_length=24)
    narration: str = Field(min_length=1, max_length=12000)
    on_screen_text: str = Field(default="", max_length=4000)
    cta: str = Field(default="", max_length=1000)
    outro: str = Field(default="", max_length=2000)
    target_duration_seconds: int = Field(default=30, ge=1, le=180)
    locale: Literal["en-IN", "hi-IN", "te-IN"] = "en-IN"


class VideoPresetPayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    video_type: VideoType = "product_showcase"
    target_channel: str = Field(default="youtube", min_length=1, max_length=40)
    aspect_ratio: str = Field(default="16:9", pattern=r"^\d{1,4}:\d{1,4}$")
    resolution: str = Field(default="1280x720", pattern=r"^\d{3,4}x\d{3,4}$")
    target_duration_seconds: int = Field(default=10, ge=1, le=60)
    max_duration_seconds: int = Field(default=60, ge=1, le=60)
    scene_limit: int = Field(default=12, ge=1, le=24)
    caption_defaults: dict[str, object] = Field(default_factory=dict)
    audio_defaults: dict[str, object] = Field(default_factory=dict)
    thumbnail_required: bool = False
    style_id: uuid.UUID | None = None
    provider: str = "deterministic_video_local"
    model: str = "local-slideshow-v1"
    guidance: str | None = Field(default=None, max_length=2000)
    is_default: bool = False


class VideoStylePayload(BaseModel):
    brand_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    config: dict[str, object] = Field(default_factory=dict)
    is_default: bool = False


class VideoPresetResponse(VideoPresetPayload):
    id: uuid.UUID
    version: int
    archived: bool
    is_default: bool


class VideoApprovalRequest(BaseModel):
    feedback: str | None = Field(default=None, max_length=1000)


class StoryboardScenePayload(BaseModel):
    stable_key: str = Field(default="scene", min_length=1, max_length=80)
    scene_order: int = Field(ge=1, le=24)
    duration_seconds: int = Field(default=3, ge=1, le=60)
    source_media_id: uuid.UUID | None = None
    scene_text: str | None = Field(default=None, max_length=500)
    narration: str | None = Field(default=None, max_length=1000)
    transition: str = Field(default="cut", min_length=1, max_length=40)
    visual_guidance: str | None = Field(default=None, max_length=1000)
    background: str | None = Field(default=None, max_length=240)
    cta: str | None = Field(default=None, max_length=240)
    locale: str = Field(default="en-IN", pattern=r"^[a-z]{2}-[A-Z]{2}$")


class StoryboardCreateRequest(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID
    source_artifact_id: uuid.UUID | None = None
    source_artifact_version: int | None = Field(default=None, ge=1)
    video_type: VideoType = "product_showcase"
    target_channel: str = Field(default="youtube", min_length=1, max_length=40)
    locale: str = Field(default="en-IN", pattern=r"^[a-z]{2}-[A-Z]{2}$")
    aspect_ratio: str = Field(default="16:9", pattern=r"^\d{1,4}:\d{1,4}$")
    resolution: str = Field(default="1280x720", pattern=r"^\d{3,4}x\d{3,4}$")
    scenes: list[StoryboardScenePayload] = Field(default_factory=list, max_length=24)


class StoryboardUpdateRequest(BaseModel):
    expected_row_version: int = Field(ge=1)
    scenes: list[StoryboardScenePayload] = Field(max_length=24)


class StoryboardApprovalRequest(BaseModel):
    expected_row_version: int = Field(ge=1)


class ThumbnailCandidateRequest(BaseModel):
    instructions: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=160)


class ThumbnailAttachRequest(BaseModel):
    image_output_id: uuid.UUID
    media_id: uuid.UUID
    image_version: int = Field(default=1, ge=1)


class RecoveryActionRequest(BaseModel):
    action: Literal[
        "retry_generation",
        "regenerate",
        "change_provider",
        "change_model",
        "open_storyboard",
        "open_source_media",
        "edit_script",
        "replace_media",
        "remove_audio",
        "review_failure",
    ]
    idempotency_key: str | None = Field(default=None, max_length=160)
    reason: str | None = Field(default=None, max_length=1000)
    expected_failure_code: str | None = Field(default=None, max_length=80)
    expected_status: str | None = Field(default=None, max_length=30)


class CaptionRequest(BaseModel):
    locale: Literal["en-IN", "hi-IN", "te-IN"] = "en-IN"
    caption_text: str = Field(min_length=1, max_length=10000)
    timing: list[dict[str, object]] = Field(default_factory=list, max_length=200)
    source_artifact_id: uuid.UUID | None = None
    source_artifact_version: int | None = Field(default=None, ge=1)


class RegenerateRequest(BaseModel):
    reason: REGENERATION_REASONS
    feedback: str | None = Field(default=None, max_length=2000)
    storyboard_id: uuid.UUID | None = None
    style_id: uuid.UUID | None = None
    preset_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=180)
