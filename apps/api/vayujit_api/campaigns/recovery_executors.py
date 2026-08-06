"""Focused callable handlers for the first Recovery dispatch extraction."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.campaign_service import transition
from vayujit_api.campaigns.completion_service import resolve_missed
from vayujit_api.campaigns.models import CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.recovery_service import CampaignRecoveryExecutionContext
from vayujit_api.campaigns.schemas import (
    CampaignRecoveryActionResult,
    CampaignRecoveryRequest,
)
from vayujit_api.campaigns.workflow_service import restore_campaign_waits
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
    PublishingJob,
    PublishingRecoveryRecord,
    PublishingSchedule,
)
from vayujit_api.publishing.service import reconcile_execution


def _now() -> datetime:
    return datetime.now(UTC)


def execute_replace_with_new_approved_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    db, owner, campaign, activity = context.db, context.owner, context.campaign, context.activity
    if (
        activity is None
        or request.replacement_artifact_id is None
        or request.replacement_artifact_version is None
        or request.expected_activity_row_version is None
    ):
        raise HTTPException(
            422,
            "Replacement requires an Artifact, exact version, and expected Activity row version.",
        )
    if campaign.status in {"cancelled", "archived"}:
        raise HTTPException(409, "This Campaign cannot accept replacement Activities.")
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == request.replacement_artifact_id,
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.version_number == request.replacement_artifact_version,
        )
    )

    if not artifact or artifact.status != "approved":
        raise HTTPException(409, "The exact replacement Artifact must be approved.")
    if artifact.product_id != activity.product_id:
        raise HTTPException(409, "The replacement Artifact belongs to another Product.")
    existing = db.scalar(
        select(CampaignActivity).where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.replaces_activity_id == activity.id,
        )
    )
    if existing:
        if existing.artifact_id != artifact.id:
            raise HTTPException(409, "This Activity already has a different replacement.")
        return CampaignRecoveryActionResult(
            action=request.action,
            outcome="reused",
            resource_ids={
                "original_activity_id": str(activity.id),
                "replacement_activity_id": str(existing.id),
            },
            safe_message="The existing replacement Activity was reused.",
            confirmation_required=False,
            correlation_id=context.correlation_id,
            idempotency_result="reused",
            idempotent_reuse=True,
        )
    if activity.row_version != request.expected_activity_row_version:
        raise HTTPException(409, "The Activity changed; refresh before replacing it.")
    sequence = (
        db.scalar(
            select(func.max(CampaignActivity.sequence)).where(
                CampaignActivity.campaign_id == campaign.id
            )
        )
        or 0
    ) + 1
    stamp = context.now_utc
    replacement = CampaignActivity(
        owner_id=owner.id,
        campaign_id=campaign.id,
        product_id=activity.product_id,
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        destination_id=activity.destination_id,
        connector_key=activity.connector_key,
        requested_action=activity.requested_action,
        activity_type=activity.activity_type,
        name=f"{activity.name} (replacement)",
        description=activity.description,
        sequence=sequence,
        dependency_policy=activity.dependency_policy,
        scheduled_local_date=activity.scheduled_local_date,
        scheduled_local_time=activity.scheduled_local_time,
        timezone_name=activity.timezone_name,
        scheduled_at_utc=activity.scheduled_at_utc,
        duration_minutes=activity.duration_minutes,
        status="draft",
        readiness_status="incomplete",
        required=activity.required,
        enabled=True,
        created_by=owner.id,
        created_at=stamp,
        updated_at=stamp,
        correlation_id=context.correlation_id,
        idempotency_key=f"replacement:{activity.id}:{artifact.id}",
        replaces_activity_id=activity.id,
        replacement_reason=request.reason,
        replacement_created_at=stamp,
    )
    db.add(replacement)
    db.flush()
    activity.replaced_by_activity_id = replacement.id
    activity.updated_at = stamp
    activity.row_version += 1
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.artifact_version_replaced",
        entity_type="campaign_activity",
        entity_id=replacement.id,
        metadata={
            "campaign_id": str(campaign.id),
            "original_activity_id": str(activity.id),
            "replacement_activity_id": str(replacement.id),
            "artifact_version": artifact.version_number,
        },
    )
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="succeeded",
        resource_ids={
            "original_activity_id": str(activity.id),
            "replacement_activity_id": str(replacement.id),
            "artifact_id": str(artifact.id),
        },
        safe_message="The approved Artifact replacement was created.",
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="created",
        idempotent_reuse=False,
    )


def execute_release_checkpoint(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    activity = context.activity
    if activity is None:
        raise HTTPException(422, "This Recovery action requires an Activity.")
    if activity.activity_type not in {"review_checkpoint", "approval_checkpoint"}:
        raise HTTPException(409, "Only manual review checkpoints can be released.")
    if activity.status in {"succeeded", "cancelled", "archived"}:
        return CampaignRecoveryActionResult(
            action=request.action,
            outcome="reused",
            resource_ids={"activity_id": str(activity.id)},
            safe_message="The checkpoint was already released.",
            confirmation_required=False,
            correlation_id=context.correlation_id,
            idempotency_result="reused",
        )
    stamp = context.now_utc
    activity.status = "succeeded"
    activity.readiness_status = "ready"
    activity.completed_at = stamp
    activity.released_by = context.owner.id
    activity.released_at = stamp
    activity.updated_at = stamp
    activity.row_version += 1
    from vayujit_api.campaigns.schedule_service import project_activity_states

    project_activity_states(context.db, context.campaign.id)
    record_event(
        context.db,
        actor_id=context.owner.id,
        action="campaign.checkpoint_released",
        entity_type="campaign_activity",
        entity_id=activity.id,
        metadata={"campaign_id": str(context.campaign.id), "activity_id": str(activity.id)},
    )
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="succeeded",
        resource_ids={"activity_id": str(activity.id)},
        safe_message="The checkpoint was released.",
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="created",
    )


def resolve_open_campaign(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    """Resolve a safe internal Campaign navigation target without mutation."""
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids={"campaign_id": str(context.campaign.id)},
        safe_message="Campaign navigation is available.",
        navigation_targets={"campaign": f"/campaigns/{context.campaign.id}"},
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_open_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Activity navigation requires an Activity.")
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids={
            "campaign_id": str(context.campaign.id),
            "activity_id": str(context.activity.id),
        },
        safe_message="Activity navigation is available.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}/activities/{context.activity.id}"
        },
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_open_product(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None or context.activity.product_id is None:
        raise ValueError("Product navigation is unavailable for this Activity.")
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids={"product_id": str(context.activity.product_id)},
        safe_message="Product navigation is available.",
        navigation_targets={"product": f"/products/{context.activity.product_id}"},
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_open_artifact(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None or context.activity.artifact_id is None:
        raise ValueError("Artifact navigation is unavailable for this Activity.")
    version = context.activity.artifact_version
    resource_ids = {"artifact_id": str(context.activity.artifact_id)}
    if version is not None:
        resource_ids["artifact_version"] = str(version)
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids=resource_ids,
        safe_message="Artifact navigation is available.",
        navigation_targets={"artifact": f"/ai/artifacts/{context.activity.artifact_id}"},
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_open_destination(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None or context.activity.destination_id is None:
        raise ValueError("Destination navigation is unavailable for this Activity.")
    destination = context.db.scalar(
        select(PublishingDestination).where(
            PublishingDestination.id == context.activity.destination_id,
            PublishingDestination.owner_id == context.owner.id,
        )
    )
    if destination is None:
        raise ValueError("Destination navigation is unavailable for this Activity.")
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids={"destination_id": str(destination.id)},
        safe_message="Destination navigation is available.",
        navigation_targets={"destination": f"/publishing/destinations/{destination.id}"},
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_open_job(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None or context.activity.job_id is None:
        raise ValueError("Job navigation is unavailable for this Activity.")
    job = context.db.scalar(
        select(PublishingJob).where(
            PublishingJob.id == context.activity.job_id,
            PublishingJob.owner_id == context.owner.id,
        )
    )
    if job is None:
        raise ValueError("Job navigation is unavailable for this Activity.")
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids={"job_id": str(job.id)},
        safe_message="Publishing job navigation is available.",
        navigation_targets={"job": f"/publishing/jobs/{job.id}"},
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_open_publishing_execution(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None or context.activity.publishing_execution_id is None:
        raise ValueError("Publishing execution navigation is unavailable for this Activity.")
    from vayujit_api.publishing.models import PublishingExecution

    execution = context.db.scalar(
        select(PublishingExecution).where(
            PublishingExecution.id == context.activity.publishing_execution_id,
            PublishingExecution.owner_id == context.owner.id,
        )
    )
    if execution is None:
        raise ValueError("Publishing execution navigation is unavailable for this Activity.")
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="navigation_available",
        resource_ids={"execution_id": str(execution.id)},
        safe_message="Publishing execution navigation is available.",
        navigation_targets={"execution": f"/publishing/executions/{execution.id}"},
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def resolve_review_dependency(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Dependency review requires an Activity.")
    edge = context.db.scalar(
        select(CampaignActivityDependency).where(
            (CampaignActivityDependency.predecessor_activity_id == context.activity.id)
            | (CampaignActivityDependency.successor_activity_id == context.activity.id)
        )
    )
    if edge is None:
        raise ValueError("No dependency is linked to this Activity.")
    predecessor = context.db.get(CampaignActivity, edge.predecessor_activity_id)
    successor = context.db.get(CampaignActivity, edge.successor_activity_id)
    if predecessor is None or successor is None:
        raise ValueError("The dependency endpoints are unavailable.")
    satisfied = predecessor.status == "succeeded"
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="dependency_reviewed",
        resource_ids={
            "campaign_id": str(context.campaign.id),
            "dependency_id": str(edge.id),
        },
        safe_message=(
            "The predecessor succeeded." if satisfied else "The predecessor has not succeeded."
        ),
        navigation_targets={
            "campaign": f"/campaigns/{context.campaign.id}",
            "predecessor": f"/campaigns/{context.campaign.id}?activity={predecessor.id}",
            "successor": f"/campaigns/{context.campaign.id}?activity={successor.id}",
        },
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="not_applicable",
    )


def execute_pause_campaign(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    """Pause a Campaign while preserving the existing resource behavior."""
    campaign = transition(context.db, context.owner, context.campaign.id, "paused")
    activities = list(
        context.db.scalars(
            select(CampaignActivity).where(CampaignActivity.campaign_id == context.campaign.id)
        )
    )
    schedule_ids = [item.schedule_id for item in activities if item.schedule_id]
    if schedule_ids:
        for schedule in context.db.scalars(
            select(PublishingSchedule).where(PublishingSchedule.id.in_(schedule_ids))
        ):
            schedule.paused = True
            schedule.updated_at = _now()
        for job in context.db.scalars(
            select(PublishingJob).where(
                PublishingJob.schedule_id.in_(schedule_ids),
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
            )
        ):
            job.state = "paused"
            job.updated_at = _now()
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="paused",
        resource_ids={"campaign_id": str(campaign.id)},
        safe_message="Campaign paused.",
        navigation_targets={"campaign": f"/campaigns/{campaign.id}"},
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="reused" if campaign.status == "paused" else "created",
    )


def execute_resume_campaign(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    campaign = context.campaign
    try:
        resolve_missed(
            context.db,
            context.owner,
            campaign,
            "reschedule_manually",
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    activities = list(
        context.db.scalars(
            select(CampaignActivity).where(CampaignActivity.campaign_id == campaign.id)
        )
    )
    future = [
        value
        for value in activities
        if value.schedule_id
        and value.scheduled_at_utc is not None
        and value.scheduled_at_utc >= _now()
    ]
    for activity in future:
        schedule = context.db.get(PublishingSchedule, activity.schedule_id)
        if schedule:
            schedule.paused = False
        job = context.db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state == "paused":
            job.state = "pending"
            job.available_at_utc = max(job.available_at_utc, _now())
    target = "scheduled" if any(value.schedule_id for value in future) else "ready"
    resumed = transition(context.db, context.owner, campaign.id, target)
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="resumed",
        resource_ids={"campaign_id": str(resumed.id)},
        safe_message="Campaign resumed.",
        navigation_targets={"campaign": f"/campaigns/{resumed.id}"},
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="reused" if resumed.status == target else "created",
    )


def execute_cancel_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Cancellation requires an Activity.")
    activity = context.activity
    if activity.status in {"succeeded", "completed_with_warning", "archived"}:
        raise ValueError("Completed activity history cannot be cancelled.")
    job = context.db.get(PublishingJob, activity.job_id) if activity.job_id else None
    if job and job.state in {"claimed", "running"}:
        job.state = "cancel_requested"
        activity.status = "cancel_requested"
    else:
        if job and job.state not in {"succeeded", "cancelled"}:
            job.state = "cancelled"
            job.completed_at = _now()
        activity.status = "cancelled"
        activity.completed_at = _now()
    activity.updated_at = _now()
    context.db.commit()
    context.db.refresh(activity)
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome=activity.status,
        resource_ids={"activity_id": str(activity.id)},
        safe_message="Activity cancellation state updated.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
        },
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="reused" if activity.status == "cancelled" else "created",
    )


def execute_cancel_campaign(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    campaign = transition(
        context.db,
        context.owner,
        context.campaign.id,
        "cancelled",
        reason=request.reason,
    )
    activities = list(
        context.db.scalars(
            select(CampaignActivity).where(CampaignActivity.campaign_id == campaign.id)
        )
    )
    for activity in activities:
        job = context.db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state in {"claimed", "running"}:
            job.state = "cancel_requested"
            activity.status = "cancel_requested"
        elif activity.status not in {"succeeded", "completed_with_warning"}:
            if job and job.state not in {"cancelled", "succeeded"}:
                job.state = "cancelled"
                job.completed_at = _now()
            schedule = (
                context.db.get(PublishingSchedule, activity.schedule_id)
                if activity.schedule_id
                else None
            )
            if schedule:
                schedule.enabled = False
                schedule.paused = True
                schedule.cancellation_reason = request.reason
            activity.status = "cancelled"
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="cancelled",
        resource_ids={"campaign_id": str(campaign.id)},
        safe_message="Campaign cancelled.",
        navigation_targets={"campaign": f"/campaigns/{campaign.id}"},
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="reused" if campaign.status == "cancelled" else "created",
    )


def execute_retry_campaign_workflow_wait(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    restored = restore_campaign_waits(context.db, owner_id=context.owner.id)
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="completed" if restored else "no_change",
        resource_ids={"campaign_id": str(context.campaign.id)},
        safe_message="Workflow wait recovery evaluated.",
        navigation_targets={"campaign": f"/campaigns/{context.campaign.id}"},
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="reused" if restored == 0 else "created",
    )


def execute_skip_optional_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Skipping requires an Activity.")
    activity = context.activity
    if activity.required:
        raise ValueError("Required Activities cannot be skipped.")
    if activity.status == "skipped":
        return CampaignRecoveryActionResult(
            action=request.action,
            outcome="skipped",
            resource_ids={"activity_id": str(activity.id)},
            safe_message="Activity was already skipped.",
            navigation_targets={
                "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
            },
            confirmation_required=True,
            correlation_id=context.correlation_id,
            idempotency_result="reused",
            status=activity.status,
            idempotent_reuse=True,
            publishing_execution_id=activity.publishing_execution_id,
        )
    activity.status = "skipped"
    activity.completed_at = activity.updated_at = _now()
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="skipped",
        resource_ids={"activity_id": str(activity.id)},
        safe_message="Optional Activity skipped.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
        },
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="created",
    )


def execute_skip_missed_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Skipping requires an Activity.")
    activity = context.activity
    if activity.status != "missed":
        raise ValueError("Only missed Activities can be skipped.")
    if activity.required:
        raise ValueError("Required Activities cannot be skipped.")
    if activity.status == "skipped":
        return CampaignRecoveryActionResult(
            action=request.action,
            outcome="skipped",
            resource_ids={"activity_id": str(activity.id)},
            safe_message="Missed Activity was already skipped.",
            navigation_targets={
                "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
            },
            confirmation_required=True,
            correlation_id=context.correlation_id,
            idempotency_result="reused",
            status=activity.status,
            idempotent_reuse=True,
            publishing_execution_id=activity.publishing_execution_id,
        )
    activity.status = "skipped"
    activity.completed_at = activity.updated_at = _now()
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="skipped",
        resource_ids={"activity_id": str(activity.id)},
        safe_message="Optional missed Activity skipped.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
        },
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="created",
    )


def execute_create_one_catch_up(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    raise ValueError("Catch-up creation requires the existing missed-resolution workflow.")


def execute_retry_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Retry requires an Activity.")
    activity = context.activity
    job = context.db.get(PublishingJob, activity.job_id) if activity.job_id else None
    if not job or job.state not in {"failed", "dead_letter", "expired", "cancelled"}:
        raise ValueError("Activity has no retryable terminal job.")
    job.state = "pending"
    job.available_at_utc = _now()
    job.completed_at = None
    job.lease_owner = None
    job.lease_expires_at = None
    job.next_retry_at = None
    job.updated_at = _now()
    activity.status = "queued"
    activity.failure_code = activity.safe_failure_message = None
    activity.updated_at = _now()
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="retrying",
        resource_ids={"activity_id": str(activity.id), "job_id": str(job.id)},
        safe_message="Activity retry queued.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
        },
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="created",
    )


def execute_reconcile_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.activity is None:
        raise ValueError("Reconciliation requires an Activity.")
    activity = context.activity
    if not activity.publishing_execution_id or not activity.job_id:
        raise ValueError("A Publishing execution and durable job are required to reconcile.")
    if activity.status == "succeeded":
        return CampaignRecoveryActionResult(
            action=request.action,
            outcome="remote_succeeded",
            resource_ids={"activity_id": str(activity.id)},
            safe_message="Activity was already reconciled successfully.",
            navigation_targets={
                "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
            },
            confirmation_required=True,
            correlation_id=context.correlation_id,
            idempotency_result="reused",
            status=activity.status,
            idempotent_reuse=True,
            publishing_execution_id=activity.publishing_execution_id,
        )
    reconciliation = reconcile_execution(
        context.db, context.owner, activity.publishing_execution_id
    )
    execution = context.db.get(PublishingExecution, activity.publishing_execution_id)
    job = context.db.get(PublishingJob, activity.job_id)
    if job is None:
        raise ValueError("The durable Publishing job is unavailable.")
    remote_exists = reconciliation.reconciliation_status in {
        "in_sync",
        "changed_remotely",
        "remote_changes_kept",
    }
    stamp = _now()
    if execution and remote_exists:
        execution.status = "succeeded"
        execution.completed_at = execution.completed_at or stamp
        execution.updated_at = stamp
    job.state = "succeeded" if remote_exists else "failed"
    job.completed_at = stamp
    job.recovery_state = "remote_succeeded" if remote_exists else "manual_review"
    job.recovered_at = stamp
    job.updated_at = stamp
    job.lease_owner = None
    job.lease_expires_at = None
    activity.status = "succeeded" if remote_exists else "failed"
    activity.completed_at = stamp if remote_exists else None
    activity.updated_at = stamp
    context.db.add(
        PublishingRecoveryRecord(
            owner_id=context.owner.id,
            job_id=job.id,
            worker_id=None,
            publishing_execution_id=activity.publishing_execution_id,
            result="remote_succeeded" if remote_exists else "manual_review",
            reason_code="campaign_activity_reconciled",
            safe_message="Existing remote state reconciled.",
            correlation_id=context.correlation_id,
            created_at=stamp,
        )
    )
    record_event(
        context.db,
        actor_id=context.owner.id,
        action="campaign.activity_reconciled",
        entity_type="campaign_activity",
        entity_id=activity.id,
        metadata={
            "campaign_id": str(context.campaign.id),
            "connector": activity.connector_key,
            "result": "remote_succeeded" if remote_exists else "manual_review",
        },
    )
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="remote_succeeded" if remote_exists else "manual_review_required",
        resource_ids={"activity_id": str(activity.id), "job_id": str(job.id)},
        safe_message="Existing remote state was reconciled.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}/activities/{activity.id}"
        },
        confirmation_required=True,
        correlation_id=context.correlation_id,
        idempotency_result="created",
        status=activity.status,
        publishing_execution_id=activity.publishing_execution_id,
        reconciliation_status=reconciliation.reconciliation_status,
    )
