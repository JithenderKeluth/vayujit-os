import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.brands.models import Brand
from vayujit_api.campaigns.activity_service import (
    add_dependency,
    create_activity,
    owned_activity,
    update_activity,
)
from vayujit_api.campaigns.calendar_service import calendar_events, calendar_projection, progress
from vayujit_api.campaigns.campaign_service import (
    create_campaign,
    owned_campaign,
    transition,
    update_campaign,
)
from vayujit_api.campaigns.completion_service import resolve_missed, resume_preview
from vayujit_api.campaigns.conflict_service import detect_conflicts
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityDependency,
    CampaignActivityReschedule,
    CampaignMissedActivityResolution,
    CampaignWorkflowWait,
)
from vayujit_api.campaigns.readiness_service import activity_readiness, campaign_readiness
from vayujit_api.campaigns.recovery_service import (
    RECOVERY_ACTION_REGISTRY,
    CampaignRecoveryExecutionContext,
    catch_up_fingerprint,
    eligible_recovery_actions,
    reschedule_fingerprint,
)
from vayujit_api.campaigns.schedule_service import (
    dependencies,
    project_activity_states,
    schedule_activities,
)
from vayujit_api.campaigns.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    AgendaCalendar,
    CalendarEvent,
    CampaignCreate,
    CampaignRecoveryActionRequest,
    CampaignRecoveryActionResult,
    CampaignRecoveryProjection,
    CampaignResponse,
    CampaignUpdate,
    CampaignWorkflowAction,
    CampaignWorkflowResult,
    CatchUpPreviewRequest,
    CatchUpPreviewResponse,
    Conflict,
    DependencyCreate,
    DependencyResponse,
    LifecycleRequest,
    MonthCalendar,
    ProgressResponse,
    ReadinessResponse,
    RescheduleHistoryResponse,
    ReschedulePreviewRequest,
    ReschedulePreviewResponse,
    RescheduleRequest,
    ResumePreviewResponse,
    ScheduleRequest,
    SelectorItem,
    SelectorPage,
    WeekCalendar,
)
from vayujit_api.campaigns.workflow_executor import execute_campaign_action
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.core.observability import correlation_id, maintenance_enabled
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingJob,
    PublishingSchedule,
)
from vayujit_api.publishing.scheduler_time import local_to_utc, timezone_for, utcnow

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _registry_dispatch_guard(
    _key: str, _request: CampaignRecoveryActionRequest
) -> CampaignRecoveryActionResult:
    raise RuntimeError("Recovery registry dispatch was unexpectedly requested.")


@router.post("/workflow-actions", response_model=CampaignWorkflowResult)
def workflow_action(action: CampaignWorkflowAction, db: DB, owner: Owner) -> CampaignWorkflowResult:
    return execute_campaign_action(db, owner, action)


