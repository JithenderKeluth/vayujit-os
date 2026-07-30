import re
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.campaigns.constants import LEGAL_TRANSITIONS
from vayujit_api.campaigns.models import Campaign, CampaignDefaultDestination
from vayujit_api.campaigns.schemas import CampaignCreate, CampaignUpdate
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.publishing.models import PublishingDestination
from vayujit_api.publishing.scheduler_time import local_to_utc


def slugify(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return result[:170] or "campaign"


def owned_campaign(
    db: Session, owner_id: uuid.UUID, campaign_id: uuid.UUID, *, lock: bool = False
) -> Campaign:
    query = select(Campaign).where(Campaign.id == campaign_id, Campaign.owner_id == owner_id)
    value = db.scalar(query.with_for_update() if lock else query)
    if not value:
        raise HTTPException(404, "Campaign not found.")
    return value


def create_campaign(db: Session, owner: User, data: CampaignCreate) -> Campaign:
    settings = get_settings()
    active = db.scalar(
        select(func.count())
        .select_from(Campaign)
        .where(
            Campaign.owner_id == owner.id,
            Campaign.status.notin_(["completed", "cancelled", "archived"]),
        )
    )
    if (active or 0) >= settings.campaign_max_active_per_owner:
        raise HTTPException(409, "The active Campaign quota has been reached.")
    brand = db.scalar(select(Brand).where(Brand.id == data.brand_id, Brand.owner_id == owner.id))
    if not brand:
        raise HTTPException(422, "Brand is unavailable.")
    if data.local_end_at - data.local_start_at > timedelta(
        days=settings.campaign_max_duration_days
    ):
        raise HTTPException(422, "Campaign duration exceeds the configured limit.")
    destinations = list(
        db.scalars(
            select(PublishingDestination).where(
                PublishingDestination.owner_id == owner.id,
                PublishingDestination.id.in_(data.default_destination_ids),
            )
        )
    )
    if len(destinations) != len(set(data.default_destination_ids)):
        raise HTTPException(422, "One or more default destinations are unavailable.")
    slug_base = slugify(data.name)
    slug = slug_base
    suffix = 2
    while db.scalar(
        select(Campaign.id).where(Campaign.owner_id == owner.id, Campaign.slug == slug)
    ):
        slug = f"{slug_base[:160]}-{suffix}"
        suffix += 1
    stamp = now()
    value = Campaign(
        owner_id=owner.id,
        brand_id=brand.id,
        name=data.name.strip(),
        slug=slug,
        description=data.description.strip(),
        objective=data.objective.strip(),
        status="draft",
        priority=data.priority,
        timezone_name=data.timezone_name,
        start_at_utc=local_to_utc(data.local_start_at, data.timezone_name, 0),
        end_at_utc=local_to_utc(data.local_end_at, data.timezone_name, 0),
        local_start_at=data.local_start_at,
        local_end_at=data.local_end_at,
        approval_policy=data.approval_policy,
        scheduling_policy=data.scheduling_policy,
        conflict_policy=data.conflict_policy,
        created_by=owner.id,
        created_at=stamp,
        updated_at=stamp,
        row_version=1,
    )
    db.add(value)
    db.flush()
    for destination in destinations:
        db.add(
            CampaignDefaultDestination(
                owner_id=owner.id,
                campaign_id=value.id,
                destination_id=destination.id,
                created_at=stamp,
            )
        )
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.created",
        entity_type="campaign",
        entity_id=value.id,
        metadata={"brand_id": str(brand.id), "timezone": value.timezone_name},
    )
    db.commit()
    db.refresh(value)
    return value


def update_campaign(
    db: Session, owner: User, campaign_id: uuid.UUID, data: CampaignUpdate
) -> Campaign:
    value = owned_campaign(db, owner.id, campaign_id, lock=True)
    if value.status not in {"draft", "planning", "ready", "paused"}:
        raise HTTPException(409, "Campaign cannot be edited in its current state.")
    if data.row_version != value.row_version:
        raise HTTPException(409, "Campaign changed; reload before saving.")
    values = data.model_dump(exclude_unset=True, exclude={"row_version"})
    for field in ("name", "description", "objective", "priority", "timezone_name"):
        if field in values:
            setattr(value, field, values[field])
    local_start = data.local_start_at or value.local_start_at
    local_end = data.local_end_at or value.local_end_at
    if local_end <= local_start:
        raise HTTPException(422, "Campaign end must be after its start.")
    if local_end - local_start > timedelta(days=get_settings().campaign_max_duration_days):
        raise HTTPException(422, "Campaign duration exceeds the configured limit.")
    if data.local_start_at is not None or data.local_end_at is not None or data.timezone_name:
        value.local_start_at = local_start
        value.local_end_at = local_end
        value.start_at_utc = local_to_utc(local_start, value.timezone_name, 0)
        value.end_at_utc = local_to_utc(local_end, value.timezone_name, 0)
    value.row_version += 1
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.updated",
        entity_type="campaign",
        entity_id=value.id,
        metadata={"row_version": value.row_version},
    )
    db.commit()
    db.refresh(value)
    return value


def transition(
    db: Session,
    owner: User,
    campaign_id: uuid.UUID,
    target: str,
    *,
    reason: str | None = None,
) -> Campaign:
    value = owned_campaign(db, owner.id, campaign_id, lock=True)
    if target not in LEGAL_TRANSITIONS.get(value.status, set()):
        raise HTTPException(409, f"Campaign cannot transition from {value.status} to {target}.")
    if target == "cancelled" and not reason:
        raise HTTPException(422, "A cancellation reason is required.")
    stamp = now()
    previous = value.status
    value.status = target
    value.updated_at = stamp
    value.row_version += 1
    if target in {"ready", "scheduled", "running"} and value.launched_at is None:
        value.launched_at = stamp
    if target == "paused":
        value.paused_at = stamp
    if target == "completed":
        value.completed_at = stamp
    if target == "archived":
        value.archived_at = stamp
    if target == "cancelled":
        value.cancellation_reason = reason
    record_event(
        db,
        actor_id=owner.id,
        action=f"campaign.{target}",
        entity_type="campaign",
        entity_id=value.id,
        metadata={"previous_status": previous, "reason": reason},
    )
    db.commit()
    db.refresh(value)
    return value
