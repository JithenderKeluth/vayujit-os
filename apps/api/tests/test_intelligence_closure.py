# ruff: noqa: E501
import pytest

from vayujit_api.intelligence.closure import (
    ECONOMIC_CLASSIFICATIONS,
    RESTRICTION_ACTIONS,
    RESTRICTION_ATTRIBUTES,
    economic_input,
    estimate_economics,
    evaluate_physical_rules,
    evaluate_policy_hierarchy,
    evidence_quality,
    legal_risk_flags,
    rank_opportunities,
    source_diversity,
    validate_restriction_matrix,
    validate_score_weights,
)


def test_physical_units_and_volume_are_normalized() -> None:
    result = evaluate_physical_rules(
        {
            "weight": {"value": 1800, "unit": "g"},
            "length": {"value": 20, "unit": "cm"},
            "width": 10,
            "height": 5,
        },
        {"weight_kg": 2, "volumetric_weight_kg": 1},
    )
    assert result["status"] == "PASS"
    assert result["normalized"]["weight_kg"] == pytest.approx(1.8)
    assert result["normalized"]["volume_cm3"] == pytest.approx(1000)


def test_physical_over_limit_blocks() -> None:
    assert evaluate_physical_rules({"weight_kg": 3.1}, {"weight_kg": 2})["status"] == "BLOCK"


def test_policy_hard_block_precedence() -> None:
    assert (
        evaluate_policy_hierarchy(
            {"GLOBAL": ["BLOCK"], "CATEGORY": ["ALLOW"], "MISSION": ["ALLOW"]}
        )["action"]
        == "BLOCK"
    )
    assert (
        evaluate_policy_hierarchy({"GLOBAL": ["WARN"], "CATEGORY": ["BLOCK"]})["action"] == "BLOCK"
    )


def test_policy_explicit_override_is_auditable_result() -> None:
    result = evaluate_policy_hierarchy(
        {"GLOBAL": ["BLOCK"], "MISSION": ["ALLOW"]}, authorized_override=True
    )
    assert result["action"] == "ALLOW"
    assert result["winning_level"] == "MISSION"


def test_restriction_matrix_has_nineteen_attributes_and_four_actions() -> None:
    assert len(RESTRICTION_ATTRIBUTES) == 19
    assert set(RESTRICTION_ACTIONS) == {"ALLOW", "WARN", "REVIEW_REQUIRED", "BLOCK"}
    assert len(validate_restriction_matrix({key: "ALLOW" for key in RESTRICTION_ATTRIBUTES})) == 19


@pytest.mark.parametrize("value", [{"unknown": "BLOCK"}, {"glass": "NOPE"}, {"liquid": ""}])
def test_restriction_matrix_rejects_unknown_or_invalid_actions(value) -> None:
    with pytest.raises(ValueError):
        validate_restriction_matrix(value)


def test_economics_has_classified_inputs_and_capital() -> None:
    result = estimate_economics(
        {
            "selling_price": economic_input(1000, "OBSERVED", evidence_id="e1"),
            "sourcing_cost": economic_input(300, "ESTIMATED", reason="fixture"),
            "moq": 10,
            "launch_allowance": 500,
            "working_capital_buffer": 200,
        }
    )
    assert set(result["inputs"]["selling_price"]) >= {
        "classification",
        "value",
        "currency",
        "source_evidence_id",
        "confidence",
    }
    assert "estimated_initial_capital" in result["outputs"]
    assert result["supplier_confirmed"] is False


def test_observed_input_requires_evidence_and_currency() -> None:
    with pytest.raises(ValueError):
        economic_input(10, "OBSERVED")
    with pytest.raises(ValueError):
        economic_input(10, "ASSUMED", currency="US")
    assert set(ECONOMIC_CLASSIFICATIONS) == {"OBSERVED", "ASSUMED", "ESTIMATED", "UNKNOWN"}


def test_source_diversity_does_not_count_duplicates() -> None:
    result = source_diversity(
        ["marketplace_fixture", "marketplace_fixture", "trend_fixture"], ["a", "a", "b"]
    )
    assert result["independent_source_count"] == 2
    assert result["critical_signal_source_count"] == 2


def test_evidence_quality_reports_missing_and_stale_ratio() -> None:
    result = evidence_quality(
        freshness=["fresh", "stale"],
        source_diversity_score=0.4,
        verification_states=["verified", "unverified"],
        observation_count=2,
        critical_signal_completeness=0.5,
        stale_evidence_ratio=0.5,
    )
    assert 0 <= result["quality_score"] <= 1
    assert result["confidence"] == result["quality_score"]
    assert "critical_signals" in result["missing_evidence"]


def test_legal_flags_never_claim_clearance() -> None:
    result = legal_risk_flags(title="Apple compatible case", brand="Apple")
    assert result["label"] == "LEGAL REVIEW MAY BE REQUIRED"
    assert result["legal_clearance"] is False


def test_score_weights_require_known_nonnegative_sum_one_hundred() -> None:
    dimensions = ["demand", "economics"]
    assert validate_score_weights({"demand": 60, "economics": 40}, dimensions)["demand"] == 60
    for value in (
        {"demand": 50, "economics": 49},
        {"demand": -1, "economics": 101},
        {"demand": 50, "other": 50},
    ):
        with pytest.raises(ValueError):
            validate_score_weights(value, dimensions)


def test_ranking_is_stable_and_hard_blocks_last() -> None:
    ranked = rank_opportunities(
        [
            {"id": "blocked", "score": 99, "confidence": 1, "risk": 1, "hard_blocked": True},
            {"id": "eligible-b", "score": 70, "confidence": 0.8, "risk": 20, "hard_blocked": False},
            {"id": "eligible-a", "score": 70, "confidence": 0.8, "risk": 20, "hard_blocked": False},
        ]
    )
    assert [row["id"] for row in ranked] == ["eligible-a", "eligible-b", "blocked"]


@pytest.mark.parametrize(
    "payload",
    [
        {"credentials": "x"},
        {"token": "x"},
        {"cookie": "x"},
        {"db_dsn": "x"},
        {"local_path": "C:/secret"},
        {"prompt": "secret"},
        {"provider_output": "x"},
        {"sql": "drop"},
        {"traceback": "stack"},
        {"environment": "prod"},
    ],
)
def test_security_payload_terms_are_not_used_as_public_error_data(payload) -> None:
    # Pure closure responses contain only bounded labels and numeric outputs.
    output = legal_risk_flags(title="Disposable fixture", attributes=payload)
    assert "secret" not in str(output).lower()
    assert "password" not in str(output).lower()