@router.get("/lookups/{kind}", response_model=SelectorPage)
def lookup(
    kind: str,
    db: DB,
    owner: Owner,
    search: Annotated[str, Query(max_length=120)] = "",
    product_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    connector_key: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SelectorPage:
    term = f"%{search.strip()}%"
    query: Any
    values: Any
    items: list[SelectorItem]
    if kind == "brand":
        query = (
            select(Brand)
            .where(Brand.owner_id == owner.id, Brand.name.ilike(term))
            .order_by(Brand.name, Brand.id)
        )
        values = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        items = [
            SelectorItem(id=value.id, label=value.name, kind="brand", status=str(value.status))
            for value in values
        ]
    elif kind == "product":
        query = (
            select(Product)
            .where(Product.owner_id == owner.id, Product.name.ilike(term))
            .order_by(Product.name, Product.id)
        )
        values = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        items = [
            SelectorItem(id=value.id, label=value.name, kind="product", status=str(value.status))
            for value in values
        ]
    elif kind == "artifact":
        clauses = [
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.status == "approved",
        ]
        if product_id:
            clauses.append(GeneratedArtifact.product_id == product_id)
        query = (
            select(GeneratedArtifact)
            .where(*clauses)
            .order_by(GeneratedArtifact.created_at.desc(), GeneratedArtifact.id)
        )
        values = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        items = [
            SelectorItem(
                id=value.id,
                label=f"Artifact v{value.version_number}",
                kind="artifact",
                version=value.version_number,
                status=value.status,
                product_id=value.product_id,
            )
            for value in values
        ]
    elif kind == "destination":
        clauses = [PublishingDestination.owner_id == owner.id]
        if connector_key:
            clauses.append(PublishingDestination.connector_key == connector_key)
        query = (
            select(PublishingDestination)
            .where(*clauses, PublishingDestination.name.ilike(term))
            .order_by(PublishingDestination.name, PublishingDestination.id)
        )
        values = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        items = [
            SelectorItem(
                id=value.id,
                label=value.name,
                kind="destination",
                status=value.status,
                connector_key=value.connector_key,
                disabled=value.status != "active",
                disabled_reason="Destination is disabled." if value.status != "active" else None,
            )
            for value in values
        ]
    elif kind == "manager":
        values = (
            [owner] if search.casefold() in f"{owner.full_name} {owner.email}".casefold() else []
        )
        items = [
            SelectorItem(
                id=value.id,
                label=f"{value.full_name} ({value.email})",
                kind="manager",
                status="active" if value.is_active else "disabled",
                disabled=not value.is_active,
            )
            for value in values
        ]
    elif kind == "activity" and campaign_id:
        owned_campaign(db, owner.id, campaign_id)
        query = (
            select(CampaignActivity)
            .where(
                CampaignActivity.owner_id == owner.id,
                CampaignActivity.campaign_id == campaign_id,
                CampaignActivity.name.ilike(term),
            )
            .order_by(CampaignActivity.sequence, CampaignActivity.id)
        )
        values = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        items = [
            SelectorItem(
                id=value.id,
                label=f"{value.sequence}. {value.name}",
                kind="activity",
                status=value.status,
            )
            for value in values
        ]
    else:
        raise HTTPException(422, "Unsupported Campaign lookup kind.")
    return SelectorPage(items=items, page=page, page_size=page_size, total=len(items))


def recovery_actions(
    activity: CampaignActivity, campaign: Campaign | None = None, db: Session | None = None
) -> list[str]:
    return eligible_recovery_actions(activity, campaign, db)


def catch_up_projection(
    db: Session, activity: CampaignActivity
) -> tuple[uuid.UUID | None, uuid.UUID | None, uuid.UUID | None, str | None]:
    resolution = db.scalar(
        select(CampaignMissedActivityResolution).where(
            CampaignMissedActivityResolution.activity_id == activity.id,
            CampaignMissedActivityResolution.policy == "one_catch_up",
        )
    )
    if resolution is None:
        return None, None, None, None
    return (
        resolution.replacement_activity_id,
        resolution.replacement_schedule_id,
        resolution.replacement_job_id,
        resolution.resolution_status,
    )


@router.get("/recovery", response_model=list[CampaignRecoveryProjection])
def campaign_recovery(db: DB, owner: Owner) -> list[CampaignRecoveryProjection]:
    rows = list(
        db.execute(
            select(CampaignActivity, Campaign)
            .join(Campaign, Campaign.id == CampaignActivity.campaign_id)
            .where(
                CampaignActivity.owner_id == owner.id,
                CampaignActivity.status.in_(
                    [
                        "blocked",
                        "retrying",
                        "failed",
                        "dead_letter",
                        "maintenance_blocked",
                        "reconciliation_required",
                        "cancel_requested",
                        "missed",
                    ]
                ),
            )
            .order_by(CampaignActivity.updated_at.desc())
            .limit(200)
        )
    )
    projections: list[CampaignRecoveryProjection] = []
    for activity, campaign in rows:
        catch_up_activity_id, catch_up_schedule_id, catch_up_job_id, catch_up_status = (
            catch_up_projection(db, activity)
        )
        projections.append(
            CampaignRecoveryProjection(
                recovery_type=f"activity_{activity.status}",
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                campaign_status=campaign.status,
                activity_id=activity.id,
                activity_name=activity.name,
                required=activity.required,
                product_id=activity.product_id,
                artifact_id=activity.artifact_id,
                artifact_version=activity.artifact_version,
                destination_id=activity.destination_id,
                connector_key=activity.connector_key,
                schedule_id=activity.schedule_id,
                job_id=activity.job_id,
                publishing_execution_id=activity.publishing_execution_id,
                workflow_wait_id=None,
                safe_failure_message=activity.safe_failure_message
                or "Campaign activity needs review.",
                correlation_id=activity.correlation_id,
                eligible_actions=recovery_actions(activity, campaign, db),
                catch_up_activity_id=catch_up_activity_id,
                catch_up_schedule_id=catch_up_schedule_id,
                catch_up_job_id=catch_up_job_id,
                catch_up_status=catch_up_status,
            )
        )
    return projections


@router.post(
    "/{campaign_id}/recovery/reschedule-activity/preview", response_model=ReschedulePreviewResponse
)
def preview_reschedule_activity(
    campaign_id: uuid.UUID,
    request: ReschedulePreviewRequest,
    db: DB,
    owner: Owner,
) -> ReschedulePreviewResponse:
    campaign = owned_campaign(db, owner.id, campaign_id)
    activity = owned_activity(db, owner.id, campaign.id, request.activity_id)
    if activity is None:
        raise HTTPException(404, "Activity not found.")
    if activity.row_version != request.expected_activity_row_version:
        raise HTTPException(409, "The Activity changed; refresh before rescheduling it.")
    try:
        zone = timezone_for(request.proposed_timezone)
        fold_zero = request.proposed_local_datetime.replace(tzinfo=zone, fold=0)
        fold_one = request.proposed_local_datetime.replace(tzinfo=zone, fold=1)
        utc_zero = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 0)
        utc_one = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 1)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ambiguous = utc_zero != utc_one and fold_zero.utcoffset() != fold_one.utcoffset()
    selected_fold = request.fold if request.fold is not None else 0
    proposed_utc = utc_one if selected_fold == 1 else utc_zero
    if not ambiguous and request.fold not in {None, 0}:
        raise HTTPException(422, "The selected DST fold is not valid for this local time.")
    fingerprint = reschedule_fingerprint(
        db,
        owner.id,
        campaign,
        activity,
        request.proposed_local_datetime,
        request.proposed_timezone,
        request.reason,
        request.fold,
    )
    readiness = activity_readiness(db, campaign, activity)
    conflict_items = detect_conflicts(campaign, [activity], dependencies(db, campaign.id))
    current_schedule = (
        db.get(PublishingSchedule, activity.schedule_id) if activity.schedule_id else None
    )
    current_job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    warnings = [issue.safe_message for issue in readiness.issues]
    warnings.extend(item.safe_explanation for item in conflict_items)
    return ReschedulePreviewResponse(
        campaign_id=campaign.id,
        activity_id=activity.id,
        original_scheduled_at_utc=activity.scheduled_at_utc,
        proposed_local_datetime=request.proposed_local_datetime,
        proposed_scheduled_at_utc=proposed_utc,
        timezone=request.proposed_timezone,
        confirmation_required=not ambiguous or request.fold is not None,
        preview_fingerprint=fingerprint,
        safe_message="Review the proposed Activity reschedule and confirm it explicitly.",
        correlation_id=correlation_id() or str(uuid.uuid4()),
        dst_classification="ambiguous_local_time" if ambiguous else "normal",
        utc_offset=str((fold_one if selected_fold == 1 else fold_zero).utcoffset()),
        fold=request.fold if ambiguous else None,
        issue_code="ambiguous_local_time" if ambiguous and request.fold is None else None,
        warnings=warnings,
        readiness_issues=readiness.issues,
        conflicts=conflict_items,
        current_schedule_status=(
            "superseded"
            if current_schedule and current_schedule.archived
            else "active"
            if current_schedule
            else None
        ),
        current_job_status=current_job.state if current_job else None,
    )


