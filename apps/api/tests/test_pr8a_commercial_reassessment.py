"""Focused PR-8A immutable commercial reassessment coverage."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare
from test_pr7a_supplier_engagement import _engagement, _seed_current_proceed, _supplier_and_contact

pytestmark = pytest.mark.integration
pytest_plugins = ["test_pr5b_landed_cost"]


def _context(client: TestClient, key: str) -> tuple[str, str, str]:
    opportunity_id, assessment_id = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity_id, supplier_id)
    engagement = _engagement(client, opportunity_id, supplier_id, contact_id, key)
    response = _ok(
        client.post(
            "/api/v1/intelligence/supplier-responses",
            json={
                "supplier_id": supplier_id,
                "opportunity_id": opportunity_id,
                "engagement_id": engagement["id"],
                "channel": "EMAIL",
                "sender_identity": "sales@fixture.example",
                "recipient_identity": "buyer@example.test",
                "provider_message_id": key,
                "raw_content": (
                    "Product: Reusable kids lunch box\n"
                    "SKU: KLB-500\n"
                    "Price: INR 112.50 per unit\n"
                    "MOQ: 500 units\n"
                    "Lead time: 21 days"
                ),
                "trust_environment": "DETERMINISTIC_TEST",
                "evidence_environment": "DETERMINISTIC_TEST",
                "idempotency_key": f"{key}-response",
            },
            headers=ORIGIN,
        )
    )
    _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{response['id']}/review",
            json={
                "decision": "ACCEPT_EXTRACTION",
                "provenance": "HUMAN",
                "idempotency_key": f"{key}-review",
            },
            headers=ORIGIN,
        )
    )
    promoted = _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{response['id']}/promote",
            headers=ORIGIN,
        )
    )
    return opportunity_id, assessment_id, promoted["promotion"]["id"]


def test_pr8a_reassessment_is_durable_scoped_and_human_reviewed(client: TestClient) -> None:
    opportunity_id, assessment_id, promotion_id = _context(client, "pr8a-happy")
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/commercial-reassessments"
    )
    payload = {
        "idempotency_key": "pr8a-blocked",
        "promotion_id": promotion_id,
        "scenario_key": "reviewed-quote",
        "assumptions": [
            {
                "key": "freight_cost",
                "value": "2500",
                "unit": "per_shipment",
                "currency": "INR",
                "reason": "Explicit seller scenario",
            },
            {
                "key": "freight_currency",
                "value": "INR",
                "reason": "Explicit seller scenario",
            },
            {"key": "origin", "value": "IN", "reason": "Explicit seller scenario"},
            {"key": "destination", "value": "IN", "reason": "Explicit seller scenario"},
        ],
    }
    blocked = _ok(client.post(url, json=payload, headers=ORIGIN))
    assert blocked["status"] == "BLOCKED"
    assert blocked["current_readiness_id"]
    assert blocked["quote_evidence"]["claim_semantics"] == "SOURCE_PROVIDED_CLAIM"
    assert "landed_cost_request_required" in blocked["blockers"]

    replay = _ok(client.post(url, json=payload, headers=ORIGIN))
    assert replay["id"] == blocked["id"]
    reviewed = _ok(
        client.post(
            f"{url}/{blocked['id']}/review",
            json={
                "idempotency_key": "pr8a-blocked-review",
                "decision": "KEEP_UNDER_REVIEW",
                "provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    assert reviewed["review"]["decision"] == "KEEP_UNDER_REVIEW"
    assert reviewed["review"]["provenance"] == "HUMAN"


def test_pr8a_reassessment_rejects_unreviewed_or_cross_context(client: TestClient) -> None:
    opportunity_id, assessment_id, promotion_id = _context(client, "pr8a-safety")
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/commercial-reassessments"
    )
    # A foreign UUID cannot cross the owner/product boundary.
    response = client.post(
        url,
        json={
            "idempotency_key": "pr8a-foreign",
            "promotion_id": "00000000-0000-0000-0000-000000000001",
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409}
    assert promotion_id


def test_pr8a_reassessment_delegates_ready_calculations(client: TestClient) -> None:
    opportunity_id, assessment_id, promotion_id = _context(client, "pr8a-ready")
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/commercial-reassessments"
    )
    response = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8a-ready",
                "promotion_id": promotion_id,
                "assumptions": [
                    {
                        "key": "freight_cost",
                        "value": "2500",
                        "unit": "per_shipment",
                        "currency": "INR",
                        "reason": "Explicit seller scenario",
                    },
                    {
                        "key": "freight_currency",
                        "value": "INR",
                        "reason": "Explicit seller scenario",
                    },
                    {"key": "origin", "value": "IN", "reason": "Explicit seller scenario"},
                    {"key": "destination", "value": "IN", "reason": "Explicit seller scenario"},
                ],
                "landed_cost": {
                    "idempotency_key": "pr8a-ready-landed",
                    "base_currency": "INR",
                    "target_quantity": "500",
                    "quantity_unit": "unit",
                },
                "unit_economics": {
                    "idempotency_key": "pr8a-ready-unit",
                    "selling_price": "250",
                    "selling_price_currency": "INR",
                    "selling_price_provenance": "DETERMINISTIC_TEST",
                    "quantity": "500",
                    "selling_cost_components": [
                        {
                            "key": "selling_cost",
                            "basis": "PER_UNIT",
                            "amount": "25.10",
                            "currency": "INR",
                            "required": True,
                            "provenance": "DETERMINISTIC_TEST",
                            "marker": "DETERMINISTIC_TEST",
                            "reason": "Explicit deterministic scenario",
                        }
                    ],
                },
            },
            headers=ORIGIN,
        )
    )
    assert response["status"] == "READY_FOR_HUMAN_REVIEW"
    assert response["current_landed_cost_id"]
    assert response["current_unit_economics_id"]
    assert response["current"]["landed_cost"]["calculation"]["per_unit_cost"]
    assert response["current"]["unit_economics"]["per_unit_contribution"]
    assert response["current"]["landed_cost"]["calculation"]["per_unit_cost"] == "117.50000000"
    assert response["current"]["unit_economics"]["per_unit_contribution"] == "107.40000000"
    assert response["current"]["unit_economics"]["capital_required"] == "58750.00000000"
    assert response["current"]["unit_economics"]["capital_headroom"] == "241250.00000000"
