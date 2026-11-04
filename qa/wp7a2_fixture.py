"""Owned offline fault/inspection helpers, not a production business authority."""

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated
from unittest.mock import patch

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def snapshot(db, owner):
    from vayujit_api.ads.models import (
        AdCampaign,
        AdFailureRecord,
        AdJob,
        AdRecoveryRecord,
    )
    from vayujit_api.ai.studio_models import AIStudioJob
    from vayujit_api.audit.models import AuditEvent
    from vayujit_api.intelligence.business_agent_models import (
        BusinessAgentGoal,
        BusinessAgentPlan,
        BusinessAgentRun,
    )
    from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
    from vayujit_api.video.models import (
        VideoApproval,
        VideoGeneration,
        VideoOutput,
        VideoStoryboard,
    )

    def owned(model):
        return db.scalars(
            select(model).where(model.owner_id == owner.id).order_by(model.id)
        ).all()

    def digest(value):
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, default=str).encode()
        ).hexdigest()

    return {
        "synthetic": True,
        "owner_id": str(owner.id),
        "goals": [
            {
                "id": str(r.id),
                "inputs_sha256": digest(r.structured_goal),
                "inputs": r.structured_goal,
                "created_at": str(r.created_at),
            }
            for r in owned(BusinessAgentGoal)
        ],
        "plans": [
            {
                "id": str(r.id),
                "goal_id": str(r.goal_id),
                "version": r.version,
                "hash": r.plan_hash,
                "status": r.status,
            }
            for r in owned(BusinessAgentPlan)
        ],
        "runs": [
            {
                "id": str(r.id),
                "goal_id": str(r.goal_id),
                "plan_id": str(r.plan_id),
                "status": r.status,
                "created_at": str(r.created_at),
            }
            for r in owned(BusinessAgentRun)
        ],
        "candidates": [
            {
                "id": str(r.id),
                "name": r.name,
                "category": r.category,
                "key": r.idempotency_key,
                "tags": r.tags,
                "evidence_state": r.evidence_state,
                "profile_sha256": digest(r.intelligence_profile),
                "created_at": str(r.created_at),
            }
            for r in owned(ProductOpportunity)
        ],
        "boards": [
            {
                "id": str(r.id),
                "product_id": str(r.product_id),
                "version": r.version,
                "row_version": r.row_version,
                "state": r.state,
                "approved_by": str(r.approved_by) if r.approved_by else None,
                "approved_at": str(r.approved_at) if r.approved_at else None,
                "fingerprint": r.context_fingerprint,
            }
            for r in owned(VideoStoryboard)
        ],
        "videos": [
            {
                "id": str(r.id),
                "status": r.status,
                "failure": r.failure_code,
                "correlation": r.correlation_id,
                "output_count": len(
                    db.scalars(
                        select(VideoOutput).where(
                            VideoOutput.generation_id == r.id,
                            VideoOutput.media_id.is_not(None),
                        )
                    ).all()
                ),
                "approval": [
                    a.state
                    for a in db.scalars(
                        select(VideoApproval).where(VideoApproval.generation_id == r.id)
                    )
                ],
            }
            for r in owned(VideoGeneration)
        ],
        "creative_jobs": [
            {
                "id": str(r.id),
                "generation_id": str(r.generation_id),
                "state": r.state,
                "attempts": r.attempt_count,
                "failure": r.failure_category,
                "error": r.last_error_code,
                "safe_error": r.safe_error_message,
                "lease": bool(r.lease_owner),
                "correlation": r.correlation_id,
            }
            for r in owned(AIStudioJob)
        ],
        "ads_campaigns": [
            {
                "id": str(r.id),
                "product_id": str(r.product_id),
                "name": r.name,
                "state": r.state,
                "input_fingerprint": r.preview_fingerprint,
                "targeting_sha256": digest(r.targeting_summary_json),
                "remote": bool(r.remote_campaign_id),
                "failure": r.failure_category,
                "retry_after": r.retry_after_seconds,
                "next_retry": str(r.next_retry_at) if r.next_retry_at else None,
            }
            for r in owned(AdCampaign)
        ],
        "ads_jobs": [
            {
                "id": str(r.id),
                "entity_id": str(r.entity_id),
                "status": r.status,
                "attempts": r.attempt_count,
                "failure": r.failure_code,
                "key": r.idempotency_key,
            }
            for r in owned(AdJob)
        ],
        "ads_recoveries": [
            {
                "id": str(r.id),
                "entity_id": str(r.entity_id),
                "key": r.idempotency_key,
                "status": r.status,
            }
            for r in owned(AdRecoveryRecord)
        ],
        "ads_failures": [
            {"id": str(r.id), "entity_id": str(r.entity_id), "code": r.code}
            for r in owned(AdFailureRecord)
        ],
        "audit": [
            {
                "id": str(r.id),
                "entity_id": str(r.entity_id),
                "action": r.action,
                "metadata": {
                    k: v
                    for k, v in (r.metadata_json or {}).items()
                    if k
                    in {
                        "version",
                        "source_storyboard_id",
                        "source_version",
                        "approval_inherited",
                        "action",
                        "correlation_id",
                    }
                },
            }
            for r in db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.actor_id == owner.id,
                    AuditEvent.action.in_(
                        [
                            "ai.video_storyboard_approved",
                            "ai.video_storyboard_updated",
                            "ai.video_recovery_requested",
                            "ads.recovery_recorded",
                        ]
                    ),
                )
                .order_by(AuditEvent.id)
            )
        ],
    }


