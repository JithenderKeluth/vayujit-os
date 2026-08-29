"""Durable, bounded website refresh scheduling and execution."""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.website_models import (
    WebsiteRefreshJob,
    WebsiteRefreshRecovery,
    WebsiteSourceProfile,
)
from vayujit_api.intelligence.website_service import run_website_mission

REFRESH_POLICIES = {"MANUAL", "DAILY", "WEEKLY", "MONTHLY"}
REFRESH_TARGET_TYPES = {
    "WEBSITE_SOURCE",
    "MANUFACTURER_CANDIDATE",
    "SUPPLIER_WEBSITE_CANDIDATE",
    "CERTIFICATION_REVIEW",
    "PRICE_RECHECK",
    "MOQ_RECHECK",
    "LEAD_TIME_RECHECK",
    "AVAILABILITY_RECHECK",
}


def _now() -> datetime:
    return datetime.now(UTC)


def next_refresh(value: datetime, policy: str, timezone: str = "UTC") -> datetime | None:
    normalized = policy.upper()
    if normalized == "MANUAL":
        return None
    local = value if value.tzinfo else value.replace(tzinfo=UTC)
    local = local.astimezone(ZoneInfo(timezone))
    if normalized == "DAILY":
        target = local + timedelta(days=1)
    elif normalized == "WEEKLY":
        target = local + timedelta(days=7)
    elif normalized == "MONTHLY":
        year = local.year + (1 if local.month == 12 else 0)
        month = 1 if local.month == 12 else local.month + 1
        target = local.replace(
            year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1])
        )
    else:
        return None
    return target.astimezone(UTC)


def schedule_profile_refresh(
    db: Session,
    owner: User,
    profile: WebsiteSourceProfile,
    *,
    policy: str,
    timezone: str = "UTC",
    next_refresh_at: datetime | None = None,
    target_type: str = "WEBSITE_SOURCE",
) -> WebsiteSourceProfile:
    normalized = policy.upper()
    if normalized not in REFRESH_POLICIES:
        raise HTTPException(422, "Unsupported website refresh policy.")
    try:
        ZoneInfo(timezone)
    except Exception as exc:
        raise HTTPException(422, "Invalid website refresh timezone.") from exc
    if profile.owner_id != owner.id:
        raise HTTPException(404, "Website source profile not found.")
    if target_type not in REFRESH_TARGET_TYPES:
        raise HTTPException(422, "Unsupported website refresh target type.")
    profile.freshness_policy = normalized
    profile.refresh_target_type = target_type
    profile.timezone = timezone
    profile.next_refresh_at = None if normalized == "MANUAL" else (next_refresh_at or _now())
    profile.version += 1
    db.commit()
    db.refresh(profile)
    return profile


