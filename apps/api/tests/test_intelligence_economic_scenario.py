from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_scenario_schemas import EconomicScenarioRun
from vayujit_api.intelligence.economic_scenario_service import run_scenario

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _baseline(
    client: Any, key: str, *, product_amount: str = "10", freight_amount: str = "5"
) -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = setup_context(client)
    context_response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": key,
            "product_id": fixture["product"]["id"],
            "origin_country": "IN",
            "destination_country": "US",
            "target_quantity": "10",
            "quantity_unit": "unit",
            "base_currency": "USD",
        },
        headers=ORIGIN,
    )
    assert context_response.status_code == 201, context_response.text
    context = context_response.json()["context"]
    for category, amount, basis in (
        ("PRODUCT_COST", product_amount, "PER_UNIT"),
        ("FREIGHT", freight_amount, "ONE_TIME"),
    ):
        response = client.post(
            "/api/v1/intelligence/sourcing-economics/components",
            json={
                "context_id": context["id"],
                "category": category,
                "amount": amount,
                "currency": "USD",
                "unit_basis": basis,
                "provenance": "CONFIGURED",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    snapshot = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    calculation = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot.json()['snapshot']['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert calculation.status_code == 201, calculation.text
    return context, calculation.json()["calculation"]


def _scenario(
    client: Any,
    context: dict[str, Any],
    calculation: dict[str, Any],
    key: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/contexts/{context['id']}",
        json={
            "idempotency_key": key,
            "name": "Explicit unit-cost what-if",
            "description": "Hypothetical scenario only; not a forecast or recommendation.",
            "baseline_calculation_id": calculation["id"],
            "overrides": overrides,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_13f_scenario_reuses_13b_and_preserves_baseline(client: Any) -> None:
    context, baseline = _baseline(client, "13f-scenario-context")
    scenario = _scenario(
        client,
        context,
        baseline,
        "13f-product-cost-scenario",
        {"product_unit_cost": "12", "reason": "Test an explicit supplier unit-cost assumption."},
    )
    result_response = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario['id']}/run",
        json={"idempotency_key": "13f-run-one"},
        headers=ORIGIN,
    )
    assert result_response.status_code == 201, result_response.text
    result = result_response.json()
    assert result["comparability"] == "COMPARABLE"
    assert result["baseline"]["total"] == "105.00000000"
    assert result["scenario"]["total"] == "125.00000000"
    assert result["delta"]["absolute"] == "20.00000000"
    assert result["delta"]["percentage"] == "19.04761905"
    assert all(item["provenance"] == "SCENARIO_OVERRIDE" for item in result["changed_inputs"])
    assert "forecast" not in result
    repeated = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario['id']}/run",
        json={"idempotency_key": "13f-run-one"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == result["id"]
    assert repeated.json()["idempotent_reuse"] is True
    baseline_detail = client.get(
        f"/api/v1/intelligence/sourcing-economics/calculations/{baseline['id']}",
        headers=ORIGIN,
    )
    assert baseline_detail.status_code == 200, baseline_detail.text
    assert float(baseline_detail.json()["calculation"]["total_included_cost"]) == 105.0


def test_13f_one_variable_sensitivity_is_deterministic(client: Any) -> None:
    context, baseline = _baseline(client, "13f-sensitivity-context")
    scenario = _scenario(
        client,
        context,
        baseline,
        "13f-sensitivity-scenario",
        {"target_quantity": 10, "reason": "Provide an explicit sensitivity baseline."},
    )
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario['id']}/sensitivity",
        json={
            "idempotency_key": "13f-unit-cost-sensitivity",
            "points": [
                {"dimension": "product_unit_cost", "value": "8"},
                {"dimension": "product_unit_cost", "value": "12"},
            ],
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dimension"] == "product_unit_cost"
    assert len(body["points"]) == 2
    assert all(point["provenance"] == "SCENARIO_OVERRIDE" for point in body["points"])
    assert all("forecast" not in point for point in body["points"])
    repeated = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario['id']}/sensitivity",
        json={
            "idempotency_key": "13f-unit-cost-sensitivity",
            "points": [
                {"dimension": "product_unit_cost", "value": "8"},
                {"dimension": "product_unit_cost", "value": "12"},
            ],
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == body["id"]
    assert repeated.json()["idempotent_reuse"] is True


def test_13f_zero_baseline_has_no_percentage_delta(client: Any) -> None:
    context, baseline = _baseline(
        client, "13f-zero-context", product_amount="0", freight_amount="0"
    )
    scenario = _scenario(
        client,
        context,
        baseline,
        "13f-zero-scenario",
        {"product_unit_cost": "1", "reason": "Test a non-zero change from a zero baseline."},
    )
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario['id']}/run",
        json={"idempotency_key": "13f-zero-run"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    assert response.json()["delta"]["percentage"] is None


def test_13f_rejects_cross_owner_baseline(client: Any) -> None:
    fixture = setup_context(client)
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/contexts/{uuid.uuid4()}",
        json={
            "idempotency_key": "13f-owner-isolation",
            "name": "Cross owner attempt",
            "baseline_calculation_id": str(uuid.uuid4()),
            "overrides": {"target_quantity": 2, "reason": "Must be rejected."},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 404, response.text
    assert fixture["product"]["id"]


def test_13f_concurrent_same_key_converges(client: Any) -> None:
    context, baseline = _baseline(client, "13f-concurrent-context")
    scenario = _scenario(
        client,
        context,
        baseline,
        "13f-concurrent-scenario",
        {"product_unit_cost": "11", "reason": "Concurrent deterministic run."},
    )
    factory = integration_helpers.factory
    assert factory is not None
    scenario_id = uuid.UUID(scenario["id"])

    def run() -> tuple[str, bool]:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            result = run_scenario(
                db,
                owner,
                scenario_id,
                EconomicScenarioRun(idempotency_key="13f-concurrent-run"),
            )
            return str(result["id"]), bool(result["idempotent_reuse"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=45) for future in [pool.submit(run), pool.submit(run)]]
    assert len({item[0] for item in results}) == 1
    assert {item[1] for item in results} == {False, True}
