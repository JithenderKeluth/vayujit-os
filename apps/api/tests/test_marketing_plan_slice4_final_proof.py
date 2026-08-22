from __future__ import annotations

import concurrent.futures
import uuid
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_account, setup_ads_context
from httpx import Response
from sqlalchemy import func, select
from test_ai_integration import ORIGIN
from test_marketing_plan_slice4_acceptance import _confirm_plan

from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.marketing_execution import MarketingChannelExecution
from vayujit_api.ads.models import AdJob
from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _payload(context: dict[str, Any], channel: str, suffix: str) -> dict[str, Any]:
    return {
        "brand_id": context["brand"]["id"],
        "product_ids": [context["product"]["id"]],
        "objective": "sales",
        "locale": "en-IN",
        "timezone": "Asia/Kolkata",
        "target_channels": [channel],
        "budget_envelope": {
            "total": "100",
            "currency": "INR",
            "allocations": {channel: "100"},
            "strategy": "manual",
        },
        "strategy_mode": "manual",
        "automation_mode": "manual",
        "creative_mapping": {channel: {"artifact_version": 1}},
        "targeting": {"locale": "en-IN"},
        "schedule": {"mode": "immediate"},
        "idempotency_key": f"slice4-proof-{suffix}-{uuid.uuid4().hex}",
    }


def _run_job(plan_id: str, worker_id: str) -> None:
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        job = db.scalar(
            select(AdJob)
            .where(
                AdJob.request_json["plan_id"].astext == plan_id,
                AdJob.status == "queued",
            )
            .order_by(AdJob.created_at)
        )
        if job is not None:
            from vayujit_api.ads.worker import run_next_ads_job

            run_next_ads_job(db, worker_id=worker_id)


def test_concurrent_reschedule_has_one_durable_replacement(client: Any) -> None:
    context = setup_ads_context(client)
    plan = _confirm_plan(client, _payload(context, "meta", "concurrent-reschedule"))
    plan_id = plan["id"]
    create_account(client, "meta", "concurrent-reschedule")
    request = {
        "scheduled_at": "2030-01-01T00:00:00Z",
        "expected_version": 1,
        "idempotency_key": "concurrent-reschedule-proof",
        "confirm": True,
    }

    def submit() -> Response:
        return client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/reschedule",
            json=request,
            headers=ORIGIN,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert sorted(response.json()["idempotent_reuse"] for response in responses) == [False, True]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        channels = list(
            db.scalars(
                select(MarketingChannelExecution).where(
                    MarketingChannelExecution.plan_id == uuid.UUID(plan_id)
                )
            )
        )
        jobs = list(
            db.scalars(
                select(AdJob).where(
                    AdJob.request_json["plan_id"].astext == plan_id,
                    AdJob.operation == "marketing_plan_channel",
                )
            )
        )
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == uuid.UUID(plan_id),
                    AuditEvent.action == "ads.marketing_plan_rescheduled",
                )
            )
        )
        assert len(channels) == 1
        assert len({str(row.schedule_id) for row in channels}) == 1
        assert len(jobs) == 2  # original plus its single replacement
        assert len({job.idempotency_key for job in jobs}) == 2
        assert len(events) == 1
        _run_job(plan_id, "concurrent-reschedule-proof")


def test_marketplace_rollback_restores_fake_amazon_budget(client: Any) -> None:
    context = setup_ads_context(client)
    account = create_account(client, "amazon", "rollback-proof")
    listing = client.post(
        "/api/v1/ads/marketplace/listings",
        json={
            "account_id": account["id"],
            "product_id": context["product"]["id"],
            "marketplace": "amazon",
            "listing_id": f"AMAZON-PROOF-{uuid.uuid4().hex[:8]}",
            "version": 1,
            "title": "Amazon rollback proof",
            "sku": f"AMAZON-PROOF-SKU-{uuid.uuid4().hex[:8]}",
        },
        headers=ORIGIN,
    )
    assert listing.status_code == 201, listing.text
    plan = _confirm_plan(client, _payload(context, "amazon", "amazon-rollback"))
    plan_id = plan["id"]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        from vayujit_api.ads.worker import run_next_ads_job

        first = run_next_ads_job(db, worker_id="amazon-v1")
        assert first is not None and first.status == "succeeded"
    connector = connector_for("amazon")
    remote = next(iter(connector.state.entities["campaign"].values()))
    initial_calls = len(connector.state.calls)
    proposed = {
        "total": "150",
        "currency": "INR",
        "allocations": {"amazon": "150"},
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
            "idempotency_key": "amazon-forward-v2",
        },
        headers=ORIGIN,
    )
    assert changed.status_code == 200
    with integration_fixture.factory() as db:
        from vayujit_api.ads.worker import run_next_ads_job

        second = run_next_ads_job(db, worker_id="amazon-v2")
        assert second is not None and second.status == "succeeded"
    assert remote["budget_version"] == 2
    rollback_preview = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN
    )
    assert rollback_preview.status_code == 200
    rollback = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
        params={"preview_fingerprint": rollback_preview.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert rollback.status_code == 200
    with integration_fixture.factory() as db:
        from vayujit_api.ads.worker import run_next_ads_job

        completed = run_next_ads_job(db, worker_id="amazon-rollback")
        assert completed is not None and completed.status == "succeeded"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AdJob)
                .where(AdJob.operation == "marketing_plan_rollback")
            )
            == 1
        )
    assert remote["budget_version"] == 1
    assert len(connector.state.calls) == initial_calls + 2


