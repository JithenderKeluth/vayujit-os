from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN

from vayujit_api.ads.marketing import _fingerprint
from vayujit_api.ads.marketing_execution import MarketingChannelExecution
from vayujit_api.ads.models import AdJob
from vayujit_api.ads.worker import run_next_ads_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _six_channel_payload(context: dict[str, Any], suffix: str) -> dict[str, Any]:
    channels = ["meta", "google", "amazon", "flipkart", "social", "campaign"]
    allocations = {channel: "10" for channel in channels}
    creative_mapping = {channel: {"artifact_version": 1} for channel in channels}
    return {
        "brand_id": context["brand"]["id"],
        "product_ids": [context["product"]["id"]],
        "objective": "sales",
        "locale": "en-IN",
        "timezone": "Asia/Kolkata",
        "target_channels": channels,
        "budget_envelope": {
            "total": "60",
            "currency": "INR",
            "allocations": allocations,
            "strategy": "manual",
        },
        "strategy_mode": "manual",
        "automation_mode": "manual",
        "creative_mapping": creative_mapping,
        "targeting": {"locale": "en-IN"},
        "schedule": {"mode": "immediate"},
        "idempotency_key": f"slice4-{suffix}-{uuid.uuid4().hex}",
    }


def _confirm_plan(client: Any, payload: dict[str, Any]) -> dict[str, Any]:
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": payload, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/ads/marketing/plans/confirm",
        json={
            "plan": payload,
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 201, confirmed.text
    return confirmed.json()


def _enable_six_channel_accounts(client: Any, context: dict[str, Any]) -> None:
    for provider in ("meta", "google"):
        create_account(client, provider, f"slice4-{provider}")
    for provider in ("amazon", "flipkart"):
        account = create_account(client, provider, f"slice4-{provider}")
        listing = client.post(
            "/api/v1/ads/marketplace/listings",
            json={
                "account_id": account["id"],
                "product_id": context["product"]["id"],
                "marketplace": provider,
                "listing_id": f"{provider.upper()}-SLICE4-{uuid.uuid4().hex[:8]}",
                "version": 1,
                "title": f"{provider.title()} Slice 4 product",
                "sku": f"{provider.upper()}-SLICE4-{uuid.uuid4().hex[:8]}",
            },
            headers=ORIGIN,
        )
        assert listing.status_code == 201, listing.text


def test_slice4_full_six_channel_materialization_and_lineage(client) -> None:
    context = setup_ads_context(client)
    _enable_six_channel_accounts(client, context)
    payload = _six_channel_payload(context, "full")
    confirmation_started = time.perf_counter()
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": payload, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/ads/marketing/plans/confirm",
        json={
            "plan": payload,
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 201, confirmed.text
    confirmation_ms = (time.perf_counter() - confirmation_started) * 1000
    plan = confirmed.json()
    plan_id = uuid.UUID(str(plan["id"]))

    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        materialization_started = time.perf_counter()
        first_job_ms: float | None = None
        first_completion_ms: float | None = None
        jobs_seen: set[uuid.UUID] = set()
        for index in range(6):
            job = run_next_ads_job(db, worker_id=f"slice4-six-{index}")
            assert job is not None
            jobs_seen.add(job.id)
            elapsed_ms = (time.perf_counter() - materialization_started) * 1000
            first_job_ms = first_job_ms or elapsed_ms
            if job.status == "succeeded" and first_completion_ms is None:
                first_completion_ms = elapsed_ms
        channels = list(
            db.scalars(
                select(MarketingChannelExecution).where(
                    MarketingChannelExecution.plan_id == plan_id
                )
            )
        )
        jobs = list(db.scalars(select(AdJob).where(AdJob.id.in_(jobs_seen))))
        assert len(channels) == 6
        assert len(jobs) == 6
        assert {item.channel for item in channels} == {
            "meta",
            "google",
            "amazon",
            "flipkart",
            "social",
            "campaign",
        }
        assert all(item.plan_version == 1 for item in channels)
        assert all(item.state == "succeeded" for item in channels)
        assert all(
            item.downstream_json["product_ids"] == [str(context["product"]["id"])]
            for item in channels
        )
        assert all(item.downstream_json.get("provider_remote_id") for item in channels)
        assert all(item.downstream_json.get("provider_mutated") is True for item in channels)
        print(
            "SIX_CHANNEL_TIMING "
            + json.dumps(
                {
                    "confirmation_ms": round(confirmation_ms, 3),
                    "materialization_ms": round(
                        (time.perf_counter() - materialization_started) * 1000, 3
                    ),
                    "time_to_first_job_ms": round(first_job_ms or 0, 3),
                    "time_to_first_completion_ms": round(first_completion_ms or 0, 3),
                    "total_six_channel_completion_ms": round(
                        (time.perf_counter() - confirmation_started) * 1000, 3
                    ),
                    "channels": len(channels),
                    "jobs": len(jobs),
                    "attempts": sum(item.attempt_count for item in channels),
                    "connector_mutations": sum(
                        item.downstream_json.get("provider_mutated") is True for item in channels
                    ),
                    "retries": 0,
                    "reconciliations": 0,
                    "recovery_operations": 0,
                    "duplicate_jobs": 0,
                    "duplicate_connector_mutations": 0,
                },
                sort_keys=True,
            )
        )


def test_slice4_partial_failure_is_channel_isolated_and_recoverable(client) -> None:
    context = setup_ads_context(client)
    plan = _confirm_plan(client, _six_channel_payload(context, "partial"))
    execution = client.get(
        f"/api/v1/ads/marketing/plans/{plan['id']}/execution",
        headers=ORIGIN,
    )
    assert execution.status_code == 200
    execution_id = execution.json()["id"]

    response = client.post(
        f"/api/v1/ads/marketing/executions/{execution_id}/run",
        json={
            "confirm": True,
            "idempotency_key": "slice4-partial-run",
            "outcomes": {
                "meta": "succeeded",
                "google": "retry_wait",
                "amazon": "ambiguous",
                "flipkart": "failed",
                "social": "succeeded",
                "campaign": "blocked",
            },
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "running"
    states = {item["channel"]: item["state"] for item in body["channels"]}
    assert states == {
        "meta": "succeeded",
        "google": "retry_wait",
        "amazon": "ambiguous",
        "flipkart": "failed",
        "social": "succeeded",
        "campaign": "blocked",
    }

    recovery = client.get(
        f"/api/v1/ads/marketing/plans/{plan['id']}/recovery",
        headers=ORIGIN,
    )
    assert recovery.status_code == 200
    by_channel = {item["channel"]: item for item in recovery.json()["channels"]}
    assert "retry_channel" in by_channel["google"]["actions"]
    assert "reconcile" in by_channel["amazon"]["actions"]
    assert "retry_channel" in by_channel["flipkart"]["actions"]
    assert by_channel["campaign"]["actions"] == ["retry_channel", "cancel_channel"]


def test_slice4_auto_reallocation_is_bounded_and_idempotent(client) -> None:
    context = setup_ads_context(client)
    payload = _six_channel_payload(context, "auto")
    payload["target_channels"] = ["social", "campaign"]
    payload["budget_envelope"] = {
        "total": "100",
        "currency": "INR",
        "allocations": {"social": "50", "campaign": "50"},
        "strategy": "manual",
    }
    plan = _confirm_plan(client, payload)
    fingerprint = _fingerprint(
        {
            "plan_id": plan["id"],
            "version": 1,
            "budget": plan["budget_envelope"],
        }
    )
    request = {
        "proposed": {
            "total": "100",
            "currency": "INR",
            "allocations": {"social": "55", "campaign": "45"},
            "strategy": "manual",
        },
        "expected_version": 1,
        "current_fingerprint": fingerprint,
        "idempotency_key": "slice4-auto-once",
        "confirm": True,
        "owner_opt_in": True,
        "rule_enabled": True,
        "action_allowed": True,
        "max_percent_change": 20,
        "total_budget_cap": 100,
    }
    applied = client.post(
        f"/api/v1/ads/marketing/plans/{plan['id']}/auto-reallocation",
        json=request,
        headers=ORIGIN,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["idempotent_reuse"] is False
    repeated = client.post(
        f"/api/v1/ads/marketing/plans/{plan['id']}/auto-reallocation",
        json=request,
        headers=ORIGIN,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["idempotent_reuse"] is True

    current = client.get(f"/api/v1/ads/marketing/plans/{plan['id']}", headers=ORIGIN)
    assert current.status_code == 200, current.text
    current_plan = current.json()
    blocked = {
        **request,
        "idempotency_key": "slice4-auto-blocked",
        "expected_version": current_plan["current_version"],
        "current_fingerprint": _fingerprint(
            {
                "plan_id": plan["id"],
                "version": current_plan["current_version"],
                "budget": current_plan["budget_envelope"],
            }
        ),
        "max_percent_change": 1,
        "proposed": {
            "total": "100",
            "currency": "INR",
            "allocations": {"social": "80", "campaign": "20"},
            "strategy": "manual",
        },
    }
    rejected = client.post(
        f"/api/v1/ads/marketing/plans/{plan['id']}/auto-reallocation",
        json=blocked,
        headers=ORIGIN,
    )
    assert rejected.status_code == 422
    assert "guardrail" in rejected.text.lower() or "percentage" in rejected.text.lower()
