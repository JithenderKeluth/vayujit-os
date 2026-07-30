from collections import defaultdict
from datetime import timedelta

from vayujit_api.campaigns.models import Campaign, CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.schemas import Conflict


def detect_conflicts(
    campaign: Campaign,
    activities: list[CampaignActivity],
    dependencies: list[CampaignActivityDependency],
) -> list[Conflict]:
    conflicts: list[Conflict] = []
    enabled = [item for item in activities if item.enabled]
    identities: dict[tuple[object, ...], list[CampaignActivity]] = defaultdict(list)
    for activity in enabled:
        identities[
            (
                activity.product_id,
                activity.artifact_id,
                activity.artifact_version,
                activity.destination_id,
                activity.requested_action,
                activity.scheduled_at_utc,
            )
        ].append(activity)
    for values in identities.values():
        if len(values) > 1:
            conflicts.append(
                Conflict(
                    conflict_type="duplicate_destination_action",
                    severity="error",
                    activity_ids=[value.id for value in values],
                    safe_explanation="Equivalent destination actions share the same occurrence.",
                    suggested_correction="Remove the duplicate or choose a different time.",
                    override_allowed=False,
                )
            )
    ordered = sorted(enabled, key=lambda item: item.scheduled_at_utc)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if right.scheduled_at_utc - left.scheduled_at_utc > timedelta(minutes=60):
                break
            if (
                left.product_id
                and left.product_id == right.product_id
                and left.destination_id == right.destination_id
                and left.id != right.id
            ):
                conflicts.append(
                    Conflict(
                        conflict_type="overlapping_product_activity",
                        severity="warning",
                        activity_ids=[left.id, right.id],
                        safe_explanation="Product activities overlap at one destination.",
                        suggested_correction="Review their order or increase spacing.",
                        override_allowed=True,
                    )
                )
    for activity in enabled:
        if (
            activity.scheduled_at_utc < campaign.start_at_utc
            or activity.scheduled_at_utc > campaign.end_at_utc
        ):
            conflicts.append(
                Conflict(
                    conflict_type="outside_campaign_window",
                    severity=(
                        "error" if campaign.scheduling_policy == "strict_window" else "warning"
                    ),
                    activity_ids=[activity.id],
                    safe_explanation="Activity is outside the Campaign window.",
                    suggested_correction="Adjust the activity or Campaign dates.",
                    override_allowed=campaign.scheduling_policy == "allow_with_confirmation",
                )
            )
    by_id = {activity.id: activity for activity in enabled}
    for dependency in dependencies:
        predecessor = by_id.get(dependency.predecessor_activity_id)
        successor = by_id.get(dependency.successor_activity_id)
        if predecessor and successor and predecessor.scheduled_at_utc > successor.scheduled_at_utc:
            conflicts.append(
                Conflict(
                    conflict_type="dependency_timing_conflict",
                    severity="error",
                    activity_ids=[predecessor.id, successor.id],
                    safe_explanation="A successor is scheduled before its predecessor.",
                    suggested_correction="Move the successor after the predecessor.",
                    override_allowed=False,
                )
            )
    destination_windows: dict[tuple[object, object], list[CampaignActivity]] = defaultdict(list)
    for activity in enabled:
        bucket = activity.scheduled_at_utc.replace(minute=0, second=0, microsecond=0)
        destination_windows[(activity.destination_id, bucket)].append(activity)
    for values in destination_windows.values():
        if values[0].destination_id and len(values) >= 10:
            conflicts.append(
                Conflict(
                    conflict_type="destination_rate_pressure",
                    severity="warning",
                    activity_ids=[value.id for value in values],
                    safe_explanation="Many activities target one destination within an hour.",
                    suggested_correction="Consider spreading activity times.",
                    override_allowed=True,
                )
            )
    return conflicts
