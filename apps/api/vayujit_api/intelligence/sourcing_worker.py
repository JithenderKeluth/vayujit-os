"""Bounded local sourcing worker; never contacts suppliers."""

from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.sourcing_models import SourcingWorkerJob
from vayujit_api.intelligence.sourcing_service import now, run_worker


def recover_expired_leases(db: Session, owner: User) -> int:
    timestamp = now()
    jobs = list(
        db.scalars(
            select(SourcingWorkerJob).where(
                SourcingWorkerJob.owner_id == owner.id,
                SourcingWorkerJob.status == "running",
                SourcingWorkerJob.lease_expires_at.is_not(None),
                SourcingWorkerJob.lease_expires_at < timestamp,
            )
        )
    )
    for job in jobs:
        job.status = "pending"
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.last_error = "Worker lease expired; execution is eligible for recovery."
        job.updated_at = timestamp
    db.commit()
    return len(jobs)


def run_next(db: Session, owner: User, *, worker_id: str | None = None):
    timestamp = now()
    job = db.scalar(
        select(SourcingWorkerJob)
        .where(
            SourcingWorkerJob.owner_id == owner.id,
            or_(
                SourcingWorkerJob.status == "pending",
                and_(
                    SourcingWorkerJob.status == "running",
                    SourcingWorkerJob.lease_expires_at.is_not(None),
                    SourcingWorkerJob.lease_expires_at < timestamp,
                ),
            ),
        )
        .order_by(SourcingWorkerJob.created_at)
    )
    return None if job is None else run_worker(db, owner, job, worker_id=worker_id)


def worker_capabilities() -> dict[str, object]:
    return {
        "tasks": [
            "cost_recalculation",
            "scenario_generation",
            "report_generation",
            "stale_quote_check",
            "expiry_alerts",
        ],
        "checkpoint_stages": [
            "claimed",
            "before_calculation",
            "calculation_complete",
            "scenario_complete",
            "report_complete",
            "finalized",
        ],
        "external_contact": "disabled",
        "purchasing": "not_implemented",
    }
