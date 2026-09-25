from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_customs_schemas import CustomsTaxSnapshotCreate
from vayujit_api.intelligence.economic_customs_service import create_snapshot

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def economic(client: Any, key: str, currency: str = "USD") -> dict[str, Any]:
    fixture = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": key,
            "product_id": fixture["product"]["id"],
            "origin_country": "IN",
            "destination_country": "US",
            "target_quantity": "10",
            "quantity_unit": "unit",
            "base_currency": currency,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["context"]


def customs(client: Any, context: dict[str, Any], key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/contexts",
        json={
            "economic_context_id": context["id"],
            "idempotency_key": key,
            "origin_country": "IN",
            "destination_country": "US",
            "reporting_currency": "USD",
            "classification_code": "0101",
            "classification_scheme": "HS",
            "classification_provenance": "USER_PROVIDED",
            "status": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["context"]


def test_13e_preserves_leading_zero_classification_and_rejects_verification(
    client: Any,
) -> None:
    context = economic(client, "customs-context-leading-zero")
    customs_context = customs(client, context, "customs-leading-zero")
    evidence = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/classifications",
        json={
            "context_id": customs_context["id"],
            "idempotency_key": "classification-leading-zero",
            "classification_code": "010121",
            "classification_scheme": "HS",
            "jurisdiction": "US",
            "supplied_description": "Disposable fixture item",
            "source": "MANUAL",
            "provenance": "USER_PROVIDED",
            "freshness": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert evidence.status_code == 201, evidence.text
    assert evidence.json()["classification"]["classification_code"] == "010121"
    blocked = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/classifications",
        json={
            "context_id": customs_context["id"],
            "idempotency_key": "classification-verified",
            "classification_code": "010122",
            "classification_scheme": "HS",
            "jurisdiction": "US",
            "source": "MANUAL",
            "provenance": "VERIFIED",
        },
        headers=ORIGIN,
    )
    assert blocked.status_code == 422
    assert "VERIFIED" not in blocked.text


def test_13e_unknown_zero_conflict_and_regulatory_separation(client: Any) -> None:
    context = economic(client, "customs-context-evidence")
    customs_context = customs(client, context, "customs-evidence")
    for key, code in (("classification-one", "0101"), ("classification-two", "0102")):
        response = client.post(
            "/api/v1/intelligence/sourcing-economics/customs-tax/classifications",
            json={
                "context_id": customs_context["id"],
                "idempotency_key": key,
                "classification_code": code,
                "classification_scheme": "HS",
                "jurisdiction": "US",
                "source": "MANUAL",
                "provenance": "USER_PROVIDED",
                "freshness": "CURRENT",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    for key, rate, basis in (
        ("rate-zero", "0", "PRODUCT_VALUE"),
        ("rate-unknown", "0.10", "UNKNOWN"),
    ):
        response = client.post(
            "/api/v1/intelligence/sourcing-economics/customs-tax/rates",
            json={
                "context_id": customs_context["id"],
                "idempotency_key": key,
                "rate_kind": "DUTY",
                "category": "CUSTOMS_DUTY",
                "rate": rate,
                "basis": basis,
                "jurisdiction": "US",
                "source": "MANUAL",
                "provenance": "USER_PROVIDED",
                "freshness": "CURRENT",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    regulatory = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/regulatory-costs",
        json={
            "context_id": customs_context["id"],
            "idempotency_key": "regulatory-observed",
            "cost_category": "INSPECTION",
            "amount": "12.50",
            "currency": "USD",
            "requirement_type": "BIS",
            "requirement_state": "OBSERVED_REQUIREMENT",
            "source": "MANUAL",
            "provenance": "OBSERVED",
            "freshness": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert regulatory.status_code == 201, regulatory.text
    snapshot = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/snapshots",
        json={
            "context_id": customs_context["id"],
            "basis_inputs": {
                "PRODUCT_VALUE": {
                    "basis_type": "PRODUCT_VALUE",
                    "amount": "100",
                    "currency": "USD",
                }
            },
        },
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    payload = snapshot.json()["snapshot"]["payload"]
    assert payload["conflicts"]["classifications"] is True
    assert payload["regulatory_costs"][0]["requirement_state"] == "OBSERVED_REQUIREMENT"
    assert snapshot.json()["snapshot"]["completeness"] == "PARTIAL"


def test_13e_calculation_includes_known_customs_and_regulatory_lines(
    client: Any,
) -> None:
    context = economic(client, "customs-context-calculation")
    product = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "PRODUCT_COST",
            "amount": "100",
            "currency": "USD",
            "unit_basis": "PER_UNIT",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert product.status_code == 201, product.text
    customs_context = customs(client, context, "customs-calculation")
    classification = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/classifications",
        json={
            "context_id": customs_context["id"],
            "idempotency_key": "classification-calculation",
            "classification_code": "0101",
            "classification_scheme": "HS",
            "jurisdiction": "US",
            "source": "MANUAL",
            "provenance": "USER_PROVIDED",
            "freshness": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert classification.status_code == 201, classification.text
    rate = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/rates",
        json={
            "context_id": customs_context["id"],
            "classification_evidence_id": classification.json()["classification"]["id"],
            "idempotency_key": "rate-calculation",
            "rate_kind": "DUTY",
            "category": "CUSTOMS_DUTY",
            "rate": "0.10",
            "basis": "PRODUCT_VALUE",
            "jurisdiction": "US",
            "source": "MANUAL",
            "provenance": "OBSERVED",
            "freshness": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert rate.status_code == 201, rate.text
    snapshot = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/snapshots",
        json={
            "context_id": customs_context["id"],
            "basis_inputs": {
                "PRODUCT_VALUE": {
                    "basis_type": "PRODUCT_VALUE",
                    "amount": "100",
                    "currency": "USD",
                }
            },
        },
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    economic_snapshot = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert economic_snapshot.status_code == 201, economic_snapshot.text
    result = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{economic_snapshot.json()['snapshot']['id']}/calculate",
        json={
            "customs_tax_snapshot_id": snapshot.json()["snapshot"]["id"],
            "calculation_version": "landed-cost-v4",
            "policy_version": "known-cost-customs-tax-v1",
        },
        headers=ORIGIN,
    )
    assert result.status_code == 201, result.text
    body = result.json()
    assert float(body["calculation"]["total_included_cost"]) == 1010.0
    assert body["calculation"]["customs_tax_snapshot_id"] == snapshot.json()["snapshot"]["id"]
    assert any(line["category"] == "CUSTOMS_DUTY" for line in body["breakdown"])


def test_13e_concurrent_snapshot_creation_converges(client: Any) -> None:
    context = economic(client, "customs-context-concurrency")
    customs_context = customs(client, context, "customs-concurrency")
    factory = integration_helpers.factory
    assert factory is not None
    context_id = uuid.UUID(customs_context["id"])

    def create() -> tuple[str, bool]:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            row, reused = create_snapshot(
                db,
                owner,
                CustomsTaxSnapshotCreate(
                    context_id=context_id,
                    basis_inputs={"UNKNOWN": {"basis_type": "UNKNOWN"}},
                ),
            )
            return str(row.id), reused

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=30) for future in [pool.submit(create), pool.submit(create)]
        ]
    assert len({item[0] for item in results}) == 1
    assert {item[1] for item in results} == {False, True}


def test_13e_snapshot_reuse_and_owner_scope(client: Any) -> None:
    context = economic(client, "customs-context-idempotency")
    customs_context = customs(client, context, "customs-idempotency")
    payload = {
        "context_id": customs_context["id"],
        "basis_inputs": {"UNKNOWN": {"basis_type": "UNKNOWN"}},
    }
    first = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/snapshots",
        json=payload,
        headers=ORIGIN,
    )
    second = client.post(
        "/api/v1/intelligence/sourcing-economics/customs-tax/snapshots",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == second.status_code == 201
    assert second.json()["idempotent_reuse"] is True
    assert second.json()["snapshot"]["id"] == first.json()["snapshot"]["id"]
