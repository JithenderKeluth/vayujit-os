from __future__ import annotations

import uuid

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN

from vayujit_api.ads.models import AdJob
from vayujit_api.ads.worker import run_next_ads_job
from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _payload(context: dict[str, dict[str, object]], suffix: str = "one") -> dict[str, object]:
    return {
        "brand_id": context["brand"]["id"],
        "product_ids": [context["product"]["id"]],
        "objective": "sales",
        "locale": "en-IN",
        "timezone": "Asia/Kolkata",
        "target_channels": ["social", "campaign"],
        "budget_envelope": {
            "total": "100",
            "currency": "INR",
            "allocations": {"social": "50", "campaign": "50"},
            "strategy": "manual",
        },
        "strategy_mode": "manual",
        "automation_mode": "manual",
        "creative_mapping": {"social": {"artifact_version": 1}},
        "targeting": {"locale": "en-IN"},
        "schedule": {"mode": "immediate"},
        "idempotency_key": f"marketing-plan-{suffix}-{uuid.uuid4().hex}",
    }


def test_marketing_plan_capabilities_and_meesho_boundary(client) -> None:
    context = setup_ads_context(client)
    response = client.get("/api/v1/ads/marketing/capabilities", headers=ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert {"meta", "google", "amazon", "flipkart", "social", "campaign"} <= set(body["channels"])
    assert body["unsupported"] == ["meesho"]
    blocked = client.post(
        "/api/v1/ads/marketing/plans/readiness",
        json={
            "brand_id": context["brand"]["id"],
            "product_ids": [context["product"]["id"]],
            "target_channels": ["meesho"],
            "idempotency_key": "meesho-plan",
        },
        headers=ORIGIN,
    )
    assert blocked.status_code == 422 and "not supported" in blocked.text.lower()


def test_marketing_plan_preview_confirm_idempotency_and_recovery(client) -> None:
    context = setup_ads_context(client)
    payload = _payload(context)
    readiness = client.post("/api/v1/ads/marketing/plans/readiness", json=payload, headers=ORIGIN)
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": payload, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200 and preview.json()["mutates"] is False
    stale = client.post(
        "/api/v1/ads/marketing/plans/confirm",
        json={
            "plan": {**payload, "objective": "traffic"},
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409
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
    assert confirmed.status_code == 201
    plan = confirmed.json()
    repeated = client.post(
        "/api/v1/ads/marketing/plans/confirm",
        json={
            "plan": payload,
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 201 and repeated.json()["id"] == plan["id"]
    assert {item["state"] for item in plan["channels"]} == {"queued"}
    detail = client.get(f"/api/v1/ads/marketing/plans/{plan['id']}", headers=ORIGIN)
    assert detail.status_code == 200
    history = client.get(f"/api/v1/ads/marketing/plans/{plan['id']}/history", headers=ORIGIN)
    assert history.status_code == 200 and any(
        item["action"] == "ads.marketing_plan_confirmed" for item in history.json()
    )
    cancelled = client.post(
        f"/api/v1/ads/marketing/plans/{plan['id']}/actions",
        json={"action": "cancel_remaining", "confirm": True},
        headers=ORIGIN,
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


def test_marketing_plan_materialization_state_and_recovery(client) -> None:
    context = setup_ads_context(client)
    payload = _payload(context, "durable")
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": payload, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200
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
    plan = confirmed.json()
    execution_response = client.get(
        f"/api/v1/ads/marketing/plans/{plan['id']}/execution", headers=ORIGIN
    )
    assert execution_response.status_code == 200
    execution = execution_response.json()
    assert execution["plan_version"] == 1
    assert {item["state"] for item in execution["channels"]} == {"queued"}
    assert all(item["job_id"] for item in execution["channels"])
    assert all(item["downstream"]["provider_mutated"] is False for item in execution["channels"])

    mixed = client.post(
        f"/api/v1/ads/marketing/executions/{execution['id']}/run",
        json={
            "confirm": True,
            "outcomes": {"social": "succeeded", "campaign": "ambiguous"},
        },
        headers=ORIGIN,
    )
    assert mixed.status_code == 200, mixed.text
    assert mixed.json()["state"] == "partially_completed"
    assert {item["state"] for item in mixed.json()["channels"]} == {"succeeded", "ambiguous"}

    recovery = client.get(f"/api/v1/ads/marketing/plans/{plan['id']}/recovery", headers=ORIGIN)
    assert recovery.status_code == 200
    ambiguous = next(item for item in recovery.json()["channels"] if item["channel"] == "campaign")
    assert ambiguous["actions"] == ["reconcile", "cancel_channel"]
    reconciled = client.post(
        f"/api/v1/ads/marketing/executions/{execution['id']}/actions",
        json={
            "action": "reconcile",
            "channel": "campaign",
            "confirm": True,
            "idempotency_key": "reconcile-campaign-once",
        },
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["state"] == "succeeded"
    assert {item["state"] for item in reconciled.json()["channels"]} == {"succeeded", "recovered"}

    revisions = client.get(f"/api/v1/ads/marketing/plans/{plan['id']}/revisions", headers=ORIGIN)
    assert revisions.status_code == 200
    assert [item["version"] for item in revisions.json()] == [1]


def test_marketing_plan_worker_materializes_one_fake_provider_identity(client) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", "marketing-worker")
    payload = _payload(context, "worker")
    payload["target_channels"] = ["meta"]
    payload["budget_envelope"] = {
        "total": "100",
        "currency": "INR",
        "allocations": {"meta": "100"},
        "strategy": "manual",
    }
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": payload, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200 and preview.json()["readiness"]["ready"] is True
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
    plan_id = uuid.UUID(str(confirmed.json()["id"]))
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        job = run_next_ads_job(db, worker_id="marketing-certification")
        assert job is not None and job.status == "succeeded"
        channel = db.scalar(
            select(
                __import__(
                    "vayujit_api.ads.marketing_execution", fromlist=["MarketingChannelExecution"]
                ).MarketingChannelExecution
            ).where(
                __import__(
                    "vayujit_api.ads.marketing_execution", fromlist=["MarketingChannelExecution"]
                ).MarketingChannelExecution.plan_id
                == plan_id
            )
        )
        assert channel is not None
        assert channel.state == "succeeded"
        assert channel.downstream_json["provider_mutated"] is True
        assert channel.downstream_json["provider_remote_id"]
        assert db.scalar(select(AdJob).where(AdJob.id == channel.job_id)) is not None
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == channel.execution_id,
                    AuditEvent.action == "ads.marketing_plan_execution_completed",
                )
            )
        )
        assert len(events) == 1


def test_marketing_plan_closure_routes_are_safe_and_idempotent(client) -> None:
    context = setup_ads_context(client)
    payload = _payload(context, "closure-routes")
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": payload, "expected_version": 1},
        headers=ORIGIN,
    )
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
    assert confirmed.status_code == 201
    plan_id = confirmed.json()["id"]
    schedule = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reschedule",
        json={
            "scheduled_at": "2030-01-01T00:00:00Z",
            "expected_version": 1,
            "idempotency_key": "closure-reschedule",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert schedule.status_code == 200
    repeated = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reschedule",
        json={
            "scheduled_at": "2030-01-01T00:00:00Z",
            "expected_version": 1,
            "idempotency_key": "closure-reschedule",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    blocked_catch_up = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/catch-up/execute?policy=manual_confirmation&confirm=false",
        headers=ORIGIN,
    )
    assert blocked_catch_up.status_code == 409
    catch_up = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/catch-up/execute?policy=manual_confirmation&confirm=true",
        headers=ORIGIN,
    )
    assert catch_up.status_code == 200
    security = client.get("/api/v1/ads/marketing/security/matrix", headers=ORIGIN)
    assert security.status_code == 200 and security.json()["case_count"] >= 40
    privacy = client.get("/api/v1/ads/marketing/privacy/matrix", headers=ORIGIN)
    assert privacy.status_code == 200 and privacy.json()["payloads_sanitized"] is True
    attribution = client.get(f"/api/v1/ads/marketing/plans/{plan_id}/attribution", headers=ORIGIN)
    assert attribution.status_code == 200
    assert attribution.json()["attributed_revenue"] == "Unavailable"


def test_marketing_plan_storage_integrity_reports_owner_scoped_counters(client) -> None:
    context = setup_ads_context(client)
    plan = _payload(context, "storage")
    preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json={"plan": plan, "expected_version": 1},
        headers=ORIGIN,
    )
    assert preview.status_code == 200
    confirmed = client.post(
        "/api/v1/ads/marketing/plans/confirm",
        json={
            "plan": plan,
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 201
    response = client.get("/api/v1/ads/marketing/storage/integrity", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pass"
    assert body["owner_scoped"] is True
    assert body["counts"]["plans"] == 1
    assert body["counts"]["plan_revisions"] == 1
    assert body["counts"]["channel_executions"] == 2
    assert all(value == 0 for value in body["integrity"].values())
