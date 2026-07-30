from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.campaigns.conflict_service import detect_conflicts
from vayujit_api.campaigns.models import Campaign, CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.schemas import CalendarEvent, ProgressResponse


def calendar_events(
    db: Session,
    owner_id: object,
    start: datetime,
    end: datetime,
    *,
    campaign_id: object | None = None,
) -> list[CalendarEvent]:
    query = (
        select(CampaignActivity, Campaign)
        .join(Campaign, Campaign.id == CampaignActivity.campaign_id)
        .where(
            CampaignActivity.owner_id == owner_id,
            CampaignActivity.scheduled_at_utc >= start,
            CampaignActivity.scheduled_at_utc < end,
        )
        .order_by(CampaignActivity.scheduled_at_utc)
    )
    if campaign_id:
        query = query.where(CampaignActivity.campaign_id == campaign_id)
    rows = list(db.execute(query))
    conflict_ids: set[object] = set()
    grouped: dict[object, tuple[Campaign, list[CampaignActivity]]] = {}
    for activity, campaign in rows:
        grouped.setdefault(campaign.id, (campaign, []))[1].append(activity)
    for value, activities in grouped.values():
        dependencies = list(
            db.scalars(
                select(CampaignActivityDependency).where(
                    CampaignActivityDependency.campaign_id == value.id
                )
            )
        )
        for conflict in detect_conflicts(value, activities, dependencies):
            conflict_ids.update(conflict.activity_ids)
    return [
        CalendarEvent(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            activity_id=activity.id,
            activity_name=activity.name,
            brand_id=campaign.brand_id,
            product_id=activity.product_id,
            destination_id=activity.destination_id,
            connector_key=activity.connector_key,
            requested_action=activity.requested_action,
            status=activity.status,
            readiness_status=activity.readiness_status,
            scheduled_at_utc=activity.scheduled_at_utc,
            timezone_name=activity.timezone_name,
            has_conflict=activity.id in conflict_ids,
        )
        for activity, campaign in rows
    ]


def progress(activities: list[CampaignActivity]) -> ProgressResponse:
    states = Counter(activity.status for activity in activities)
    required = [activity for activity in activities if activity.required and activity.enabled]
    succeeded = sum(
        activity.status in {"succeeded", "completed_with_warning"} for activity in required
    )
    percentage = round((succeeded / len(required)) * 100) if required else 0
    return ProgressResponse(
        total=len(activities),
        required=len(required),
        optional=sum(not activity.required for activity in activities),
        ready=states["ready"],
        scheduled=states["scheduled"] + states["queued"],
        running=states["running"] + states["retrying"],
        succeeded=states["succeeded"] + states["completed_with_warning"],
        failed=states["failed"] + states["dead_letter"],
        blocked=states["blocked"] + states["waiting_dependency"],
        cancelled=states["cancelled"],
        completion_percentage=percentage,
    )
