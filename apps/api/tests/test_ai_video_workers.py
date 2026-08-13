from __future__ import annotations

from datetime import timedelta

import pytest
import test_ai_integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt
from vayujit_api.ai.studio_worker import (
    AIWorkerCrash,
    claim_ai_jobs,
    execute_ai_job,
    recover_expired_ai_jobs,
)
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_video_crash_after_checkpoint_recovers_once(client):
    assert test_ai_integration.factory is not None
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/video/queue",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "resolution": "320x240",
            "duration_seconds": 2,
            "idempotency_key": "video-crash-after",
            "failure_scenario": "success",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    with test_ai_integration.factory() as db:
        claimed = claim_ai_jobs(db, "video-crash-a", 1, 1)
        assert claimed
        with pytest.raises(AIWorkerCrash):
            execute_ai_job(db, claimed[0], "video-crash-a", crash_after_checkpoint=True)
        job = db.get(AIStudioJob, claimed[0])
        assert job is not None
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_ai_jobs(db) == 1
        assert claim_ai_jobs(db, "video-crash-b", 1, 120)
        execute_ai_job(db, claimed[0], "video-crash-b")
        generation = db.scalar(select(VideoGeneration))
        assert generation is not None and generation.status == "succeeded"
        assert (
            db.scalar(
                select(VideoOutput).where(VideoOutput.generation_id == generation.id)
            ).media_id
            is not None
        )
        assert len(list(db.scalars(select(AIStudioJobAttempt)))) == 2
