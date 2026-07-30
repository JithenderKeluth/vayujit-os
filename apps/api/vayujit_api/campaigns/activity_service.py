import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.campaign_service import owned_campaign
from vayujit_api.campaigns.constants import ACTIVITY_ACTIONS
from vayujit_api.campaigns.models import CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.schemas import ActivityCreate, ActivityUpdate, DependencyCreate
from vayujit_api.core.config import get_settings
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import PublishingDestination
from vayujit_api.publishing.scheduler_time import local_to_utc


def owned_activity(
    db: Session, owner_id: uuid.UUID, campaign_id: uuid.UUID, activity_id: uuid.UUID
) -> CampaignActivity:
    value = db.scalar(
        select(CampaignActivity).where(
            CampaignActivity.id == activity_id,
            CampaignActivity.campaign_id == campaign_id,
            CampaignActivity.owner_id == owner_id,
        )
    )
    if not value:
        raise HTTPException(404, "Campaign activity not found.")
    return value


def create_activity(
    db: Session, owner: User, campaign_id: uuid.UUID, data: ActivityCreate
) -> CampaignActivity:
    campaign = owned_campaign(db, owner.id, campaign_id)
    if campaign.status not in {"draft", "planning", "ready", "paused"}:
        raise HTTPException(409, "Activities cannot be added in this Campaign state.")
    count = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(CampaignActivity.campaign_id == campaign.id)
    )
    if (count or 0) >= get_settings().campaign_max_activities:
        raise HTTPException(409, "The Campaign activity limit has been reached.")
    connector, action = ACTIVITY_ACTIONS[data.activity_type]
    checkpoint = connector is None
    product = (
        db.scalar(
            select(Product).where(Product.id == data.product_id, Product.owner_id == owner.id)
        )
        if data.product_id
        else None
    )
    artifact = (
        db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == data.artifact_id,
                GeneratedArtifact.owner_id == owner.id,
            )
        )
        if data.artifact_id
        else None
    )
    destination = (
        db.scalar(
            select(PublishingDestination).where(
                PublishingDestination.id == data.destination_id,
                PublishingDestination.owner_id == owner.id,
            )
        )
        if data.destination_id
        else None
    )
    if not checkpoint and (not product or not artifact or not destination):
        raise HTTPException(
            422, "Publishing activities require Product, Artifact, and destination."
        )
    if artifact and (
        not product
        or artifact.status != "approved"
        or artifact.product_id != product.id
        or artifact.brand_id != campaign.brand_id
    ):
        raise HTTPException(422, "The exact approved Artifact is incompatible.")
    if destination and (destination.status != "active" or destination.connector_key != connector):
        raise HTTPException(422, "The destination is inactive or connector-incompatible.")
    timezone_name = data.timezone_name or campaign.timezone_name
    local_value = datetime.combine(data.scheduled_local_date, data.scheduled_local_time)
    scheduled_utc = local_to_utc(local_value, timezone_name, 0)
    stamp = now()
    value = CampaignActivity(
        owner_id=owner.id,
        campaign_id=campaign.id,
        product_id=product.id if product else None,
        artifact_id=artifact.id if artifact else None,
        artifact_version=artifact.version_number if artifact else None,
        destination_id=destination.id if destination else None,
        connector_key=connector,
        requested_action=action,
        activity_type=data.activity_type,
        name=data.name.strip(),
        description=data.description.strip(),
        sequence=data.sequence,
        dependency_policy="success_required",
        scheduled_local_date=data.scheduled_local_date,
        scheduled_local_time=data.scheduled_local_time,
        timezone_name=timezone_name,
        scheduled_at_utc=scheduled_utc,
        duration_minutes=data.duration_minutes,
        status="draft",
        readiness_status="incomplete",
        required=data.required,
        enabled=data.enabled,
        created_by=owner.id,
        created_at=stamp,
        updated_at=stamp,
        correlation_id=correlation_id(),
        idempotency_key=f"campaign:{campaign.id}:sequence:{data.sequence}",
        row_version=1,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.activity_created",
        entity_type="campaign_activity",
        entity_id=value.id,
        metadata={"campaign_id": str(campaign.id), "activity_type": value.activity_type},
    )
    db.commit()
    db.refresh(value)
    return value


def update_activity(
    db: Session,
    owner: User,
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    data: ActivityUpdate,
) -> CampaignActivity:
    value = owned_activity(db, owner.id, campaign_id, activity_id)
    if value.status not in {"draft", "blocked", "ready", "paused"}:
        raise HTTPException(409, "A scheduled or running activity cannot be edited.")
    if value.row_version != data.row_version:
        raise HTTPException(409, "Activity changed; reload before saving.")
    values = data.model_dump(exclude_unset=True, exclude={"row_version"})
    for field, content in values.items():
        setattr(value, field, content)
    if {"scheduled_local_date", "scheduled_local_time", "timezone_name"} & values.keys():
        value.scheduled_at_utc = local_to_utc(
            datetime.combine(value.scheduled_local_date, value.scheduled_local_time),
            value.timezone_name,
            0,
        )
    value.readiness_status = "incomplete"
    value.status = "draft"
    value.updated_at = now()
    value.row_version += 1
    db.commit()
    db.refresh(value)
    return value


def dependency_would_cycle(
    edges: list[tuple[uuid.UUID, uuid.UUID]], predecessor: uuid.UUID, successor: uuid.UUID
) -> bool:
    graph: dict[uuid.UUID, list[uuid.UUID]] = {}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
    graph.setdefault(predecessor, []).append(successor)
    pending = [successor]
    seen: set[uuid.UUID] = set()
    while pending:
        node = pending.pop()
        if node == predecessor:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, []))
    return False


def add_dependency(
    db: Session, owner: User, campaign_id: uuid.UUID, data: DependencyCreate
) -> CampaignActivityDependency:
    if data.predecessor_activity_id == data.successor_activity_id:
        raise HTTPException(422, "An activity cannot depend on itself.")
    owned_activity(db, owner.id, campaign_id, data.predecessor_activity_id)
    owned_activity(db, owner.id, campaign_id, data.successor_activity_id)
    count = db.scalar(
        select(func.count())
        .select_from(CampaignActivityDependency)
        .where(CampaignActivityDependency.campaign_id == campaign_id)
    )
    if (count or 0) >= get_settings().campaign_max_dependencies:
        raise HTTPException(409, "The Campaign dependency limit has been reached.")
    existing = [
        (row[0], row[1])
        for row in db.execute(
            select(
                CampaignActivityDependency.predecessor_activity_id,
                CampaignActivityDependency.successor_activity_id,
            ).where(CampaignActivityDependency.campaign_id == campaign_id)
        )
    ]
    if (data.predecessor_activity_id, data.successor_activity_id) in existing:
        raise HTTPException(409, "This dependency already exists.")
    if dependency_would_cycle(existing, data.predecessor_activity_id, data.successor_activity_id):
        raise HTTPException(422, "The dependency would create a cycle.")
    value = CampaignActivityDependency(
        owner_id=owner.id,
        campaign_id=campaign_id,
        predecessor_activity_id=data.predecessor_activity_id,
        successor_activity_id=data.successor_activity_id,
        dependency_type=data.dependency_type,
        created_at=now(),
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.dependency_created",
        entity_type="campaign_activity_dependency",
        entity_id=value.id,
        metadata={"campaign_id": str(campaign_id), "type": value.dependency_type},
    )
    db.commit()
    db.refresh(value)
    return value