def install(app, token, engine, output):
    from vayujit_api.core.database import get_session
    from vayujit_api.core.test_database import assert_safe_test_database
    from vayujit_api.identity.models import User
    from vayujit_api.identity.router import current_user

    if (
        os.environ.get("QA_BROWSER_PHASE")
        not in {"WP7A2", "WP7A3", "WP7A4", "WP7A5", "WP7A6", "WP7A7"}
        or engine.url.database != f"vayujit_qa{token}_test"
    ):
        raise ValueError("EXACT_WP7A2_ONLY")
    with engine.connect() as c:
        assert_safe_test_database(c, database_url=str(engine.url), environment="test")
    lock = Lock()

    @app.get("/__qa/wp7a2/state", include_in_schema=False)
    def state(
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if x_qa_token != token:
            raise HTTPException(403, "Exact QA ownership required")
        return {"token": token, **snapshot(db, owner)}

    @app.post("/__qa/wp7a2/control", include_in_schema=False)
    def control(
        data: dict,
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        from vayujit_api.ads.connectors import connector_for
        from vayujit_api.ads.models import AdCampaign, AdJob
        from vayujit_api.ads.service import run_job
        from vayujit_api.ai import studio_worker
        from vayujit_api.ai.studio_models import AIStudioJob
        from vayujit_api.products.models import Product
        from vayujit_api.video.models import VideoGeneration
        from vayujit_api.video.provider import video_provider
        from vayujit_api.video.worker import execute_video_job

        if x_qa_token != token:
            raise HTTPException(403, "Exact QA ownership required")
        identity = uuid.UUID(data["id"])
        scenario = data["scenario"]
        with lock:
            if scenario == "VIDEO_FAILURE":
                row = db.scalar(
                    select(VideoGeneration).where(
                        VideoGeneration.id == identity,
                        VideoGeneration.owner_id == owner.id,
                    )
                )
                product = db.get(Product, row.product_id) if row else None
                if (
                    not product
                    or not product.name.startswith("[QA SYNTHETIC] WP7A2")
                    or row.provider_key != "deterministic_video_local"
                ):
                    raise HTTPException(403, "Owned local Video fixture required")
                job = db.scalar(
                    select(AIStudioJob).where(
                        AIStudioJob.owner_id == owner.id,
                        AIStudioJob.correlation_id == row.correlation_id,
                    )
                )
                if not job or job.state not in {"queued", "retry_wait"}:
                    raise HTTPException(409, "Expected queued local job")
                for _ in range(3):
                    moment = max(datetime.now(UTC), job.available_at)
                    with (
                        patch.object(studio_worker, "utcnow", return_value=moment),
                        patch.object(
                            video_provider,
                            "generate",
                            side_effect=RuntimeError("QA controlled local failure"),
                        ),
                    ):
                        claimed = studio_worker.claim_ai_jobs(
                            db, "wp7a2-owned-worker", 1, 120
                        )
                        if claimed != [job.id]:
                            raise HTTPException(409, "Exact owned job claim required")
                        execute_video_job(db, job.id, "wp7a2-owned-worker")
                    db.expire_all()
                    if job.state == "failed":
                        break
            elif scenario == "ADS_FAILURE":
                campaign = db.scalar(
                    select(AdCampaign).where(
                        AdCampaign.id == identity, AdCampaign.owner_id == owner.id
                    )
                )
                if (
                    not campaign
                    or not campaign.name.startswith("[QA SYNTHETIC] WP7A2")
                    or campaign.provider != "meta"
                    or campaign.remote_campaign_id
                ):
                    raise HTTPException(403, "Owned offline campaign required")
                connector = connector_for("meta")
                if not type(connector).__module__.startswith(
                    "vayujit_api.ads.connectors"
                ):
                    raise HTTPException(403, "Fake connector required")
                job = db.scalar(
                    select(AdJob)
                    .where(
                        AdJob.owner_id == owner.id,
                        AdJob.entity_id == identity,
                        AdJob.status.in_(["queued", "retry_wait"]),
                    )
                    .order_by(AdJob.created_at.desc())
                )
                if not job:
                    raise HTTPException(409, "Queued owned Ads job required")
                prior = dict(connector.state.failures)
                try:
                    connector.state.failures["create_campaign"] = "unavailable"
                    run_job(db, job)
                finally:
                    connector.state.failures.clear()
                    connector.state.failures.update(prior)
            else:
                raise HTTPException(422, "Unsupported offline control")
        return {"token": token, **snapshot(db, owner)}
