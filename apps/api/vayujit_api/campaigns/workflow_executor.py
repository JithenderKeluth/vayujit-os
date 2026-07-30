import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.activity_service import add_dependency, create_activity
from vayujit_api.campaigns.campaign_service import (
    create_campaign,
    owned_campaign,
    transition,
    update_campaign,
)
from vayujit_api.campaigns.completion_service import resolve_missed
from vayujit_api.campaigns.conflict_service import detect_conflicts
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.campaigns.readiness_service import campaign_readiness
from vayujit_api.campaigns.schedule_service import (
    dependencies,
    schedule_activities,
)
from vayujit_api.campaigns.schemas import (
    AddCampaignActivityAction,
    AddCampaignDependencyAction,
    CampaignWorkflowAction,
    CampaignWorkflowResult,
    CancelCampaignAction,
    CreateCampaignAction,
    PauseCampaignAction,
    ReleaseCampaignAction,
    ResumeCampaignAction,
    ScheduleCampaignAction,
    UpdateCampaignAction,
    ValidateCampaignAction,
    WaitForCampaignAction,
)
from vayujit_api.campaigns.workflow_service import (
    create_campaign_wait,
    project_campaign_state,
)
from vayujit_api.identity.models import User
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.workflows.models import WorkflowInstance, WorkflowStepExecution


def _activities(db: Session, campaign_id: object) -> list[CampaignActivity]:
    return list(
        db.scalars(
            select(CampaignActivity)
            .where(CampaignActivity.campaign_id == campaign_id)
            .order_by(CampaignActivity.sequence)
        )
    )


