from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.commerce.models import MarketplaceListing
from vayujit_api.core.database import Base, get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.social.models import SocialAccount, SocialPost
from vayujit_api.video.models import VideoCaptionTrack, VideoGeneration, VideoOutput

Channel = Literal["youtube", "instagram", "facebook", "amazon", "flipkart", "meesho", "campaign"]
# Local-only rules. These are deterministic test certifications, not live policy claims.
_SOCIAL_RULE = {
    "mime_types": ["video/mp4"],
    "min_duration": 1,
    "max_bytes": 50_000_000,
    "caption_support": True,
    "thumbnail_support": True,
    "thumbnail_required": False,
    "scheduling_support": True,
    "account_capability": "social_fake_video",
}
SOCIAL_FORMATS = {
    "youtube_video": {
        **_SOCIAL_RULE,
        "channel": "youtube",
        "ratio": "16:9",
        "min_duration": 1,
        "max_duration": 900,
        "min_width": 240,
        "min_height": 240,
        "max_width": 3840,
        "max_height": 2160,
        "supported_video_type": "youtube_video",
    },
    "youtube_short": {
        **_SOCIAL_RULE,
        "channel": "youtube",
        "ratio": "9:16",
        "min_duration": 1,
        "max_duration": 60,
        "min_width": 240,
        "min_height": 426,
        "max_width": 2160,
        "max_height": 3840,
        "supported_video_type": "youtube_short",
    },
    "instagram_reel": {
        **_SOCIAL_RULE,
        "channel": "instagram",
        "ratio": "9:16",
        "min_duration": 1,
        "max_duration": 90,
        "min_width": 240,
        "min_height": 426,
        "max_width": 2160,
        "max_height": 3840,
        "supported_video_type": "instagram_reel",
    },
    "instagram_story": {
        **_SOCIAL_RULE,
        "channel": "instagram",
        "ratio": "9:16",
        "min_duration": 1,
        "max_duration": 60,
        "min_width": 240,
        "min_height": 426,
        "max_width": 2160,
        "max_height": 3840,
        "supported_video_type": "instagram_story",
    },
    "facebook_reel": {
        **_SOCIAL_RULE,
        "channel": "facebook",
        "ratio": "9:16",
        "min_duration": 1,
        "max_duration": 90,
        "min_width": 240,
        "min_height": 426,
        "max_width": 2160,
        "max_height": 3840,
        "supported_video_type": "facebook_reel",
    },
    "facebook_story": {
        **_SOCIAL_RULE,
        "channel": "facebook",
        "ratio": "9:16",
        "min_duration": 1,
        "max_duration": 60,
        "min_width": 240,
        "min_height": 426,
        "max_width": 2160,
        "max_height": 3840,
        "supported_video_type": "facebook_story",
    },
}


class VideoChannelHandoff(Base):
    __tablename__ = "video_channel_handoffs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_video_handoff_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    video_generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="RESTRICT"), index=True
    )
    video_output_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_outputs.id", ondelete="RESTRICT"), index=True
    )
    video_media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    video_version: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(200))
    target_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    readiness_fingerprint: Mapped[str] = mapped_column(String(64))
    handoff_fingerprint: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(32), default="previewed", index=True)
    social_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="SET NULL")
    )
    marketplace_mapping_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_media_mappings.id", ondelete="SET NULL")
    )
    publishing_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_jobs.id", ondelete="SET NULL")
    )
    remote_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HandoffRequest(BaseModel):
    video_generation_id: uuid.UUID
    channel: Channel
    target_id: str | None = Field(default=None, max_length=200)
    target_type: str = Field(default="account", max_length=32)
    idempotency_key: str = Field(min_length=1, max_length=160)
    campaign_id: uuid.UUID | None = None
    metadata_artifact_id: uuid.UUID | None = None
    metadata_artifact_version: int | None = Field(default=None, gt=0)
    title_artifact_id: uuid.UUID | None = None
    title_artifact_version: int | None = Field(default=None, gt=0)
    description_artifact_id: uuid.UUID | None = None
    description_artifact_version: int | None = Field(default=None, gt=0)
    copy_artifact_id: uuid.UUID | None = None
    copy_artifact_version: int | None = Field(default=None, gt=0)
    cta_artifact_id: uuid.UUID | None = None
    cta_artifact_version: int | None = Field(default=None, gt=0)
    tags_artifact_id: uuid.UUID | None = None
    tags_artifact_version: int | None = Field(default=None, gt=0)
    thumbnail_output_id: uuid.UUID | None = None
    thumbnail_media_id: uuid.UUID | None = None
    thumbnail_version: int | None = Field(default=None, gt=0)
    caption_track_id: uuid.UUID | None = None
    caption_version: int | None = Field(default=None, gt=0)


class VideoReplacementPreviewRequest(BaseModel):
    post_id: uuid.UUID
    replacement_video_generation_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=160)


class VideoReplacementConfirm(BaseModel):
    post_id: uuid.UUID
    replacement_video_generation_id: uuid.UUID
    fingerprint: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=160)
    confirm: bool = False


class HandoffConfirm(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64)
    confirm: bool = False


def _now() -> datetime:
    return datetime.now(UTC)


