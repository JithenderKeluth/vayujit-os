"""Explicit signed WP7A4 fixture preparation through canonical local authorities."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def install(app, token, engine, output):
    if (
        os.environ.get("QA_BROWSER_PHASE") not in {"WP7A4", "WP7A5", "WP7A6", "WP7A7"}
        or engine.url.database != f"vayujit_qa{token}_test"
    ):
        raise ValueError("EXACT_WP7A4_REQUIRED")
    from vayujit_api.core.test_database import assert_safe_test_database

    with engine.connect() as c:
        assert_safe_test_database(c, database_url=str(engine.url), environment="test")
    from vayujit_api.core.database import get_session
    from vayujit_api.identity.models import User
    from vayujit_api.identity.router import current_user

    @app.get("/__qa/wp7a4/state", include_in_schema=False)
    def state(
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if x_qa_token != token:
            raise HTTPException(403, "Exact QA token required")
        from vayujit_api.publishing.models import (
            PublishingDestination,
            PublishingExecution,
            PublishingJob,
            PublishingSchedule,
        )
        from vayujit_api.social.models import SocialPost
        from vayujit_api.workflows.models import WorkflowInstance

        models = [
            PublishingDestination,
            PublishingExecution,
            PublishingJob,
            PublishingSchedule,
            SocialPost,
            WorkflowInstance,
        ]
        result = {"synthetic": True, "token": token}
        for model in models:
            result[model.__tablename__] = [
                {
                    "id": str(r.id),
                    "owner_id": str(r.owner_id),
                    **{
                        key: (
                            str(getattr(r, key))
                            if getattr(r, key, None) is not None
                            else None
                        )
                        for key in [
                            "product_id",
                            "artifact_id",
                            "artifact_version",
                            "destination_id",
                            "status",
                            "state",
                        ]
                    },
                }
                for r in db.scalars(select(model).where(model.owner_id == owner.id))
            ]
        if os.environ.get("QA_BROWSER_PHASE") in {"WP7A5", "WP7A6", "WP7A7"}:
            from qa.wp7a3_fixture import snapshot as ai_snapshot
            from qa.wp7a5_snapshot import snapshot as continuation_snapshot

            result.update(ai_snapshot(db, owner))
            result.update(continuation_snapshot(db, owner))
        if os.environ.get("QA_BROWSER_PHASE") in {"WP7A6", "WP7A7"}:
            from qa.wp7a6_snapshot import snapshot as closure_snapshot

            result.update(closure_snapshot(db, owner))
        if os.environ.get("QA_BROWSER_PHASE") == "WP7A7":
            from qa.wp7a7_snapshot import snapshot as final_snapshot

            result.update(final_snapshot(db, owner))
        return result

    @app.post("/__qa/wp7a4/prepare", include_in_schema=False)
    def prepare(
        data: dict,
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if x_qa_token != token or set(data) != {"artifact_id"}:
            raise HTTPException(403, "Exact authenticated QA ownership required")
        from vayujit_api.ai.models import GeneratedArtifact

        try:
            artifact_id = uuid.UUID(str(data["artifact_id"]))
        except (TypeError, ValueError) as error:
            raise HTTPException(422, "Valid artifact identity required") from error
        artifact = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == artifact_id,
                GeneratedArtifact.owner_id == owner.id,
            )
        )
        if not artifact or artifact.status != "approved":
            raise HTTPException(409, "Existing HUMAN-approved artifact required")
        from vayujit_api.publishing.models import PublishingJob
        from vayujit_api.publishing.scheduler_schemas import ScheduleCreate
        from vayujit_api.publishing.scheduler_service import (
            create_schedule,
            materialize_due_schedules,
        )
        from vayujit_api.publishing.schemas import CreateExecution, DestinationWrite
        from vayujit_api.publishing.service import create_destination, create_execution
        from vayujit_api.publishing.worker import heartbeat

        result = {
            "synthetic": True,
            "mode": "LOCAL_MOCK_ONLY",
            "artifact_id": str(artifact.id),
        }
        destination = create_destination(
            db,
            owner,
            DestinationWrite(
                name="[QA SYNTHETIC] WP7A4 destination " + str(artifact.id),
                connector_key="mock_publisher_v1",
                configuration={"channel_name": "QA-WP7A4-LOCAL"},
            ),
        )
        result["destination_id"] = str(destination.id)
        # This connector is the application-owned in-process mock, never a remote connector.
        execution = create_execution(
            db,
            owner,
            CreateExecution(
                artifact_id=artifact.id,
                destination_id=destination.id,
                action="create_draft",
                idempotency_key="wp7a4-" + str(artifact.id),
            ),
        )
        result["execution_id"] = str(execution.id)
        schedule = create_schedule(
            db,
            owner,
            ScheduleCreate(
                name="[QA SYNTHETIC] WP7A4 schedule " + str(artifact.id),
                artifact_id=artifact.id,
                destination_id=destination.id,
                requested_action="create_draft",
                timezone_name="UTC",
                local_scheduled_at=(datetime.now(UTC) + timedelta(hours=2)).replace(
                    tzinfo=None
                ),
            ),
        )
        materialize_due_schedules(db)
        job = db.scalar(
            select(PublishingJob).where(PublishingJob.schedule_id == schedule.id)
        )
        result.update(schedule_id=str(schedule.id), job_id=str(job.id) if job else None)
        worker_id = "wp7a4-" + token
        heartbeat(worker_id, 1, 0, False)
        from vayujit_api.operations.control_center import _safe_worker_id

        result["worker_id"] = _safe_worker_id(worker_id)
        # No job dispatcher, scheduler loop, real connector or production worker is started.
        return result
