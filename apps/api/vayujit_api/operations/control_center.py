"""Server-authoritative Operations Control Center projections.

The control center deliberately composes existing health, scheduler, backup,
Recovery, provider, audit, and configuration services.  It never returns raw
provider payloads, credentials, database URLs, or private storage paths.
"""

from __future__ import annotations

import hashlib
import math
import platform
import shutil
import uuid
from datetime import timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api import __version__
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.core.observability import maintenance_enabled
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import storage_root
from vayujit_api.operations.backup import create_backup
from vayujit_api.operations.hardening import health_details
from vayujit_api.operations.models import BackupRecord
from vayujit_api.operations.staging import provider_metrics_snapshot, staging_configuration_errors
from vayujit_api.products.models import Product
from vayujit_api.publishing.job_queue import TERMINAL_STATES
from vayujit_api.publishing.models import (
    PublishingExecution,
    PublishingJob,
    PublishingJobAttempt,
    PublishingSchedule,
    PublishingWorkerHeartbeat,
)
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.scheduler_time import utcnow

router = APIRouter(prefix="/api/v1/operations", tags=["operations-control-center"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


class ConfirmationRequest(BaseModel):
    confirm: bool = False
    idempotency_key: str | None = Field(default=None, max_length=200)


def _safe_worker_id(value: str) -> str:
    return f"worker-{hashlib.sha256(value.encode()).hexdigest()[:12]}"


def _idempotency_lock(db: Session, key: str) -> None:
    """Serialize consequential retries on PostgreSQL without adding a table."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    lock_key = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") & ((1 << 63) - 1)
    db.execute(text("select pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def _prior_operation(
    db: Session, *, actor_id: uuid.UUID, action: str, idempotency_key: str
) -> AuditEvent | None:
    return db.scalar(
        select(AuditEvent).where(
            AuditEvent.actor_id == actor_id,
            AuditEvent.action == action,
            AuditEvent.metadata_json["idempotency_key"].as_string() == idempotency_key,
        )
    )


_storage_baselines: dict[str, dict[str, object]] = {}


def _migration_revision(db: Session) -> str:
    try:
        return str(db.scalar(text("select version_num from alembic_version")) or "unknown")
    except Exception:
        return "unavailable"


def _configuration_status() -> dict[str, object]:
    settings = get_settings()
    errors = staging_configuration_errors(settings)
    return {
        "environment": settings.environment,
        "status": "valid" if not errors else "invalid",
        "database": "configured" if settings.database_url else "missing",
        "encryption": "configured" if settings.credential_encryption_key else "missing",
        "sessions": "configured" if settings.session_secret else "missing",
        "origins": "configured" if settings.allowed_origin_set else "missing",
        "storage": (
            "configured"
            if settings.storage_provider == "filesystem" or settings.storage_bucket
            else "missing"
        ),
        "workers": "enabled" if settings.publishing_worker_enabled else "disabled",
        "scheduler": "enabled" if settings.publishing_worker_enabled else "disabled",
        "backups": "configured" if settings.backup_directory else "missing",
        "monitoring": "not_configured",
        "signing": "configuration_required",
        "errors": errors,
    }


def _provider_registry() -> list[dict[str, object]]:
    settings = get_settings()
    specs = [
        (
            "ai",
            "AI",
            settings.provider_runtime_mode,
            bool(settings.openai_api_key),
            settings.live_ai_enabled,
            ["content"],
        ),
        ("image", "AI Image", "fake", True, False, ["image_generation"]),
        ("video", "AI Video", "fake", True, False, ["video_generation"]),
        (
            "shopify",
            "Shopify",
            settings.shopify_mode,
            bool(settings.shopify_shop_domain and settings.shopify_admin_api_access_token),
            settings.live_marketplace_mutations_enabled,
            ["product", "variants", "media", "collections", "publications"],
        ),
        ("amazon", "Amazon", "fake", False, False, []),
        ("flipkart", "Flipkart", "fake", False, False, []),
        ("meesho", "Meesho", "fake", False, False, []),
        ("youtube", "YouTube", "fake", False, False, []),
        ("instagram", "Instagram", "fake", False, False, []),
        ("facebook", "Facebook", "fake", False, False, []),
        ("meta_ads", "Meta Ads", "fake", False, False, []),
        ("google_ads", "Google Ads", "fake", False, False, []),
        ("amazon_ads", "Amazon Ads", "fake", False, False, []),
        ("flipkart_ads", "Flipkart Ads", "fake", False, False, []),
    ]
    result: list[dict[str, object]] = []
    for key, label, mode, configured, enabled, capabilities in specs:
        if key == "meesho":
            status = "not_supported"
        elif not configured:
            status = "not_configured"
        elif enabled and mode in {"sandbox", "live"}:
            status = mode
        elif mode == "fake":
            status = "fake"
        else:
            status = "disabled"
        result.append(
            {
                "key": key,
                "provider": label,
                "domain": "marketplace" if key == "shopify" else key,
                "mode": mode,
                "status": status,
                "enabled": enabled,
                "configured": configured,
                "capabilities": capabilities,
                "account_state": "configured" if configured else "not_configured",
                "last_validation": None,
                "last_success": None,
                "last_failure": None,
                "rate_limit_state": "unknown",
                "timeout_policy": {
                    "connect_seconds": settings.provider_connect_timeout_seconds,
                    "read_seconds": settings.provider_read_timeout_seconds,
                    "total_seconds": settings.provider_total_timeout_seconds,
                },
                "recovery_supported": True,
                "reconciliation_supported": key in {"shopify", "amazon", "flipkart"},
                "mutation_enabled": bool(
                    enabled and not settings.external_mutations_emergency_stop
                ),
            }
        )
    return result


def _worker_domain_coverage() -> list[dict[str, str]]:
    return [
        {
            "domain": "publishing",
            "classification": "FULL DETAIL",
            "source": "durable worker heartbeat and jobs",
        },
        {
            "domain": "ai_content_image",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "ai_video",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "bulk_video",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "social",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "marketplace",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "campaign",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "ads",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
        {
            "domain": "marketing_plan",
            "classification": "SUMMARY ONLY",
            "source": "shared job/recovery projections",
        },
    ]


def _worker_rows(db: Session, owner_id: uuid.UUID) -> list[dict[str, object]]:
    now = utcnow()
    try:
        rows = list(
            db.scalars(
                select(PublishingWorkerHeartbeat).order_by(
                    PublishingWorkerHeartbeat.last_heartbeat_at.desc()
                )
            )
        )
    except Exception:
        db.rollback()
        return []
    output: list[dict[str, object]] = []
    for worker in rows:
        try:
            queue = db.execute(
                select(PublishingJob.state, func.count())
                .where(
                    PublishingJob.owner_id == owner_id,
                    PublishingJob.lease_owner == worker.worker_id,
                )
                .group_by(PublishingJob.state)
            ).all()
        except Exception:
            db.rollback()
            queue = []
        output.append(
            {
                "worker_id": _safe_worker_id(worker.worker_id),
                "worker_type": "publishing",
                "status": (
                    "draining"
                    if worker.draining
                    else (
                        "online"
                        if worker.last_heartbeat_at >= now - timedelta(minutes=2)
                        else "stale"
                    )
                ),
                "enabled": True,
                "configured_concurrency": worker.concurrency,
                "active_leases": worker.active_jobs,
                "queue": {state: int(count) for state, count in queue},
                "retry_wait": int(sum(count for state, count in queue if state == "retry_wait")),
                "failed_jobs": worker.failed_jobs,
                "last_heartbeat_at": worker.last_heartbeat_at,
                "completed_jobs": worker.completed_jobs,
                "lease_renewal_failures": worker.lease_renewal_failures,
                "stale_recoveries": worker.stale_recoveries,
                "draining": worker.draining,
                "restart_required_for_pause": True,
            }
        )
    return output


def _safe_job(job: PublishingJob, product_name: str | None = None) -> dict[str, object]:
    return {
        "id": str(job.id),
        "logical_identity": job.idempotency_key,
        "owner_id": str(job.owner_id),
        "product_id": str(job.product_id),
        "product_name": product_name,
        "domain": "publishing",
        "connector": job.connector_key,
        "operation": job.requested_action,
        "status": job.state,
        "attempt_count": job.execution_attempt_count,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "lease_owner": _safe_worker_id(job.lease_owner) if job.lease_owner else None,
        "lease_expires_at": job.lease_expires_at,
        "checkpoint_state": job.recovery_state,
        "correlation_id": job.correlation_id,
        "provider_mode": (
            get_settings().shopify_mode
            if job.connector_key == "shopify"
            else get_settings().provider_runtime_mode
        ),
        "failure_code": job.last_error_code,
        "safe_failure_message": job.last_error_message,
        "retryable": job.retryable,
        "recovery_eligibility": (
            ["retry"]
            if job.state in {"failed", "dead_letter", "cancelled", "expired"} and job.retryable
            else []
        ),
    }


@router.get("/overview")
def overview(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    health = health_details(db)
    jobs = {
        state: int(total)
        for state, total in db.execute(
            select(PublishingJob.state, func.count())
            .where(PublishingJob.owner_id == user.id)
            .group_by(PublishingJob.state)
        ).all()
    }
    recovery_count = int(
        db.scalar(
            select(func.count())
            .select_from(PublishingJob)
            .where(
                PublishingJob.owner_id == user.id,
                PublishingJob.state.in_(
                    ["retry_wait", "failed", "dead_letter", "cancel_requested"]
                ),
            )
        )
        or 0
    )
    latest_backup = db.scalar(
        select(BackupRecord)
        .where(BackupRecord.owner_id == user.id)
        .order_by(BackupRecord.created_at.desc())
        .limit(1)
    )
    storage = storage_summary(db, user)
    providers = _provider_registry()
    alerts = alert_projection(db, user)
    return {
        "status": (
            "healthy"
            if not alerts
            else (
                "warning" if all(item["severity"] != "critical" for item in alerts) else "critical"
            )
        ),
        "environment": settings.environment.upper(),
        "provider_modes": {
            "shopify": settings.shopify_mode.upper(),
            "default": settings.provider_runtime_mode.upper(),
        },
        "app_version": __version__,
        "health": health.model_dump(mode="json"),
        "database": {"status": "healthy", "migration": _migration_revision(db)},
        "migrations": {
            "current": _migration_revision(db),
            "repository_head": "20260913_0062",
            "head_match": _migration_revision(db) == "20260913_0062",
            "pending": False,
        },
        "storage": storage,
        "workers": {
            "enabled": settings.publishing_worker_enabled,
            "items": _worker_rows(db, user.id),
            "domain_coverage": _worker_domain_coverage(),
        },
        "scheduler": scheduler_projection(db, user),
        "jobs": jobs,
        "recovery": {"recoverable": recovery_count},
        "providers": providers,
        "backup": {
            "latest": latest_backup.created_at if latest_backup else None,
            "status": latest_backup.status if latest_backup else "not_configured",
            "destination_configured": bool(settings.backup_directory),
        },
        "security": security_projection(db),
        "configuration": _configuration_status(),
        "release": {
            "version": __version__,
            "build_identifier": settings.build_identifier,
            "git_commit": settings.git_commit[:40],
            "python": platform.python_version(),
        },
        "alerts": alerts,
    }


@router.get("/health")
def control_health(db: DatabaseSession, _user: CurrentUser) -> dict[str, object]:
    value = health_details(db)
    return {
        "status": value.status,
        "environment": get_settings().environment.upper(),
        "components": [item.model_dump(mode="json") for item in value.components],
    }


@router.get("/workers")
def workers(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    return {
        "items": _worker_rows(db, user.id),
        "domain_coverage": _worker_domain_coverage(),
        "pause_resume": "restart_required",
    }


@router.get("/workers/{worker_id}")
def worker_detail(worker_id: str, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    items = _worker_rows(db, user.id)
    value = next((item for item in items if item["worker_id"] == worker_id), None)
    if value is None:
        raise HTTPException(404, "Worker not found.")
    return value


@router.post("/workers/{worker_id}/pause")
def pause_worker(worker_id: str, _user: CurrentUser) -> dict[str, object]:
    del worker_id
    raise HTTPException(
        409, "Worker pause is restart-controlled; active work is never killed by the UI."
    )


@router.post("/workers/{worker_id}/resume")
def resume_worker(worker_id: str, _user: CurrentUser) -> dict[str, object]:
    del worker_id
    raise HTTPException(
        409, "Worker resume is restart-controlled; update deployment configuration safely."
    )


def scheduler_projection(db: Session, user: User) -> dict[str, object]:
    now = utcnow()
    due = int(
        db.scalar(
            select(func.count())
            .select_from(PublishingJob)
            .where(
                PublishingJob.owner_id == user.id,
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
                PublishingJob.available_at_utc <= now,
            )
        )
        or 0
    )
    overdue = int(
        db.scalar(
            select(func.count())
            .select_from(PublishingJob)
            .where(
                PublishingJob.owner_id == user.id,
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
                PublishingJob.available_at_utc < now,
            )
        )
        or 0
    )
    return {
        "enabled": get_settings().publishing_worker_enabled,
        "deployment_topology": "shared durable worker",
        "maintenance_blocked": maintenance_enabled(),
        "last_tick": now,
        "next_tick": now + timedelta(seconds=get_settings().publishing_worker_poll_seconds),
        "lease_lock": {"active_workers": len(_worker_rows(db, user.id))},
        "scheduled_jobs": int(
            db.scalar(
                select(func.count())
                .select_from(PublishingSchedule)
                .where(PublishingSchedule.owner_id == user.id)
            )
            or 0
        ),
        "overdue_schedules": overdue,
        "cancelled": int(
            db.scalar(
                select(func.count())
                .select_from(PublishingJob)
                .where(PublishingJob.owner_id == user.id, PublishingJob.state == "cancelled")
            )
            or 0
        ),
        "rescheduled": int(
            db.scalar(
                select(func.count())
                .select_from(PublishingJob)
                .where(PublishingJob.owner_id == user.id, PublishingJob.state == "retry_wait")
            )
            or 0
        ),
        "catch_up_eligible": 0,
        "catch_up_deferred": 0,
        "due_jobs": due,
    }


@router.get("/scheduler")
def scheduler(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    return scheduler_projection(db, user)


@router.post("/scheduler/run-due")
def run_due(data: ConfirmationRequest, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(
            422, "Explicit confirmation is required to run a bounded due-work cycle."
        )
    key = data.idempotency_key
    if key:
        _idempotency_lock(db, f"scheduler:{user.id}:{key}")
        prior = _prior_operation(
            db,
            actor_id=user.id,
            action="operations.scheduler_due_cycle",
            idempotency_key=key,
        )
        if prior is not None:
            return {
                "status": "reused",
                "materialized": 0,
                "idempotent_reuse": True,
                "audit_id": str(prior.id),
            }
    count = materialize_due_schedules(db, commit=False)
    event = record_event(
        db,
        actor_id=user.id,
        action="operations.scheduler_due_cycle",
        entity_type="scheduler",
        entity_id=user.id,
        metadata={"materialized": count, "idempotency_key": key or str(uuid.uuid4())},
    )
    db.commit()
    return {
        "status": "completed",
        "materialized": count,
        "idempotent_reuse": False,
        "audit_id": str(event.id),
    }


@router.get("/jobs")
def jobs(
    db: DatabaseSession,
    user: CurrentUser,
    state: str | None = None,
    product_id: uuid.UUID | None = None,
    connector: str | None = None,
    correlation_id: Annotated[str | None, Query(max_length=64)] = None,
    retryable: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    filters: list[Any] = [PublishingJob.owner_id == user.id]
    if state:
        filters.append(PublishingJob.state == state)
    if product_id:
        filters.append(PublishingJob.product_id == product_id)
    if connector:
        filters.append(PublishingJob.connector_key == connector)
    if correlation_id:
        filters.append(PublishingJob.correlation_id == correlation_id)
    if retryable is not None:
        filters.append(PublishingJob.retryable.is_(retryable))
    total = int(db.scalar(select(func.count()).select_from(PublishingJob).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(PublishingJob)
            .where(*filters)
            .order_by(PublishingJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    names = {
        str(item.id): item.name
        for item in db.scalars(
            select(Product).where(
                Product.owner_id == user.id, Product.id.in_([row.product_id for row in rows])
            )
        )
    }
    return {
        "items": [_safe_job(row, names.get(str(row.product_id))) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/jobs/{job_id}")
def job_detail(job_id: uuid.UUID, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    job = db.scalar(
        select(PublishingJob).where(PublishingJob.id == job_id, PublishingJob.owner_id == user.id)
    )
    if job is None:
        raise HTTPException(404, "Job not found.")
    product = db.scalar(
        select(Product).where(Product.id == job.product_id, Product.owner_id == user.id)
    )
    attempts = db.scalars(
        select(PublishingJobAttempt)
        .where(PublishingJobAttempt.job_id == job.id)
        .order_by(PublishingJobAttempt.attempt_number)
    ).all()
    return {
        **_safe_job(job, product.name if product else None),
        "attempts": [
            {
                "attempt_number": item.attempt_number,
                "worker_id": _safe_worker_id(item.worker_id),
                "started_at": item.started_at,
                "completed_at": item.completed_at,
                "outcome": item.outcome,
                "retryable": item.retryable,
                "error_code": item.error_code,
                "safe_error_message": item.safe_error_message,
                "checkpoint": item.connector_execution_id is not None,
            }
            for item in attempts
        ],
    }


@router.post("/jobs/{job_id}/actions")
def job_action(
    job_id: uuid.UUID,
    action: str,
    data: ConfirmationRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required for a Job action.")
    if action not in {"retry", "cancel", "inspect", "review"}:
        raise HTTPException(422, "The requested Job action is not available.")
    job = db.scalar(
        select(PublishingJob).where(PublishingJob.id == job_id, PublishingJob.owner_id == user.id)
    )
    if job is None:
        raise HTTPException(404, "Job not found.")
    if action in {"inspect", "review"}:
        return {
            "status": "inspected",
            "action": action,
            "idempotent_reuse": False,
            "job": _safe_job(job),
        }
    key = data.idempotency_key or f"{job.id}:{action}"
    _idempotency_lock(db, f"job:{user.id}:{key}")
    prior = _prior_operation(
        db,
        actor_id=user.id,
        action=f"operations.job_{action}",
        idempotency_key=key,
    )
    if prior is not None:
        return {
            "status": "reused",
            "action": action,
            "idempotent_reuse": True,
            "audit_id": str(prior.id),
        }
    if action == "retry":
        if job.state not in {"failed", "dead_letter", "cancelled", "expired"} or not job.retryable:
            raise HTTPException(409, "This Job is not eligible for retry.")
        job.state = "pending"
        job.available_at_utc = utcnow()
        job.updated_at = utcnow()
        job.row_version += 1
    elif action == "cancel":
        if job.state in TERMINAL_STATES:
            raise HTTPException(409, "This Job is already terminal and cannot be cancelled.")
        job.state = "cancel_requested" if job.state in {"claimed", "running"} else "cancelled"
        job.updated_at = utcnow()
    event = record_event(
        db,
        actor_id=user.id,
        action=f"operations.job_{action}",
        entity_type="publishing_job",
        entity_id=job.id,
        metadata={"action": action, "status": job.state, "idempotency_key": key},
    )
    db.commit()
    return {
        "status": "accepted",
        "action": action,
        "idempotent_reuse": False,
        "audit_id": str(event.id),
        "job": _safe_job(job),
    }


@router.get("/providers")
def providers(_user: CurrentUser) -> dict[str, object]:
    return {"items": _provider_registry()}


@router.get("/providers/{provider}")
def provider_detail(provider: str, _user: CurrentUser) -> dict[str, object]:
    value = next((item for item in _provider_registry() if item["key"] == provider), None)
    if value is None:
        raise HTTPException(404, "Provider not found.")
    return value


@router.post("/providers/{provider}/switch")
def provider_switch(
    provider: str, data: ConfirmationRequest, _user: CurrentUser
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required to change provider state.")
    del provider
    raise HTTPException(
        409, "Provider enablement is deployment-controlled; no runtime bypass is available."
    )


@router.get("/configuration")
def configuration(_user: CurrentUser) -> dict[str, object]:
    return _configuration_status()


def security_projection(db: Session) -> dict[str, object]:
    settings = get_settings()
    return {
        "environment": settings.environment,
        "https_required": settings.require_https,
        "secure_cookie": settings.session_secure_cookie,
        "cors_safe": "*" not in settings.allowed_origin_set,
        "credential_encryption": bool(settings.credential_encryption_key),
        "global_mutations": settings.live_mutations_enabled,
        "emergency_stop": settings.external_mutations_emergency_stop or maintenance_enabled(),
        "ads_spend": settings.ads_live_spend_enabled,
        "dependency_audit": "not_configured",
        "security_tests": "repository_suite",
        "secret_scan": "not_configured",
        "recent_security_events": int(
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action.like("security.%"))
            )
            or 0
        ),
    }


@router.get("/security")
def security(db: DatabaseSession, _user: CurrentUser) -> dict[str, object]:
    return security_projection(db)


def storage_summary(db: Session, user: User) -> dict[str, object]:
    root = storage_root()
    try:
        usage = shutil.disk_usage(root)
        free = usage.free
    except OSError:
        free = None
    media_rows = int(
        db.scalar(
            select(func.count()).select_from(MediaAsset).where(MediaAsset.owner_id == user.id)
        )
        or 0
    )
    image_count = int(
        db.scalar(
            select(func.count())
            .select_from(MediaAsset)
            .where(MediaAsset.owner_id == user.id, MediaAsset.mime_type.like("image/%"))
        )
        or 0
    )
    video_count = int(
        db.scalar(
            select(func.count())
            .select_from(MediaAsset)
            .where(MediaAsset.owner_id == user.id, MediaAsset.mime_type.like("video/%"))
        )
        or 0
    )
    total_bytes = int(
        db.scalar(
            select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(
                MediaAsset.owner_id == user.id
            )
        )
        or 0
    )
    observed_at = utcnow()
    current = {
        "media_count": media_rows,
        "file_count": media_rows,
        "total_bytes": total_bytes,
        "temporary_files": 0,
        "checkpoint_files": 0,
    }
    owner_key = str(user.id)
    previous = _storage_baselines.get(owner_key)
    if previous is None and len(_storage_baselines) >= 1024:
        _storage_baselines.pop(next(iter(_storage_baselines)))
    _storage_baselines[owner_key] = {**current, "observed_at": observed_at}
    return {
        "media_rows": media_rows,
        "image_count": image_count,
        "video_count": video_count,
        "total_bytes": total_bytes,
        "free_bytes": free,
        "temporary_files": 0,
        "checkpoint_files": 0,
        "orphan_count": 0,
        "growth": {
            "current": current,
            "previous": previous,
            "delta": (
                {
                    key: current[key] - cast(int, previous[key])
                    for key in (
                        "media_count",
                        "file_count",
                        "total_bytes",
                        "temporary_files",
                        "checkpoint_files",
                    )
                }
                if previous is not None
                else None
            ),
            "observed_at": observed_at,
            # Compatibility fields for existing consumers.
            "current_bytes": total_bytes,
            "previous_bytes": cast(int, previous["total_bytes"]) if previous else None,
            "delta_bytes": (total_bytes - cast(int, previous["total_bytes"]) if previous else None),
        },
    }


@router.get("/storage")
def storage(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    return storage_summary(db, user)


def alert_projection(db: Session, user: User) -> list[dict[str, object]]:
    settings = get_settings()
    alerts: list[dict[str, object]] = []
    if maintenance_enabled():
        alerts.append(
            {
                "severity": "warning",
                "code": "maintenance_mode",
                "message": "Maintenance mode is active.",
            }
        )
    if settings.live_mutations_enabled:
        alerts.append(
            {
                "severity": "warning",
                "code": "live_mutations_enabled",
                "message": "One or more live mutation switches are enabled.",
            }
        )
    failed = int(
        db.scalar(
            select(func.count())
            .select_from(PublishingJob)
            .where(
                PublishingJob.owner_id == user.id,
                PublishingJob.state.in_(["failed", "dead_letter"]),
            )
        )
        or 0
    )
    if failed:
        alerts.append(
            {
                "severity": "warning",
                "code": "failed_jobs",
                "message": f"{failed} durable publishing jobs require review.",
            }
        )
    if not settings.credential_encryption_key:
        alerts.append(
            {
                "severity": "warning",
                "code": "encryption_key_missing",
                "message": "Credential encryption is not configured.",
            }
        )
    return alerts


@router.get("/alerts")
def alerts(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    return {"items": alert_projection(db, user)}


@router.get("/release-readiness")
def release_readiness(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    checks = {
        "configuration": not _configuration_status()["errors"],
        "database": bool(db.scalar(text("select 1"))),
        "migrations": _migration_revision(db) == "20260913_0062",
        "storage": storage_root().is_dir(),
        "workers": settings.publishing_worker_enabled,
        "scheduler": settings.publishing_worker_enabled,
        "backups": bool(settings.backup_directory),
        "system_doctor": True,
        "security": not settings.live_ads_mutations_enabled or settings.ads_live_spend_enabled,
        "live_provider_signoff": False,
    }
    status = (
        "ready"
        if all(checks.values())
        else ("conditional" if checks["database"] and checks["migrations"] else "blocked")
    )
    return {
        "status": status,
        "checks": checks,
        "environment": settings.environment,
        "production_blockers": [key for key, value in checks.items() if not value],
    }


@router.get("/backups/overview")
def backup_overview(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    latest = db.scalar(
        select(BackupRecord)
        .where(BackupRecord.owner_id == user.id)
        .order_by(BackupRecord.created_at.desc())
        .limit(1)
    )
    return {
        "last_database_backup": latest.created_at if latest else None,
        "last_media_backup": None,
        "last_restore_drill": None,
        "destination_configured": bool(settings.backup_directory),
        "retention": {
            "count": settings.backup_retention_count,
            "days": settings.backup_retention_days,
        },
        "failures": int(
            db.scalar(
                select(func.count())
                .select_from(BackupRecord)
                .where(BackupRecord.owner_id == user.id, BackupRecord.status == "failed")
            )
            or 0
        ),
    }


@router.post("/backups/trigger")
def trigger_backup(
    data: ConfirmationRequest, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before creating a backup.")
    key = data.idempotency_key
    if key:
        _idempotency_lock(db, f"backup:{user.id}:{key}")
        prior = _prior_operation(
            db,
            actor_id=user.id,
            action="operations.backup_triggered",
            idempotency_key=key,
        )
        if prior is not None:
            return {"status": "reused", "idempotent_reuse": True, "audit_id": str(prior.id)}
    try:
        value = create_backup(db, user.id)
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    event = record_event(
        db,
        actor_id=user.id,
        action="operations.backup_triggered",
        entity_type="backup",
        entity_id=value.id,
        metadata={"idempotency_key": key or str(value.id), "status": value.status},
    )
    db.commit()
    return {
        "status": "created",
        "backup_id": str(value.id),
        "backup_key": value.backup_key,
        "idempotent_reuse": False,
        "audit_id": str(event.id),
    }


@router.get("/cleanup/preview")
def cleanup_preview(_user: CurrentUser) -> dict[str, object]:
    return {
        "items": [],
        "bytes": 0,
        "protected": ["approved final media", "current lineage", "audit-required assets"],
        "message": "No automatic cleanup policy is enabled.",
    }


@router.get("/audit")
def audit(
    db: DatabaseSession,
    user: CurrentUser,
    correlation_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, object]:
    query = select(AuditEvent).where(AuditEvent.actor_id == user.id)
    if correlation_id:
        query = query.where(AuditEvent.correlation_id == correlation_id)
    values = db.scalars(query.order_by(AuditEvent.occurred_at.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": str(item.entity_id),
                "correlation_id": item.correlation_id,
                "occurred_at": item.occurred_at,
            }
            for item in values
        ]
    }


@router.get("/trace/{correlation_id}")
def trace(correlation_id: str, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_id == user.id, AuditEvent.correlation_id == correlation_id)
        .order_by(AuditEvent.occurred_at)
    ).all()
    jobs = db.scalars(
        select(PublishingJob).where(
            PublishingJob.owner_id == user.id, PublishingJob.correlation_id == correlation_id
        )
    ).all()
    executions = db.scalars(
        select(PublishingExecution).where(
            PublishingExecution.owner_id == user.id,
            PublishingExecution.correlation_id == correlation_id,
        )
    ).all()
    return {
        "correlation_id": correlation_id,
        "events": [
            {
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": str(item.entity_id),
                "occurred_at": item.occurred_at,
            }
            for item in events
        ],
        "jobs": [_safe_job(item) for item in jobs],
        "executions": [
            {
                "id": str(item.id),
                "status": item.status,
                "connector": item.connector_key,
                "remote_status": item.remote_status,
                "reconciliation_status": item.reconciliation_status,
            }
            for item in executions
        ],
    }


@router.post("/emergency-stop")
def emergency_stop(data: ConfirmationRequest, _user: CurrentUser) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required to request emergency stop.")
    raise HTTPException(
        409,
        "Emergency stop is deployment-controlled; update runtime configuration and restart safely.",
    )


@router.get("/metrics")
def metrics(_user: CurrentUser) -> dict[str, object]:
    return {"metrics": provider_metrics_snapshot()}


@router.get("/system-doctor")
def system_doctor(db: DatabaseSession, _user: CurrentUser) -> dict[str, object]:
    value = health_details(db)
    return {
        "status": value.status,
        "checks": [
            {
                "component": item.component,
                "status": item.status,
                "message": item.message,
                "checked_at": item.checked_at,
            }
            for item in value.components
        ],
    }


@router.get("/drain")
def drain_status(_user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    return {
        "enabled": maintenance_enabled(),
        "claiming_new_jobs": not maintenance_enabled() and settings.publishing_worker_enabled,
        "active_jobs_finish": True,
        "queued_jobs_preserved": True,
        "control": "deployment_restart_required",
    }


@router.post("/drain")
def set_drain(data: ConfirmationRequest, _user: CurrentUser) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required to change drain mode.")
    raise HTTPException(
        409,
        "Drain mode is deployment-controlled; update maintenance configuration and restart safely.",
    )


@router.get("/recovery/history")
def recovery_history(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    values = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_id == user.id, AuditEvent.action.like("%recovery%"))
        .order_by(AuditEvent.occurred_at.desc())
        .limit(200)
    ).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": str(item.entity_id),
                "correlation_id": item.correlation_id,
                "occurred_at": item.occurred_at,
                "result": item.metadata_json.get("status"),
            }
            for item in values
        ]
    }


@router.post("/recovery/actions")
def recovery_action(
    data: ConfirmationRequest,
    action: Annotated[str, Query(min_length=1, max_length=64)],
    _user: CurrentUser,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required for a Recovery action.")
    raise HTTPException(
        409,
        f"Recovery action '{action}' is available through the domain-specific Recovery API.",
    )


@router.get("/mutation-control")
def mutation_control(_user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    return {
        "enabled": settings.live_mutations_enabled,
        "emergency_stop": settings.external_mutations_emergency_stop or maintenance_enabled(),
        "ads_spend_enabled": settings.ads_live_spend_enabled,
        "marketplace_mutations_enabled": settings.live_marketplace_mutations_enabled,
        "ai_live_enabled": settings.live_ai_enabled,
        "control": "deployment_restart_required",
    }


@router.post("/mutation-control")
def set_mutation_control(data: ConfirmationRequest, _user: CurrentUser) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required to change mutation controls.")
    raise HTTPException(
        409,
        "Mutation controls are deployment-controlled; no runtime bypass is available.",
    )


@router.get("/emergency-stop")
def emergency_stop_status(_user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    return {
        "active": settings.external_mutations_emergency_stop or maintenance_enabled(),
        "blocks_external_mutations": True,
        "reads_allowed": True,
        "diagnostics_allowed": True,
        "reconciliation_allowed": True,
        "control": "deployment_restart_required",
    }


@router.get("/ads/safety")
def ads_safety(_user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    return {
        "global_mutations_enabled": settings.live_ads_mutations_enabled,
        "live_spend_enabled": settings.ads_live_spend_enabled,
        "daily_caps": {"configured": False},
        "provider_caps": {"configured": False},
        "campaign_caps": {"configured": False},
        "marketing_plan_caps": {"configured": False},
        "recent_safe_actions": [],
        "blocked_actions": [] if settings.ads_live_spend_enabled else ["external_ads_spend"],
    }


@router.get("/restore/readiness")
def restore_readiness(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    latest = db.scalar(
        select(BackupRecord)
        .where(BackupRecord.owner_id == user.id)
        .order_by(BackupRecord.created_at.desc())
        .limit(1)
    )
    return {
        "ready": bool(latest and latest.verification_status == "verified"),
        "backup_id": str(latest.id) if latest else None,
        "execution_supported": False,
        "operator_action": "Use the documented restore runbook in a disposable environment first.",
        "runbook": "docs/operations/operations-control-center.md#restore-safety",
    }


@router.get("/migrations")
def migrations(db: DatabaseSession, _user: CurrentUser) -> dict[str, object]:
    current = _migration_revision(db)
    return {
        "current": current,
        "repository_head": "20260913_0062",
        "head_match": current == "20260913_0062",
        "multiple_heads": False,
        "pending": current != "20260913_0062",
        "actions": "runbook_only",
    }


@router.post("/migrations/run")
def migration_action(data: ConfirmationRequest, _user: CurrentUser) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required to request migrations.")
    raise HTTPException(409, "Migrations are runbook-controlled and cannot be started from the UI.")


@router.get("/security/events")
def security_events(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    values = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.actor_id == user.id,
            AuditEvent.action.like("security.%"),
        )
        .order_by(AuditEvent.occurred_at.desc())
        .limit(200)
    ).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "action": item.action,
                "entity_type": item.entity_type,
                "occurred_at": item.occurred_at,
                "correlation_id": item.correlation_id,
            }
            for item in values
        ]
    }


@router.post("/alerts/acknowledge")
def acknowledge_alert(
    data: ConfirmationRequest,
    alert_code: Annotated[str, Query(min_length=1, max_length=100)],
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required to acknowledge an alert.")
    key = data.idempotency_key or alert_code
    _idempotency_lock(db, f"alert:{user.id}:{key}")
    prior = _prior_operation(
        db,
        actor_id=user.id,
        action="operations.alert_acknowledged",
        idempotency_key=key,
    )
    if prior is not None:
        return {"status": "reused", "idempotent_reuse": True, "audit_id": str(prior.id)}
    event = record_event(
        db,
        actor_id=user.id,
        action="operations.alert_acknowledged",
        entity_type="alert",
        entity_id=user.id,
        metadata={
            "alert_code": alert_code,
            "idempotency_key": key,
            "comment": "operator acknowledged",
        },
    )
    db.commit()
    return {"status": "acknowledged", "idempotent_reuse": False, "audit_id": str(event.id)}


@router.get("/staging-readiness")
def staging_readiness(_user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ready",
        "environment": settings.environment,
        "shopify": "deferred",
        "live_providers": "deferred",
        "external_mutations": "disabled" if not settings.live_mutations_enabled else "configured",
    }


@router.get("/production-readiness")
def production_readiness(_user: CurrentUser) -> dict[str, object]:
    return {
        "status": "blocked",
        "blockers": [
            "live providers",
            "object storage",
            "monitoring vendor",
            "signing",
            "external secrets",
            "deployment infrastructure",
        ],
        "shopify_sandbox": "deferred",
        "real_ads_spend": "disabled",
    }


@router.post("/cleanup")
def cleanup(data: ConfirmationRequest, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before cleanup.")
    key = data.idempotency_key or "current-state-cleanup"
    _idempotency_lock(db, f"cleanup:{user.id}:{key}")
    prior = _prior_operation(
        db,
        actor_id=user.id,
        action="operations.cleanup_completed",
        idempotency_key=key,
    )
    if prior is not None:
        return {
            "status": "reused",
            "removed_items": 0,
            "idempotent_reuse": True,
            "audit_id": str(prior.id),
        }
    event = record_event(
        db,
        actor_id=user.id,
        action="operations.cleanup_completed",
        entity_type="storage",
        entity_id=user.id,
        metadata={"status": "no_action", "idempotency_key": key},
    )
    db.commit()
    return {
        "status": "no_action",
        "removed_items": 0,
        "idempotent_reuse": False,
        "audit_id": str(event.id),
    }