def _video(
    db: Session, owner: User, generation_id: uuid.UUID
) -> tuple[VideoGeneration, VideoOutput, MediaAsset]:
    generation = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation_id))
    media = (
        db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == output.media_id, MediaAsset.owner_id == owner.id
            )
        )
        if output and output.media_id
        else None
    )
    if generation is None or output is None or media is None:
        raise HTTPException(404, "Approved Video output was not found.")
    if generation.status != "succeeded" or output.status != "approved" or media.status != "ready":
        raise HTTPException(409, "Only an approved, ready Video Output can be handed off.")
    return generation, output, media


def _video_version(db: Session, generation: VideoGeneration) -> int:
    version = 1
    current = generation
    seen: set[uuid.UUID] = set()
    while current.parent_generation_id and current.parent_generation_id not in seen:
        seen.add(current.id)
        parent = db.get(VideoGeneration, current.parent_generation_id)
        if parent is None:
            break
        version += 1
        current = parent
    return version


def _readiness(
    generation: VideoGeneration, output: VideoOutput, media: MediaAsset, channel: str
) -> dict[str, object]:
    blockers: list[str] = []
    warnings: list[str] = []
    rule = next(
        (value for key, value in SOCIAL_FORMATS.items() if key == generation.video_type), None
    )
    if channel in {"youtube", "instagram", "facebook"} and rule:
        if rule["channel"] != channel:
            blockers.append("video_type_channel_mismatch")
        if generation.video_type != rule["supported_video_type"]:
            blockers.append("video_type_unsupported")
        if output.duration_seconds < int(cast(int, rule["min_duration"])):
            blockers.append("duration_below_channel_minimum")
        if output.duration_seconds > int(cast(int, rule["max_duration"])):
            blockers.append("duration_exceeds_channel_limit")
        if output.width < int(cast(int, rule["min_width"])) or output.height < int(
            cast(int, rule["min_height"])
        ):
            blockers.append("dimensions_below_channel_minimum")
        if output.width > int(cast(int, rule["max_width"])) or output.height > int(
            cast(int, rule["max_height"])
        ):
            blockers.append("dimensions_exceed_channel_maximum")
        if rule["ratio"] == "9:16" and output.height <= output.width:
            blockers.append("vertical_video_required")
        if rule["ratio"] == "16:9" and output.height > output.width:
            blockers.append("landscape_video_required")
        ratio = f"{output.width}:{output.height}"
        if ratio != rule["ratio"]:
            warnings.append("aspect_ratio_differs_from_recommended")
    if output.mime_type not in cast(list[str], rule["mime_types"] if rule else ["video/mp4"]):
        blockers.append("video_mp4_required")
    if media.size_bytes > int(cast(int, rule["max_bytes"])) if rule else 50_000_000:
        blockers.append("video_file_size_exceeds_limit")
    return {
        "status": "blocked" if blockers else "ready",
        "blockers": blockers,
        "warnings": warnings,
        "duration_seconds": output.duration_seconds,
        "aspect_ratio": output.aspect_ratio,
        "dimensions": {"width": output.width, "height": output.height},
        "mime_type": output.mime_type,
        "caption": {"state": "available", "supported": bool(rule and rule["caption_support"])},
        "thumbnail": {
            "state": "not_attached",
            "supported": bool(rule and rule["thumbnail_support"]),
            "required": bool(rule and rule["thumbnail_required"]),
        },
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
    }


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(repr(payload).encode()).hexdigest()