def materialize_due_refreshes(
    db: Session, owner: User, *, at: datetime | None = None, limit: int = 50
) -> list[WebsiteRefreshJob]:
    due = at or _now()
    profiles = list(
        db.scalars(
            select(WebsiteSourceProfile)
            .where(
                WebsiteSourceProfile.owner_id == owner.id,
                WebsiteSourceProfile.enabled.is_(True),
                WebsiteSourceProfile.freshness_policy != "MANUAL",
                WebsiteSourceProfile.next_refresh_at.is_not(None),
                WebsiteSourceProfile.next_refresh_at <= due,
            )
            .order_by(WebsiteSourceProfile.next_refresh_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    jobs: list[WebsiteRefreshJob] = []
    for profile in profiles:
        scheduled_for = profile.next_refresh_at
        if scheduled_for is None:
            continue
        identity = f"website-refresh:{profile.id}:{scheduled_for.isoformat()}"
        existing = db.scalar(
            select(WebsiteRefreshJob).where(
                WebsiteRefreshJob.owner_id == owner.id,
                WebsiteRefreshJob.source_profile_id == profile.id,
                WebsiteRefreshJob.scheduled_for == scheduled_for,
            )
        )
        if existing is not None:
            jobs.append(existing)
            continue
        job = WebsiteRefreshJob(
            owner_id=owner.id,
            source_profile_id=profile.id,
            target_type=profile.refresh_target_type,
            scheduled_for=scheduled_for,
            timezone=profile.timezone,
            policy_version=profile.version,
            correlation_id=str(uuid.uuid4()),
            idempotency_key=identity,
            status="QUEUED",
            created_at=_now(),
        )
        try:
            with db.begin_nested():
                db.add(job)
                db.flush()
        except IntegrityError:
            existing = db.scalar(
                select(WebsiteRefreshJob).where(
                    WebsiteRefreshJob.owner_id == owner.id,
                    WebsiteRefreshJob.source_profile_id == profile.id,
                    WebsiteRefreshJob.scheduled_for == scheduled_for,
                )
            )
            if existing is not None:
                jobs.append(existing)
            continue
        profile.next_refresh_at = next_refresh(
            scheduled_for, profile.freshness_policy, profile.timezone
        )
        record_event(
            db,
            actor_id=owner.id,
            action="website.refresh.materialized",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"source_profile_id": str(profile.id), "target_type": job.target_type},
            idempotency_key=identity,
        )
        jobs.append(job)
    db.commit()
    return jobs


def execute_refresh_job(
    db: Session,
    owner: User,
    job: WebsiteRefreshJob,
    *,
    content: str | None = None,
    worker_id: str | None = None,
) -> WebsiteRefreshJob:
    if job.owner_id != owner.id:
        raise HTTPException(404, "Website refresh job not found.")
    profile = db.scalar(
        select(WebsiteSourceProfile).where(
            WebsiteSourceProfile.id == job.source_profile_id,
            WebsiteSourceProfile.owner_id == owner.id,
        )
    )
    if profile is None:
        raise HTTPException(404, "Website source profile not found.")
    if job.status in {"SUCCEEDED", "SKIPPED"}:
        return job
    if job.status == "RUNNING" and job.lease_owner != worker_id:
        raise HTTPException(409, "Website refresh job is already running.")
    if profile.classification.upper() in {"BLOCKED", "REVIEW_REQUIRED"}:
        job.status = "SKIPPED"
        job.failure_code = "domain_policy_blocked"
        job.completed_at = _now()
        profile.last_failure_at = job.completed_at
        profile.refresh_failure_code = job.failure_code
        record_event(
            db,
            actor_id=owner.id,
            action="website.refresh.skipped",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"reason": job.failure_code},
            idempotency_key=f"refresh:skipped:{job.id}",
        )
        db.commit()
        return job
    settings = get_settings()
    if settings.external_mutations_emergency_stop or not settings.intelligence_enabled:
        job.status = "SKIPPED"
        job.failure_code = "intelligence_disabled"
        job.completed_at = _now()
        profile.last_failure_at = job.completed_at
        profile.refresh_failure_code = job.failure_code
        record_event(
            db,
            actor_id=owner.id,
            action="website.refresh.skipped",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"reason": job.failure_code},
            idempotency_key=f"refresh:skipped:{job.id}",
        )
        db.commit()
        return job
    if not profile.enabled:
        job.status = "SKIPPED"
        job.failure_code = "source_disabled"
        job.completed_at = _now()
        profile.last_failure_at = job.completed_at
        record_event(
            db,
            actor_id=owner.id,
            action="website.refresh.skipped",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"reason": job.failure_code},
            idempotency_key=f"refresh:skipped:{job.id}",
        )
        db.commit()
        return job
    job.status = "RUNNING"
    job.started_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action="website.refresh.started",
        entity_type="website_refresh_job",
        entity_id=job.id,
        metadata={"source_profile_id": str(profile.id)},
        idempotency_key=f"refresh:started:{job.id}",
    )
    try:
        result = run_website_mission(
            db,
            owner,
            url=f"https://{profile.domain}",
            content=content
            or f"Company Name: {profile.display_name}. Website refresh for {profile.domain}.",
            source_type=profile.source_type,
            idempotency_key=job.idempotency_key,
        )
        job.mission_id = uuid.UUID(str(result["mission_id"]))
        job.status = "SUCCEEDED"
        profile.last_refresh_at = profile.last_success_at = _now()
        profile.last_failure_at = None
        profile.refresh_failure_code = None
        record_event(
            db,
            actor_id=owner.id,
            action="website.refresh.completed",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"mission_id": str(job.mission_id)},
            idempotency_key=f"refresh:completed:{job.id}",
        )
    except Exception:
        job.status = "FAILED"
        job.failure_code = "refresh_failed"
        profile.last_refresh_at = _now()
        profile.last_failure_at = profile.last_refresh_at
        profile.refresh_failure_code = job.failure_code
        record_event(
            db,
            actor_id=owner.id,
            action="website.refresh.failed",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"failure_code": job.failure_code},
            idempotency_key=f"refresh:failed:{job.id}",
        )
        db.commit()
        raise
    job.completed_at = _now()
    db.commit()
    return job


REFRESH_RECOVERY_FAILURES = {
    "SOURCE_DISABLED": {"skip_optional_source", "cancel"},
    "DOMAIN_BLOCKED": {"review_source", "skip_optional_source", "cancel"},
    "DOMAIN_REVIEW_REQUIRED": {"review_source", "skip_optional_source", "cancel"},
    "GLOBAL_EXTERNAL_DISABLED": {"retry_after", "review_source", "cancel"},
    "FETCH_DISABLED": {"review_source", "retry_after", "cancel"},
    "BUDGET_EXHAUSTED": {"retry_after", "cancel"},
    "RATE_LIMITED": {"retry_after", "cancel"},
    "TIMEOUT": {"retry", "retry_after", "cancel"},
    "NETWORK_FAILURE": {"retry", "retry_after", "cancel"},
    "PROVIDER_5XX": {"retry", "retry_after", "cancel"},
    "VERIFICATION_FAILED": {"review_source", "retry", "cancel"},
    "CHECKPOINT_INVALID": {"reconcile", "cancel"},
}


