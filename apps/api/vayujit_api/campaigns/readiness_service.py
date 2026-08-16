from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.campaigns.models import Campaign, CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.schemas import ReadinessIssue, ReadinessResponse
from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceListing
from vayujit_api.core.config import get_settings
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.models import PublishingDestination
from vayujit_api.social.models import SocialAccount
from vayujit_api.video.models import VideoCaptionTrack, VideoGeneration, VideoOutput


def activity_readiness(
    db: Session, campaign: Campaign, activity: CampaignActivity
) -> ReadinessResponse:
    issues: list[ReadinessIssue] = []

    def issue(code: str, message: str, resolution: str, target: str | None = None) -> None:
        issues.append(
            ReadinessIssue(
                code=code,
                severity="error",
                safe_message=message,
                activity_id=activity.id,
                suggested_resolution=resolution,
                navigation_target=target,
            )
        )

    checkpoint = activity.connector_key is None
    video_activity = activity.activity_type == "video_campaign"
    artifact = db.get(GeneratedArtifact, activity.artifact_id) if activity.artifact_id else None
    destination = (
        db.get(PublishingDestination, activity.destination_id) if activity.destination_id else None
    )
    if not activity.enabled:
        issue("activity_disabled", "Activity is disabled.", "Enable the activity.")
    if video_activity:
        if (
            artifact is None
            or artifact.owner_id != campaign.owner_id
            or artifact.product_id != activity.product_id
            or artifact.status != "approved"
            or artifact.version_number != activity.artifact_version
        ):
            issue(
                "video_metadata_invalid",
                "The exact approved Video metadata Artifact is unavailable.",
                "Select the exact approved metadata Artifact.",
                "/ai",
            )
        generation = (
            db.get(VideoGeneration, activity.video_generation_id)
            if activity.video_generation_id
            else None
        )
        output = db.get(VideoOutput, activity.video_output_id) if activity.video_output_id else None
        media = db.get(MediaAsset, activity.video_media_id) if activity.video_media_id else None
        if (
            not generation
            or not output
            or not media
            or generation.owner_id != campaign.owner_id
            or output.owner_id != campaign.owner_id
            or media.owner_id != campaign.owner_id
        ):
            issue(
                "video_reference_missing",
                "The exact approved Video reference is unavailable.",
                "Select the exact approved Video.",
                "/ai/video",
            )
        else:
            if generation.product_id != activity.product_id or generation.status != "succeeded":
                issue(
                    "video_generation_invalid",
                    "The exact Video Generation is not approved for this Product.",
                    "Review the approved Video.",
                    "/ai/video",
                )
            version = 1
            parent_id = generation.parent_generation_id
            seen: set[object] = set()
            while parent_id and parent_id not in seen:
                seen.add(parent_id)
                version += 1
                parent = db.get(VideoGeneration, parent_id)
                parent_id = parent.parent_generation_id if parent else None
            if activity.video_version != version:
                issue(
                    "video_version_changed",
                    "The exact Video version is unavailable; replace the Activity.",
                    "Create a fresh Video replacement preview.",
                )
            if output.generation_id != generation.id or output.status != "approved":
                issue(
                    "video_output_invalid",
                    "The exact Video Output is not approved.",
                    "Approve the exact Video Output.",
                    "/ai/video",
                )
            if media.status != "ready" or output.media_id != media.id:
                issue(
                    "video_media_invalid",
                    "The exact Video Media is not ready.",
                    "Prepare the exact Video Media.",
                    "/media",
                )
        if any(
            (
                activity.video_thumbnail_output_id,
                activity.video_thumbnail_media_id,
                activity.video_thumbnail_version,
            )
        ):
            thumbnail_output = (
                db.get(AIImageOutput, activity.video_thumbnail_output_id)
                if activity.video_thumbnail_output_id
                else None
            )
            thumbnail_media = (
                db.get(MediaAsset, activity.video_thumbnail_media_id)
                if activity.video_thumbnail_media_id
                else None
            )
            if (
                thumbnail_output is None
                or thumbnail_media is None
                or thumbnail_output.owner_id != campaign.owner_id
                or thumbnail_output.product_id != activity.product_id
                or thumbnail_output.status != "approved"
                or thumbnail_output.media_id != thumbnail_media.id
                or thumbnail_media.status != "ready"
            ):
                issue(
                    "video_thumbnail_invalid",
                    "The exact approved Video Thumbnail is unavailable.",
                    "Review the Video Thumbnail.",
                    "/ai/images",
                )
        if any((activity.video_caption_track_id, activity.video_caption_version)):
            caption = (
                db.get(VideoCaptionTrack, activity.video_caption_track_id)
                if activity.video_caption_track_id
                else None
            )
            if (
                caption is None
                or caption.generation_id != activity.video_generation_id
                or caption.version != activity.video_caption_version
                or caption.approval_state != "approved"
            ):
                issue(
                    "video_caption_invalid",
                    "The exact approved Video Caption is unavailable.",
                    "Review the Video Caption.",
                    "/ai/video",
                )
        if activity.video_channel in {
            "youtube_video",
            "youtube_short",
            "instagram_reel",
            "instagram_story",
            "facebook_reel",
            "facebook_story",
        }:
            account = (
                db.get(SocialAccount, activity.video_target_account_id)
                if activity.video_target_account_id
                else None
            )
            expected = {
                "youtube_video": "youtube",
                "youtube_short": "youtube",
                "instagram_reel": "instagram",
                "instagram_story": "instagram",
                "facebook_reel": "facebook",
                "facebook_story": "facebook",
            }[activity.video_channel]
            if not account or account.owner_id != campaign.owner_id:
                issue(
                    "video_account_missing",
                    "The target Social account is unavailable.",
                    "Select a valid Social account.",
                )
            elif (
                account.platform != expected
                or not account.enabled
                or account.validation_status != "valid"
            ):
                issue(
                    "video_account_not_ready",
                    "The target Social account is not ready.",
                    "Enable and validate the target account.",
                )
        elif activity.video_channel in {"amazon", "flipkart", "meesho"}:
            marketplace_account = (
                db.get(MarketplaceAccount, activity.video_target_account_id)
                if activity.video_target_account_id
                else None
            )
            listing = (
                db.get(MarketplaceListing, activity.video_target_listing_id)
                if activity.video_target_listing_id
                else None
            )
            if (
                not marketplace_account
                or marketplace_account.owner_id != campaign.owner_id
                or marketplace_account.marketplace != activity.video_channel
            ):
                issue(
                    "video_marketplace_account_missing",
                    "The target marketplace account is unavailable.",
                    "Select a valid marketplace account.",
                )
            elif (
                not marketplace_account.enabled or marketplace_account.validation_status != "valid"
            ):
                issue(
                    "video_marketplace_account_not_ready",
                    "The marketplace account is not ready.",
                    "Enable and validate the marketplace account.",
                )
            if (
                not listing
                or listing.owner_id != campaign.owner_id
                or listing.product_id != activity.product_id
            ):
                issue(
                    "video_listing_missing",
                    "The target marketplace listing is unavailable.",
                    "Select a matching listing.",
                )
            elif listing.status not in {"active", "ready"}:
                issue(
                    "video_listing_not_ready",
                    "The marketplace listing is not ready.",
                    "Prepare the listing.",
                )
        else:
            issue(
                "video_channel_invalid",
                "The target Video channel is unsupported.",
                "Select a supported channel.",
            )
    if not checkpoint and not video_activity:
        if not artifact or artifact.owner_id != campaign.owner_id:
            issue("artifact_missing", "Artifact is unavailable.", "Select an Artifact.", "/ai")
        elif artifact.version_number != activity.artifact_version:
            issue(
                "artifact_version_changed", "Exact Artifact version is unavailable.", "Replace it."
            )
        elif artifact.status != "approved":
            issue("approval_missing", "Artifact approval is required.", "Approve the Artifact.")
        if not destination or destination.owner_id != campaign.owner_id:
            issue("destination_missing", "Destination is unavailable.", "Select a destination.")
        elif destination.status != "active":
            issue("destination_disabled", "Destination is disabled.", "Enable the destination.")
        elif destination.connector_key != activity.connector_key:
            issue("connector_mismatch", "Destination connector is incompatible.", "Choose a match.")
    if (
        activity.scheduled_at_utc < campaign.start_at_utc
        or activity.scheduled_at_utc > campaign.end_at_utc
    ):
        severity: Literal["error", "warning"] = (
            "error" if campaign.scheduling_policy == "strict_window" else "warning"
        )
        issues.append(
            ReadinessIssue(
                code="outside_campaign_window",
                severity=severity,
                safe_message="Activity falls outside the Campaign window.",
                activity_id=activity.id,
                suggested_resolution="Change the activity time or Campaign window.",
            )
        )
    if Path(get_settings().maintenance_marker).resolve().exists():
        issue("maintenance_mode", "Maintenance mode blocks scheduling.", "Exit maintenance mode.")
    dependencies = list(
        db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.successor_activity_id == activity.id
            )
        )
    )
    for dependency in dependencies:
        predecessor = db.get(CampaignActivity, dependency.predecessor_activity_id)
        satisfied = bool(
            predecessor
            and (
                predecessor.status in {"succeeded", "completed_with_warning"}
                or (
                    dependency.dependency_type == "completion_required"
                    and predecessor.status in {"failed", "cancelled"}
                )
                or (
                    dependency.dependency_type == "manual_release"
                    and dependency.released_at is not None
                )
            )
        )
        if not satisfied:
            issue(
                "dependency_unsatisfied",
                "A predecessor dependency is not satisfied.",
                "Complete or release the predecessor.",
            )
    state: Literal["ready", "blocked", "warning"] = "ready"
    if any(item.severity == "error" for item in issues):
        state = "blocked"
    elif issues:
        state = "warning"
    activity.readiness_status = state
    if activity.status not in {
        "succeeded",
        "completed_with_warning",
        "failed",
        "dead_letter",
        "missed",
        "cancelled",
        "archived",
    }:
        activity.status = "ready" if state in {"ready", "warning"} else "blocked"
    return ReadinessResponse(state=state, issues=issues)


def campaign_readiness(
    db: Session, campaign: Campaign, activities: list[CampaignActivity]
) -> ReadinessResponse:
    issues: list[ReadinessIssue] = []
    if not activities:
        issues.append(
            ReadinessIssue(
                code="no_activities",
                severity="error",
                safe_message="Campaign has no activities.",
                suggested_resolution="Add at least one activity.",
            )
        )
    for activity in activities:
        issues.extend(activity_readiness(db, campaign, activity).issues)
    state: Literal["ready", "blocked", "warning"] = (
        "blocked"
        if any(item.severity == "error" for item in issues)
        else "warning" if issues else "ready"
    )
    return ReadinessResponse(state=state, issues=issues)