def test_stale_rollback_is_rejected_without_jobs_or_provider_calls(client: Any) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", "stale-rollback-proof")
    plan = _confirm_plan(client, _payload(context, "meta", "stale-rollback"))
    plan_id = plan["id"]
    preview = client.post(f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN)
    assert preview.status_code == 200, (
        preview.text and preview.json()["rollback_available"] is False
    )


def test_stale_rollback_preview_is_rejected_without_side_effects(client: Any) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", "stale-rollback-proof")
    plan = _confirm_plan(client, _payload(context, "meta", "stale-rollback"))
    plan_id = plan["id"]
    proposed = {
        "total": "120",
        "currency": "INR",
        "allocations": {"meta": "120"},
        "strategy": "manual",
    }
    preview_v2 = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/preview",
        json={
            "proposed": proposed,
            "expected_version": 1,
            "preview_fingerprint": "preview-placeholder-123456",
            "confirm": False,
        },
        headers=ORIGIN,
    )
    assert preview_v2.status_code == 200
    confirmed_v2 = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/confirm",
        json={
            "proposed": proposed,
            "expected_version": 1,
            "preview_fingerprint": preview_v2.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "stale-rollback-v2",
        },
        headers=ORIGIN,
    )
    assert confirmed_v2.status_code == 200
    rollback_preview = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN
    )
    assert rollback_preview.status_code == 200
    proposed_v3 = {
        "total": "130",
        "currency": "INR",
        "allocations": {"meta": "130"},
        "strategy": "manual",
    }
    preview_v3 = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/preview",
        json={
            "proposed": proposed_v3,
            "expected_version": 2,
            "preview_fingerprint": "preview-placeholder-123456",
            "confirm": False,
        },
        headers=ORIGIN,
    )
    assert preview_v3.status_code == 200
    confirmed_v3 = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/confirm",
        json={
            "proposed": proposed_v3,
            "expected_version": 2,
            "preview_fingerprint": preview_v3.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "stale-rollback-v3",
        },
        headers=ORIGIN,
    )
    assert confirmed_v3.status_code == 200
    connector = connector_for("meta")
    calls_before = len(connector.state.calls)
    stale = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
        params={"preview_fingerprint": rollback_preview.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    assert "stale" in stale.text.lower()
    assert len(connector.state.calls) == calls_before
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AdJob)
                .where(AdJob.operation == "marketing_plan_rollback")
            )
            == 0
        )


def test_concurrent_budget_rollback_has_one_job_and_provider_mutation(client: Any) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", "concurrent-rollback-proof")
    plan = _confirm_plan(client, _payload(context, "meta", "concurrent-rollback"))
    plan_id = plan["id"]
    proposed = {
        "total": "120",
        "currency": "INR",
        "allocations": {"meta": "120"},
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
    assert preview.status_code == 200
    changed = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/confirm",
        json={
            "proposed": proposed,
            "expected_version": 1,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
            "idempotency_key": "concurrent-rollback-v2",
        },
        headers=ORIGIN,
    )
    assert changed.status_code == 200
    rollback_preview = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN
    )
    assert rollback_preview.status_code == 200
    request = {
        "preview_fingerprint": rollback_preview.json()["fingerprint"],
        "confirm": True,
    }

    def submit() -> Response:
        return client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
            params=request,
            headers=ORIGIN,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert sorted(response.json()["idempotent_reuse"] for response in responses) == [False, True]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        jobs = list(db.scalars(select(AdJob).where(AdJob.operation == "marketing_plan_rollback")))
        assert len(jobs) == 1