def execute_campaign_action(
    db: Session, owner: User, action: CampaignWorkflowAction
) -> CampaignWorkflowResult:
    if isinstance(action, CreateCampaignAction):
        campaign = create_campaign(db, owner, action.campaign)
        return _result(action, campaign.id, "campaign_created", campaign.status)
    if isinstance(action, UpdateCampaignAction):
        campaign = update_campaign(db, owner, action.campaign_id, action.changes)
        return _result(action, campaign.id, "campaign_updated", campaign.status)
    campaign = owned_campaign(db, owner.id, action.campaign_id, lock=True)
    if isinstance(action, AddCampaignActivityAction):
        activity = create_activity(db, owner, campaign.id, action.activity)
        return _result(
            action,
            campaign.id,
            "activity_created",
            campaign.status,
            activity_id=activity.id,
        )
    if isinstance(action, AddCampaignDependencyAction):
        edge = add_dependency(db, owner, campaign.id, action.dependency)
        return _result(
            action,
            campaign.id,
            "dependency_created",
            campaign.status,
            dependency_id=edge.id,
        )
    values = _activities(db, campaign.id)
    if isinstance(action, ValidateCampaignAction):
        readiness = campaign_readiness(db, campaign, values)
        conflicts = detect_conflicts(campaign, values, dependencies(db, campaign.id))
        db.commit()
        return _result(
            action,
            campaign.id,
            "campaign_validated",
            campaign.status,
            readiness_state=readiness.state,
            blocking_issue_count=sum(issue.severity == "error" for issue in readiness.issues),
            warning_count=sum(issue.severity == "warning" for issue in readiness.issues),
            conflict_count=len(conflicts),
            blocked_activity_ids=[
                value.id for value in values if value.readiness_status in {"blocked", "invalid"}
            ],
        )
    if isinstance(action, ReleaseCampaignAction):
        readiness = campaign_readiness(db, campaign, values)
        if readiness.state not in {"ready", "warning"}:
            return _result(
                action,
                campaign.id,
                "campaign_validated",
                campaign.status,
                readiness_state=readiness.state,
                blocking_issue_count=sum(issue.severity == "error" for issue in readiness.issues),
            )
        if campaign.status == "draft":
            transition(db, owner, campaign.id, "planning")
        campaign = transition(db, owner, campaign.id, "ready")
        _audit(db, owner, campaign.id, action, "campaign.workflow_released")
        db.commit()
        return _result(action, campaign.id, "campaign_released", campaign.status)
    if isinstance(action, ScheduleCampaignAction):
        scheduled = schedule_activities(db, owner, campaign, values, action.request)
        results = cast(list[dict[str, Any]], scheduled.get("results", []))
        return _result(
            action,
            campaign.id,
            "campaign_scheduled",
            campaign.status,
            scheduled_activity_ids=[
                value["activity_id"] for value in results if value.get("status") == "scheduled"
            ],
            blocked_activity_ids=[
                value["activity_id"] for value in results if value.get("status") != "scheduled"
            ],
            schedule_ids=[value["schedule_id"] for value in results if value.get("schedule_id")],
            job_ids=[value["job_id"] for value in results if value.get("job_id")],
        )
    if isinstance(action, PauseCampaignAction):
        campaign = transition(db, owner, campaign.id, "paused")
        _set_paused(db, values, True)
        _audit(db, owner, campaign.id, action, "campaign.workflow_paused")
        db.commit()
        return _result(action, campaign.id, "campaign_paused", campaign.status)
    if isinstance(action, ResumeCampaignAction):
        resolve_missed(db, owner, campaign, action.missed_activity_policy)
        _set_paused(db, values, False)
        campaign = transition(
            db,
            owner,
            campaign.id,
            "scheduled" if any(value.schedule_id for value in values) else "ready",
        )
        _audit(db, owner, campaign.id, action, "campaign.workflow_resumed")
        db.commit()
        return _result(action, campaign.id, "campaign_resumed", campaign.status)
    if isinstance(action, CancelCampaignAction):
        campaign = transition(db, owner, campaign.id, "cancelled", reason=action.reason)
        for value in values:
            if value.status not in {"succeeded", "completed_with_warning"}:
                value.status = "cancelled"
        _audit(db, owner, campaign.id, action, "campaign.workflow_cancelled")
        db.commit()
        return _result(action, campaign.id, "campaign_cancelled", campaign.status)
    if isinstance(action, WaitForCampaignAction):
        workflow = db.scalar(
            select(WorkflowInstance).where(
                WorkflowInstance.id == action.workflow_instance_id,
                WorkflowInstance.owner_id == owner.id,
            )
        )
        step = db.scalar(
            select(WorkflowStepExecution).where(
                WorkflowStepExecution.id == action.workflow_step_id,
                WorkflowStepExecution.workflow_instance_id == action.workflow_instance_id,
            )
        )
        if workflow is None or step is None:
            from fastapi import HTTPException

            raise HTTPException(404, "Workflow step was not found.")
        wait = create_campaign_wait(
            db, owner, workflow, step, campaign, expected_state=action.expected_state
        )
        db.commit()
        state = project_campaign_state(db, campaign)
        result_key = (
            "campaign_wait_completed"
            if state in {"completed", "partially_completed"}
            else (
                "campaign_wait_failed"
                if state in {"failed", "cancelled"}
                else "campaign_wait_created"
            )
        )
        return _result(
            action,
            campaign.id,
            result_key,
            state,
            workflow_wait_id=wait.id,
        )
    raise AssertionError("Validated Campaign action was not handled.")


def _set_paused(db: Session, activities: list[CampaignActivity], paused: bool) -> None:
    for activity in activities:
        schedule = (
            db.get(PublishingSchedule, activity.schedule_id) if activity.schedule_id else None
        )
        if schedule:
            schedule.paused = paused
        job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state in {"paused", "pending", "scheduled", "retry_wait"}:
            job.state = "pending" if not paused else "paused"
            if not paused:
                job.available_at_utc = max(job.available_at_utc, utcnow())


def _audit(
    db: Session,
    owner: User,
    campaign_id: uuid.UUID,
    action: CampaignWorkflowAction,
    event: str,
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=event,
        entity_type="campaign",
        entity_id=campaign_id,
        metadata={"workflow_action": action.action},
    )


def _result(
    action: CampaignWorkflowAction,
    campaign_id: uuid.UUID,
    result: str,
    status: str,
    **values: object,
) -> CampaignWorkflowResult:
    return CampaignWorkflowResult.model_validate(
        {
            "result": result,
            "campaign_id": campaign_id,
            "correlation_id": action.correlation_id,
            "status": status,
            **values,
        }
    )