def recover_expired_refresh_leases(db: Session) -> int:
    timestamp = _now()
    jobs = list(
        db.scalars(
            select(WebsiteRefreshJob)
            .where(
                WebsiteRefreshJob.status == "RUNNING",
                WebsiteRefreshJob.lease_expires_at.is_not(None),
                WebsiteRefreshJob.lease_expires_at < timestamp,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for job in jobs:
        job.status = "QUEUED"
        job.lease_owner = None
        job.lease_expires_at = None
        job.failure_code = "lease_expired"
        record_event(
            db,
            actor_id=job.owner_id,
            action="website.refresh.lease_recovered",
            entity_type="website_refresh_job",
            entity_id=job.id,
            metadata={"failure_code": job.failure_code},
            idempotency_key=f"website-refresh:lease-recovered:{job.id}:{job.claim_count}",
        )
    db.commit()
    return len(jobs)


def claim_refresh_jobs(
    db: Session, worker_id: str, limit: int = 1, lease_seconds: int = 60
) -> list[uuid.UUID]:
    timestamp = _now()
    jobs = list(
        db.scalars(
            select(WebsiteRefreshJob)
            .where(
                WebsiteRefreshJob.status == "QUEUED",
                or_(
                    WebsiteRefreshJob.lease_expires_at.is_(None),
                    WebsiteRefreshJob.lease_expires_at < timestamp,
                ),
            )
            .order_by(WebsiteRefreshJob.scheduled_for)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for job in jobs:
        job.status = "RUNNING"
        job.lease_owner = worker_id
        job.lease_expires_at = timestamp + timedelta(seconds=lease_seconds)
        job.claim_count += 1
        job.started_at = timestamp
    db.commit()
    return [job.id for job in jobs]


def run_refresh_jobs_once(
    db: Session, worker_id: str, limit: int = 1, lease_seconds: int = 60
) -> int:
    claimed = claim_refresh_jobs(db, worker_id, limit, lease_seconds)
    for job_id in claimed:
        job = db.get(WebsiteRefreshJob, job_id)
        if job is None:
            continue
        owner = db.get(User, job.owner_id)
        if owner is None:
            continue
        try:
            execute_refresh_job(db, owner, job, worker_id=worker_id)
        except Exception:
            db.rollback()
        finally:
            current = db.get(WebsiteRefreshJob, job_id)
            if current is not None:
                current.lease_owner = None
                current.lease_expires_at = None
                if current.status == "RUNNING":
                    current.status = "FAILED"
                    current.failure_code = "refresh_failed"
                db.commit()
    return len(claimed)


def recover_refresh_job(
    db: Session,
    owner: User,
    job: WebsiteRefreshJob,
    *,
    action: str,
    failure_code: str,
    idempotency_key: str,
    correlation_id: str,
) -> dict[str, object]:
    normalized = failure_code.upper()
    allowed = REFRESH_RECOVERY_FAILURES.get(normalized)
    if allowed is None or action not in allowed:
        raise HTTPException(422, "Recovery action is not allowed for this refresh failure.")
    if job.owner_id != owner.id:
        raise HTTPException(404, "Website refresh job not found.")
    existing = db.scalar(
        select(WebsiteRefreshRecovery).where(
            WebsiteRefreshRecovery.owner_id == owner.id,
            WebsiteRefreshRecovery.job_id == job.id,
            WebsiteRefreshRecovery.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return {
            "status": existing.status,
            "action": existing.action,
            "idempotent_reuse": True,
            "safe_reason_code": existing.safe_reason_code,
        }
    if action in {"retry", "retry_after", "reconcile"}:
        job.status = "QUEUED"
        job.failure_code = None
    elif action == "cancel":
        job.status = "CANCELLED"
    else:
        job.status = "SKIPPED"
    row = WebsiteRefreshRecovery(
        owner_id=owner.id,
        job_id=job.id,
        action=action,
        failure_code=normalized,
        status="COMPLETED",
        safe_reason_code=f"WEBSITE_REFRESH_{normalized}",
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(WebsiteRefreshRecovery).where(
                WebsiteRefreshRecovery.owner_id == owner.id,
                WebsiteRefreshRecovery.job_id == job.id,
                WebsiteRefreshRecovery.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return {
                "status": existing.status,
                "action": existing.action,
                "idempotent_reuse": True,
                "safe_reason_code": existing.safe_reason_code,
            }
        raise
    record_event(
        db,
        actor_id=owner.id,
        action="website.refresh.recovery.executed",
        entity_type="website_refresh_job",
        entity_id=job.id,
        metadata={"action": action, "failure_code": normalized},
        idempotency_key=f"website-refresh-recovery:{idempotency_key}",
    )
    db.commit()
    return {
        "status": row.status,
        "action": row.action,
        "idempotent_reuse": False,
        "safe_reason_code": row.safe_reason_code,
    }