def _resolve_lineage(
    db: Session, owner: User, generation: VideoGeneration, data: HandoffRequest
) -> dict[str, object]:
    field_lineage = [
        (data.metadata_artifact_id, data.metadata_artifact_version),
        (data.title_artifact_id, data.title_artifact_version),
        (data.description_artifact_id, data.description_artifact_version),
        (data.copy_artifact_id, data.copy_artifact_version),
        (data.cta_artifact_id, data.cta_artifact_version),
        (data.tags_artifact_id, data.tags_artifact_version),
    ]
    supplied_lineage = [
        (item_id, item_version) for item_id, item_version in field_lineage if item_id
    ]
    if (
        supplied_lineage
        and len({(item_id, item_version) for item_id, item_version in supplied_lineage}) != 1
    ):
        raise HTTPException(409, "Metadata fields must use one exact approved Artifact version.")
    metadata_id = (
        supplied_lineage[0][0] if supplied_lineage else data.metadata_artifact_id
    ) or generation.source_artifact_id
    metadata_version = (
        supplied_lineage[0][1] if supplied_lineage else data.metadata_artifact_version
    ) or generation.source_artifact_version
    metadata = None
    if metadata_id is None:
        metadata = db.scalar(
            select(GeneratedArtifact)
            .where(
                GeneratedArtifact.owner_id == owner.id,
                GeneratedArtifact.product_id == generation.product_id,
                GeneratedArtifact.status == "approved",
            )
            .order_by(GeneratedArtifact.version_number.desc())
        )
        if metadata is not None:
            metadata_id = metadata.id
            metadata_version = metadata.version_number
    if metadata_id is not None:
        metadata = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == metadata_id,
                GeneratedArtifact.owner_id == owner.id,
                GeneratedArtifact.product_id == generation.product_id,
                GeneratedArtifact.status == "approved",
            )
        )
        if metadata is None or (
            metadata_version is not None and metadata.version_number != metadata_version
        ):
            raise HTTPException(409, "The selected approved metadata Artifact is unavailable.")
        metadata_version = metadata.version_number

    thumbnail_output_id = data.thumbnail_output_id or generation.thumbnail_image_output_id
    thumbnail_media_id = data.thumbnail_media_id or generation.thumbnail_media_id
    thumbnail_version = data.thumbnail_version or generation.thumbnail_version
    thumbnail_output = None
    if thumbnail_output_id is not None:
        from vayujit_api.ai.image_models import AIImageOutput

        thumbnail_output = db.scalar(
            select(AIImageOutput).where(
                AIImageOutput.id == thumbnail_output_id,
                AIImageOutput.owner_id == owner.id,
                AIImageOutput.product_id == generation.product_id,
                AIImageOutput.status == "approved",
            )
        )
        if thumbnail_output is None:
            raise HTTPException(409, "The selected approved thumbnail is unavailable.")
        if thumbnail_media_id is not None and thumbnail_output.media_id != thumbnail_media_id:
            raise HTTPException(409, "The selected thumbnail lineage is stale.")
        thumbnail_media_id = thumbnail_output.media_id
        thumbnail_version = thumbnail_version or 1

    caption_track_id = data.caption_track_id
    caption_version = data.caption_version
    caption_track = None
    if caption_track_id is not None:
        caption_track = db.scalar(
            select(VideoCaptionTrack)
            .join(VideoGeneration, VideoGeneration.id == VideoCaptionTrack.generation_id)
            .where(
                VideoCaptionTrack.id == caption_track_id,
                VideoCaptionTrack.generation_id == generation.id,
                VideoCaptionTrack.approval_state == "approved",
            )
        )
        if caption_track is None:
            raise HTTPException(409, "The selected approved caption track is unavailable.")
    else:
        caption_track = db.scalar(
            select(VideoCaptionTrack)
            .where(
                VideoCaptionTrack.generation_id == generation.id,
                VideoCaptionTrack.locale == "en-IN",
                VideoCaptionTrack.approval_state == "approved",
            )
            .order_by(VideoCaptionTrack.version.desc())
        )
    if caption_track is not None:
        if caption_version is not None and caption_track.version != caption_version:
            raise HTTPException(409, "The selected caption track is stale.")
        caption_track_id = caption_track.id
        caption_version = caption_track.version

    return {
        "metadata_artifact_id": metadata.id if metadata else None,
        "metadata_artifact_version": metadata_version,
        "title_artifact_id": metadata.id if metadata else None,
        "title_artifact_version": metadata_version,
        "description_artifact_id": metadata.id if metadata else None,
        "description_artifact_version": metadata_version,
        "copy_artifact_id": metadata.id if metadata else None,
        "copy_artifact_version": metadata_version,
        "cta_artifact_id": metadata.id if metadata else None,
        "cta_artifact_version": metadata_version,
        "tags_artifact_id": metadata.id if metadata else None,
        "tags_artifact_version": metadata_version,
        "thumbnail_output_id": thumbnail_output.id if thumbnail_output else None,
        "thumbnail_media_id": thumbnail_media_id,
        "thumbnail_version": thumbnail_version,
        "caption_track_id": caption_track_id,
        "caption_version": caption_version,
        "caption_text": caption_track.caption_text if caption_track else None,
    }


