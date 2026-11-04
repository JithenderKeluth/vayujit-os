"""Explicit offline worker faults and read-only evidence on a signed QA database."""

import json
import os
from contextlib import nullcontext
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated
from unittest.mock import patch

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def snapshot(db, owner):
    from vayujit_api.ai.bulk_models import AIStudioBulkOperation
    from vayujit_api.ai.image_models import AIImageOutput
    from vayujit_api.ai.models import GeneratedArtifact
    from vayujit_api.ai.studio_models import AIStudioGeneration, AIStudioJob
    from vayujit_api.campaigns.models import Campaign, CampaignActivity
    from vayujit_api.media.models import MediaAsset

    fields = {
        GeneratedArtifact: [
            "id",
            "product_id",
            "brand_id",
            "status",
            "version_number",
            "parent_artifact_id",
            "source",
            "channel",
            "content_type",
            "context_fingerprint",
        ],
        AIImageOutput: [
            "id",
            "product_id",
            "brand_id",
            "generation_id",
            "job_id",
            "media_id",
            "parent_output_id",
            "status",
            "provider",
            "model",
            "checksum_sha256",
        ],
        AIStudioGeneration: [
            "id",
            "status",
            "context_fingerprint",
            "total_outputs",
            "completed_outputs",
            "failed_outputs",
        ],
        AIStudioJob: [
            "id",
            "generation_id",
            "state",
            "job_type",
            "attempt_count",
            "last_error_code",
            "safe_error_message",
            "context_fingerprint",
        ],
        AIStudioBulkOperation: ["id", "status"],
        Campaign: ["id", "brand_id", "name", "status"],
        CampaignActivity: [
            "id",
            "campaign_id",
            "product_id",
            "artifact_id",
            "artifact_version",
            "status",
            "activity_type",
        ],
        MediaAsset: ["id", "status", "width", "height", "checksum_sha256", "mime_type"],
    }
    result = {"synthetic": True, "owner_id": str(owner.id)}
    for model, names in fields.items():
        result[model.__tablename__] = [
            {
                name: json.loads(json.dumps(getattr(r, name, None), default=str))
                for name in names
            }
            for r in db.scalars(
                select(model).where(model.owner_id == owner.id).order_by(model.id)
            )
        ]
    return result


def install(app, token, engine, output):
    from vayujit_api.core.database import get_session
    from vayujit_api.core.test_database import assert_safe_test_database
    from vayujit_api.identity.models import User
    from vayujit_api.identity.router import current_user

    if (
        os.environ.get("QA_BROWSER_PHASE")
        not in {"WP7A3", "WP7A4", "WP7A5", "WP7A6", "WP7A7"}
        or engine.url.database != f"vayujit_qa{token}_test"
    ):
        raise ValueError("EXACT_WP7A3_REQUIRED")
    with engine.connect() as c:
        assert_safe_test_database(c, database_url=str(engine.url), environment="test")
    lock = Lock()

    @app.get("/__qa/wp7a3/state", include_in_schema=False)
    def state(
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if x_qa_token != token:
            raise HTTPException(403, "Exact owned QA token required")
        return {"token": token, **snapshot(db, owner)}

    @app.post("/__qa/wp7a3/control", include_in_schema=False)
    def control(
        data: dict,
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        from vayujit_api.ai import studio_worker
        from vayujit_api.ai.failures import StudioProviderFailure
        from vayujit_api.ai.image_provider import image_provider
        from vayujit_api.ai.studio_models import AIStudioJob
        from vayujit_api.video.provider import video_provider

        if (
            x_qa_token != token
            or data.get("scenario") not in {"WORKER_SUCCESS", "WORKER_FAIL"}
            or set(data)
            - (
                {"scenario", "limit"}
                if os.environ.get("QA_BROWSER_PHASE") in {"WP7A5", "WP7A6", "WP7A7"}
                else {"scenario"}
            )
            or type(data.get("limit", 16)) is not int
            or not 1 <= data.get("limit", 16) <= 16
        ):
            raise HTTPException(403, "Bounded owned local worker control required")
        with lock:
            jobs = db.scalars(
                select(AIStudioJob).where(
                    AIStudioJob.owner_id == owner.id,
                    AIStudioJob.state.in_(["queued", "retry_wait"]),
                )
            ).all()
            if len(jobs) > 16:
                raise HTTPException(409, "Worker budget exceeded")
            if any(
                j.provider != "deterministic_mock_v1"
                and not (
                    os.environ.get("QA_BROWSER_PHASE")
                    in {"WP7A4", "WP7A5", "WP7A6", "WP7A7"}
                    and j.provider == "deterministic_video_local"
                    and j.job_type.startswith("ai_video_")
                )
                for j in jobs
            ):
                raise HTTPException(403, "Only local deterministic jobs allowed")
            moment = max([datetime.now(UTC), *[j.available_at for j in jobs]])
            with patch.object(studio_worker, "utcnow", return_value=moment):
                if data["scenario"] == "WORKER_FAIL":
                    with (
                        patch.object(
                            studio_worker,
                            "_provider_call",
                            side_effect=StudioProviderFailure("provider_unavailable"),
                        ),
                        patch.object(
                            image_provider,
                            "generate",
                            side_effect=StudioProviderFailure("provider_unavailable"),
                        ),
                        (
                            patch.object(
                                video_provider,
                                "generate",
                                side_effect=RuntimeError(
                                    "QA local provider unavailable"
                                ),
                            )
                            if os.environ.get("QA_BROWSER_PHASE")
                            in {"WP7A5", "WP7A6", "WP7A7"}
                            else nullcontext()
                        ),
                    ):
                        studio_worker.run_ai_jobs_once(
                            db,
                            "wp7a3-owned-offline-worker",
                            limit=data.get("limit", 16),
                        )
                else:
                    studio_worker.run_ai_jobs_once(
                        db, "wp7a3-owned-offline-worker", limit=data.get("limit", 16)
                    )
        return {"token": token, **snapshot(db, owner)}
