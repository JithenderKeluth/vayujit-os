"""Standalone durable publishing worker.

Run with ``python -m vayujit_api.publishing.worker run``. The API never starts
this loop implicitly, keeping web and worker lifecycle/failure domains separate.
"""

from __future__ import annotations

import argparse
import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert

from vayujit_api import __version__
from vayujit_api.commerce.amazon_worker import execute_amazon_job, parse_account_id
from vayujit_api.commerce.flipkart_worker import (
    execute_flipkart_job,
)
from vayujit_api.commerce.flipkart_worker import (
    parse_account_id as parse_flipkart_account_id,
)
from vayujit_api.commerce.meesho_worker import (
    execute_meesho_job,
)
from vayujit_api.commerce.meesho_worker import (
    parse_account_id as parse_meesho_account_id,
)
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User
from vayujit_api.publishing.job_queue import (
    claim_jobs,
    finish_job,
    recover_expired_leases,
    renew_lease,
    start_attempt,
)
from vayujit_api.publishing.models import (
    PublishingExecution,
    PublishingJob,
    PublishingSchedule,
    PublishingWorkerHeartbeat,
)
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.publishing.schemas import CreateExecution
from vayujit_api.publishing.service import (
    create_execution,
    move_execution_to_draft,
    reconcile_execution,
)
from vayujit_api.workflows.service import (
    resume_publishing_waits,
    resume_terminal_publishing_waits,
)

logger = logging.getLogger(__name__)


def default_worker_id() -> str:
    return f"worker-{uuid.uuid4().hex[:16]}"


def heartbeat(worker_id: str, concurrency: int, active_jobs: int, draining: bool) -> None:
    timestamp = utcnow()
    statement = insert(PublishingWorkerHeartbeat).values(
        worker_id=worker_id,
        process_started_at=PROCESS_STARTED_AT,
        last_heartbeat_at=timestamp,
        version=__version__,
        concurrency=concurrency,
        active_jobs=active_jobs,
        draining=draining,
        shutdown_requested=False,
        safe_status="draining" if draining else "healthy",
        created_at=timestamp,
        updated_at=timestamp,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[PublishingWorkerHeartbeat.worker_id],
        set_={
            "last_heartbeat_at": timestamp,
            "concurrency": concurrency,
            "active_jobs": active_jobs,
            "draining": draining,
            "safe_status": "draining" if draining else "healthy",
            "updated_at": timestamp,
        },
    )
    with SessionFactory() as db:
        db.execute(statement)
        db.commit()


def _lease_pulse(job_id: uuid.UUID, worker_id: str, stopped: threading.Event) -> None:
    settings = get_settings()
    while not stopped.wait(settings.publishing_worker_heartbeat_seconds):
        with SessionFactory() as pulse_db:
            if not renew_lease(pulse_db, job_id, worker_id, settings.publishing_job_lease_seconds):
                worker = pulse_db.get(PublishingWorkerHeartbeat, worker_id)
                if worker:
                    worker.lease_renewal_failures += 1
                    pulse_db.commit()
                return