def preview_handoff(db: Session, owner: User, data: HandoffRequest) -> dict[str, object]:
    generation, output, media = _video(db, owner, data.video_generation_id)
    readiness = _readiness(generation, output, media, data.channel)
    lineage = _resolve_lineage(db, owner, generation, data)
    readiness["caption"] = {
        "state": "available" if lineage["caption_track_id"] else "not_attached",
        "supported": True,
        "track_id": lineage["caption_track_id"],
        "version": lineage["caption_version"],
    }
    readiness["thumbnail"] = {
        "state": "available" if lineage["thumbnail_output_id"] else "not_attached",
        "supported": True,
        "required": False,
        "output_id": lineage["thumbnail_output_id"],
        "media_id": lineage["thumbnail_media_id"],
        "version": lineage["thumbnail_version"],
    }
    target_state: dict[str, object] = {"target_id": data.target_id, "target_type": data.target_type}
    if data.channel in {"youtube", "instagram", "facebook"} and data.target_id:
        account = db.scalar(
            select(SocialAccount).where(
                SocialAccount.id == uuid.UUID(data.target_id), SocialAccount.owner_id == owner.id
            )
        )
        if account is None or account.platform != data.channel or not account.enabled:
            readiness["blockers"] = [
                *cast(list[str], readiness["blockers"]),
                "social_account_unavailable",
            ]
        elif account.validation_status != "valid":
            readiness["blockers"] = [
                *cast(list[str], readiness["blockers"]),
                "social_account_not_validated",
            ]
        elif data.channel in {"youtube", "instagram", "facebook"}:
            capabilities = account.capabilities_json
            supported = cast(list[object], capabilities.get("supported_content_types", []))
            if generation.video_type not in supported:
                readiness["blockers"] = [
                    *cast(list[str], readiness["blockers"]),
                    "social_account_format_capability_missing",
                ]
        if account is not None:
            target_state["account"] = {
                "id": str(account.id),
                "platform": account.platform,
                "display_name": account.display_name,
                "enabled": account.enabled,
                "validation_status": account.validation_status,
            }
    if data.channel in {"amazon", "flipkart", "meesho"} and data.target_id:
        listing = db.scalar(
            select(MarketplaceListing).where(
                MarketplaceListing.id == uuid.UUID(data.target_id),
                MarketplaceListing.owner_id == owner.id,
                MarketplaceListing.marketplace == data.channel,
            )
        )
        if listing is None or listing.status not in {"active", "ready"}:
            readiness["blockers"] = [
                *cast(list[str], readiness["blockers"]),
                "marketplace_listing_unavailable",
            ]
        elif listing:
            target_state.update(
                {
                    "listing_id": str(listing.id),
                    "sku": listing.marketplace_sku,
                    "listing_status": listing.status,
                }
            )
    readiness["status"] = "blocked" if readiness["blockers"] else "ready"
    fingerprint_payload = {
        "video_output_id": str(output.id),
        "video_media_id": str(media.id),
        "video_version": generation.id.hex,
        "video_state": {
            "generation_updated_at": generation.updated_at.isoformat(),
            "output_status": output.status,
            "media_status": media.status,
            "media_checksum": media.checksum_sha256,
        },
        "product_id": str(generation.product_id),
        "lineage": {
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in lineage.items()
            if key != "caption_text"
        },
        "channel": data.channel,
        "target": target_state,
        "ruleset": "video-channel-v1",
    }
    fingerprint = _fingerprint(fingerprint_payload)
    return {
        "video_generation_id": generation.id,
        "video_output_id": output.id,
        "video_media_id": media.id,
        "video_version": _video_version(db, generation),
        "product_id": generation.product_id,
        "metadata_artifact_id": lineage["metadata_artifact_id"],
        "metadata_artifact_version": lineage["metadata_artifact_version"],
        "title_artifact_id": lineage["title_artifact_id"],
        "title_artifact_version": lineage["title_artifact_version"],
        "description_artifact_id": lineage["description_artifact_id"],
        "description_artifact_version": lineage["description_artifact_version"],
        "copy_artifact_id": lineage["copy_artifact_id"],
        "copy_artifact_version": lineage["copy_artifact_version"],
        "cta_artifact_id": lineage["cta_artifact_id"],
        "cta_artifact_version": lineage["cta_artifact_version"],
        "tags_artifact_id": lineage["tags_artifact_id"],
        "tags_artifact_version": lineage["tags_artifact_version"],
        "thumbnail_output_id": lineage["thumbnail_output_id"],
        "thumbnail_media_id": lineage["thumbnail_media_id"],
        "thumbnail_version": lineage["thumbnail_version"],
        "caption_track_id": lineage["caption_track_id"],
        "caption_version": lineage["caption_version"],
        "caption_text": lineage["caption_text"],
        "channel": data.channel,
        "target": target_state,
        "account": target_state.get("account"),
        "duration_seconds": output.duration_seconds,
        "aspect_ratio": output.aspect_ratio,
        "dimensions": {"width": output.width, "height": output.height},
        "mime_type": output.mime_type,
        "caption": readiness["caption"],
        "thumbnail": readiness["thumbnail"],
        "compatibility": readiness["status"],
        "blockers": readiness["blockers"],
        "warnings": readiness["warnings"],
        "changes": (
            ["Create an exact Video channel handoff"] if readiness["status"] == "ready" else []
        ),
        "target_state": target_state,
        "fingerprint": fingerprint,
        "readiness_rules": readiness["ruleset"],
    }


router = APIRouter(prefix="/api/v1/ai/video/channels", tags=["ai-video-channels"])
DB = Annotated[Session, Depends(get_session)]


@router.get("/readiness-rules")
def readiness_rules() -> dict[str, object]:
    return {
        "classification": "LOCAL FAKE-CERTIFIED RULESET",
        "social": SOCIAL_FORMATS,
        "marketplace": {
            "amazon": {"video": True},
            "flipkart": {"video": True},
            "meesho": {"video": True},
        },
    }


@router.post("/preview")
def handoff_preview(
    data: HandoffRequest, db: DB, owner: Annotated[User, Depends(current_user)]
) -> dict[str, object]:
    return preview_handoff(db, owner, data)


