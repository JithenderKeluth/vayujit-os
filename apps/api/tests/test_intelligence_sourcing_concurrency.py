from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.sourcing_models import (
    CostScenario,
    RequestForQuote,
    SampleEvaluation,
    SourcingApproval,
    SourcingDecision,
    SourcingRecoveryRecord,
    SourcingScoreEvaluation,
    SupplierQuote,
)
from vayujit_api.intelligence.sourcing_schemas import RFQCreate
from vayujit_api.intelligence.sourcing_service import (
    create_rfq,
)

pytest_plugins = ["test_ai_integration"]
pytestmark = pytest.mark.integration


def _parallel(work: Callable[[], Any]) -> list[Any]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(lambda _: work(), range(2)))


def _owner_session() -> tuple[Any, User]:
    assert integration_helpers.factory is not None
    db = integration_helpers.factory()
    owner = db.scalar(select(User).where(User.email == "owner@example.com"))
    assert owner is not None
    return db, owner


def test_concurrent_rfq_approval_quote_sample_cost_and_score(client: Any) -> None:
    context = setup_context(client)
    supplier = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": "Concurrent Fixture Supplier",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "concurrency fixture",
        },
        headers=ORIGIN,
    )
    assert supplier.status_code in (200, 201), supplier.text
    supplier_id = supplier.json()["id"]
    requirement = client.post(
        "/api/v1/intelligence/sourcing/requirements",
        json={
            "product_id": context["product"]["id"],
            "idempotency_key": "concurrent-requirement",
            "payload": {"category": "outdoors", "target_quantity": 20},
        },
        headers=ORIGIN,
    )
    assert requirement.status_code == 201, requirement.text
    requirement_id = requirement.json()["requirement"]["id"]
    rfq_payload = {
        "requirement_id": requirement_id,
        "requirement_version": 1,
        "title": "Concurrent RFQ",
        "supplier_ids": [supplier_id],
        "idempotency_key": "concurrent-rfq",
        "payload": {},
    }

    def rfq_call() -> Any:
        db, owner = _owner_session()
        try:
            row, reused = create_rfq(db, owner, RFQCreate(**rfq_payload))
            return str(row.id), reused
        finally:
            db.close()

    rfq_results = _parallel(rfq_call)
    assert len({result[0] for result in rfq_results}) == 1
    rfq_id = rfq_results[0][0]
    assert {result[1] for result in rfq_results} == {False, True}

    def approve_call() -> int:
        response = client.post(
            f"/api/v1/intelligence/sourcing/rfqs/{rfq_id}/approve", headers=ORIGIN
        )
        return response.status_code

    assert set(_parallel(approve_call)) <= {200, 409}
    assert (
        client.get(f"/api/v1/intelligence/sourcing/rfqs/{rfq_id}", headers=ORIGIN).json()["status"]
        == "approved"
    )

    quote_payload = {
        "rfq_id": rfq_id,
        "supplier_id": supplier_id,
        "quote_reference": "CONCURRENT-QUOTE",
        "currency": "INR",
        "unit_price": 125,
        "moq": 20,
        "idempotency_key": "concurrent-quote-v1",
        "lines": [],
    }
    quote_responses = _parallel(
        lambda: client.post(
            "/api/v1/intelligence/sourcing/quotes", json=quote_payload, headers=ORIGIN
        )
    )
    assert all(response.status_code == 201 for response in quote_responses), [
        r.text for r in quote_responses
    ]
    quote_ids = {response.json()["id"] for response in quote_responses}
    assert len(quote_ids) == 1
    quote_id = next(iter(quote_ids))

    sample = client.post(
        "/api/v1/intelligence/sourcing/samples",
        json={"rfq_id": rfq_id, "supplier_id": supplier_id, "quantity": 1},
        headers=ORIGIN,
    )
    assert sample.status_code == 201, sample.text
    sample_id = sample.json()["id"]
    evaluations = _parallel(
        lambda: client.post(
            f"/api/v1/intelligence/sourcing/samples/{sample_id}/evaluate",
            json={"decision": "PASS", "dimensions": {"quality": 5}, "notes": "same decision"},
            headers=ORIGIN,
        )
    )
    assert {response.status_code for response in evaluations} <= {200, 201}
    assert len({response.json()["id"] for response in evaluations}) == 1

    scenario_payload = {
        "requirement_id": requirement_id,
        "quote_id": quote_id,
        "name": "BASE",
        "currency": "INR",
        "inputs": {"unit_supplier_price": 125, "freight": 10, "quantity": 20, "selling_price": 250},
    }
    scenario_results = _parallel(
        lambda: client.post(
            "/api/v1/intelligence/sourcing/scenarios", json=scenario_payload, headers=ORIGIN
        )
    )
    assert all(response.status_code == 201 for response in scenario_results), [
        r.text for r in scenario_results
    ]
    assert len({response.json()["id"] for response in scenario_results}) == 1

    score_payload = {
        "requirement_id": requirement_id,
        "quote_id": quote_id,
        "model_version": "v1",
        "inputs": {"supplier_verification": 80, "supplier_verification_evidence": "manual"},
    }
    score_results = _parallel(
        lambda: client.post(
            "/api/v1/intelligence/sourcing/scores/evaluate", json=score_payload, headers=ORIGIN
        )
    )
    assert all(response.status_code == 200 for response in score_results), [
        r.text for r in score_results
    ]
    assert len({response.json()["evaluation"]["id"] for response in score_results}) == 1

    decision_payload = {
        "requirement_id": requirement_id,
        "quote_id": quote_id,
        "decision": "hold",
        "classification": "review_required",
        "confirmed": True,
    }
    decision_results = _parallel(
        lambda: client.post(
            "/api/v1/intelligence/sourcing/decisions", json=decision_payload, headers=ORIGIN
        )
    )
    assert all(response.status_code == 201 for response in decision_results), [
        r.text for r in decision_results
    ]
    assert len({response.json()["id"] for response in decision_results}) == 1
    decision_id = decision_results[0].json()["id"]

    approval_results = _parallel(
        lambda: client.post(
            f"/api/v1/intelligence/sourcing/decisions/{decision_id}/approve",
            json={"note": "concurrent approval"},
            headers=ORIGIN,
        )
    )
    assert all(response.status_code == 200 for response in approval_results), [
        r.text for r in approval_results
    ]

    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        assert db.scalar(select(func.count()).select_from(RequestForQuote)) == 1
        assert db.scalar(select(func.count()).select_from(SupplierQuote)) == 1
        assert db.scalar(select(func.count()).select_from(SampleEvaluation)) == 1
        assert db.scalar(select(func.count()).select_from(CostScenario)) == 1
        assert db.scalar(select(func.count()).select_from(SourcingScoreEvaluation)) == 1
        assert db.scalar(select(func.count()).select_from(SourcingDecision)) == 1
        assert db.scalar(select(func.count()).select_from(SourcingApproval)) == 1


def test_concurrent_recovery_is_idempotent(client: Any) -> None:
    setup_context(client)
    job = client.post(
        "/api/v1/intelligence/sourcing/worker/jobs",
        json={"task": "cost_recalculation", "idempotency_key": "recovery-job", "payload": {}},
        headers=ORIGIN,
    )
    assert job.status_code == 201, job.text
    payload = {
        "entity_type": "worker_job",
        "entity_id": job.json()["id"],
        "action": "retry",
        "failure_code": "cost_calculation_failed",
        "idempotency_key": "concurrent-recovery",
        "reason": "bounded recovery test",
    }
    responses = _parallel(
        lambda: client.post("/api/v1/intelligence/sourcing/recovery", json=payload, headers=ORIGIN)
    )
    assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
    assert len({response.json()["id"] for response in responses}) == 1
    assert {response.json()["idempotent_reuse"] for response in responses} == {False, True}
    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        assert db.scalar(select(func.count()).select_from(SourcingRecoveryRecord)) == 1
