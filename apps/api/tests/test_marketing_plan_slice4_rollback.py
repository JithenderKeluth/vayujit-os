from __future__ import annotations

import uuid
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN
from test_marketing_plan_slice4_acceptance import _confirm_plan

from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.marketing_execution import MarketingChannelExecution
from vayujit_api.ads.models import AdJob
from vayujit_api.ads.worker import run_next_ads_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_meta_budget_rollback_is_provider_backed_and_idempotent(client: Any) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", f"rollback-{uuid.uuid4().hex[:8]}")
    payload = {
        "brand_id": context["brand"]["id"],
        "product_ids": [context["product"]["id"]],
        "objective": "sales",
        "locale": "en-IN",
        "timezone": "Asia/Kolkata",
        "target_channels": ["meta"],
        "budget_envelope": {
            "total": "100",
            "currency": "INR",
            "allocations": {"meta": "100"},
            "strategy": "manual",
        },
        "strategy_mode": "manual",
        "automation_mode": "manual",
        "creative_mapping": {"meta": {"artifact_version": 1}},
        "targeting": {"locale": "en-IN"},
        "schedule": {"mode": "immediate"},
        "idempotency_key": f"rollback-{uuid.uuid4().hex}",
    }
    plan = _confirm_plan(client, payload)
    plan_id = plan["id"]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        first = run_next_ads_job(db, worker_id="rollback-forward-v1")
        assert first is not None and first.status == "succeeded"
    connector = connector_for("meta")
    initial_calls = len(connector.state.calls)
    remote = next(iter(connector.state.entities["campaign"].values()))
    assert remote["budget_version"] == 1

    proposed = {
        "total": "150",
        "currency": "INR",
        "allocations": {"meta": "150"},
        "strategy": "manual",
    }
    preview = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/preview",
        json={
            "proposed": proposed,
            "expected_version": 1,
            "preview_fingerprint": "preview-placeholder-123456",
            "confirm": False,
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    changed = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/confirm",
        json={
            "proposed": proposed,
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "rollback-forward-v2",
        },
        headers=ORIGIN,
    )
    assert changed.status_code == 200, changed.text
    with integration_fixture.factory() as db:
        second = run_next_ads_job(db, worker_id="rollback-forward-v2")
        assert second is not None and second.status == "succeeded", (
            second.status if second else None,
            second.failure_code if second else None,
            second.safe_failure_message if second else None,
        )
    assert remote["budget_version"] == 2
    assert len(connector.state.calls) == initial_calls + 1

    rollback_preview = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN
    )
    assert rollback_preview.status_code == 200, rollback_preview.text
    rollback = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
        params={"preview_fingerprint": rollback_preview.json()["fingerprint"], "confirm": "true"},
        headers=ORIGIN,
    )
    assert rollback.status_code == 200, rollback.text
    with integration_fixture.factory() as db:
        rollback_job = run_next_ads_job(db, worker_id="rollback-v1")
        assert rollback_job is not None and rollback_job.status == "succeeded"
    assert remote["budget_version"] == 1
    assert len(connector.state.calls) == initial_calls + 2
    assert connector.state.calls[-1]["payload"]["rollback"] is True
    repeated = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
        params={
            "preview_fingerprint": rollback_preview.json()["fingerprint"],
            "confirm": "true",
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["idempotent_reuse"] is True
    assert len(connector.state.calls) == initial_calls + 2
    with integration_fixture.factory() as db:
        assert (
            db.scalar(
                select(AdJob.id).where(
                    AdJob.operation == "marketing_plan_rollback",
                    AdJob.request_json["plan_id"].astext == str(plan_id),
                )
            )
            is not None
        )
        channel = db.scalar(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.plan_id == uuid.UUID(str(plan_id))
            )
        )
        assert channel is not None
        assert channel.downstream_json["budget_version"] == 1
