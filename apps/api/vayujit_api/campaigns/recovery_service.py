"""Authoritative, side-effect-free Campaign Recovery eligibility policy."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Protocol

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.campaigns.models import Campaign, CampaignActivity
from vayujit_api.campaigns.schemas import (
    CampaignRecoveryActionResult,
    CampaignRecoveryRequest,
)
from vayujit_api.publishing.models import PublishingDestination, PublishingJob, PublishingSchedule


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    eligible: bool
    reason_code: str
    explanation: str
    confirmation_required: bool
    navigation_target: str | None = None


CampaignRecoveryResult = CampaignRecoveryActionResult


def reschedule_fingerprint(
    db: Any,
    owner_id: Any,
    campaign: Campaign,
    activity: CampaignActivity,
    proposed_local_datetime: Any,
    proposed_timezone: str,
    reason: str,
    fold: int | None,
    row_version: int | None = None,
) -> str:
    schedule = db.get(PublishingSchedule, activity.schedule_id) if activity.schedule_id else None
    job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    artifact = db.get(GeneratedArtifact, activity.artifact_id) if activity.artifact_id else None
    destination = (
        db.get(PublishingDestination, activity.destination_id) if activity.destination_id else None
    )
    payload = {
        "owner": str(owner_id),
        "campaign": str(campaign.id),
        "campaign_status": campaign.status,
        "activity": str(activity.id),
        "row_version": activity.row_version if row_version is None else row_version,
        "local": proposed_local_datetime.isoformat(),
        "timezone": proposed_timezone,
        "reason": reason.strip(),
        "fold": fold,
        "schedule_id": str(activity.schedule_id) if activity.schedule_id else None,
        "schedule_enabled": schedule.enabled if schedule else None,
        "schedule_archived": schedule.archived if schedule else None,
        "job_id": str(activity.job_id) if activity.job_id else None,
        "job_state": job.state if job else None,
        "job_lease_owner": job.lease_owner if job else None,
        "job_lease_expires_at": job.lease_expires_at.isoformat()
        if job and job.lease_expires_at
        else None,
        "artifact_id": str(activity.artifact_id) if activity.artifact_id else None,
        "artifact_version": activity.artifact_version,
        "artifact_status": artifact.status if artifact else None,
        "destination_id": str(activity.destination_id) if activity.destination_id else None,
        "destination_status": destination.status if destination else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class CampaignRecoveryExecutionContext:
    db: Any
    owner: Any
    campaign: Campaign
    activity: CampaignActivity | None
    workflow_wait: Any | None
    correlation_id: str
    now_utc: Any
    maintenance_mode: bool
    action: RecoveryActionSpec
    dispatch: Callable[[str, CampaignRecoveryRequest], CampaignRecoveryResult]


class CampaignRecoveryExecutor(Protocol):
    def __call__(
        self,
        context: CampaignRecoveryExecutionContext,
        request: CampaignRecoveryRequest,
    ) -> CampaignRecoveryResult: ...


class CampaignRecoveryNavigationResolver(Protocol):
    def __call__(
        self,
        context: CampaignRecoveryExecutionContext,
        request: CampaignRecoveryRequest,
    ) -> CampaignRecoveryResult: ...


class _RegisteredCallable:
    """Typed registry handle; the router supplies the validated dispatch context."""

    def __init__(self, key: str) -> None:
        self.key = key

    def __call__(
        self,
        context: CampaignRecoveryExecutionContext,
        request: CampaignRecoveryRequest,
    ) -> CampaignRecoveryResult:
        return context.dispatch(self.key, request)


def _open_campaign_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_campaign

    return resolve_open_campaign(context, request)


def _replace_activity_handler(
    context: CampaignRecoveryExecutionContext, request: CampaignRecoveryRequest
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_replace_with_new_approved_activity

    return execute_replace_with_new_approved_activity(context, request)


def _release_checkpoint_handler(
    context: CampaignRecoveryExecutionContext, request: CampaignRecoveryRequest
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_release_checkpoint

    return execute_release_checkpoint(context, request)


def _reschedule_activity_handler(
    context: CampaignRecoveryExecutionContext, request: CampaignRecoveryRequest
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_reschedule_activity

    return execute_reschedule_activity(context, request)


def _pause_campaign_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_pause_campaign

    return execute_pause_campaign(context, request)


def _open_activity_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_activity

    return resolve_open_activity(context, request)


def _resume_campaign_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_resume_campaign

    return execute_resume_campaign(context, request)


def _open_product_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_product

    return resolve_open_product(context, request)


def _cancel_activity_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_cancel_activity

    return execute_cancel_activity(context, request)


def _open_artifact_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_artifact

    return resolve_open_artifact(context, request)


def _open_destination_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_destination

    return resolve_open_destination(context, request)


def _open_job_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_job

    return resolve_open_job(context, request)


def _open_execution_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_open_publishing_execution

    return resolve_open_publishing_execution(context, request)


def _review_dependency_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import resolve_review_dependency

    return resolve_review_dependency(context, request)


def _cancel_campaign_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_cancel_campaign

    return execute_cancel_campaign(context, request)


def _retry_wait_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import (
        execute_retry_campaign_workflow_wait,
    )

    return execute_retry_campaign_workflow_wait(context, request)


def _skip_optional_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_skip_optional_activity

    return execute_skip_optional_activity(context, request)


def _skip_missed_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_skip_missed_activity

    return execute_skip_missed_activity(context, request)


def _catch_up_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_create_one_catch_up

    return execute_create_one_catch_up(context, request)


def _retry_activity_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_retry_activity

    return execute_retry_activity(context, request)


def _reconcile_activity_handler(
    context: CampaignRecoveryExecutionContext,
    request: CampaignRecoveryRequest,
) -> CampaignRecoveryResult:
    from vayujit_api.campaigns.recovery_executors import execute_reconcile_activity

    return execute_reconcile_activity(context, request)


@dataclass(frozen=True)
class RecoveryActionSpec:
    key: str
    label: str
    classification: Literal["mutating", "navigation_only", "informational"]
    permission: str
    request_contract: str
    result_contract: str
    eligibility_evaluator: Callable[..., list[RecoveryDecision]]
    executor: CampaignRecoveryExecutor | None
    navigation_resolver: CampaignRecoveryNavigationResolver | None
    confirmation_required: bool
    idempotency: str
    audit_event: str
    safe_success_message: str
    safe_failure_behavior: str
    implementation_status: Literal["implemented", "unsupported"] = "implemented"


def _spec(
    key: str,
    label: str,
    classification: Literal["mutating", "navigation_only", "informational"],
    *,
    executor: CampaignRecoveryExecutor | None = None,
    resolver: CampaignRecoveryNavigationResolver | None = None,
    implementation_status: Literal["implemented", "unsupported"] = "implemented",
    audit: str = "campaign.recovery_action_executed",
) -> RecoveryActionSpec:
    return RecoveryActionSpec(
        key=key,
        label=label,
        classification=classification,
        permission="campaign:operate",
        request_contract="CampaignRecoveryActionRequest",
        result_contract="CampaignRecoveryActionResult",
        eligibility_evaluator=_eligibility_dispatch,
        executor=executor if classification == "mutating" else None,
        navigation_resolver=(
            None if classification == "mutating" else (resolver or _RegisteredCallable(key))
        ),
        confirmation_required=classification == "mutating",
        idempotency="reuse_existing_logical_result",
        audit_event=audit,
        safe_success_message=f"{label} completed.",
        safe_failure_behavior="reject_with_safe_reason_code",
        implementation_status=implementation_status,
    )


def _eligibility_dispatch(*args: Any, **kwargs: Any) -> list[RecoveryDecision]:
    """Late-bound registry hook so specs can be created before policy definition."""
    return recovery_eligibility(*args, **kwargs)


_MUTATING = {
    "retry_activity": "retry_activity",
    "reconcile_activity": "reconcile_activity",
    "replace_with_new_approved_activity": "replace_activity",
    "release_checkpoint": "release_checkpoint",
    "reschedule_activity": "reschedule_activity",
    "create_one_catch_up": "create_one_catch_up",
    "skip_optional_activity": "skip_optional_activity",
    "skip_missed_activity": "skip_missed_activity",
    "pause_campaign": "pause_campaign",
    "resume_campaign": "resume_campaign",
    "cancel_activity": "cancel_activity",
    "cancel_campaign": "cancel_campaign",
    "retry_campaign_workflow_wait": "retry_campaign_workflow_wait",
}
_NAVIGATION = {
    "open_campaign": "Open Campaign",
    "open_activity": "Open Activity",
    "open_product": "Open Product",
    "open_artifact": "Open Artifact",
    "open_destination": "Open Destination",
    "open_job": "Open Publishing Job",
    "open_publishing_execution": "Open Publishing Execution",
    "review_dependency": "Review Dependency",
}

RECOVERY_ACTION_REGISTRY = MappingProxyType(
    {
        **{
            key: _spec(
                key,
                key.replace("_", " ").title(),
                "mutating",
                executor=(
                    None
                    if key == "create_one_catch_up"
                    else _pause_campaign_handler
                    if key == "pause_campaign"
                    else _retry_activity_handler
                    if key == "retry_activity"
                    else _reconcile_activity_handler
                    if key == "reconcile_activity"
                    else _replace_activity_handler
                    if key == "replace_with_new_approved_activity"
                    else _release_checkpoint_handler
                    if key == "release_checkpoint"
                    else _reschedule_activity_handler
                    if key == "reschedule_activity"
                    else _resume_campaign_handler
                    if key == "resume_campaign"
                    else _cancel_activity_handler
                    if key == "cancel_activity"
                    else _cancel_campaign_handler
                    if key == "cancel_campaign"
                    else _retry_wait_handler
                    if key == "retry_campaign_workflow_wait"
                    else _skip_optional_handler
                    if key == "skip_optional_activity"
                    else _skip_missed_handler
                    if key == "skip_missed_activity"
                    else _catch_up_handler
                    if key == "create_one_catch_up"
                    else _RegisteredCallable(executor)
                ),
                audit=(
                    "campaign.activity_reconciled"
                    if key == "reconcile_activity"
                    else "campaign.recovery_action_executed"
                ),
                implementation_status=(
                    "unsupported" if key == "create_one_catch_up" else "implemented"
                ),
            )
            for key, executor in _MUTATING.items()
        },
        **{
            key: _spec(
                key,
                label,
                "navigation_only",
                resolver=(
                    _open_campaign_handler
                    if key == "open_campaign"
                    else _open_activity_handler
                    if key == "open_activity"
                    else _open_product_handler
                    if key == "open_product"
                    else _open_artifact_handler
                    if key == "open_artifact"
                    else _open_destination_handler
                    if key == "open_destination"
                    else _open_job_handler
                    if key == "open_job"
                    else _open_execution_handler
                    if key == "open_publishing_execution"
                    else _review_dependency_handler
                    if key == "review_dependency"
                    else None
                ),
            )
            for key, label in _NAVIGATION.items()
        },
    }
)


def _decision(
    action: str,
    eligible: bool,
    reason_code: str,
    explanation: str,
    *,
    confirmation: bool = False,
    target: str | None = None,
) -> RecoveryDecision:
    return RecoveryDecision(
        action=action,
        eligible=eligible,
        reason_code=reason_code,
        explanation=explanation,
        confirmation_required=confirmation,
        navigation_target=target,
    )


def recovery_eligibility(
    campaign: Campaign | None,
    activity: CampaignActivity,
) -> list[RecoveryDecision]:
    """Return every Activity-scoped action with an explicit safe reason."""
    campaign_id = str(getattr(activity, "campaign_id", ""))
    activity_id = str(getattr(activity, "id", ""))
    terminal = activity.status in {"succeeded", "skipped", "cancelled", "archived"}
    missed = activity.status == "missed"
    decisions = [
        _decision(
            "open_campaign",
            True,
            "navigation_available",
            "Open the owning Campaign.",
            target=f"/campaigns/{campaign_id}",
        ),
        _decision(
            "open_activity",
            True,
            "navigation_available",
            "Open the Campaign Activity.",
            target=f"/campaigns/{campaign_id}?activity={activity_id}",
        ),
        _decision(
            "open_product",
            activity.product_id is not None,
            "navigation_available" if activity.product_id else "product_unavailable",
            "Open the selected Product." if activity.product_id else "No Product is linked.",
            target=f"/products/{activity.product_id}" if activity.product_id else None,
        ),
        _decision(
            "open_artifact",
            activity.artifact_id is not None,
            "navigation_available" if activity.artifact_id else "artifact_unavailable",
            (
                "Open the exact Artifact version."
                if activity.artifact_id
                else "No Artifact is linked."
            ),
            target=f"/ai/artifacts/{activity.artifact_id}" if activity.artifact_id else None,
        ),
        _decision(
            "open_destination",
            activity.destination_id is not None,
            "navigation_available" if activity.destination_id else "destination_unavailable",
            (
                "Open the Publishing destination."
                if activity.destination_id
                else "No destination is linked."
            ),
            target=(
                f"/publishing/destinations/{activity.destination_id}"
                if activity.destination_id
                else None
            ),
        ),
        _decision(
            "open_job",
            activity.job_id is not None,
            "navigation_available" if activity.job_id else "job_unavailable",
            "Open the durable Publishing job." if activity.job_id else "No job is linked.",
            target=f"/publishing/jobs/{activity.job_id}" if activity.job_id else None,
        ),
        _decision(
            "open_publishing_execution",
            activity.publishing_execution_id is not None,
            (
                "navigation_available"
                if activity.publishing_execution_id
                else "execution_unavailable"
            ),
            (
                "Open the Publishing execution."
                if activity.publishing_execution_id
                else "No Publishing execution is linked."
            ),
            target=(
                f"/publishing/executions/{activity.publishing_execution_id}"
                if activity.publishing_execution_id
                else None
            ),
        ),
        _decision(
            "retry_activity",
            activity.status in {"failed", "dead_letter"},
            (
                "activity_retryable"
                if activity.status in {"failed", "dead_letter"}
                else "activity_not_failed"
            ),
            (
                "Retry this failed Activity."
                if activity.status in {"failed", "dead_letter"}
                else "Only failed Activities can be retried."
            ),
            confirmation=True,
        ),
        _decision(
            "reconcile_activity",
            activity.status in {"reconciliation_required", "succeeded"}
            and activity.publishing_execution_id is not None
            and activity.job_id is not None,
            (
                "remote_result_ambiguous"
                if activity.status in {"reconciliation_required", "succeeded"}
                and activity.publishing_execution_id
                and activity.job_id
                else "reconciliation_not_required"
            ),
            (
                "Reconcile the existing remote result."
                if activity.status in {"reconciliation_required", "succeeded"}
                and activity.publishing_execution_id
                and activity.job_id
                else "The Activity has no ambiguous remote execution."
            ),
            confirmation=True,
        ),
        _decision(
            "skip_optional_activity",
            not activity.required and not terminal,
            (
                "optional_activity"
                if not activity.required and not terminal
                else "required_or_terminal"
            ),
            (
                "Skip this optional Activity."
                if not activity.required and not terminal
                else "Required or terminal Activities cannot be skipped."
            ),
            confirmation=True,
        ),
        _decision(
            "skip_missed_activity",
            missed and not activity.required,
            "optional_missed" if missed and not activity.required else "not_optional_missed",
            (
                "Resolve this optional missed Activity as skipped."
                if missed and not activity.required
                else "Only optional missed Activities can be skipped."
            ),
            confirmation=True,
        ),
        _decision(
            "reschedule_activity",
            missed,
            "activity_missed" if missed else "activity_not_missed",
            (
                "Create a replacement schedule occurrence."
                if missed
                else "Only missed Activities can be rescheduled."
            ),
            confirmation=True,
        ),
        _decision(
            "create_one_catch_up",
            missed,
            "activity_missed" if missed else "activity_not_missed",
            (
                "Create or reuse one catch-up Activity."
                if missed
                else "Catch-up is available only for missed Activities."
            ),
            confirmation=True,
        ),
        _decision(
            "cancel_activity",
            not terminal,
            "activity_non_terminal" if not terminal else "activity_terminal",
            (
                "Cancel this non-terminal Activity."
                if not terminal
                else "Terminal Activities cannot be cancelled."
            ),
            confirmation=True,
        ),
        _decision(
            "replace_with_new_approved_activity",
            activity.status in {"blocked", "failed", "dead_letter", "missed"},
            (
                "activity_replacement_allowed"
                if activity.status in {"blocked", "failed", "dead_letter", "missed"}
                else "activity_replacement_not_allowed"
            ),
            (
                "Replace this Activity with an exact approved Artifact."
                if activity.status in {"blocked", "failed", "dead_letter", "missed"}
                else "The current Activity state does not permit replacement."
            ),
            confirmation=True,
        ),
        _decision(
            "review_dependency",
            True,
            "dependency_diagnostics_available",
            "Review dependency state without mutating it.",
            target=f"/campaigns/{campaign_id}?activity={activity_id}&panel=dependencies",
        ),
        _decision(
            "release_checkpoint",
            getattr(activity, "activity_type", None) in {"review_checkpoint", "approval_checkpoint"}
            and not terminal,
            (
                "checkpoint_releasable"
                if getattr(activity, "activity_type", None)
                in {"review_checkpoint", "approval_checkpoint"}
                and not terminal
                else "activity_not_releasable_checkpoint"
            ),
            (
                "Release this manual checkpoint."
                if getattr(activity, "activity_type", None)
                in {"review_checkpoint", "approval_checkpoint"}
                and not terminal
                else "This Activity is not a releasable checkpoint."
            ),
            confirmation=True,
        ),
    ]
    if campaign is not None:
        decisions.extend(
            [
                _decision(
                    "pause_campaign",
                    campaign.status in {"scheduled", "running"},
                    (
                        "campaign_active"
                        if campaign.status in {"scheduled", "running"}
                        else "campaign_not_active"
                    ),
                    "Pause this Campaign.",
                    confirmation=True,
                ),
                _decision(
                    "resume_campaign",
                    campaign.status == "paused",
                    "campaign_paused" if campaign.status == "paused" else "campaign_not_paused",
                    "Resume this paused Campaign.",
                    confirmation=True,
                ),
                _decision(
                    "cancel_campaign",
                    campaign.status not in {"completed", "cancelled", "archived"},
                    (
                        "campaign_non_terminal"
                        if campaign.status not in {"completed", "cancelled", "archived"}
                        else "campaign_terminal"
                    ),
                    "Cancel this non-terminal Campaign.",
                    confirmation=True,
                ),
                _decision(
                    "retry_campaign_workflow_wait",
                    campaign.status not in {"completed", "cancelled", "archived"},
                    "campaign_wait_retryable",
                    "Retry restoration of the existing Campaign Workflow wait.",
                    confirmation=True,
                ),
            ]
        )
    return decisions


def eligible_recovery_actions(
    activity: CampaignActivity, campaign: Campaign | None = None
) -> list[str]:
    return [
        decision.action
        for decision in recovery_eligibility(campaign, activity)
        if decision.eligible
        and RECOVERY_ACTION_REGISTRY[decision.action].implementation_status == "implemented"
    ]
