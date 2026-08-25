from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vayujit_api.intelligence.sourcing_closure import (
    capital_requirement,
    concentration,
    convert_currency,
    critic,
    evaluate_rules,
    landed_cost,
    negotiation_delta,
    safe_report,
    score_candidate,
    sensitivity,
    sourcing_decision,
    validate_duty_tax,
    validate_fx,
    validate_incoterm,
    validate_logistics,
    validate_shipping_mode,
)


def test_shipping_modes_and_incoterms_are_bounded() -> None:
    assert validate_shipping_mode("air") == "AIR"
    assert validate_incoterm("cif") == "CIF"
    with pytest.raises(ValueError):
        validate_shipping_mode("teleport")
    with pytest.raises(ValueError):
        validate_incoterm("CASH_ON_DELIVERY")


def test_logistics_duty_tax_and_fx_are_explicit_assumptions() -> None:
    logistics = validate_logistics(
        {
            "origin": "IN",
            "destination": "US",
            "shipping_mode": "SEA",
            "incoterm": "FOB",
            "carton_length": 50,
            "carton_width": 40,
            "carton_height": 20,
            "classification": "ASSUMED",
        }
    )
    assert logistics["volumetric_weight"] == 8
    assert logistics["responsibility_notice"] == "VERIFY INCOTERM RESPONSIBILITIES BEFORE ORDER"
    assert (
        validate_duty_tax(
            {"duty_percent": 12, "classification": "CONFIGURED", "reason": "manual tariff review"}
        )["duty_percent"]
        == 12
    )
    fx = validate_fx(
        {"from_currency": "USD", "to_currency": "INR", "rate": 83, "classification": "OBSERVED"}
    )
    assert convert_currency(2, "USD", "INR", fx)["label"] == "ESTIMATED_CONVERSION"
    assert convert_currency(2, "USD", "INR")["label"] == "NOT DIRECTLY COMPARABLE"
    expired = {**fx, "valid_until": datetime.now(UTC) - timedelta(days=1)}
    assert convert_currency(2, "USD", "INR", expired)["comparable"] is False
    with pytest.raises(ValueError):
        validate_fx({"from_currency": "USD", "to_currency": "INR", "rate": 0})


def test_landed_cost_confidence_and_capital_timeline() -> None:
    result = landed_cost(
        {
            "unit_supplier_price": 100,
            "freight": 10,
            "quantity": 10,
            "unit_supplier_price_classification": "SUPPLIER_QUOTED",
            "freight_classification": "ASSUMED",
        }
    )
    assert result["landed_cost_per_unit"] == 11
    assert result["confidence"] == "INSUFFICIENT"
    incomplete = landed_cost({"quantity": 1})
    assert incomplete["confidence"] == "INSUFFICIENT"
    capital = capital_requirement(
        {"sample_costs": 20, "deposit": 100, "balance": 100, "ads_launch_allowance": 30}
    )
    assert capital["initial_cash_required"] == 120
    assert {item["event"] for item in capital["timed_cash_requirements"]} >= {
        "sample",
        "deposit",
        "Ads launch",
    }


def test_sensitivity_score_critic_rules_and_decision_are_explainable() -> None:
    inputs = {
        "unit_supplier_price": 100,
        "freight": 10,
        "selling_price": 250,
        "quantity": 1,
        "ads_cac": 15,
    }
    assert {item["scenario"] for item in sensitivity(inputs)} >= {
        "supplier_price_+10%",
        "freight_+20%",
    }
    score = score_candidate(
        {"supplier_verification": 90, "supplier_verification_evidence": "manual-check"}
    )
    assert sum(item["weight"] for item in score["dimensions"]) == 100
    assert score["confidence"] == "INSUFFICIENT"
    findings = critic({"supplier_risk": 80, "sample_result": "FAIL"})
    assert {item["finding"] for item in findings} == {"supplier_risk", "sample_result"}
    rules = evaluate_rules({"moq": 100}, {"max_moq": 50})
    assert rules["action"] == "BLOCK"
    assert sourcing_decision(85, confidence="HIGH") == "STRONG_CANDIDATE"
    assert sourcing_decision(None) == "INSUFFICIENT_EVIDENCE"
    assert concentration(1) == "SINGLE_SOURCE"
    assert concentration(0) == "INSUFFICIENT_EVIDENCE"


def test_negotiation_delta_and_safe_reports() -> None:
    delta = negotiation_delta({"unit_price": 100, "moq": 500}, {"unit_price": 90, "moq": 500})
    assert delta["overall"] == "IMPROVED"
    assert negotiation_delta({"unit_price": 100}, {"moq": 500})["overall"] == "NOT_COMPARABLE"
    payload = {"notes": "<script>alert(1)</script>", "status": "review"}
    assert "<script>" not in safe_report(payload, "html")
    assert "notes" in safe_report(payload, "markdown")
