from __future__ import annotations

import uuid
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN
from test_marketing_plan_slice4_acceptance import _confirm_plan, _six_channel_payload

from vayujit_api.ads.marketing_execution import MarketingChannelExecution, run_marketing_channel_job
from vayujit_api.ads.models import AdJob
from vayujit_api.ads.worker import run_next_ads_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_durable_reschedule_reuses_replacement_and_rejects_stale_job(client: Any) -> None:
    context = setup_ads_context(client)
    payload = _six_channel_payload(context, "durable-reschedule")
    payload["target_channels"] = ["social", "campaign"]
    payload["budget_envelope"] = {
        "total": "20",
        "currency": "INR",
        "allocations": {"social": "10", "campaign": "10"},
        "strategy": "manual",
    }
    plan = _confirm_plan(client, payload)
    plan_id = uuid.UUID(str(plan["id"]))
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        run_next_ads_job(db, worker_id="durable-initial-1")
        run_next_ads_job(db, worker_id="durable-initial-2")
        channels = list(
            db.scalars(
                select(MarketingChannelExecution).where(
                    MarketingChannelExecution.plan_id == plan_id
                )
            )
        )
        old_jobs = {row.channel: db.get(AdJob, row.job_id) for row in channels}
        old_schedules = {row.channel: str(row.schedule_id) for row in channels}
        assert all(job is not None for job in old_jobs.values())

    request = {
        "scheduled_at": "2030-01-01T00:00:00Z",
        "expected_version": 1,
        "idempotency_key": "durable-reschedule-once",
        "confirm": True,
    }
    first = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reschedule", json=request, headers=ORIGIN
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reschedule", json=request, headers=ORIGIN
    )
    assert second.status_code == 200 and second.json()["idempotent_reuse"] is True
    with integration_fixture.factory() as db:
        channels = list(
            db.scalars(
                select(MarketingChannelExecution).where(
                    MarketingChannelExecution.plan_id == plan_id
                )
            )
        )
        assert len({str(row.schedule_id) for row in channels}) == 2
        for row in channels:
            assert str(row.schedule_id) != old_schedules[row.channel]
            old_job = old_jobs[row.channel]
            assert old_job is not None
            run_marketing_channel_job(db, old_job, worker_id="durable-stale")
            assert old_job.status == "failed"
            assert old_job.failure_code == "marketing.stale_schedule"
        replacement = run_next_ads_job(db, worker_id="durable-replacement")
        assert replacement is not None and replacement.status == "succeeded"
