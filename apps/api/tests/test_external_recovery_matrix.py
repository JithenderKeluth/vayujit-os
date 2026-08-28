from __future__ import annotations

import os
import uuid

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_WEB_FETCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS"] = "example.org"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_recovery_matrix_executes_every_catalog_code_and_advertised_action(
    client: TestClient,
) -> None:
    setup_context(client)
    catalog_response = client.get("/api/v1/intelligence/external/recovery/catalog")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    codes = catalog["failure_codes"]
    assert len(codes) == 21
    assert len(set(codes)) == 21

    from vayujit_api.intelligence.external_durability import recovery_actions

    evidence: list[dict[str, object]] = []
    for failure_code in codes:
        actions = recovery_actions(failure_code)
        assert actions, failure_code
        for action in actions:
            idempotency_key = f"matrix-{failure_code}-{action}-{uuid.uuid4()}"
            response = client.post(
                "/api/v1/intelligence/external/recovery",
                json={
                    "action": action,
                    "failure_code": failure_code,
                    "idempotency_key": idempotency_key,
                    "correlation_id": f"matrix-{failure_code}",
                },
                headers=ORIGIN,
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["failure_code"] == failure_code
            assert result["action"] == action
            assert result["available_actions"] == actions
            assert result["safe_reason_code"] == f"EXTERNAL_{failure_code.upper()}"
            assert result["idempotent_reuse"] is False

            repeated = client.post(
                "/api/v1/intelligence/external/recovery",
                json={
                    "action": action,
                    "failure_code": failure_code,
                    "idempotency_key": idempotency_key,
                    "correlation_id": f"matrix-{failure_code}",
                },
                headers=ORIGIN,
            )
            assert repeated.status_code == 200
            assert repeated.json()["idempotent_reuse"] is True
            evidence.append(
                {
                    "failure_code": failure_code,
                    "safe_message": result["safe_reason_code"],
                    "allowed_actions": actions,
                    "action_executed": action,
                    "result_state": result["status"],
                    "retryable": action in {"retry", "retry_after", "refresh_search"},
                    "side_effect_count": 0,
                    "result": result["status"],
                }
            )

    # The matrix is deliberately emitted as bounded evidence, not raw rows or payloads.
    print({"failure_code_count": len(codes), "cases": evidence})
    assert len(evidence) >= 21

    from test_ai_integration import factory

    from vayujit_api.audit.models import AuditEvent
    from vayujit_api.intelligence.external_models import (
        ExternalExecution,
        ExternalFetch,
        ExternalRecoveryAction,
        ExternalSearchRequest,
        ExternalSearchResult,
    )

    assert factory is not None
    with factory() as db:
        recovery_count = db.scalar(select(func.count()).select_from(ExternalRecoveryAction))
        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "external.recovery.executed")
        )
        assert recovery_count == len(evidence)
        assert audit_count == len(evidence)
        assert db.scalar(select(func.count()).select_from(ExternalExecution)) == 0
        assert db.scalar(select(func.count()).select_from(ExternalSearchRequest)) == 0
        assert db.scalar(select(func.count()).select_from(ExternalSearchResult)) == 0
        assert db.scalar(select(func.count()).select_from(ExternalFetch)) == 0

    for failure_code, invalid_action in (
        ("search_rate_limited", "retry"),
        ("unsafe_url", "retry_after"),
        ("domain_disabled", "refresh_search"),
        ("budget_exhausted", "retry"),
        ("prompt_injection_detected", "retry"),
    ):
        response = client.post(
            "/api/v1/intelligence/external/recovery",
            json={
                "action": invalid_action,
                "failure_code": failure_code,
                "idempotency_key": f"invalid-{failure_code}-{uuid.uuid4()}",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 422
        assert "not allowed" in response.text.lower()

    forged = client.post(
        "/api/v1/intelligence/external/recovery",
        json={
            "action": "retry",
            "failure_code": "search_provider_unavailable",
            "execution_id": str(uuid.uuid4()),
            "idempotency_key": f"forged-{uuid.uuid4()}",
        },
        headers=ORIGIN,
    )
    assert forged.status_code == 404
    assert "external execution not found" in forged.text.lower()