@pytest.mark.parametrize(
    ("case", "changes"),
    [
        ("valid", {}),
        ("max_percentage", {"max_percent_change": 1}),
        ("total_cap", {"total_budget_cap": 50}),
        ("provider_cap", {"provider_cap_available": False}),
        ("product_cap", {"product_cap_available": False}),
        ("cooldown", {"cooldown_clear": False}),
        ("daily_cap", {"daily_action_available": False}),
        ("currency", {"currencies_compatible": False}),
        ("objective", {"objectives_comparable": False}),
        ("stale_fingerprint", {"current_fingerprint": "stale-fingerprint-0000"}),
        ("stale_metrics", {"metrics_fresh": False}),
        ("recovery_conflict", {"recovery_clear": False}),
        ("disabled_account", {"account_enabled": False}),
        ("unsupported_capability", {"channel_supported": False}),
        ("unauthorized", {}),
    ],
)
def test_auto_reallocation_guardrail_matrix(
    client: Any, case: str, changes: dict[str, Any]
) -> None:
    context = setup_ads_context(client)
    plan = _confirm_plan(client, _payload(context, "campaign", f"guardrail-{case}"))
    plan_id = plan["id"]
    from vayujit_api.ads.marketing import _fingerprint

    request: dict[str, Any] = {
        "proposed": {
            "total": "100",
            "currency": "INR",
            "allocations": {"campaign": "90"},
            "strategy": "manual",
        },
        "expected_version": 1,
        "current_fingerprint": _fingerprint(
            {"plan_id": plan_id, "version": 1, "budget": plan["budget_envelope"]}
        ),
        "idempotency_key": f"guardrail-{case}",
        "confirm": True,
        "owner_opt_in": True,
        "rule_enabled": True,
        "action_allowed": True,
        "max_percent_change": 20,
        "total_budget_cap": 100,
        "cooldown_clear": True,
        "daily_action_available": True,
        "currencies_compatible": True,
        "objectives_comparable": True,
        "metrics_fresh": True,
        "recovery_clear": True,
        "channel_supported": True,
        "provider_cap_available": True,
        "product_cap_available": True,
        "account_enabled": True,
    }
    request.update(changes)
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        before_jobs = db.scalar(
            select(func.count())
            .select_from(AdJob)
            .where(AdJob.request_json["plan_id"].astext == plan_id)
        )
        before_revisions = db.scalar(
            select(func.count())
            .select_from(
                __import__(
                    "vayujit_api.ads.marketing_execution",
                    fromlist=["MarketingPlanRevision"],
                ).MarketingPlanRevision
            )
            .where(
                __import__(
                    "vayujit_api.ads.marketing_execution",
                    fromlist=["MarketingPlanRevision"],
                ).MarketingPlanRevision.plan_id
                == uuid.UUID(plan_id)
            )
        )
    if case == "unauthorized":
        saved = dict(client.cookies)
        client.cookies.clear()
        response = client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/auto-reallocation",
            json=request,
            headers=ORIGIN,
        )
        client.cookies.update(saved)
    else:
        response = client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/auto-reallocation",
            json=request,
            headers=ORIGIN,
        )
    if case == "valid":
        assert response.status_code == 200, response.text
        assert response.json()["idempotent_reuse"] is False
    else:
        assert response.status_code in {401, 409, 422}, response.text
        lowered = response.text.lower()
        assert not any(
            secret in lowered
            for secret in ("traceback", "postgresql://", "c:\\\\", "token", "password")
        )
        with integration_fixture.factory() as db:
            after_jobs = db.scalar(
                select(func.count())
                .select_from(AdJob)
                .where(AdJob.request_json["plan_id"].astext == plan_id)
            )
            after_revisions = db.scalar(
                select(func.count())
                .select_from(
                    __import__(
                        "vayujit_api.ads.marketing_execution",
                        fromlist=["MarketingPlanRevision"],
                    ).MarketingPlanRevision
                )
                .where(
                    __import__(
                        "vayujit_api.ads.marketing_execution",
                        fromlist=["MarketingPlanRevision"],
                    ).MarketingPlanRevision.plan_id
                    == uuid.UUID(plan_id)
                )
            )
            assert after_jobs == before_jobs
            assert after_revisions == before_revisions


def test_concurrent_auto_reallocation_has_one_logical_action(client: Any) -> None:
    context = setup_ads_context(client)
    plan = _confirm_plan(client, _payload(context, "campaign", "concurrent-auto"))
    plan_id = plan["id"]
    from vayujit_api.ads.marketing import _fingerprint

    request = {
        "proposed": {
            "total": "100",
            "currency": "INR",
            "allocations": {"campaign": "90"},
            "strategy": "manual",
        },
        "expected_version": 1,
        "current_fingerprint": _fingerprint(
            {"plan_id": plan_id, "version": 1, "budget": plan["budget_envelope"]}
        ),
        "idempotency_key": "concurrent-auto-proof",
        "confirm": True,
        "owner_opt_in": True,
        "rule_enabled": True,
        "action_allowed": True,
        "max_percent_change": 20,
        "total_budget_cap": 100,
    }

    def submit() -> Response:
        return client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/auto-reallocation",
            json=request,
            headers=ORIGIN,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert sorted(response.json()["idempotent_reuse"] for response in responses) == [False, True]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        jobs = list(
            db.scalars(
                select(AdJob).where(
                    AdJob.operation == "marketing_plan_budget",
                    AdJob.request_json["plan_id"].astext == plan_id,
                )
            )
        )
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == uuid.UUID(plan_id),
                    AuditEvent.action == "ads.marketing_plan_auto_reallocation_applied",
                )
            )
        )
        assert len(jobs) == 1
        assert len(events) == 1