def _replacement_preview(
    db: Session, owner: User, data: VideoReplacementPreviewRequest
) -> dict[str, object]:
    post = db.scalar(
        select(SocialPost).where(SocialPost.id == data.post_id, SocialPost.owner_id == owner.id)
    )
    if post is None or post.video_generation_id is None:
        raise HTTPException(404, "Video Social post was not found.")
    current_generation, current_output, current_media = _video(db, owner, post.video_generation_id)
    replacement_generation, replacement_output, replacement_media = _video(
        db, owner, data.replacement_video_generation_id
    )
    if (
        replacement_generation.product_id != post.product_id
        or replacement_generation.video_type != post.content_type
    ):
        raise HTTPException(409, "Replacement Video must match the Product and Social format.")
    lineage = {
        "metadata_artifact_id": post.metadata_artifact_id or post.content_artifact_id,
        "metadata_artifact_version": post.metadata_artifact_version
        or post.content_artifact_version,
        "title_artifact_id": post.title_artifact_id,
        "title_artifact_version": post.title_artifact_version,
        "description_artifact_id": post.description_artifact_id,
        "description_artifact_version": post.description_artifact_version,
        "copy_artifact_id": post.copy_artifact_id,
        "copy_artifact_version": post.copy_artifact_version,
        "cta_artifact_id": post.cta_artifact_id,
        "cta_artifact_version": post.cta_artifact_version,
        "tags_artifact_id": post.tags_artifact_id,
        "tags_artifact_version": post.tags_artifact_version,
        "thumbnail_output_id": post.thumbnail_output_id,
        "thumbnail_media_id": post.thumbnail_media_id,
        "thumbnail_version": post.thumbnail_version,
        "caption_track_id": post.caption_track_id,
        "caption_version": post.caption_version,
    }
    fingerprint = _fingerprint(
        {
            "post_id": str(post.id),
            "current_video_output_id": str(current_output.id),
            "current_video_media_id": str(current_media.id),
            "current_video_version": post.video_version,
            "replacement_video_output_id": str(replacement_output.id),
            "replacement_video_media_id": str(replacement_media.id),
            "replacement_video_version": _video_version(db, replacement_generation),
            "platform": post.platform,
            "content_type": post.content_type,
            "lineage": {
                key: str(value) if isinstance(value, uuid.UUID) else value
                for key, value in lineage.items()
            },
        }
    )
    return {
        "post_id": post.id,
        "current_video": {
            "generation_id": current_generation.id,
            "output_id": current_output.id,
            "media_id": current_media.id,
            "version": post.video_version,
        },
        "proposed_video": {
            "generation_id": replacement_generation.id,
            "output_id": replacement_output.id,
            "media_id": replacement_media.id,
            "version": _video_version(db, replacement_generation),
        },
        "metadata": lineage,
        "thumbnail": {
            "output_id": post.thumbnail_output_id,
            "media_id": post.thumbnail_media_id,
            "version": post.thumbnail_version,
        },
        "caption": {"track_id": post.caption_track_id, "version": post.caption_version},
        "format_compatible": True,
        "metadata_impact": "unchanged_exact_approved_lineage",
        "schedule_impact": "new_publication_representation",
        "previous_publication": {
            "state": post.lifecycle_status,
            "remote_publication_id": post.remote_publication_id,
        },
        "blockers": [],
        "warnings": ["The existing publication history will remain unchanged."],
        "fingerprint": fingerprint,
    }


@router.post("/replacement/preview")
def replacement_preview(
    data: VideoReplacementPreviewRequest, db: DB, owner: Annotated[User, Depends(current_user)]
) -> dict[str, object]:
    return _replacement_preview(db, owner, data)


