import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.completion_service import terminal_state
from vayujit_api.campaigns.models import Campaign, CampaignActivity, CampaignWorkflowWait
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.workflows.models import WorkflowInstance, WorkflowStepExecution

WAIT_STATES = {
    "planning",
    "scheduled",
    "running",
    "partially_completed",
    "completed",
    "failed",
    "cancelled",
    "blocked",
}
SUCCESS_STATES = {"completed", "partially_completed"}
FAILURE_STATES = {"failed", "cancelled", "blocked"}


def create_campaign_wait(
    db: Session,
    owner: User,
    workflow: WorkflowInstance,
    step: WorkflowStepExecution,
    campaign: Campaign,
    expected_state: str = "completed",
) -> CampaignWorkflowWait:
    if workflow.owner_id != owner.id or campaign.owner_id != owner.id:
        raise HTTPException(404, "Campaign Workflow target was not found.")
    if expected_state not in WAIT_STATES:
        raise HTTPException(422, "Unsupported Campaign wait state.")
    existing = db.scalar(
        select(CampaignWorkflowWait).where(CampaignWorkflowWait.workflow_step_id == step.id)
    )
    if existing:
        return existing
    state = project_campaign_state(db, campaign)
    stamp = now()
    value = CampaignWorkflowWait(
        owner_id=owner.id,
        workflow_instance_id=workflow.id,
        workflow_step_id=step.id,
        campaign_id=campaign.id,
        expected_state=expected_state,
        current_state=state,
        terminal_success_states="completed,partially_completed",
        terminal_failure_states="failed,cancelled,blocked",
        correlation_id=correlation_id(),
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    step.status = "waiting"
    step.paused_at = step.updated_at = stamp
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.workflow_wait_started",
        entity_type="campaign",
        entity_id=campaign.id,
        metadata={"workflow_instance_id": str(workflow.id), "expected_state": expected_state},
    )
    db.flush()
    return value


def project_campaign_state(db: Session, campaign: Campaign) -> str:
    if campaign.status in {"cancelled", "failed"}:
        return campaign.status
    activities = list(
        db.scalars(select(CampaignActivity).where(CampaignActivity.campaign_id == campaign.id))
    )
    state = terminal_state(activities)
    if state == "planning" and campaign.status in {"scheduled", "running"}:
        return campaign.status
    return state


def restore_campaign_waits(db: Session, *, owner_id: uuid.UUID | None = None) -> int:
    query = (
        select(CampaignWorkflowWait)
        .where(CampaignWorkflowWait.completed_at.is_(None))
        .with_for_update(skip_locked=True)
    )
    if owner_id:
        query = query.where(CampaignWorkflowWait.owner_id == owner_id)
    waits = list(db.scalars(query))
    completed = 0
    for wait in waits:
        campaign = db.get(Campaign, wait.campaign_id)
        workflow = db.get(WorkflowInstance, wait.workflow_instance_id)
        step = db.get(WorkflowStepExecution, wait.workflow_step_id)
        if not campaign or not workflow or not step:
            continue
        state = project_campaign_state(db, campaign)
        wait.current_state = state
        wait.updated_at = now()
        wait.row_version += 1
        if state not in SUCCESS_STATES | FAILURE_STATES:
            continue
        wait.completed_at = now()
        if state in SUCCESS_STATES:
            step.status = "succeeded"
            step.completed_at = step.updated_at = now()
            workflow.status = "completed"
            workflow.completed_at = workflow.updated_at = now()
            workflow.current_step_key = None
            action = "campaign.workflow_wait_completed"
        else:
            wait.failure_code = f"campaign_{state}"
            wait.safe_failure_message = f"Campaign reached terminal state: {state}."
            step.status = "failed"
            step.error_code = wait.failure_code
            step.safe_error_message = wait.safe_failure_message
            step.failed_at = step.updated_at = now()
            workflow.status = "failed"
            workflow.error_code = wait.failure_code
            workflow.safe_error_message = wait.safe_failure_message
            workflow.failed_at = workflow.updated_at = now()
            action = "campaign.workflow_wait_failed"
        record_event(
            db,
            actor_id=wait.owner_id,
            action=action,
            entity_type="campaign",
            entity_id=campaign.id,
            metadata={"workflow_instance_id": str(workflow.id), "state": state},
        )
        completed += 1
    db.commit()
    return completed