def execute_job(job_id: uuid.UUID, worker_id: str) -> None:
    with SessionFactory() as db:
        attempt = start_attempt(db, job_id, worker_id)
        if not attempt:
            return
    stopped = threading.Event()
    pulse = threading.Thread(target=_lease_pulse, args=(job_id, worker_id, stopped), daemon=True)
    pulse.start()
    execution_id: uuid.UUID | None = None
    succeeded = False
    retryable = False
    error_code: str | None = None
    safe_message: str | None = None
    try:
        with SessionFactory() as db:
            job = db.get(PublishingJob, job_id)
            if not job:
                return
            owner = db.get(User, job.owner_id)
            if not owner:
                raise ValueError("Publishing job owner no longer exists.")
            amazon_account_id = parse_account_id(job.connector_key)
            flipkart_account_id = parse_flipkart_account_id(job.connector_key)
            meesho_account_id = parse_meesho_account_id(job.connector_key)
            if amazon_account_id is not None:
                amazon_result = execute_amazon_job(db, job, account_id=amazon_account_id)
                succeeded = amazon_result.status == "succeeded"
                retryable = amazon_result.retryable
                error_code = amazon_result.error_code
                safe_message = amazon_result.safe_message
            elif meesho_account_id is not None:
                meesho_result = execute_meesho_job(db, job, account_id=meesho_account_id)
                succeeded = meesho_result.status == "succeeded"
                retryable = meesho_result.retryable
                error_code = meesho_result.error_code
                safe_message = meesho_result.safe_message
            elif flipkart_account_id is not None:
                flipkart_result = execute_flipkart_job(db, job, account_id=flipkart_account_id)
                succeeded = flipkart_result.status == "succeeded"
                retryable = flipkart_result.retryable
                error_code = flipkart_result.error_code
                safe_message = flipkart_result.safe_message
            elif job.requested_action in {"move_to_draft", "reconcile"}:
                execution = (
                    db.get(PublishingExecution, job.publishing_execution_id)
                    if job.publishing_execution_id
                    else None
                )
                if not execution:
                    raise ValueError("This action requires an existing publishing execution.")
                response = (
                    move_execution_to_draft(db, owner, execution.id)
                    if job.requested_action == "move_to_draft"
                    else reconcile_execution(db, owner, execution.id)
                )
                execution_id = response.id
                succeeded = True
            else:
                action = cast(
                    Literal["create_draft", "publish", "activate", "update", "archive"],
                    {
                        "update_product": "update",
                        "activate_product": "activate",
                        "archive_product": "archive",
                    }.get(job.requested_action, job.requested_action),
                )
                response = create_execution(
                    db,
                    owner,
                    CreateExecution(
                        artifact_id=job.artifact_id,
                        destination_id=job.destination_id,
                        idempotency_key=f"job:{job.id}",
                        action=action,
                    ),
                )
                execution_id = response.id
                succeeded = response.status == "succeeded"
                retryable = response.retryable
                error_code = response.error_code
                safe_message = response.safe_error_message
    except HTTPException as error:
        error_code = f"http_{error.status_code}"
        safe_message = str(error.detail)[:500]
        retryable = error.status_code >= 500 or error.status_code == 429
    except Exception as error:  # connector boundaries normalize details below
        logger.exception("publishing_job_failed", extra={"job_id": str(job_id)})
        error_code = "worker_execution_error"
        safe_message = str(error)[:500] or "Publishing job execution failed."
        retryable = not isinstance(error, ValueError)
    finally:
        stopped.set()
        pulse.join(timeout=2)
    with SessionFactory() as db:
        final_state = finish_job(
            db,
            job_id,
            worker_id,
            succeeded=succeeded,
            connector_execution_id=execution_id,
            retryable=retryable,
            error_code=error_code,
            safe_error_message=safe_message,
        )
        job = db.get(PublishingJob, job_id)
        if job and job.schedule_id and final_state != "lease_lost":
            schedule = db.get(PublishingSchedule, job.schedule_id)
            if schedule:
                schedule.last_run_at_utc = utcnow()
                schedule.last_result = final_state
                schedule.updated_at = utcnow()
                db.commit()
        if final_state in {"succeeded", "failed", "dead_letter", "cancelled", "expired"}:
            heartbeat_row = db.get(PublishingWorkerHeartbeat, worker_id)
            if heartbeat_row:
                if final_state == "succeeded":
                    heartbeat_row.completed_jobs += 1
                else:
                    heartbeat_row.failed_jobs += 1
                db.commit()
            resume_publishing_waits(db, job_id)


def run_worker(*, once: bool = False) -> None:
    settings = get_settings()
    worker_id = settings.publishing_worker_id or default_worker_id()
    futures: set[Future[None]] = set()
    draining = False
    logger.info("publishing_worker_started", extra={"worker_id": worker_id})
    heartbeat(worker_id, settings.publishing_worker_concurrency, 0, False)
    with ThreadPoolExecutor(
        max_workers=settings.publishing_worker_concurrency,
        thread_name_prefix="publishing",
    ) as pool:
        try:
            while True:
                futures = {future for future in futures if not future.done()}
                marker = Path(settings.maintenance_marker).resolve()
                maintenance = marker.exists()
                with SessionFactory() as db:
                    recover_expired_leases(db)
                    resume_terminal_publishing_waits(db)
                if not maintenance:
                    with SessionFactory() as db:
                        materialize_due_schedules(db)
                    capacity = settings.publishing_worker_concurrency - len(futures)
                    if capacity > 0:
                        with SessionFactory() as db:
                            claimed = claim_jobs(
                                db,
                                worker_id,
                                capacity,
                                settings.publishing_job_lease_seconds,
                            )
                        futures.update(
                            pool.submit(execute_job, job_id, worker_id) for job_id in claimed
                        )
                else:
                    with SessionFactory() as db:
                        claim_jobs(
                            db,
                            worker_id,
                            0,
                            settings.publishing_job_lease_seconds,
                            maintenance_mode=True,
                        )
                heartbeat(worker_id, settings.publishing_worker_concurrency, len(futures), draining)
                if once:
                    break
                time.sleep(settings.publishing_worker_poll_seconds)
        except KeyboardInterrupt:
            draining = True
            heartbeat(worker_id, settings.publishing_worker_concurrency, len(futures), True)
            logger.info("publishing_worker_draining", extra={"worker_id": worker_id})
        finally:
            for future in futures:
                future.result()
            heartbeat(worker_id, settings.publishing_worker_concurrency, 0, True)
            with SessionFactory() as db:
                value = db.get(PublishingWorkerHeartbeat, worker_id)
                if value:
                    value.graceful_shutdowns += 1
                    value.safe_status = "stopped"
                    value.updated_at = utcnow()
                    db.commit()


PROCESS_STARTED_AT = utcnow()


def main() -> None:
    parser = argparse.ArgumentParser(description="VAYUJIT durable publishing worker")
    parser.add_argument("command", choices=["run", "once", "recover", "materialize"])
    arguments = parser.parse_args()
    if arguments.command in {"run", "once"}:
        run_worker(once=arguments.command == "once")
        return
    with SessionFactory() as db:
        count = (
            recover_expired_leases(db)
            if arguments.command == "recover"
            else materialize_due_schedules(db)
        )
    print(count)


if __name__ == "__main__":
    main()
