from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.models import AdCampaign
from vayujit_api.ads.schemas import AdsCreativeCreate
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.video.models import VideoGeneration, VideoOutput


def _fail(message: str) -> None:
    raise HTTPException(status_code=422, detail=message)


def creative_readiness(
    db: Session, owner: User, data: AdsCreativeCreate, campaign: AdCampaign | None = None
) -> dict[str, Any]:
    campaign = campaign or db.scalar(
        select(AdCampaign).where(AdCampaign.id == data.campaign_id, AdCampaign.owner_id == owner.id)
    )
    if campaign is None:
        _fail("Ads campaign not found.")
    assert campaign is not None
    blockers: list[str] = []
    warnings: list[str] = []
    informational: list[str] = [
        "Readiness is server-authoritative and uses exact immutable lineage."
    ]
    provider = campaign.provider
    capabilities = connector_for(provider).capabilities()
    placements = [str(value) for value in (data.model_dump().get("placements") or [])]
    exact: dict[str, object] = {
        "creative_type": data.creative_type,
        "campaign_id": str(campaign.id),
        "product_id": (
            str(data.product_id or campaign.product_id)
            if (data.product_id or campaign.product_id)
            else None
        ),
    }
    if data.product_id and campaign.product_id and data.product_id != campaign.product_id:
        blockers.append("Creative Product does not match the Campaign Product.")
    if data.destination_url:
        from vayujit_api.ads.service import safe_destination

        try:
            safe_destination(data.destination_url)
        except HTTPException as error:
            blockers.append(str(error.detail))
    if data.creative_type == "content":
        if data.artifact_id is None or data.artifact_version is None:
            blockers.append("An exact approved Content Artifact version is required.")
        else:
            artifact = db.scalar(
                select(GeneratedArtifact).where(
                    GeneratedArtifact.id == data.artifact_id,
                    GeneratedArtifact.owner_id == owner.id,
                    GeneratedArtifact.version_number == data.artifact_version,
                )
            )
            if artifact is None or artifact.status != "approved":
                blockers.append("The exact Content Artifact version must be approved.")
            else:
                if campaign.product_id and artifact.product_id != campaign.product_id:
                    blockers.append("Content Artifact Product does not match the Campaign Product.")
                if artifact.locale != data.locale:
                    blockers.append("Content Artifact locale does not match the creative locale.")
                exact.update(
                    {"artifact_id": str(artifact.id), "artifact_version": artifact.version_number}
                )
    elif data.creative_type == "image":
        if not data.image_output_id or not data.image_media_id or not data.image_version:
            blockers.append("An exact approved Image Output and Media version are required.")
        else:
            image_output = db.scalar(
                select(AIImageOutput).where(
                    AIImageOutput.id == data.image_output_id,
                    AIImageOutput.owner_id == owner.id,
                )
            )
            media = db.scalar(
                select(MediaAsset).where(
                    MediaAsset.id == data.image_media_id,
                    MediaAsset.owner_id == owner.id,
                )
            )
            if image_output is None or image_output.status != "approved":
                blockers.append("The exact Image Output must be approved.")
            if media is None or media.status != "ready" or not media.mime_type.startswith("image/"):
                blockers.append("The exact Image Media must be ready and use an image MIME type.")
            if (
                image_output
                and media
                and image_output.media_id
                and image_output.media_id != media.id
            ):
                blockers.append("Image Output Media does not match the exact Media identity.")
            if image_output and media:
                if not image_output.checksum_sha256 or not media.checksum_sha256:
                    blockers.append("Image checksum is required for exact Media identity.")
                elif image_output.checksum_sha256 != media.checksum_sha256:
                    blockers.append("Image checksum does not match the exact Media identity.")
                if not image_output.size_bytes or not media.size_bytes:
                    blockers.append("Image size is required for exact Media identity.")
                elif image_output.size_bytes != media.size_bytes:
                    blockers.append("Image size does not match the exact Media identity.")
                if not image_output.actual_width or not media.width:
                    blockers.append("Image dimensions are required for exact Media identity.")
                elif image_output.actual_width != media.width:
                    blockers.append("Image width does not match the exact Media identity.")
                if not image_output.actual_height or not media.height:
                    blockers.append("Image dimensions are required for exact Media identity.")
                elif image_output.actual_height != media.height:
                    blockers.append("Image height does not match the exact Media identity.")
            if (
                image_output
                and campaign.product_id
                and image_output.product_id != campaign.product_id
            ):
                blockers.append("Image Output Product does not match the Campaign Product.")
            exact.update(
                {
                    "image_output_id": str(data.image_output_id),
                    "image_media_id": str(data.image_media_id),
                    "image_version": data.image_version,
                }
            )
    elif data.creative_type == "video":
        if (
            not data.video_generation_id
            or not data.video_output_id
            or not data.video_media_id
            or not data.video_version
        ):
            blockers.append(
                "An exact approved Video Generation, Output, and Media version are required."
            )
        else:
            generation = db.scalar(
                select(VideoGeneration).where(
                    VideoGeneration.id == data.video_generation_id,
                    VideoGeneration.owner_id == owner.id,
                )
            )
            video_output = db.scalar(
                select(VideoOutput).where(
                    VideoOutput.id == data.video_output_id,
                    VideoOutput.owner_id == owner.id,
                )
            )
            media = db.scalar(
                select(MediaAsset).where(
                    MediaAsset.id == data.video_media_id,
                    MediaAsset.owner_id == owner.id,
                )
            )
            if generation is None or generation.status != "succeeded":
                blockers.append("The exact Video Generation must be succeeded.")
            if video_output is None or video_output.status not in {"approved", "succeeded"}:
                blockers.append("The exact Video Output must be approved.")
            if media is None or media.status != "ready" or not media.mime_type.startswith("video/"):
                blockers.append("The exact Video Media must be ready and use a video MIME type.")
            if video_output and video_output.generation_id != data.video_generation_id:
                blockers.append("Video Output does not match the exact Video Generation.")
            if video_output and media:
                if not video_output.checksum_sha256 or not media.checksum_sha256:
                    blockers.append("Video checksum is required for exact Media identity.")
                elif video_output.checksum_sha256 != media.checksum_sha256:
                    blockers.append("Video checksum does not match the exact Media identity.")
                if video_output.size_bytes != media.size_bytes:
                    blockers.append("Video size does not match the exact Media identity.")
                if video_output.width != media.width or video_output.height != media.height:
                    blockers.append("Video dimensions do not match the exact Media identity.")
                if video_output.mime_type != media.mime_type:
                    blockers.append("Video MIME type does not match the exact Media identity.")
            if generation and campaign.product_id and generation.product_id != campaign.product_id:
                blockers.append("Video Generation Product does not match the Campaign Product.")
            exact.update(
                {
                    "video_generation_id": str(data.video_generation_id),
                    "video_output_id": str(data.video_output_id),
                    "video_media_id": str(data.video_media_id),
                    "video_version": data.video_version,
                }
            )
    if data.cta and capabilities.get("cta_types") and data.cta not in capabilities["cta_types"]:
        blockers.append("The selected CTA is unsupported by this provider.")
    if placements:
        unsupported = sorted(set(placements).difference(capabilities.get("placements", [])))
        if unsupported:
            blockers.append("One or more placements are unsupported by this provider.")
    if data.headline and len(data.headline) > capabilities.get("text_limits", {}).get(
        "headline", 10000
    ):
        blockers.append("Headline exceeds the provider character limit.")
    ready = not blockers
    result = {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "informational": informational,
        "exact_creative": exact,
        "provider": provider,
        "objective": campaign.objective,
        "placements": placements,
    }
    result["fingerprint"] = (
        __import__("hashlib")
        .sha256(__import__("json").dumps(result, sort_keys=True, default=str).encode())
        .hexdigest()
    )
    return result


def require_creative_readiness(
    db: Session, owner: User, data: AdsCreativeCreate, campaign: AdCampaign | None = None
) -> dict[str, Any]:
    result = creative_readiness(db, owner, data, campaign)
    if not result["ready"]:
        _fail(str(result["blockers"][0]))
    return result