@router.post("/replacement/confirm")
def replacement_confirm(
    data: VideoReplacementConfirm, db: DB, owner: Annotated[User, Depends(current_user)]
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required.")
    existing = db.scalar(
        select(SocialPost).where(
            SocialPost.owner_id == owner.id, SocialPost.idempotency_key == data.idempotency_key
        )
    )
    if existing is not None:
        return {
            "post_id": existing.id,
            "state": existing.lifecycle_status,
            "idempotent_reuse": True,
            "fingerprint": data.fingerprint,
        }
    preview = _replacement_preview(
        db,
        owner,
        VideoReplacementPreviewRequest(
            post_id=data.post_id,
            replacement_video_generation_id=data.replacement_video_generation_id,
            idempotency_key=data.idempotency_key,
        ),
    )
    if preview["fingerprint"] != data.fingerprint:
        raise HTTPException(409, "This Video replacement preview is stale; create a fresh preview.")
    post = db.scalar(
        select(SocialPost).where(SocialPost.id == data.post_id, SocialPost.owner_id == owner.id)
    )
    assert post is not None and post.video_generation_id is not None
    generation, output, media = _video(db, owner, data.replacement_video_generation_id)
    stamp = _now()
    new_post = SocialPost(
        owner_id=post.owner_id,
        brand_id=post.brand_id,
        product_id=post.product_id,
        account_id=post.account_id,
        platform=post.platform,
        content_type=post.content_type,
        content_artifact_id=post.content_artifact_id,
        content_artifact_version=post.content_artifact_version,
        source_artifact_id=post.source_artifact_id,
        source_artifact_version=post.source_artifact_version,
        generation_reason="video_replacement",
        media_ids=[
            str(media.id),
            *([str(post.thumbnail_media_id)] if post.thumbnail_media_id else []),
        ],
        video_generation_id=generation.id,
        video_output_id=output.id,
        video_media_id=media.id,
        video_version=_video_version(db, generation),
        metadata_artifact_id=post.metadata_artifact_id,
        metadata_artifact_version=post.metadata_artifact_version,
        title_artifact_id=post.title_artifact_id,
        title_artifact_version=post.title_artifact_version,
        description_artifact_id=post.description_artifact_id,
        description_artifact_version=post.description_artifact_version,
        copy_artifact_id=post.copy_artifact_id,
        copy_artifact_version=post.copy_artifact_version,
        cta_artifact_id=post.cta_artifact_id,
        cta_artifact_version=post.cta_artifact_version,
        tags_artifact_id=post.tags_artifact_id,
        tags_artifact_version=post.tags_artifact_version,
        thumbnail_output_id=post.thumbnail_output_id,
        thumbnail_media_id=post.thumbnail_media_id,
        thumbnail_version=post.thumbnail_version,
        caption_track_id=post.caption_track_id,
        caption_version=post.caption_version,
        locale=post.locale,
        caption=post.caption,
        title=post.title,
        description=post.description,
        hashtags=list(post.hashtags),
        cta_json=post.cta_json,
        destination_url=post.destination_url,
        lifecycle_status="draft",
        correlation_id=uuid.uuid4().hex[:32],
        idempotency_key=data.idempotency_key,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(new_post)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="social.video_replacement_confirmed",
        entity_type="social_post",
        entity_id=new_post.id,
        metadata={
            "previous_post_id": str(post.id),
            "video_output_id": str(output.id),
            "video_version": new_post.video_version,
        },
    )
    db.commit()
    return {
        "post_id": new_post.id,
        "state": new_post.lifecycle_status,
        "idempotent_reuse": False,
        "fingerprint": data.fingerprint,
        "previous_post_id": post.id,
    }


@router.post("/{handoff_id}/confirm")
def handoff_confirm(
    handoff_id: uuid.UUID,
    data: HandoffConfirm,
    db: DB,
    owner: Annotated[User, Depends(current_user)],
) -> dict[str, object]:
    handoff = db.scalar(
        select(VideoChannelHandoff).where(
            VideoChannelHandoff.id == handoff_id, VideoChannelHandoff.owner_id == owner.id
        )
    )
    if handoff is None:
        raise HTTPException(404, "Video handoff was not found.")
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required.")
    if data.fingerprint != handoff.handoff_fingerprint:
        raise HTTPException(409, "This Video preview is stale; create a fresh preview.")
    if handoff.state == "confirmed":
        return {
            "id": handoff.id,
            "state": handoff.state,
            "idempotent_reuse": True,
            "fingerprint": handoff.handoff_fingerprint,
        }
    generation, output, media = _video(db, owner, handoff.video_generation_id)
    lineage_state = cast(dict[str, object], handoff.target_state_json.get("lineage", {}))
    current = preview_handoff(
        db,
        owner,
        HandoffRequest(
            video_generation_id=generation.id,
            channel=cast(Channel, handoff.channel),
            target_id=handoff.target_id,
            target_type=handoff.target_type,
            idempotency_key="recheck",
            metadata_artifact_id=(
                uuid.UUID(str(lineage_state["metadata_artifact_id"]))
                if lineage_state.get("metadata_artifact_id")
                else None
            ),
            metadata_artifact_version=cast(
                int | None, lineage_state.get("metadata_artifact_version")
            ),
            title_artifact_id=(
                uuid.UUID(str(lineage_state["title_artifact_id"]))
                if lineage_state.get("title_artifact_id")
                else None
            ),
            title_artifact_version=cast(int | None, lineage_state.get("title_artifact_version")),
            description_artifact_id=(
                uuid.UUID(str(lineage_state["description_artifact_id"]))
                if lineage_state.get("description_artifact_id")
                else None
            ),
            description_artifact_version=cast(
                int | None, lineage_state.get("description_artifact_version")
            ),
            copy_artifact_id=(
                uuid.UUID(str(lineage_state["copy_artifact_id"]))
                if lineage_state.get("copy_artifact_id")
                else None
            ),
            copy_artifact_version=cast(int | None, lineage_state.get("copy_artifact_version")),
            cta_artifact_id=(
                uuid.UUID(str(lineage_state["cta_artifact_id"]))
                if lineage_state.get("cta_artifact_id")
                else None
            ),
            cta_artifact_version=cast(int | None, lineage_state.get("cta_artifact_version")),
            tags_artifact_id=(
                uuid.UUID(str(lineage_state["tags_artifact_id"]))
                if lineage_state.get("tags_artifact_id")
                else None
            ),
            tags_artifact_version=cast(int | None, lineage_state.get("tags_artifact_version")),
            thumbnail_output_id=(
                uuid.UUID(str(lineage_state["thumbnail_output_id"]))
                if lineage_state.get("thumbnail_output_id")
                else None
            ),
            thumbnail_media_id=(
                uuid.UUID(str(lineage_state["thumbnail_media_id"]))
                if lineage_state.get("thumbnail_media_id")
                else None
            ),
            thumbnail_version=cast(int | None, lineage_state.get("thumbnail_version")),
            caption_track_id=(
                uuid.UUID(str(lineage_state["caption_track_id"]))
                if lineage_state.get("caption_track_id")
                else None
            ),
            caption_version=cast(int | None, lineage_state.get("caption_version")),
        ),
    )
    if current["fingerprint"] != handoff.handoff_fingerprint:
        raise HTTPException(409, "This Video preview is stale; create a fresh preview.")
    if handoff.channel in {"youtube", "instagram", "facebook"}:
        if not handoff.target_id:
            raise HTTPException(409, "A Social account is required for this Video handoff.")
        account = db.scalar(
            select(SocialAccount).where(
                SocialAccount.id == uuid.UUID(handoff.target_id),
                SocialAccount.owner_id == owner.id,
            )
        )
        if account is None or account.platform != handoff.channel or not account.enabled:
            raise HTTPException(409, "The selected Social account is unavailable.")
        content_artifact_id = cast(uuid.UUID | None, current["metadata_artifact_id"])
        if content_artifact_id is None:
            content_artifact_id = db.scalar(
                select(GeneratedArtifact.id)
                .where(
                    GeneratedArtifact.owner_id == owner.id,
                    GeneratedArtifact.product_id == generation.product_id,
                    GeneratedArtifact.status == "approved",
                )
                .order_by(GeneratedArtifact.version_number.desc())
            )
        if content_artifact_id is None:
            raise HTTPException(
                409, "An approved content Artifact is required for Social metadata."
            )
        existing = db.scalar(
            select(SocialPost).where(
                SocialPost.owner_id == owner.id,
                SocialPost.idempotency_key == f"video-handoff:{handoff.id}",
            )
        )
        if existing is None:
            post = SocialPost(
                owner_id=owner.id,
                brand_id=generation.brand_id,
                product_id=generation.product_id,
                account_id=account.id,
                platform=handoff.channel,
                content_type=generation.video_type,
                content_artifact_id=content_artifact_id,
                content_artifact_version=cast(int, current["metadata_artifact_version"] or 1),
                media_ids=[
                    str(value)
                    for value in [media.id, current["thumbnail_media_id"]]
                    if value is not None
                ],
                locale="en-IN",
                caption=cast(str | None, current["caption_text"]),
                title=None,
                description=None,
                hashtags=[],
                cta_json=None,
                destination_url=None,
                lifecycle_status="draft",
                correlation_id=handoff.correlation_id,
                idempotency_key=f"video-handoff:{handoff.id}",
                created_at=_now(),
                updated_at=_now(),
                video_generation_id=generation.id,
                video_output_id=output.id,
                video_media_id=media.id,
                video_version=_video_version(db, generation),
                metadata_artifact_id=cast(uuid.UUID | None, current["metadata_artifact_id"]),
                metadata_artifact_version=cast(int | None, current["metadata_artifact_version"]),
                title_artifact_id=cast(uuid.UUID | None, current["title_artifact_id"]),
                title_artifact_version=cast(int | None, current["title_artifact_version"]),
                description_artifact_id=cast(uuid.UUID | None, current["description_artifact_id"]),
                description_artifact_version=cast(
                    int | None, current["description_artifact_version"]
                ),
                copy_artifact_id=cast(uuid.UUID | None, current["copy_artifact_id"]),
                copy_artifact_version=cast(int | None, current["copy_artifact_version"]),
                cta_artifact_id=cast(uuid.UUID | None, current["cta_artifact_id"]),
                cta_artifact_version=cast(int | None, current["cta_artifact_version"]),
                tags_artifact_id=cast(uuid.UUID | None, current["tags_artifact_id"]),
                tags_artifact_version=cast(int | None, current["tags_artifact_version"]),
                thumbnail_output_id=cast(uuid.UUID | None, current["thumbnail_output_id"]),
                thumbnail_media_id=cast(uuid.UUID | None, current["thumbnail_media_id"]),
                thumbnail_version=cast(int | None, current["thumbnail_version"]),
                caption_track_id=cast(uuid.UUID | None, current["caption_track_id"]),
                caption_version=cast(int | None, current["caption_version"]),
            )
            db.add(post)
            db.flush()
            handoff.social_post_id = post.id
    handoff.state = "confirmed"
    handoff.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action=f"{handoff.channel}_video_handoff_confirmed",
        entity_type="video_channel_handoff",
        entity_id=handoff.id,
        metadata={"video_output_id": str(output.id), "video_media_id": str(media.id)},
    )
    db.commit()
    return {
        "id": handoff.id,
        "state": handoff.state,
        "idempotent_reuse": False,
        "fingerprint": handoff.handoff_fingerprint,
    }


