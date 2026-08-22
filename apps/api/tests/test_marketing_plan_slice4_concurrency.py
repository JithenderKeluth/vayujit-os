from __future__ import annotations

import concurrent.futures
import uuid
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import setup_ads_context
from httpx import Response
from sqlalchemy import func, select
from test_ai_integration import ORIGIN

from vayujit_api.ads.marketing_execution import MarketingPlanRevision
from vayujit_api.ads.models import AdJob
from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _plan_payload(context: dict[str, Any]) -> dict[str, Any]:
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
            "allocations": {"social": "60", "campaign": "40"},
            "strategy": "manual",
        },
        "strategy_mode": "manual",
        "automation_mode": "manual",
        "creative_mapping": {"social": {"artifact_version": 1}},
        "targeting": {"locale": "en-IN"},
        "schedule": {"mode": "immediate"},
        "idempotency_key": f"concurrency-{uuid.uuid4().hex}",
    }


def _confirm(client: Any, payload: dict[str, Any]) -> dict[str, Any]:
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


def test_concurrent_budget_reallocation_has_one_logical_commit(client) -> None:
    context = setup_ads_context(client)
    plan = _confirm(client, _plan_payload(context))
    plan_id = plan["id"]
    proposed = {
        "total": "100",
        "currency": "INR",
        "allocations": {"social": "50", "campaign": "50"},
        "strategy": "manual",
    }
    preview = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/budget/preview",
        json={
            "proposed": proposed,
            "expected_version": 1,
            "preview_fingerprint": "unused-preview-input",
            "confirm": False,
            "idempotency_key": "concurrent-budget",
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    request = {
        "proposed": proposed,
        "expected_version": 1,
        "preview_fingerprint": preview.json()["fingerprint"],
        "confirm": True,
        "idempotency_key": "concurrent-budget",
    }

    def submit() -> Response:
        return client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/reallocation/confirm",
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
        jobs = [
            item
            for item in db.scalars(select(AdJob))
            if item.request_json.get("plan_id") == str(plan_id)
            and item.operation == "marketing_plan_budget"
        ]
        assert len(jobs) == 2
        assert len({item.idempotency_key for item in jobs}) == 2
        revisions = list(
            db.scalars(
                select(MarketingPlanRevision).where(MarketingPlanRevision.plan_id == plan_id)
            )
        )
        assert [item.version for item in revisions] == [1, 2]
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == plan_id,
                    AuditEvent.action == "ads.marketing_plan_budget_reallocated",
                )
            )
        )
        assert len(events) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AdJob)
                .where(
                    AdJob.operation == "marketing_plan_budget",
                    AdJob.request_json["plan_id"].astext == str(plan_id),
                )
            )
            == 2
        )
