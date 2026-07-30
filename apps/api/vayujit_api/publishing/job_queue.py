"""PostgreSQL-backed publishing queue with short, lease-based claim transactions."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.publishing.models import (
    PublishingExecution,
    PublishingJob,
    PublishingJobAttempt,
    PublishingRecoveryRecord,
    PublishingWorkerHeartbeat,
)
from vayujit_api.publishing.scheduler_time import utcnow

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "expired", "dead_letter"}
CLAIMABLE_STATES = {"pending", "scheduled", "retry_wait"}


def retry_delay(attempt: int, *, jitter: bool = True) -> int:
    base = min(30 * (2 ** max(attempt - 1, 0)), 3600)
    return base + (random.randint(0, max(base // 4, 1)) if jitter else 0)


def claim_jobs(
    db: Session,
    worker_id: str,
    limit: int,
    lease_seconds: int,
    *,
    maintenance_mode: bool = False,
) -> list[uuid.UUID]:
    timestamp = utcnow()
    if maintenance_mode:
        blocked = list(
            db.scalars(
                select(PublishingJob).where(
                    PublishingJob.state.in_(CLAIMABLE_STATES),
                    PublishingJob.available_at_utc <= timestamp,
                    PublishingJob.maintenance_blocked_at.is_(None),
                )
            )
        )
        for job in blocked:
            job.maintenance_blocked_at = timestamp
            job.updated_at = timestamp
            record_event(
                db,
                actor_id=job.owner_id,
                action="publishing.scheduler_maintenance_blocked",
                entity_type="publishing_job",
                entity_id=job.id,
            )
        db.commit()
        return []
    jobs = list(
        db.scalars(
            select(PublishingJob)
            .where(
                PublishingJob.state.in_(CLAIMABLE_STATES),
                PublishingJob.available_at_utc <= timestamp,
                or_(
                    PublishingJob.lease_expires_at.is_(None),
                    PublishingJob.lease_expires_at < timestamp,
                ),
            )
            .order_by(
                PublishingJob.priority.desc(),
                PublishingJob.available_at_utc,
                PublishingJob.created_at,
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for job in jobs:
        job.state = "claimed"
        job.lease_owner = worker_id
        job.claimed_at = timestamp
        job.heartbeat_at = timestamp
        job.lease_expires_at = timestamp + timedelta(seconds=lease_seconds)
        job.claim_count += 1
        job.row_version += 1
        job.updated_at = timestamp
        job.maintenance_blocked_at = None
    db.commit()
    return [job.id for job in jobs]


def start_attempt(db: Session, job_id: uuid.UUID, worker_id: str) -> PublishingJobAttempt | None:
    timestamp = utcnow()
    job = db.scalar(select(PublishingJob).where(PublishingJob.id == job_id).with_for_update())
    if not job or job.lease_owner != worker_id or job.state not in {"claimed", "cancel_requested"}:
        db.rollback()
        return None
    if job.state == "cancel_requested":
        job.state = "cancelled"
        job.completed_at = timestamp
        db.commit()
        return None
    job.state = "running"
    job.started_at = timestamp
    job.execution_attempt_count += 1
    job.row_version += 1
    attempt = PublishingJobAttempt(
        job_id=job.id,
        attempt_number=job.execution_attempt_count,
        worker_id=worker_id,
        started_at=timestamp,
        outcome="running",
        retryable=False,
        correlation_id=job.correlation_id,
        created_at=timestamp,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def renew_lease(db: Session, job_id: uuid.UUID, worker_id: str, lease_seconds: int) -> bool:
    timestamp = utcnow()
    job = db.scalar(select(PublishingJob).where(PublishingJob.id == job_id).with_for_update())
    if not job or job.lease_owner != worker_id or job.state not in {"claimed", "running"}:
        db.rollback()
        return False
    job.heartbeat_at = timestamp
    job.lease_expires_at = timestamp + timedelta(seconds=lease_seconds)
    job.updated_at = timestamp
    db.commit()
    return True


def finish_job(
    db: Session,
    job_id: uuid.UUID,
    worker_id: str,
    *,
    succeeded: bool,
    connector_execution_id: uuid.UUID | None = None,
    retryable: bool = False,
    error_code: str | None = None,
    safe_error_message: str | None = None,
) -> str:
    timestamp = utcnow()
    job = db.scalar(select(PublishingJob).where(PublishingJob.id == job_id).with_for_update())
    if not job or job.lease_owner != worker_id:
        db.rollback()
        return "lease_lost"
    attempt = db.scalar(
        select(PublishingJobAttempt)
        .where(PublishingJobAttempt.job_id == job_id)
        .order_by(PublishingJobAttempt.attempt_number.desc())
        .with_for_update()
    )
    cancelled = job.state == "cancel_requested"
    exhausted = job.execution_attempt_count >= job.max_execution_attempts
    if cancelled:
        state, outcome = "cancelled", "cancelled"
    elif succeeded:
        state, outcome = "succeeded", "succeeded"
    elif retryable and not exhausted:
        state, outcome = "retry_wait", "failed"
        delay = retry_delay(job.execution_attempt_count)
        job.available_at_utc = timestamp + timedelta(seconds=delay)
        job.next_retry_at = job.available_at_utc
        if attempt:
            attempt.delay_seconds = delay
    else:
        state, outcome = ("dead_letter" if exhausted else "failed"), "failed"
    job.state = state
    job.publishing_execution_id = connector_execution_id
    job.completed_at = timestamp if state in TERMINAL_STATES else None
    job.last_error_code = error_code
    job.last_error_message = safe_error_message
    job.retryable = retryable
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.updated_at = timestamp
    job.row_version += 1
    if attempt:
        attempt.completed_at = timestamp
        attempt.outcome = outcome
        attempt.retryable = retryable
        attempt.error_code = error_code
        attempt.safe_error_message = safe_error_message
        attempt.connector_execution_id = connector_execution_id
    db.commit()
    return state


def recover_expired_leases(db: Session) -> int:
    timestamp = utcnow()
    jobs = list(
        db.scalars(
            select(PublishingJob)
            .where(
                PublishingJob.state.in_({"claimed", "running", "cancel_requested"}),
                PublishingJob.lease_expires_at < timestamp,
            )
            .with_for_update(skip_locked=True)
        )
    )
    recovered = 0
    for job in jobs:
        worker = db.get(PublishingWorkerHeartbeat, job.lease_owner) if job.lease_owner else None
        if worker and worker.last_heartbeat_at >= timestamp - timedelta(minutes=2):
            continue
        attempt = db.scalar(
            select(PublishingJobAttempt)
            .where(
                PublishingJobAttempt.job_id == job.id,
                PublishingJobAttempt.outcome == "running",
            )
            .order_by(PublishingJobAttempt.attempt_number.desc())
            .with_for_update()
        )
        execution = (
            db.get(PublishingExecution, job.publishing_execution_id)
            if job.publishing_execution_id
            else db.scalar(
                select(PublishingExecution).where(
                    PublishingExecution.owner_id == job.owner_id,
                    PublishingExecution.idempotency_key == f"job:{job.id}",
                )
            )
        )
        if execution and not job.publishing_execution_id:
            job.publishing_execution_id = execution.id
        old_worker_id = job.lease_owner
        if attempt:
            attempt.outcome = "lease_lost"
            attempt.completed_at = timestamp
            attempt.retryable = True
            attempt.safe_error_message = "Worker lease expired; execution outcome may be ambiguous."
        if job.state == "cancel_requested":
            job.state = "cancelled"
            job.completed_at = timestamp
            result = "cancelled"
        elif execution and execution.status == "succeeded":
            job.state = "succeeded"
            job.completed_at = timestamp
            result = "remote_succeeded"
        elif execution and execution.status == "running":
            job.state = "failed"
            job.completed_at = timestamp
            job.recovery_state = "manual_review"
            job.recovery_reason = "Remote outcome is ambiguous after worker lease expiry."
            result = "manual_review"
        elif job.execution_attempt_count >= job.max_execution_attempts:
            job.state = "dead_letter"
            job.completed_at = timestamp
            result = "dead_letter"
        else:
            job.state = "retry_wait"
            job.available_at_utc = timestamp + timedelta(
                seconds=retry_delay(job.execution_attempt_count, jitter=False)
            )
            result = "retry_wait"
        job.last_error_code = (
            "remote_result_ambiguous" if result == "manual_review" else "worker_lease_expired"
        )
        job.last_error_message = (
            "Remote result requires operator reconciliation."
            if result == "manual_review"
            else "Worker lease expired; job was recovered safely."
        )
        job.retryable = job.state == "retry_wait"
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.updated_at = timestamp
        job.recovered_at = timestamp
        job.recovery_state = job.recovery_state or result
        job.recovery_reason = job.recovery_reason or job.last_error_message
        job.row_version += 1
        db.add(
            PublishingRecoveryRecord(
                owner_id=job.owner_id,
                job_id=job.id,
                worker_id=old_worker_id,
                publishing_execution_id=job.publishing_execution_id,
                result=result,
                reason_code=job.last_error_code,
                safe_message=job.last_error_message,
                correlation_id=job.correlation_id,
                created_at=timestamp,
            )
        )
        if worker:
            worker.stale_recoveries += 1
        record_event(
            db,
            actor_id=job.owner_id,
            action=(
                "publishing.job_recovery_requires_review"
                if result == "manual_review"
                else "publishing.worker_recovered_job"
            ),
            entity_type="publishing_job",
            entity_id=job.id,
            metadata={
                "result": result,
                "publishing_execution_id": (
                    str(job.publishing_execution_id) if job.publishing_execution_id else None
                ),
            },
        )
        recovered += 1
    db.commit()
    return recovered
