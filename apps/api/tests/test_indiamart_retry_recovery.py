from __future__ import annotations

import httpx
import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from helpers.indiamart_certification import mission
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_planner import RECOVERY_ACTIONS
from vayujit_api.intelligence.external_durability import (
    BudgetExhausted,
    consume_budget,
    ensure_budget,
    recovery_actions,
)
from vayujit_api.intelligence.external_provider import HttpSearchProvider

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "failure_code,retryable",
    (
        ("timeout", True),
        ("network", True),
        ("search_rate_limited", True),
        ("server_error", True),
        ("service_unavailable", True),
        ("source_auth_failed", True),
        ("invalid_payload", True),
        ("unsafe_url", False),
        ("provider_disabled", False),
        ("bad_request", True),
    ),
)
def test_indiamart_retry_classification_matrix(
    client: TestClient, failure_code: str, retryable: bool
) -> None:
    setup_context(client)
    actions = recovery_actions(failure_code)
    assert actions
    assert all(
        action in RECOVERY_ACTIONS or action in {"retry_after", "skip_optional_source"}
        for action in actions
    )
    assert ("retry" in actions or "retry_after" in actions) is retryable


def test_indiamart_recovery_execution_is_idempotent(client: TestClient) -> None:
    setup_context(client)
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_DISCOVERY",
            "goal": "Recovery execution certification",
            "market": "IN",
            "category": "outdoors",
            "provider_mode": "LOCAL_DETERMINISTIC",
            "idempotency_key": "indiamart-recovery-execution",
        },
        headers=ORIGIN,
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    payload = {
        "failure_code": "timeout",
        "action": "retry",
        "idempotency_key": "indiamart-recovery-retry",
    }
    first = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    second = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["idempotent_reuse"] is False
    assert second.json()["idempotent_reuse"] is True


def test_indiamart_retry_and_provider_budgets_fail_closed(client: TestClient) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, "budget-certification")
        parent.budget_policy = {"max_retries": 1, "max_provider_requests": 1}
        db.flush()
        budget = ensure_budget(db, owner.id, parent)
        consume_budget(db, budget, dimension="retries")
        consume_budget(db, budget, dimension="provider_requests")
        with pytest.raises(BudgetExhausted):
            consume_budget(db, budget, dimension="retries")
        with pytest.raises(BudgetExhausted):
            consume_budget(db, budget, dimension="provider_requests")


@pytest.mark.parametrize(
    "action",
    (
        "retry",
        "reconcile",
        "refresh_source",
        "review_source",
        "review_evidence",
        "resolve_contradiction",
        "skip_optional_task",
        "cancel",
    ),
)
def test_indiamart_every_advertised_recovery_action_executes(
    client: TestClient, action: str
) -> None:
    setup_context(client)
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_DISCOVERY",
            "goal": f"Recovery action {action}",
            "market": "IN",
            "category": "outdoors",
            "provider_mode": "LOCAL_DETERMINISTIC",
            "idempotency_key": f"recovery-action-{action}",
        },
        headers=ORIGIN,
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    payload = {
        "failure_code": "timeout",
        "action": action,
        "idempotency_key": f"recovery-action-{action}-request",
    }
    first = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    replay = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == replay.status_code == 200
    assert first.json()["action"] == action
    assert first.json()["status"] == "COMPLETED"
    assert replay.json()["idempotent_reuse"] is True


def test_indiamart_retry_after_is_bounded_and_invalid_values_are_safe() -> None:
    request = httpx.Request("GET", "https://example.test")
    assert (
        HttpSearchProvider._retry_after(
            httpx.Response(429, headers={"Retry-After": "10"}, request=request)
        )
        == 10.0
    )
    assert (
        HttpSearchProvider._retry_after(
            httpx.Response(429, headers={"Retry-After": "999"}, request=request)
        )
        == 60.0
    )
    assert (
        HttpSearchProvider._retry_after(
            httpx.Response(429, headers={"Retry-After": "-4"}, request=request)
        )
        == 0.0
    )
    assert (
        HttpSearchProvider._retry_after(
            httpx.Response(429, headers={"Retry-After": "invalid"}, request=request)
        )
        is None
    )


def test_indiamart_recovery_api_two_session_race_has_one_durable_result(
    client: TestClient,
) -> None:
    """Concurrent identical recovery submissions resolve to one durable row."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from vayujit_api.intelligence.autonomous_models import (
        AutonomousResearchMission,
        AutonomousResearchRecovery,
    )
    from vayujit_api.intelligence.autonomous_schemas import AutonomousRecoveryRequest
    from vayujit_api.intelligence.autonomous_service import recover_mission

    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, "recovery-concurrency")
        mission_id = parent.id
        owner_id = owner.id
        db.commit()

    barrier = threading.Barrier(2)

    def invoke(_: int) -> tuple[bool, bool]:
        assert test_ai_integration.factory is not None
        with test_ai_integration.factory() as db:
            owner = db.get(User, owner_id)
            parent = db.get(AutonomousResearchMission, mission_id)
            assert owner is not None and parent is not None
            barrier.wait()
            result = recover_mission(
                db,
                owner,
                parent,
                AutonomousRecoveryRequest(
                    failure_code="timeout",
                    action="retry",
                    idempotency_key="recovery-concurrency-request",
                ),
            )
            return bool(result["idempotent_reuse"]), bool(result["status"] == "COMPLETED")

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(invoke, (1, 2)))

    with test_ai_integration.factory() as db:
        rows = list(
            db.scalars(
                select(AutonomousResearchRecovery).where(
                    AutonomousResearchRecovery.owner_id == owner_id,
                    AutonomousResearchRecovery.mission_id == mission_id,
                    AutonomousResearchRecovery.idempotency_key == "recovery-concurrency-request",
                )
            )
        )
    assert len(rows) == 1
    assert sum(reused for reused, _ in outcomes) == 1
    assert all(completed for _, completed in outcomes)


def test_indiamart_recovery_route_two_session_race(client: TestClient) -> None:
    """Concurrent authenticated HTTP submissions share one recovery identity."""
    setup_context(client)
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_DISCOVERY",
            "goal": "Route recovery concurrency",
            "market": "IN",
            "category": "outdoors",
            "provider_mode": "LOCAL_DETERMINISTIC",
            "idempotency_key": "route-recovery-concurrency",
        },
        headers=ORIGIN,
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    import threading
    from concurrent.futures import ThreadPoolExecutor

    barrier = threading.Barrier(2)
    payload = {
        "failure_code": "timeout",
        "action": "retry",
        "idempotency_key": "route-recovery-race",
    }

    def invoke(_: int) -> tuple[int, dict[str, object]]:
        barrier.wait()
        response = client.post(
            f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
            json=payload,
            headers=ORIGIN,
        )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(invoke, (1, 2)))
    assert [status for status, _ in outcomes] == [200, 200]
    bodies = [body for _, body in outcomes]
    assert sum(bool(body["idempotent_reuse"]) for body in bodies) == 1
    assert all(body["status"] == "COMPLETED" for body in bodies)
