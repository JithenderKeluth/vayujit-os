"""Ads execution on the repository shared durable worker runtime."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from vayujit_api.ads.models import AdJob
from vayujit_api.ads.service import now, run_job

ADS_LEASE_SECONDS = 300


def run_next_ads_job(
    db: Session, *, owner_id: uuid.UUID | None = None, worker_id: str = "shared-publishing-worker"
) -> AdJob | None:
    timestamp = now()
    statement = select(AdJob).where(
        or_(
            AdJob.status.in_(["queued", "retry_wait"]),
            AdJob.status == "running",
            AdJob.status == "claimed",
        ),
        or_(
            AdJob.status.in_(["queued", "retry_wait"]),
            AdJob.lease_expires_at.is_(None),
            AdJob.lease_expires_at < timestamp,
        ),
        or_(AdJob.next_retry_at.is_(None), AdJob.next_retry_at <= timestamp),
    )
    if owner_id is not None:
        statement = statement.where(AdJob.owner_id == owner_id)
    job = db.scalar(statement.order_by(AdJob.created_at).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return None
    job.status = "claimed"
    job.lease_expires_at = timestamp + timedelta(seconds=ADS_LEASE_SECONDS)
    job.correlation_id = job.correlation_id or f"ads-{uuid.uuid4().hex}"
    db.commit()
    return run_job(db, job, worker_id=worker_id)


def run_ads_jobs_once(
    db: Session, worker_id: str, limit: int = 1, owner_id: uuid.UUID | None = None
) -> list[AdJob]:
    completed: list[AdJob] = []
    for _ in range(max(limit, 0)):
        value = run_next_ads_job(db, owner_id=owner_id, worker_id=worker_id)
        if value is None:
            break
        completed.append(value)
    return completed
