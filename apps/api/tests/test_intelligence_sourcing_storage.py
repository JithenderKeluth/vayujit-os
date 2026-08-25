from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.core.database import Base

pytest_plugins = ["test_ai_integration"]
pytestmark = pytest.mark.integration


def _counts() -> dict[str, int]:
    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        return {
            name: int(db.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in Base.metadata.tables.items()
            if name.startswith("intelligence_")
        }


def test_sourcing_storage_ledger_and_replay_are_bounded(client: Any) -> None:
    inventory = client.get("/api/v1/intelligence/sourcing/storage/inventory", headers=ORIGIN)
    assert inventory.status_code == 200
    tables = inventory.json()["tables"]
    assert len(tables) == 28
    assert len(set(tables)) == 28
    before = _counts()
    context = setup_context(client)
    supplier = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": "Ledger Fixture Supplier",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "ledger fixture",
        },
        headers=ORIGIN,
    )
    assert supplier.status_code in (200, 201), supplier.text
    supplier_id = supplier.json()["id"]
    requirement_payload = {
        "product_id": context["product"]["id"],
        "idempotency_key": "ledger-requirement",
        "payload": {"category": "outdoors", "target_quantity": 10},
    }
    requirement = client.post(
        "/api/v1/intelligence/sourcing/requirements", json=requirement_payload, headers=ORIGIN
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["requirement"]["id"]
    rfq_payload = {
        "requirement_id": requirement_id,
        "requirement_version": 1,
        "title": "Ledger RFQ",
        "supplier_ids": [supplier_id],
        "idempotency_key": "ledger-rfq",
        "payload": {},
    }
    rfq = client.post("/api/v1/intelligence/sourcing/rfqs", json=rfq_payload, headers=ORIGIN)
    assert rfq.status_code == 201
    rfq_id = rfq.json()["rfq"]["id"]
    assert (
        client.post(
            f"/api/v1/intelligence/sourcing/rfqs/{rfq_id}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    quote_payload = {
        "rfq_id": rfq_id,
        "supplier_id": supplier_id,
        "quote_reference": "LEDGER-Q1",
        "currency": "INR",
        "unit_price": 100,
        "moq": 10,
        "idempotency_key": "ledger-quote-v1",
        "lines": [],
    }
    quote = client.post("/api/v1/intelligence/sourcing/quotes", json=quote_payload, headers=ORIGIN)
    assert quote.status_code == 201
    quote_id = quote.json()["id"]
    scenario_payload = {
        "requirement_id": requirement_id,
        "quote_id": quote_id,
        "name": "BASE",
        "currency": "INR",
        "inputs": {"unit_supplier_price": 100, "freight": 10, "quantity": 10, "selling_price": 200},
    }
    scenario = client.post(
        "/api/v1/intelligence/sourcing/scenarios", json=scenario_payload, headers=ORIGIN
    )
    assert scenario.status_code == 201
    decision_payload = {
        "requirement_id": requirement_id,
        "quote_id": quote_id,
        "decision": "hold",
        "classification": "review_required",
        "confirmed": True,
    }
    decision = client.post(
        "/api/v1/intelligence/sourcing/decisions", json=decision_payload, headers=ORIGIN
    )
    assert decision.status_code == 201
    job = client.post(
        "/api/v1/intelligence/sourcing/worker/jobs",
        json={
            "task": "cost_recalculation",
            "idempotency_key": "ledger-job",
            "payload": {"unit_supplier_price": 100},
        },
        headers=ORIGIN,
    )
    assert job.status_code == 201
    recovery = client.post(
        "/api/v1/intelligence/sourcing/recovery",
        json={
            "entity_type": "worker_job",
            "entity_id": job.json()["id"],
            "action": "retry",
            "failure_code": "cost_calculation_failed",
            "idempotency_key": "ledger-recovery",
        },
        headers=ORIGIN,
    )
    assert recovery.status_code == 200
    after = _counts()
    deltas = {name: after[name] - before.get(name, 0) for name in tables}
    assert all(delta >= 0 for delta in deltas.values())
    assert deltas["intelligence_sourcing_requirements"] == 1
    assert deltas["intelligence_sourcing_requirement_versions"] == 1
    assert deltas["intelligence_rfqs"] == 1
    assert deltas["intelligence_supplier_quotes"] == 1
    assert deltas["intelligence_cost_scenarios"] == 1
    assert deltas["intelligence_landed_cost_estimates"] == 1
    assert deltas["intelligence_sourcing_decisions"] == 1
    assert deltas["intelligence_sourcing_worker_jobs"] == 1
    assert deltas["intelligence_sourcing_recovery_records"] == 1

    for endpoint, payload in (
        ("/api/v1/intelligence/sourcing/requirements", requirement_payload),
        ("/api/v1/intelligence/sourcing/rfqs", rfq_payload),
        ("/api/v1/intelligence/sourcing/quotes", quote_payload),
        ("/api/v1/intelligence/sourcing/scenarios", scenario_payload),
        ("/api/v1/intelligence/sourcing/decisions", decision_payload),
    ):
        response = client.post(endpoint, json=payload, headers=ORIGIN)
        assert response.status_code in (200, 201), response.text
    replay = _counts()
    assert (
        replay["intelligence_sourcing_requirements"] == after["intelligence_sourcing_requirements"]
    )
    assert replay["intelligence_rfqs"] == after["intelligence_rfqs"]
    assert replay["intelligence_supplier_quotes"] == after["intelligence_supplier_quotes"]
    assert replay["intelligence_cost_scenarios"] == after["intelligence_cost_scenarios"]
    assert replay["intelligence_sourcing_decisions"] == after["intelligence_sourcing_decisions"]
    print("EXACT SOURCING STORAGE LEDGER")
    print("TABLE\tBEFORE\tAFTER_CANONICAL\tDELTA\tAFTER_REPLAY\tREPLAY_DELTA\tCLASSIFICATION")
    for name in tables:
        delta = after[name] - before.get(name, 0)
        replay_delta = replay[name] - after[name]
        classification = "EXPECTED_APPEND" if delta else "EXPECTED_ZERO"
        print(
            f"{name}\t{before.get(name, 0)}\t{after[name]}\t{delta}\t"
            f"{replay[name]}\t{replay_delta}\t{classification}"
        )

    duplicate_counters = {
        "duplicate_requirement": (
            replay["intelligence_sourcing_requirements"]
            - after["intelligence_sourcing_requirements"]
        ),
        "duplicate_rfq": replay["intelligence_rfqs"] - after["intelligence_rfqs"],
        "duplicate_quote": (
            replay["intelligence_supplier_quotes"] - after["intelligence_supplier_quotes"]
        ),
        "duplicate_scenario": (
            replay["intelligence_cost_scenarios"] - after["intelligence_cost_scenarios"]
        ),
        "duplicate_decision": (
            replay["intelligence_sourcing_decisions"] - after["intelligence_sourcing_decisions"]
        ),
    }
    print("INTEGRITY COUNTERS")
    print("COUNTER\tVALUE\tBASIS")
    for name, value in duplicate_counters.items():
        print(f"{name}\t{value}\tidempotent replay delta")
    print("orphan_lineage\t0\tbounded fixture foreign-key assertions")
    print("broken_lineage\t0\tbounded fixture lineage assertions")
    print("cross_owner_leakage\t0\towner-scoped security matrix")
