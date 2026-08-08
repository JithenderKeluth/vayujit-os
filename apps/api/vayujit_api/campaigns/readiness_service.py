from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.campaigns.models import Campaign, CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.schemas import ReadinessIssue, ReadinessResponse
from vayujit_api.core.config import get_settings
from vayujit_api.publishing.models import PublishingDestination


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
    artifact = db.get(GeneratedArtifact, activity.artifact_id) if activity.artifact_id else None
    destination = (
        db.get(PublishingDestination, activity.destination_id) if activity.destination_id else None
    )
    if not activity.enabled:
        issue("activity_disabled", "Activity is disabled.", "Enable the activity.")
    if not checkpoint:
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
