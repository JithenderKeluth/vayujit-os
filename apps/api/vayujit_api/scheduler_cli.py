"""Safe scheduler diagnostics and explicitly confirmed recovery commands."""

from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import func, select

from vayujit_api.core.database import SessionFactory
from vayujit_api.publishing.job_queue import recover_expired_leases
from vayujit_api.publishing.models import (
    PublishingJob,
    PublishingSchedule,
    PublishingWorkerHeartbeat,
)
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.scheduler_time import utcnow


def counts() -> dict[str, object]:
    with SessionFactory() as db:
        return {
            "schedules": db.scalar(select(func.count()).select_from(PublishingSchedule)) or 0,
            "jobs": db.scalar(select(func.count()).select_from(PublishingJob)) or 0,
            "due": db.scalar(
                select(func.count())
                .select_from(PublishingJob)
                .where(
                    PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
                    PublishingJob.available_at_utc <= utcnow(),
                )
            )
            or 0,
            "retry_wait": db.scalar(
                select(func.count())
                .select_from(PublishingJob)
                .where(PublishingJob.state == "retry_wait")
            )
            or 0,
            "dead_letter": db.scalar(
                select(func.count())
                .select_from(PublishingJob)
                .where(PublishingJob.state == "dead_letter")
            )
            or 0,
            "workers": db.scalar(select(func.count()).select_from(PublishingWorkerHeartbeat)) or 0,
            "stale_workers": db.scalar(
                select(func.count())
                .select_from(PublishingWorkerHeartbeat)
                .where(
                    PublishingWorkerHeartbeat.last_heartbeat_at < utcnow() - timedelta(minutes=2)
                )
            )
            or 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="VAYUJIT scheduler diagnostics")
    parser.add_argument(
        "command",
        choices=["schedules", "jobs", "due", "dead-letter", "workers", "materialize", "recover"],
    )
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command in {"materialize", "recover"} and not args.confirm:
        parser.error("Mutating scheduler commands require --confirm.")
    if args.command == "materialize":
        with SessionFactory() as db:
            print({"materialized": materialize_due_schedules(db)})
        return
    if args.command == "recover":
        with SessionFactory() as db:
            print({"recovered": recover_expired_leases(db)})
        return
    values = counts()
    key = {
        "due": "due",
        "dead-letter": "dead_letter",
        "workers": "workers",
        "schedules": "schedules",
        "jobs": "jobs",
    }.get(args.command)
    print({key: values[key]} if key else values)


if __name__ == "__main__":
    main()
