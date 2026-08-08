"""Focused callable handlers for the first Recovery dispatch extraction."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.campaign_service import transition
from vayujit_api.campaigns.completion_service import resolve_missed
from vayujit_api.campaigns.models import (
    CampaignActivity,
    CampaignActivityDependency,
    CampaignActivityReschedule,
    CampaignMissedActivityResolution,
    CampaignScheduleLink,
)
from vayujit_api.campaigns.recovery_service import (
    CampaignRecoveryExecutionContext,
    catch_up_fingerprint,
    reschedule_fingerprint,
)
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
from vayujit_api.publishing.scheduler_time import local_to_utc
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
            status="succeeded",
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
    context.db.commit()
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
        status="succeeded",
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
    restore_campaign_waits(context.db, owner_id=context.owner.id)
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
        idempotency_result="released",
        status="succeeded",
    )


def execute_reschedule_activity(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryActionResult:
    if context.maintenance_mode:
        raise HTTPException(503, "Campaign changes are unavailable during maintenance.")
    if context.campaign.status in {"cancelled", "archived"}:
        raise HTTPException(409, "Cancelled or archived Campaigns cannot be rescheduled.")
    activity = context.activity
    if activity is None or request.proposed_local_datetime is None or not request.proposed_timezone:
        raise HTTPException(422, "Rescheduling requires a proposed local time and timezone.")
    if request.expected_activity_row_version is None:
        raise HTTPException(409, "A current Activity row version is required.")
    expected_row_version = request.expected_activity_row_version
    activity = context.db.scalar(
        select(CampaignActivity)
        .where(
            CampaignActivity.id == activity.id,
            CampaignActivity.owner_id == context.owner.id,
            CampaignActivity.campaign_id == context.campaign.id,
        )
        .with_for_update()
    )
    if activity is None:
        raise HTTPException(404, "Activity not found.")
    if not request.preview_fingerprint:
        raise HTTPException(409, "A valid reschedule preview fingerprint is required.")
    try:
        resolved_zero = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 0)
        resolved_one = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 1)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ambiguous = resolved_zero != resolved_one
    if ambiguous and request.fold is None:
        raise HTTPException(422, "An explicit DST fold is required for this local time.")
    if not ambiguous and request.fold not in {None, 0}:
        raise HTTPException(422, "The selected DST fold is not valid for this local time.")
    selected_fold = request.fold if request.fold is not None else 0
    resolved = resolved_one if selected_fold == 1 else resolved_zero
    existing = context.db.scalar(
        select(CampaignActivityReschedule)
        .where(
            CampaignActivityReschedule.owner_id == context.owner.id,
            CampaignActivityReschedule.campaign_id == context.campaign.id,
            CampaignActivityReschedule.activity_id == activity.id,
            CampaignActivityReschedule.preview_fingerprint == request.preview_fingerprint,
            CampaignActivityReschedule.status == "confirmed",
        )
        .with_for_update()
    )
    if existing:
        return CampaignRecoveryActionResult(
            action=request.action,
            outcome="reused",
            resource_ids={"activity_id": str(activity.id), "reschedule_id": str(existing.id)},
            safe_message="The existing Activity reschedule was reused.",
            confirmation_required=False,
            correlation_id=context.correlation_id,
            idempotency_result="reused",
            idempotent_reuse=True,
        )
    fingerprint = reschedule_fingerprint(
        context.db,
        context.owner.id,
        context.campaign,
        activity,
        request.proposed_local_datetime,
        request.proposed_timezone,
        request.reason,
        request.fold,
        expected_row_version,
    )
    if request.preview_fingerprint != fingerprint:
        raise HTTPException(409, "The reschedule preview is stale or invalid.")
    if activity.status not in {"missed", "scheduled", "retry_wait", "paused", "failed"}:
        raise HTTPException(409, "The Activity is not eligible for rescheduling.")
    if activity.row_version != expected_row_version:
        raise HTTPException(409, "The Activity changed; refresh before rescheduling it.")
    stamp = context.now_utc
    original_schedule_id = activity.schedule_id
    original_job_id = activity.job_id
    original_scheduled_for_utc = activity.scheduled_at_utc
    old_job = context.db.get(PublishingJob, original_job_id) if original_job_id else None
    if old_job is not None:
        old_job = context.db.scalar(
            select(PublishingJob).where(PublishingJob.id == old_job.id).with_for_update()
        )
        active_lease = (
            old_job.lease_owner is not None
            and old_job.lease_expires_at is not None
            and old_job.lease_expires_at > stamp
        )
        if old_job is not None and (
            active_lease or (old_job.state == "running" and not old_job.lease_expires_at)
        ):
            raise HTTPException(409, "The Activity job is actively leased or running.")
    artifact = (
        context.db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == activity.artifact_id,
                GeneratedArtifact.owner_id == context.owner.id,
            )
        )
        if activity.artifact_id
        else None
    )
    destination = (
        context.db.scalar(
            select(PublishingDestination).where(
                PublishingDestination.id == activity.destination_id,
                PublishingDestination.owner_id == context.owner.id,
            )
        )
        if activity.destination_id
        else None
    )
    if (
        not artifact
        or artifact.status != "approved"
        or artifact.version_number != activity.artifact_version
    ):
        raise HTTPException(409, "The Activity Artifact approval is no longer valid.")
    if not destination or destination.status != "active":
        raise HTTPException(409, "The Activity destination is no longer active.")
    if original_schedule_id:
        old_schedule = context.db.get(PublishingSchedule, original_schedule_id)
        if old_schedule:
            old_schedule.enabled = False
            old_schedule.archived = True
            old_schedule.cancellation_reason = "Superseded by Activity reschedule."
    if old_job is not None and old_job.state not in {
        "succeeded",
        "failed",
        "cancelled",
        "dead_letter",
    }:
        old_job.state = "cancelled"
        old_job.recovery_state = "superseded"
        old_job.recovery_reason = "Superseded by Activity reschedule."
        old_job.lease_owner = None
        old_job.lease_expires_at = None
        old_job.updated_at = stamp
        old_job.row_version += 1
    artifact_id = artifact.id
    destination_id = destination.id
    schedule = PublishingSchedule(
        owner_id=context.owner.id,
        brand_id=artifact.brand_id,
        product_id=activity.product_id,
        artifact_id=artifact_id,
        artifact_version=artifact.version_number,
        destination_id=destination_id,
        connector_key=destination.connector_key,
        requested_action=activity.requested_action or "publish",
        name=f"{activity.name} (rescheduled)",
        schedule_type="one_time",
        scheduled_at_utc=resolved,
        timezone_name=request.proposed_timezone,
        local_scheduled_at=request.proposed_local_datetime.replace(tzinfo=None),
        recurrence_json=None,
        recurrence_end_at=None,
        enabled=True,
        paused=False,
        archived=False,
        approval_snapshot_json={
            "artifact_status": artifact.status,
            "approved_at": artifact.approved_at.isoformat() if artifact.approved_at else None,
            "approved_by": str(artifact.approved_by) if artifact.approved_by else None,
        },
        destination_snapshot_version=destination.updated_at.isoformat(),
        created_by=context.owner.id,
        created_at=stamp,
        updated_at=stamp,
        next_run_at_utc=resolved,
        missed_occurrence_policy="next_occurrence",
        max_occurrences=1,
        materialized_occurrence_count=0,
    )
    context.db.add(schedule)
    context.db.flush()
    from vayujit_api.publishing.scheduler_service import materialize_due_schedules

    materialize_due_schedules(context.db, commit=False)
    replacement_job = context.db.scalar(
        select(PublishingJob).where(PublishingJob.schedule_id == schedule.id)
    )
    link = CampaignScheduleLink(
        owner_id=context.owner.id,
        campaign_id=context.campaign.id,
        activity_id=activity.id,
        schedule_id=schedule.id,
        job_id=replacement_job.id if replacement_job else None,
        occurrence_key=f"reschedule:{activity.id}:{fingerprint}",
        created_at=stamp,
    )
    context.db.add(link)
    activity.scheduled_local_date = request.proposed_local_datetime.date()
    activity.scheduled_local_time = request.proposed_local_datetime.time()
    activity.timezone_name = request.proposed_timezone
    activity.scheduled_at_utc = resolved
    activity.schedule_id = schedule.id
    activity.job_id = replacement_job.id if replacement_job else None
    activity.status = "scheduled"
    activity.updated_at = stamp
    activity.row_version += 1
    record = CampaignActivityReschedule(
        owner_id=context.owner.id,
        campaign_id=context.campaign.id,
        activity_id=activity.id,
        original_schedule_id=original_schedule_id,
        replacement_schedule_id=schedule.id,
        original_job_id=original_job_id,
        replacement_job_id=replacement_job.id if replacement_job else None,
        original_scheduled_for_utc=original_scheduled_for_utc,
        requested_local_datetime=request.proposed_local_datetime.replace(tzinfo=None),
        requested_timezone=request.proposed_timezone,
        resolved_scheduled_for_utc=resolved,
        reason=request.reason.strip(),
        preview_fingerprint=fingerprint,
        status="confirmed",
        requested_by=context.owner.id,
        requested_at=stamp,
        confirmed_by=context.owner.id,
        confirmed_at=stamp,
        created_at=stamp,
        updated_at=stamp,
    )
    context.db.add(record)
    record_event(
        context.db,
        actor_id=context.owner.id,
        action="campaign.activity_rescheduled",
        entity_type="campaign_activity",
        entity_id=activity.id,
        metadata={
            "campaign_id": str(context.campaign.id),
            "activity_id": str(activity.id),
            "original_schedule_id": str(original_schedule_id) if original_schedule_id else None,
            "replacement_schedule_id": str(schedule.id),
            "original_job_id": str(original_job_id) if original_job_id else None,
            "replacement_job_id": str(replacement_job.id) if replacement_job else None,
            "old_scheduled_at_utc": (
                original_scheduled_for_utc.isoformat() if original_scheduled_for_utc else None
            ),
            "new_scheduled_at_utc": resolved.isoformat(),
            "timezone": request.proposed_timezone,
            "reason": request.reason.strip(),
        },
    )
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="succeeded",
        resource_ids={
            "activity_id": str(activity.id),
            "schedule_id": str(schedule.id),
            "replacement_schedule_id": str(schedule.id),
            "replacement_job_id": str(replacement_job.id) if replacement_job else "",
            "original_schedule_id": str(original_schedule_id) if original_schedule_id else "",
            "original_job_id": str(original_job_id) if original_job_id else "",
            "reschedule_id": str(record.id),
        },
        safe_message="The Activity was rescheduled.",
        navigation_targets={
            "activity": f"/campaigns/{context.campaign.id}?activity={activity.id}",
            "replacement_schedule": f"/publishing/schedules/{schedule.id}",
            **(
                {"replacement_job": f"/publishing/jobs/{replacement_job.id}"}
                if replacement_job
                else {}
            ),
            **(
                {"original_schedule": f"/publishing/schedules/{original_schedule_id}"}
                if original_schedule_id
                else {}
            ),
            **({"original_job": f"/publishing/jobs/{original_job_id}"} if original_job_id else {}),
        },
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
    if context.maintenance_mode:
        raise HTTPException(503, "Campaign changes are unavailable during maintenance.")
    if context.campaign.status not in {
        "ready",
        "scheduled",
        "running",
        "paused",
        "partially_completed",
        "failed",
    }:
        raise HTTPException(409, "Catch-up is unavailable in the current Campaign state.")
    activity = context.activity
    if activity is None:
        raise HTTPException(404, "Missed Activity not found.")
    if activity.status != "missed":
        raise HTTPException(409, "Catch-up is available only for missed Activities.")
    if request.proposed_local_datetime is None or not request.proposed_timezone:
        raise HTTPException(422, "Catch-up requires a proposed local time and timezone.")
    if request.expected_activity_row_version is None:
        raise HTTPException(409, "A current Activity row version is required.")
    original = context.db.scalar(
        select(CampaignActivity)
        .where(
            CampaignActivity.id == activity.id,
            CampaignActivity.owner_id == context.owner.id,
            CampaignActivity.campaign_id == context.campaign.id,
        )
        .with_for_update()
    )
    if original is None:
        raise HTTPException(404, "Missed Activity not found.")
    resolution = context.db.scalar(
        select(CampaignMissedActivityResolution)
        .where(
            CampaignMissedActivityResolution.owner_id == context.owner.id,
            CampaignMissedActivityResolution.campaign_id == context.campaign.id,
            CampaignMissedActivityResolution.activity_id == original.id,
            CampaignMissedActivityResolution.policy == "one_catch_up",
        )
        .with_for_update()
    )
    try:
        resolved_zero = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 0)
        resolved_one = local_to_utc(request.proposed_local_datetime, request.proposed_timezone, 1)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ambiguous = resolved_zero != resolved_one
    if ambiguous and request.fold is None:
        raise HTTPException(422, "An explicit DST fold is required for this local time.")
    if not ambiguous and request.fold not in {None, 0}:
        raise HTTPException(422, "The selected DST fold is not valid for this local time.")
    resolved = resolved_one if request.fold == 1 else resolved_zero
    fingerprint = catch_up_fingerprint(
        context.owner.id,
        context.campaign,
        original,
        request.proposed_local_datetime,
        request.proposed_timezone,
        request.reason,
        request.fold,
        request.expected_activity_row_version,
    )
    if not request.preview_fingerprint or request.preview_fingerprint != fingerprint:
        raise HTTPException(409, "The catch-up preview is stale or invalid.")
    if resolution and resolution.replacement_activity_id:
        if resolution.preview_fingerprint == fingerprint:
            replacement = context.db.get(CampaignActivity, resolution.replacement_activity_id)
            if replacement:
                record_event(
                    context.db,
                    actor_id=context.owner.id,
                    action="campaign.catch_up_reused",
                    entity_type="campaign_activity",
                    entity_id=replacement.id,
                    metadata={
                        "campaign_id": str(context.campaign.id),
                        "original_activity_id": str(original.id),
                        "catch_up_activity_id": str(replacement.id),
                        "reason": request.reason.strip(),
                    },
                )
                context.db.commit()
                return CampaignRecoveryActionResult(
                    action=request.action,
                    outcome="reused",
                    resource_ids={
                        "original_activity_id": str(original.id),
                        "activity_id": str(replacement.id),
                        "schedule_id": str(replacement.schedule_id or ""),
                        "job_id": str(replacement.job_id or ""),
                        "resolution_id": str(resolution.id),
                    },
                    safe_message="The existing catch-up Activity was reused.",
                    navigation_targets={
                        "original_activity": (
                            f"/campaigns/{context.campaign.id}?activity={original.id}"
                        ),
                        "activity": f"/campaigns/{context.campaign.id}?activity={replacement.id}",
                        "schedule": f"/publishing/schedules/{replacement.schedule_id}",
                        "job": f"/publishing/jobs/{replacement.job_id}",
                    },
                    confirmation_required=False,
                    correlation_id=context.correlation_id,
                    idempotency_result="reused",
                    scheduled=True,
                    status="scheduled",
                    idempotent_reuse=True,
                )
        raise HTTPException(409, "This missed Activity already has a catch-up Activity.")
    if original.row_version != request.expected_activity_row_version:
        raise HTTPException(409, "The Activity changed; refresh before creating catch-up.")
    if original.publishing_execution_id:
        raise HTTPException(409, "An Activity with a Publishing execution cannot create catch-up.")
    artifact = (
        context.db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == original.artifact_id,
                GeneratedArtifact.owner_id == context.owner.id,
            )
        )
        if original.artifact_id
        else None
    )
    destination = (
        context.db.scalar(
            select(PublishingDestination).where(
                PublishingDestination.id == original.destination_id,
                PublishingDestination.owner_id == context.owner.id,
            )
        )
        if original.destination_id
        else None
    )
    if (
        not artifact
        or artifact.status != "approved"
        or artifact.version_number != original.artifact_version
    ):
        raise HTTPException(409, "The exact Activity Artifact must remain approved.")
    if not destination or destination.status != "active":
        raise HTTPException(409, "The Activity destination must remain active.")
    if (
        not original.connector_key
        or not original.requested_action
        or destination.connector_key != original.connector_key
    ):
        raise HTTPException(409, "The Activity has no supported publishing action.")
    stamp = context.now_utc
    if original.job_id:
        original_job = context.db.scalar(
            select(PublishingJob).where(PublishingJob.id == original.job_id).with_for_update()
        )
        if original_job and (
            original_job.state in {"claimed", "running"}
            or (
                original_job.lease_owner
                and original_job.lease_expires_at
                and original_job.lease_expires_at > stamp
            )
        ):
            raise HTTPException(409, "Catch-up is blocked while the original job is active.")
    sequence = (
        context.db.scalar(
            select(func.max(CampaignActivity.sequence)).where(
                CampaignActivity.campaign_id == context.campaign.id
            )
        )
        or 0
    ) + 1
    replacement = CampaignActivity(
        owner_id=original.owner_id,
        campaign_id=original.campaign_id,
        product_id=original.product_id,
        artifact_id=original.artifact_id,
        artifact_version=original.artifact_version,
        destination_id=original.destination_id,
        connector_key=original.connector_key,
        requested_action=original.requested_action,
        activity_type=original.activity_type,
        name=f"{original.name} (catch-up)",
        description=original.description,
        sequence=sequence,
        dependency_policy=original.dependency_policy,
        scheduled_local_date=request.proposed_local_datetime.date(),
        scheduled_local_time=request.proposed_local_datetime.time(),
        timezone_name=request.proposed_timezone,
        scheduled_at_utc=resolved,
        duration_minutes=original.duration_minutes,
        status="ready",
        readiness_status="ready",
        required=original.required,
        enabled=True,
        created_by=context.owner.id,
        created_at=stamp,
        updated_at=stamp,
        correlation_id=context.correlation_id,
        idempotency_key=f"catch-up:{original.id}:{fingerprint}",
        replaces_activity_id=original.id,
        replacement_reason=request.reason.strip(),
        replacement_created_at=stamp,
        row_version=1,
    )
    context.db.add(replacement)
    context.db.flush()
    linked_edges = list(
        context.db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.campaign_id == context.campaign.id,
                (CampaignActivityDependency.predecessor_activity_id == original.id)
                | (CampaignActivityDependency.successor_activity_id == original.id),
            )
        )
    )
    for edge in linked_edges:
        predecessor_id = (
            edge.predecessor_activity_id
            if edge.successor_activity_id == original.id
            else replacement.id
        )
        successor_id = (
            replacement.id
            if edge.successor_activity_id == original.id
            else edge.successor_activity_id
        )
        context.db.add(
            CampaignActivityDependency(
                owner_id=edge.owner_id,
                campaign_id=edge.campaign_id,
                predecessor_activity_id=predecessor_id,
                successor_activity_id=successor_id,
                dependency_type=edge.dependency_type,
                released_at=edge.released_at,
                created_at=stamp,
            )
        )
    schedule = PublishingSchedule(
        owner_id=context.owner.id,
        brand_id=artifact.brand_id,
        product_id=original.product_id,
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        destination_id=destination.id,
        connector_key=destination.connector_key,
        requested_action=original.requested_action,
        name=f"{context.campaign.name}: {replacement.name}",
        schedule_type="one_time",
        scheduled_at_utc=resolved,
        timezone_name=request.proposed_timezone,
        local_scheduled_at=request.proposed_local_datetime.replace(tzinfo=None),
        recurrence_json=None,
        recurrence_end_at=None,
        enabled=True,
        paused=False,
        archived=False,
        approval_snapshot_json={
            "artifact_status": artifact.status,
            "artifact_version": artifact.version_number,
        },
        destination_snapshot_version=destination.updated_at.isoformat(),
        created_by=context.owner.id,
        created_at=stamp,
        updated_at=stamp,
        next_run_at_utc=resolved,
        missed_occurrence_policy="next_occurrence",
        max_occurrences=1,
        materialized_occurrence_count=0,
    )
    context.db.add(schedule)
    context.db.flush()
    from vayujit_api.publishing.scheduler_service import materialize_due_schedules

    materialize_due_schedules(context.db, commit=False)
    catch_up_job = context.db.scalar(
        select(PublishingJob).where(PublishingJob.schedule_id == schedule.id)
    )
    replacement.schedule_id = schedule.id
    replacement.job_id = catch_up_job.id if catch_up_job else None
    replacement.status = "scheduled"
    replacement.updated_at = stamp
    link = CampaignScheduleLink(
        owner_id=context.owner.id,
        campaign_id=context.campaign.id,
        activity_id=replacement.id,
        schedule_id=schedule.id,
        job_id=catch_up_job.id if catch_up_job else None,
        occurrence_key=f"campaign:{context.campaign.id}:catch-up:{fingerprint}",
        created_at=stamp,
    )
    context.db.add(link)
    if resolution is None:
        resolution = CampaignMissedActivityResolution(
            owner_id=context.owner.id,
            campaign_id=context.campaign.id,
            activity_id=original.id,
            policy="one_catch_up",
            original_scheduled_at_utc=original.scheduled_at_utc,
            resolution_status="catch_up_created",
            replacement_activity_id=replacement.id,
            replacement_schedule_id=schedule.id,
            replacement_job_id=catch_up_job.id if catch_up_job else None,
            original_schedule_id=original.schedule_id,
            original_job_id=original.job_id,
            preview_fingerprint=fingerprint,
            requested_local_datetime=request.proposed_local_datetime.replace(tzinfo=None),
            requested_timezone=request.proposed_timezone,
            resolved_scheduled_for_utc=resolved,
            fold=request.fold,
            reason=request.reason.strip(),
            correlation_id=context.correlation_id,
            resolved_by=context.owner.id,
            resolved_at=stamp,
        )
        context.db.add(resolution)
    context.db.flush()
    record_event(
        context.db,
        actor_id=context.owner.id,
        action="campaign.catch_up_created",
        entity_type="campaign_activity",
        entity_id=replacement.id,
        metadata={
            "campaign_id": str(context.campaign.id),
            "original_activity_id": str(original.id),
            "catch_up_activity_id": str(replacement.id),
            "original_schedule_id": str(original.schedule_id) if original.schedule_id else None,
            "catch_up_schedule_id": str(schedule.id),
            "original_job_id": str(original.job_id) if original.job_id else None,
            "catch_up_job_id": str(catch_up_job.id) if catch_up_job else None,
            "artifact_id": str(artifact.id),
            "product_id": str(original.product_id),
            "brand_id": str(artifact.brand_id) if artifact.brand_id else None,
            "artifact_version": artifact.version_number,
            "destination_id": str(destination.id),
            "old_scheduled_at_utc": original.scheduled_at_utc.isoformat(),
            "new_scheduled_at_utc": resolved.isoformat(),
            "timezone": request.proposed_timezone,
            "reason": request.reason.strip(),
        },
    )
    context.db.commit()
    return CampaignRecoveryActionResult(
        action=request.action,
        outcome="succeeded",
        resource_ids={
            "original_activity_id": str(original.id),
            "activity_id": str(replacement.id),
            "schedule_id": str(schedule.id),
            "job_id": str(catch_up_job.id) if catch_up_job else "",
            "resolution_id": str(resolution.id),
        },
        safe_message="One catch-up Activity was created.",
        navigation_targets={
            "original_activity": f"/campaigns/{context.campaign.id}?activity={original.id}",
            "activity": f"/campaigns/{context.campaign.id}?activity={replacement.id}",
            "schedule": f"/publishing/schedules/{schedule.id}",
            "job": f"/publishing/jobs/{catch_up_job.id}" if catch_up_job else "",
        },
        confirmation_required=False,
        correlation_id=context.correlation_id,
        idempotency_result="created",
        scheduled=True,
        status="scheduled",
    )


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