@router.post("/prepare")
def prepare_handoff(
    data: HandoffRequest, db: DB, owner: Annotated[User, Depends(current_user)]
) -> dict[str, object]:
    existing = db.scalar(
        select(VideoChannelHandoff).where(
            VideoChannelHandoff.owner_id == owner.id,
            VideoChannelHandoff.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return {
            "id": existing.id,
            "state": existing.state,
            "fingerprint": existing.handoff_fingerprint,
            "idempotent_reuse": True,
        }
    result = preview_handoff(db, owner, data)
    if result["compatibility"] != "ready":
        raise HTTPException(409, "Video is not ready for this channel.")
    stamp = _now()
    row = VideoChannelHandoff(
        owner_id=owner.id,
        product_id=result["product_id"],
        video_generation_id=data.video_generation_id,
        video_output_id=result["video_output_id"],
        video_media_id=result["video_media_id"],
        video_version=result["video_version"],
        channel=data.channel,
        target_type=data.target_type,
        target_id=data.target_id,
        target_state_json={
            **cast(dict[str, object], result["target_state"]),
            "lineage": {
                key: str(value) if isinstance(value, uuid.UUID) else value
                for key, value in {
                    "metadata_artifact_id": result["metadata_artifact_id"],
                    "metadata_artifact_version": result["metadata_artifact_version"],
                    "title_artifact_id": result["title_artifact_id"],
                    "title_artifact_version": result["title_artifact_version"],
                    "description_artifact_id": result["description_artifact_id"],
                    "description_artifact_version": result["description_artifact_version"],
                    "copy_artifact_id": result["copy_artifact_id"],
                    "copy_artifact_version": result["copy_artifact_version"],
                    "cta_artifact_id": result["cta_artifact_id"],
                    "cta_artifact_version": result["cta_artifact_version"],
                    "tags_artifact_id": result["tags_artifact_id"],
                    "tags_artifact_version": result["tags_artifact_version"],
                    "thumbnail_output_id": result["thumbnail_output_id"],
                    "thumbnail_media_id": result["thumbnail_media_id"],
                    "thumbnail_version": result["thumbnail_version"],
                    "caption_track_id": result["caption_track_id"],
                    "caption_version": result["caption_version"],
                }.items()
                if value is not None
            },
        },
        readiness_fingerprint=result["fingerprint"],
        handoff_fingerprint=result["fingerprint"],
        actor_id=owner.id,
        correlation_id=uuid.uuid4().hex[:32],
        idempotency_key=data.idempotency_key,
        state="previewed",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action=f"{data.channel}_video_handoff_preview",
        entity_type="video_channel_handoff",
        entity_id=row.id,
        metadata={"fingerprint": row.handoff_fingerprint},
    )
    db.commit()
    return {
        "id": row.id,
        "state": row.state,
        "fingerprint": row.handoff_fingerprint,
        "idempotent_reuse": False,
        "preview": result,
    }


@router.get("/products/{product_id}")
def product_video_channels(
    product_id: uuid.UUID, db: DB, owner: Annotated[User, Depends(current_user)]
) -> list[dict[str, object]]:
    if (
        db.scalar(select(Product.id).where(Product.id == product_id, Product.owner_id == owner.id))
        is None
    ):
        raise HTTPException(404, "Product not found.")
    rows = list(
        db.scalars(
            select(VideoChannelHandoff)
            .where(
                VideoChannelHandoff.owner_id == owner.id,
                VideoChannelHandoff.product_id == product_id,
            )
            .order_by(VideoChannelHandoff.updated_at.desc())
        )
    )
    projection: list[dict[str, object]] = []
    for row in rows:
        generation = db.get(VideoGeneration, row.video_generation_id)
        latest_generation = db.scalar(
            select(VideoGeneration)
            .join(VideoOutput, VideoOutput.generation_id == VideoGeneration.id)
            .join(MediaAsset, MediaAsset.id == VideoOutput.media_id)
            .where(
                VideoGeneration.owner_id == owner.id,
                VideoGeneration.product_id == product_id,
                VideoGeneration.video_type
                == (generation.video_type if generation else row.channel),
                VideoGeneration.status == "succeeded",
                VideoOutput.status == "approved",
                MediaAsset.status == "ready",
            )
            .order_by(VideoGeneration.created_at.desc())
        )
        latest_output = (
            db.scalar(select(VideoOutput).where(VideoOutput.generation_id == latest_generation.id))
            if latest_generation
            else None
        )
        post = db.scalar(
            select(SocialPost).where(
                SocialPost.owner_id == owner.id,
                SocialPost.video_generation_id == row.video_generation_id,
                SocialPost.platform == row.channel,
            )
        )
        account = db.get(SocialAccount, post.account_id) if post else None
        job = (
            db.scalar(
                select(PublishingJob).where(
                    PublishingJob.owner_id == owner.id,
                    PublishingJob.idempotency_key == f"social-post:{post.id}",
                )
            )
            if post
            else None
        )
        schedule = (
            db.get(PublishingSchedule, post.schedule_id) if post and post.schedule_id else None
        )
        current_version = post.video_version if post else row.video_version
        update_available = bool(latest_output and latest_output.id != row.video_output_id)
        actions = ["preview_social_video", "open_social_post"]
        if update_available:
            actions.append("preview_video_update")
        if post:
            if post.lifecycle_status in {"draft", "failed", "approved"}:
                actions.extend(["publish_now", "schedule"])
            if post.failure_code:
                actions.append("open_recovery")
        projection.append(
            {
                "channel": row.channel,
                "handoff_id": row.id,
                "video_generation_id": row.video_generation_id,
                "video_output_id": row.video_output_id,
                "video_media_id": row.video_media_id,
                "video_version": current_version,
                "current_video_output_id": row.video_output_id,
                "current_video_version": current_version,
                "latest_approved_video_output_id": (
                    latest_output.id if latest_output else row.video_output_id
                ),
                "latest_approved_video_version": (
                    _video_version(db, latest_generation) if latest_generation else current_version
                ),
                "update_available": update_available,
                "current_publication": (
                    {
                        "social_post_id": post.id,
                        "remote_publication_id": post.remote_publication_id,
                        "state": post.lifecycle_status,
                    }
                    if post
                    else None
                ),
                "next_scheduled_publication": (
                    {"schedule_id": schedule.id, "scheduled_at_utc": schedule.next_run_at_utc}
                    if schedule
                    else None
                ),
                "account_state": (
                    {
                        "id": account.id,
                        "enabled": account.enabled,
                        "validation_status": account.validation_status,
                    }
                    if account
                    else None
                ),
                "readiness": "ready" if row.state == "confirmed" else "needs_review",
                "failure_state": (
                    {"code": post.failure_code, "safe_message": post.safe_failure_message}
                    if post and post.failure_code
                    else None
                ),
                "blockers": [],
                "warnings": [],
                "actions": actions,
                "job_id": job.id if job else None,
            }
        )
    return projection
