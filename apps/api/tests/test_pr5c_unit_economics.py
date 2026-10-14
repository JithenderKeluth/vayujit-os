"""Focused PR-5C unit-economics and capital-fit validation."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare

pytest_plugins = ["test_pr5b_landed_cost"]

pytestmark = pytest.mark.integration


@pytest.fixture
def prepared(pr56_client: TestClient) -> tuple[TestClient, str, str]:
    oid, aid = _prepare(pr56_client)
    readiness_url = (
        f"/api/v1/intelligence/product-opportunities/{oid}/assessments/{aid}/commercial-readiness"
    )
    assumptions = [
        {
            "key": "supplier_unit_price",
            "value": "100.125",
            "unit": "per_unit",
            "currency": "INR",
            "reason": "Deterministic PR-5C landed-cost setup",
        },
        {"key": "supplier_currency", "value": "INR", "reason": "Deterministic PR-5C setup"},
        {
            "key": "freight_cost",
            "value": "2500",
            "unit": "per_shipment",
            "currency": "INR",
            "reason": "Deterministic PR-5C setup",
        },
        {"key": "freight_currency", "value": "INR", "reason": "Deterministic PR-5C setup"},
        {"key": "origin", "value": "IN", "reason": "Deterministic PR-5C setup"},
        {"key": "destination", "value": "IN", "reason": "Deterministic PR-5C setup"},
    ]
    ready = _ok(
        pr56_client.post(
            readiness_url,
            json={
                "idempotency_key": "pr5c-ready",
                "scenario_key": "deterministic-pr5c",
                "assumptions": assumptions,
            },
            headers=ORIGIN,
        )
    )
    assert ready["readiness"]["calculations"]["LANDED_UNIT_COST"]["status"] == "READY"
    landed = _ok(
        pr56_client.post(
            f"/api/v1/intelligence/product-opportunities/{oid}/assessments/{aid}/landed-cost",
            json={
                "idempotency_key": "pr5c-landed",
                "base_currency": "INR",
                "target_quantity": "500",
                "quantity_unit": "unit",
            },
            headers=ORIGIN,
        )
    )
    assert landed["calculable"]
    return pr56_client, oid, aid


def _url(oid: str, aid: str) -> str:
    return (
        f"/api/v1/intelligence/product-opportunities/{oid}/assessments/{aid}"
        "/commercial/unit-economics"
    )


def _component(
    *, key: str = "referral", basis: str = "PERCENT_OF_SELLING_PRICE", **extra: Any
) -> dict[str, Any]:
    return {
        "key": key,
        "basis": basis,
        "rate": "10" if basis == "PERCENT_OF_SELLING_PRICE" else None,
        "amount": None if basis == "PERCENT_OF_SELLING_PRICE" else "50",
        "currency": "INR",
        "required": True,
        "provenance": "ASSUMED",
        "marker": "DETERMINISTIC_TEST",
        "reason": "Explicit PR-5C deterministic scenario",
        **extra,
    }


def test_pr5c_readiness_arithmetic_idempotency_history_and_projection(
    prepared: tuple[TestClient, str, str],
) -> None:
    api, oid, aid = prepared
    url = _url(oid, aid)
    blocked = _ok(
        api.post(
            url,
            json={
                "idempotency_key": "pr5c-missing-fee",
                "selling_price": "250",
                "selling_price_currency": "INR",
            },
            headers=ORIGIN,
        )
    )
    assert blocked["status"] == "BLOCKED"
    assert "required_selling_cost_components" in blocked["missing_inputs"]

    payload = {
        "idempotency_key": "pr5c-ready-result",
        "selling_price": "250",
        "selling_price_currency": "INR",
        "selling_price_provenance": "DETERMINISTIC_TEST",
        "quantity": "500",
        "scenario_key": "deterministic-pr5c",
        "selling_cost_components": [
            _component(),
            _component(key="closing", basis="PER_ORDER"),
            _component(key="returns", basis="PER_UNIT", amount=None, required=False),
        ],
    }
    result = _ok(api.post(url, json=payload, headers=ORIGIN))
    assert result["status"] == "READY"
    assert result["selling_price_provenance"] == "DETERMINISTIC_TEST"
    assert result["per_unit_landed_cost"] == "105.12500000"
    assert result["per_unit_selling_cost"] == "25.10000000"
    assert result["per_unit_total_cost"] == "130.22500000"
    assert result["per_unit_contribution"] == "119.77500000"
    assert result["contribution_margin"] == "0.47910000"
    assert result["capital_available"] == "300000.00000000"
    assert result["capital_required"] == "52562.50000000"
    assert result["capital_fit_status"] == "FITS"
    assert result["capital_headroom"] == "247437.50000000"
    assert result["order_economics"]["sales_quantity"] is None
    assert any(row["key"] == "returns" for row in result["unknown_excluded"])
    assert any(row["key"] == "tax" for row in result["unknown_excluded"])

    replay = _ok(api.post(url, json=payload, headers=ORIGIN))
    assert replay["id"] == result["id"] and replay["idempotent_reuse"] is True
    changed_price = dict(payload)
    changed_price["idempotency_key"] = "pr5c-changed-price"
    changed_price["selling_price"] = "90"
    negative = _ok(api.post(url, json=changed_price, headers=ORIGIN))
    assert negative["id"] != result["id"]
    assert negative["per_unit_contribution"] == "-24.22500000"
    assert negative["capital_fit_status"] == "FITS"
    changed_fee = dict(payload)
    changed_fee["idempotency_key"] = "pr5c-changed-fee"
    changed_fee["selling_cost_components"] = [
        _component(rate="12"),
        _component(key="closing", basis="PER_ORDER"),
        _component(key="returns", basis="PER_UNIT", amount=None, required=False),
    ]
    fee_result = _ok(api.post(url, json=changed_fee, headers=ORIGIN))
    assert fee_result["id"] != result["id"]
    changed_quantity = dict(payload)
    changed_quantity["idempotency_key"] = "pr5c-shortfall"
    changed_quantity["quantity"] = "3000"
    shortfall = _ok(api.post(url, json=changed_quantity, headers=ORIGIN))
    assert shortfall["id"] != result["id"]
    assert shortfall["capital_fit_status"] == "DOES_NOT_FIT"
    assert shortfall["capital_shortfall"] == "15375.00000000"

    history = _ok(api.get(url + "/history", headers=ORIGIN))
    assert len(history) == 4
    latest = _ok(api.get(url, headers=ORIGIN))
    assert latest["id"] == shortfall["id"]
    projection = _ok(
        api.get(
            f"/api/v1/intelligence/product-opportunities/{oid}/sourcing-economics",
            headers=ORIGIN,
        )
    )
    assert projection["unit_economics"]["id"] == shortfall["id"]
    assert projection["unit_economics"]["capital_fit_status"] == "DOES_NOT_FIT"


def test_pr5c_currency_and_invalid_price_are_safe(prepared: tuple[TestClient, str, str]) -> None:
    api, oid, aid = prepared
    url = _url(oid, aid)
    zero = _ok(
        api.post(
            url,
            json={
                "idempotency_key": "pr5c-zero",
                "selling_price": "0",
                "selling_price_currency": "INR",
                "selling_cost_components": [_component()],
            },
            headers=ORIGIN,
        )
    )
    assert zero["status"] == "BLOCKED" and "selling_price_positive" in zero["missing_inputs"]
    mismatch = _ok(
        api.post(
            url,
            json={
                "idempotency_key": "pr5c-fx-missing",
                "selling_price": "250",
                "selling_price_currency": "USD",
                "selling_cost_components": [_component()],
            },
            headers=ORIGIN,
        )
    )
    assert mismatch["status"] == "BLOCKED" and any(
        "explicit_fx" in item for item in mismatch["missing_inputs"]
    )