@router.post(
    "/{campaign_id}/recovery/create-one-catch-up/preview",
    response_model=CatchUpPreviewResponse,
)
def preview_create_one_catch_up(
    campaign_id: uuid.UUID,
    request: CatchUpPreviewRequest,
    db: DB,
    owner: Owner,
) -> CatchUpPreviewResponse:
    campaign = owned_campaign(db, owner.id, campaign_id)
    activity = owned_activity(db, owner.id, campaign.id, request.activity_id)
    if activity.status != "missed":
        raise HTTPException(409, "Catch-up is available only for missed Activities.")
    if activity.row_version != request.expected_activity_row_version:
        raise HTTPException(409, "The Activity changed; refresh before creating catch-up.")
    try:
        zone = timezone_for(request.proposed_timezone)
        fold_zero = request.proposed_local_datetime.replace(tzinfo=zone, fold=0)
        fold_one = request.proposed_local_datetime.replace(tzinfo=zone, fold=1)
        utc_zero = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 0)
        utc_one = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 1)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ambiguous = utc_zero != utc_one and fold_zero.utcoffset() != fold_one.utcoffset()
    if not ambiguous and request.fold not in {None, 0}:
        raise HTTPException(422, "The selected DST fold is not valid for this local time.")
    selected_fold = request.fold if request.fold is not None else 0
    proposed = utc_one if selected_fold == 1 else utc_zero
    readiness = activity_readiness(db, campaign, activity)
    conflicts = detect_conflicts(campaign, [activity], dependencies(db, campaign.id))
    artifact = db.get(GeneratedArtifact, activity.artifact_id) if activity.artifact_id else None
    destination = (
        db.get(PublishingDestination, activity.destination_id) if activity.destination_id else None
    )
    warnings = [issue.safe_message for issue in readiness.issues]
    warnings.extend(item.safe_explanation for item in conflicts)
    fingerprint = catch_up_fingerprint(
        owner.id,
        campaign,
        activity,
        request.proposed_local_datetime,
        request.proposed_timezone,
        request.reason,
        request.fold,
        request.expected_activity_row_version,
    )
    current_schedule = (
        db.get(PublishingSchedule, activity.schedule_id) if activity.schedule_id else None
    )
    current_job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    return CatchUpPreviewResponse(
        campaign_id=campaign.id,
        activity_id=activity.id,
        original_scheduled_at_utc=activity.scheduled_at_utc,
        proposed_local_datetime=request.proposed_local_datetime,
        proposed_scheduled_at_utc=proposed,
        timezone=request.proposed_timezone,
        confirmation_required=not ambiguous or request.fold is not None,
        preview_fingerprint=fingerprint,
        safe_message="Review the proposed catch-up Activity and confirm it explicitly.",
        correlation_id=correlation_id() or str(uuid.uuid4()),
        dst_classification="ambiguous_local_time" if ambiguous else "normal",
        utc_offset=str((fold_one if selected_fold == 1 else fold_zero).utcoffset()),
        fold=request.fold if ambiguous else None,
        issue_code="ambiguous_local_time" if ambiguous and request.fold is None else None,
        warnings=warnings,
        readiness_issues=readiness.issues,
        conflicts=conflicts,
        current_schedule_status=(
            "superseded"
            if current_schedule and current_schedule.archived
            else "active"
            if current_schedule
            else None
        ),
        current_job_status=current_job.state if current_job else None,
        original_activity_name=activity.name,
        original_activity_status=activity.status,
        artifact_id=artifact.id if artifact else activity.artifact_id,
        artifact_version=activity.artifact_version,
        artifact_status=artifact.status if artifact else None,
        destination_id=destination.id if destination else activity.destination_id,
        destination_status=destination.status if destination else None,
        dependency_warnings=[
            issue.safe_message
            for issue in readiness.issues
            if issue.code == "dependency_unsatisfied"
        ],
    )


@router.get(
    "/{campaign_id}/activities/{activity_id}/reschedules",
    response_model=list[RescheduleHistoryResponse],
)
def activity_reschedule_history(
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> list[CampaignActivityReschedule]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    activity = owned_activity(db, owner.id, campaign.id, activity_id)
    if activity is None:
        raise HTTPException(404, "Activity not found.")
    return list(
        db.scalars(
            select(CampaignActivityReschedule)
            .where(
                CampaignActivityReschedule.owner_id == owner.id,
                CampaignActivityReschedule.campaign_id == campaign.id,
                CampaignActivityReschedule.activity_id == activity.id,
            )
            .order_by(CampaignActivityReschedule.requested_at)
        )
    )


@router.post("/recovery/actions")
def execute_recovery_action(
    request: CampaignRecoveryActionRequest, db: DB, owner: Owner
) -> dict[str, object]:
    specification = RECOVERY_ACTION_REGISTRY[request.action]
    if specification.implementation_status == "unsupported":
        return {
            "action": request.action,
            "outcome": "unsupported",
            "safe_message": "Catch-up creation is not implemented yet.",
            "correlation_id": correlation_id() or str(uuid.uuid4()),
            "idempotency_result": "not_applicable",
        }
    campaign = owned_campaign(db, owner.id, request.campaign_id)
    activity = (
        owned_activity(db, owner.id, campaign.id, request.activity_id)
        if request.activity_id
        else None
    )
    if specification.implementation_status == "implemented":
        handler = (
            specification.navigation_resolver
            if specification.classification == "navigation_only"
            else specification.executor
        )
        if handler is None:
            raise HTTPException(500, "Recovery action handler is unavailable.")
        existing_reschedule = bool(
            request.action == "reschedule_activity"
            and activity is not None
            and request.preview_fingerprint
            and db.scalar(
                select(CampaignActivityReschedule.id).where(
                    CampaignActivityReschedule.owner_id == owner.id,
                    CampaignActivityReschedule.campaign_id == campaign.id,
                    CampaignActivityReschedule.activity_id == activity.id,
                    CampaignActivityReschedule.preview_fingerprint == request.preview_fingerprint,
                    CampaignActivityReschedule.status == "confirmed",
                )
            )
        )
        if (
            activity
            and not existing_reschedule
            and request.action not in recovery_actions(activity, campaign, db)
        ):
            raise HTTPException(409, "Recovery action is not eligible for the current state.")
        context = CampaignRecoveryExecutionContext(
            db=db,
            owner=owner,
            campaign=campaign,
            activity=activity,
            workflow_wait=None,
            correlation_id=correlation_id() or str(uuid.uuid4()),
            now_utc=utcnow(),
            maintenance_mode=maintenance_enabled(),
            action=specification,
            dispatch=_registry_dispatch_guard,
        )
        try:
            typed_result = handler(context, request)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        result_payload = cast(dict[str, object], typed_result.model_dump(mode="json"))
        return {
            "action": request.action,
            "result": result_payload,
        }


def campaign_activities(db: Session, campaign_id: uuid.UUID) -> list[CampaignActivity]:
    return list(
        db.scalars(
            select(CampaignActivity)
            .where(CampaignActivity.campaign_id == campaign_id)
            .order_by(CampaignActivity.sequence)
        )
    )


@router.get("/calendar", response_model=MonthCalendar | WeekCalendar | AgendaCalendar)
def global_calendar(
    db: DB,
    owner: Owner,
    start: datetime,
    end: datetime,
    campaign_id: uuid.UUID | None = None,
    view: str = Query(default="month", pattern="^(month|week|agenda)$"),
    timezone_name: str = "UTC",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> MonthCalendar | WeekCalendar | AgendaCalendar:
    maximum = {"month": 62, "week": 21, "agenda": 90}[view]
    if end <= start or end - start > timedelta(days=maximum):
        raise HTTPException(422, "Calendar range must be positive and within the configured limit.")
    events = calendar_events(db, owner.id, start, end, campaign_id=campaign_id)
    return calendar_projection(events, view, start, end, timezone_name, offset=offset, limit=limit)


@router.get("/health")
def health(db: DB, owner: Owner) -> dict[str, object]:
    timestamp = utcnow()
    active = db.scalar(
        select(func.count())
        .select_from(Campaign)
        .where(
            Campaign.owner_id == owner.id,
            Campaign.status.notin_(["completed", "cancelled", "archived"]),
        )
    )
    upcoming = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.scheduled_at_utc >= timestamp,
            CampaignActivity.status.notin_(["cancelled", "archived"]),
        )
    )
    blocked = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.status.in_(["blocked", "dead_letter", "maintenance_blocked"]),
        )
    )
    overdue = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.scheduled_at_utc < timestamp,
            CampaignActivity.status.in_(["draft", "ready", "scheduled", "queued"]),
        )
    )
    active_waits = db.scalar(
        select(func.count())
        .select_from(CampaignWorkflowWait)
        .where(
            CampaignWorkflowWait.owner_id == owner.id,
            CampaignWorkflowWait.completed_at.is_(None),
        )
    )
    failed_waits = db.scalar(
        select(func.count())
        .select_from(CampaignWorkflowWait)
        .where(
            CampaignWorkflowWait.owner_id == owner.id,
            CampaignWorkflowWait.failure_code.is_not(None),
        )
    )
    missed = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(CampaignActivity.owner_id == owner.id, CampaignActivity.status == "missed")
    )
    catch_ups = db.scalar(
        select(func.count())
        .select_from(CampaignMissedActivityResolution)
        .where(
            CampaignMissedActivityResolution.owner_id == owner.id,
            CampaignMissedActivityResolution.resolution_status == "catch_up_created",
        )
    )
    return {
        "active_campaigns": active or 0,
        "upcoming_activities": upcoming or 0,
        "blocked_activities": blocked or 0,
        "overdue_activities": overdue or 0,
        "active_campaign_waits": active_waits or 0,
        "failed_campaign_waits": failed_waits or 0,
        "missed_activities": missed or 0,
        "catch_ups_created": catch_ups or 0,
        "generated_at": timestamp,
    }


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    db: DB,
    owner: Owner,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Campaign]:
    query = select(Campaign).where(Campaign.owner_id == owner.id)
    if status:
        query = query.where(Campaign.status == status)
    return list(
        db.scalars(
            query.order_by(Campaign.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )


@router.post("", response_model=CampaignResponse, status_code=201)
def create(data: CampaignCreate, db: DB, owner: Owner) -> Campaign:
    return create_campaign(db, owner, data)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    project_activity_states(db, campaign_id)
    return owned_campaign(db, owner.id, campaign_id)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update(campaign_id: uuid.UUID, data: CampaignUpdate, db: DB, owner: Owner) -> Campaign:
    return update_campaign(db, owner, campaign_id, data)


@router.get("/{campaign_id}/activities", response_model=list[ActivityResponse])
def activities(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[CampaignActivity]:
    owned_campaign(db, owner.id, campaign_id)
    project_activity_states(db, campaign_id)
    return campaign_activities(db, campaign_id)


@router.post("/{campaign_id}/activities", response_model=ActivityResponse, status_code=201)
def activity_create(
    campaign_id: uuid.UUID, data: ActivityCreate, db: DB, owner: Owner
) -> CampaignActivity:
    return create_activity(db, owner, campaign_id, data)


@router.get("/{campaign_id}/activities/{activity_id}", response_model=ActivityResponse)
def activity_get(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    return owned_activity(db, owner.id, campaign_id, activity_id)


@router.put("/{campaign_id}/activities/{activity_id}", response_model=ActivityResponse)
def activity_update(
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    data: ActivityUpdate,
    db: DB,
    owner: Owner,
) -> CampaignActivity:
    return update_activity(db, owner, campaign_id, activity_id, data)


@router.post("/{campaign_id}/dependencies", response_model=DependencyResponse, status_code=201)
def dependency_create(
    campaign_id: uuid.UUID, data: DependencyCreate, db: DB, owner: Owner
) -> CampaignActivityDependency:
    return add_dependency(db, owner, campaign_id, data)


@router.get("/{campaign_id}/dependencies", response_model=list[DependencyResponse])
def dependency_list(
    campaign_id: uuid.UUID, db: DB, owner: Owner
) -> list[CampaignActivityDependency]:
    owned_campaign(db, owner.id, campaign_id)
    return dependencies(db, campaign_id)


@router.delete("/{campaign_id}/dependencies/{dependency_id}", status_code=204)
def dependency_delete(
    campaign_id: uuid.UUID, dependency_id: uuid.UUID, db: DB, owner: Owner
) -> None:
    owned_campaign(db, owner.id, campaign_id)
    value = db.scalar(
        select(CampaignActivityDependency).where(
            CampaignActivityDependency.id == dependency_id,
            CampaignActivityDependency.campaign_id == campaign_id,
            CampaignActivityDependency.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Campaign dependency was not found.")
    db.delete(value)
    db.commit()


@router.post("/{campaign_id}/activities/{activity_id}/validate", response_model=ReadinessResponse)
def activity_validate(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> ReadinessResponse:
    campaign = owned_campaign(db, owner.id, campaign_id)
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    result = activity_readiness(db, campaign, activity)
    db.commit()
    return result


@router.post("/{campaign_id}/validate", response_model=ReadinessResponse)
def validate(campaign_id: uuid.UUID, db: DB, owner: Owner) -> ReadinessResponse:
    campaign = owned_campaign(db, owner.id, campaign_id)
    result = campaign_readiness(db, campaign, campaign_activities(db, campaign_id))
    if result.state in {"ready", "warning"} and campaign.status in {"draft", "planning"}:
        campaign.status = "ready"
        campaign.updated_at = now()
        campaign.row_version += 1
    db.commit()
    return result


@router.get("/{campaign_id}/conflicts", response_model=list[Conflict])
def conflicts(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[Conflict]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    return detect_conflicts(
        campaign, campaign_activities(db, campaign_id), dependencies(db, campaign_id)
    )


@router.post("/{campaign_id}/schedule-preview")
def schedule_preview(
    campaign_id: uuid.UUID, request: ScheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    values = campaign_activities(db, campaign_id)
    selected = [
        value for value in values if not request.activity_ids or value.id in request.activity_ids
    ]
    readiness = [
        {"activity_id": value.id, **activity_readiness(db, campaign, value).model_dump()}
        for value in selected
    ]
    return {
        "campaign_id": campaign.id,
        "selected_count": len(selected),
        "readiness": readiness,
        "conflicts": detect_conflicts(campaign, selected, dependencies(db, campaign_id)),
        "requires_confirmation": True,
    }


@router.post("/{campaign_id}/schedule")
def schedule(
    campaign_id: uuid.UUID, request: ScheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id, lock=True)
    if campaign.status not in {"ready", "scheduled", "paused"}:
        raise HTTPException(409, "Campaign is not eligible for scheduling.")
    return schedule_activities(db, owner, campaign, campaign_activities(db, campaign_id), request)


@router.post("/{campaign_id}/activities/{activity_id}/schedule")
def schedule_one(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id, lock=True)
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    return schedule_activities(
        db,
        owner,
        campaign,
        [activity],
        ScheduleRequest(activity_ids=[activity.id], confirm=True),
    )


@router.post("/{campaign_id}/activities/{activity_id}/cancel", response_model=ActivityResponse)
def activity_cancel(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    if activity.status in {"succeeded", "completed_with_warning", "archived"}:
        raise HTTPException(409, "Completed activity history cannot be cancelled.")
    job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    if job and job.state in {"claimed", "running"}:
        job.state = "cancel_requested"
        activity.status = "cancel_requested"
    else:
        if job and job.state not in {"succeeded", "cancelled"}:
            job.state = "cancelled"
            job.completed_at = now()
        activity.status = "cancelled"
        activity.completed_at = now()
    activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


@router.post("/{campaign_id}/activities/{activity_id}/retry", response_model=ActivityResponse)
def activity_retry(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    if not job or job.state not in {"failed", "dead_letter", "expired", "cancelled"}:
        raise HTTPException(409, "Activity has no retryable terminal job.")
    job.state = "pending"
    job.available_at_utc = utcnow()
    job.completed_at = None
    job.lease_owner = None
    job.lease_expires_at = None
    job.next_retry_at = None
    job.updated_at = utcnow()
    activity.status = "queued"
    activity.failure_code = activity.safe_failure_message = None
    activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


@router.post("/{campaign_id}/activities/{activity_id}/release", response_model=ActivityResponse)
def activity_release(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    edges = list(
        db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.predecessor_activity_id == activity.id,
                CampaignActivityDependency.dependency_type == "manual_release",
                CampaignActivityDependency.released_at.is_(None),
            )
        )
    )
    if not edges:
        raise HTTPException(409, "Activity has no manual checkpoint to release.")
    for edge in edges:
        edge.released_at = now()
    activity.status = "succeeded"
    activity.completed_at = activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


@router.post("/{campaign_id}/activities/{activity_id}/archive", response_model=ActivityResponse)
def activity_archive(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    if activity.status not in {"succeeded", "failed", "cancelled", "dead_letter"}:
        raise HTTPException(409, "Only terminal activities can be archived.")
    activity.status = "archived"
    activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


def reschedule_projection(
    db: Session, campaign: Campaign, request: RescheduleRequest
) -> list[dict[str, object]]:
    projection: list[dict[str, object]] = []
    for change in request.changes:
        activity = owned_activity(db, campaign.owner_id, campaign.id, change.activity_id)
        new_utc = local_to_utc(
            datetime.combine(change.scheduled_local_date, change.scheduled_local_time),
            change.timezone_name,
            0,
        )
        projection.append(
            {
                "activity_id": activity.id,
                "old_scheduled_at_utc": activity.scheduled_at_utc,
                "new_scheduled_at_utc": new_utc,
                "requires_recreation": activity.status in {"scheduled", "queued"},
                "blocked": activity.status in {"running", "succeeded"},
            }
        )
    return projection


@router.post("/{campaign_id}/reschedule-preview")
def reschedule_preview(
    campaign_id: uuid.UUID, request: RescheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    return {"campaign_id": campaign.id, "changes": reschedule_projection(db, campaign, request)}


@router.post("/{campaign_id}/reschedule")
def reschedule(
    campaign_id: uuid.UUID, request: RescheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    if not request.confirm:
        raise HTTPException(409, "Rescheduling requires explicit confirmation.")
    projection = reschedule_projection(db, campaign, request)
    if any(bool(value["blocked"]) for value in projection):
        raise HTTPException(409, "Running or completed activities cannot be rescheduled.")
    for change in request.changes:
        activity = owned_activity(db, owner.id, campaign.id, change.activity_id)
        if activity.row_version != change.row_version:
            raise HTTPException(409, "Activity changed; reload the rescheduling preview.")
        activity.scheduled_local_date = change.scheduled_local_date
        activity.scheduled_local_time = change.scheduled_local_time
        activity.timezone_name = change.timezone_name
        activity.scheduled_at_utc = local_to_utc(
            datetime.combine(change.scheduled_local_date, change.scheduled_local_time),
            change.timezone_name,
            0,
        )
        activity.row_version += 1
        activity.updated_at = now()
        if activity.schedule_id:
            schedule_value = db.get(PublishingSchedule, activity.schedule_id)
            if schedule_value:
                schedule_value.archived = True
                schedule_value.enabled = False
            activity.schedule_id = None
            activity.job_id = None
            activity.status = "ready"
    db.commit()
    return {"campaign_id": campaign.id, "changes": projection}


@router.get("/{campaign_id}/calendar", response_model=list[CalendarEvent])
def campaign_calendar(
    campaign_id: uuid.UUID, db: DB, owner: Owner, start: datetime, end: datetime
) -> list[CalendarEvent]:
    owned_campaign(db, owner.id, campaign_id)
    if end <= start or end - start > timedelta(days=get_settings().campaign_calendar_max_days):
        raise HTTPException(422, "Calendar range must be positive and within the configured limit.")
    return calendar_events(db, owner.id, start, end, campaign_id=campaign_id)


@router.get("/{campaign_id}/progress", response_model=ProgressResponse)
def campaign_progress(campaign_id: uuid.UUID, db: DB, owner: Owner) -> ProgressResponse:
    owned_campaign(db, owner.id, campaign_id)
    project_activity_states(db, campaign_id)
    return progress(campaign_activities(db, campaign_id))


def pause_campaign_resources(db: Session, campaign_id: uuid.UUID) -> None:
    activity_values = campaign_activities(db, campaign_id)
    schedule_ids = [value.schedule_id for value in activity_values if value.schedule_id]
    if schedule_ids:
        for schedule_value in db.scalars(
            select(PublishingSchedule).where(PublishingSchedule.id.in_(schedule_ids))
        ):
            schedule_value.paused = True
            schedule_value.updated_at = now()
        for job in db.scalars(
            select(PublishingJob).where(
                PublishingJob.schedule_id.in_(schedule_ids),
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
            )
        ):
            job.state = "paused"
            job.updated_at = now()


@router.post("/{campaign_id}/release", response_model=CampaignResponse)
def release(campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner) -> Campaign:
    if not request.confirm:
        raise HTTPException(409, "Campaign release requires explicit confirmation.")
    campaign = owned_campaign(db, owner.id, campaign_id)
    readiness = campaign_readiness(db, campaign, campaign_activities(db, campaign_id))
    if readiness.state not in {"ready", "warning"}:
        raise HTTPException(409, "Campaign is not ready for release.")
    if campaign.status == "draft":
        transition(db, owner, campaign_id, "planning")
    return transition(db, owner, campaign_id, "ready")


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
def pause(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    value = transition(db, owner, campaign_id, "paused")
    pause_campaign_resources(db, campaign_id)
    db.commit()
    return value


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
def resume(campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner) -> Campaign:
    if not request.missed_activity_policy:
        raise HTTPException(422, "A missed-activity policy is required.")
    campaign = owned_campaign(db, owner.id, campaign_id)
    if campaign.status != "paused":
        raise HTTPException(409, "Only paused Campaigns can resume.")
    try:
        resolve_missed(db, owner, campaign, request.missed_activity_policy)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    future = [
        value
        for value in campaign_activities(db, campaign_id)
        if value.schedule_id and value.scheduled_at_utc >= utcnow()
    ]
    for activity in future:
        schedule_value = db.get(PublishingSchedule, activity.schedule_id)
        if schedule_value:
            schedule_value.paused = False
        job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state == "paused":
            job.state = "pending"
            job.available_at_utc = max(job.available_at_utc, utcnow())
    target = "scheduled" if any(value.schedule_id for value in future) else "ready"
    value = transition(db, owner, campaign_id, target)
    db.commit()
    return value


@router.post("/{campaign_id}/resume-preview", response_model=ResumePreviewResponse)
def preview_resume(
    campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner
) -> object:
    if not request.missed_activity_policy:
        raise HTTPException(422, "A missed-activity policy is required.")
    campaign = owned_campaign(db, owner.id, campaign_id)
    if campaign.status != "paused":
        raise HTTPException(409, "Only paused Campaigns have a resume preview.")
    return resume_preview(db, campaign, request.missed_activity_policy)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
def cancel(campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner) -> Campaign:
    value = transition(db, owner, campaign_id, "cancelled", reason=request.reason)
    for activity in campaign_activities(db, campaign_id):
        job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state in {"claimed", "running"}:
            job.state = "cancel_requested"
            activity.status = "cancel_requested"
        elif activity.status not in {"succeeded", "completed_with_warning"}:
            if job and job.state not in {"cancelled", "succeeded"}:
                job.state = "cancelled"
                job.completed_at = now()
            schedule_value = (
                db.get(PublishingSchedule, activity.schedule_id) if activity.schedule_id else None
            )
            if schedule_value:
                schedule_value.enabled = False
                schedule_value.paused = True
                schedule_value.cancellation_reason = request.reason
            activity.status = "cancelled"
    db.commit()
    return value


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
def complete(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    values = campaign_activities(db, campaign_id)
    required = [value for value in values if value.required and value.enabled]
    if any(value.status not in {"succeeded", "completed_with_warning"} for value in required):
        raise HTTPException(409, "All required activities must complete successfully.")
    return transition(db, owner, campaign_id, "completed")


@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
def archive(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    return transition(db, owner, campaign_id, "archived")
