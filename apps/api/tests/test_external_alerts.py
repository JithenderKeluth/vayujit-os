# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import confidence_handoff


def test_alert_policy_inputs_are_bounded_by_confidence():
    result = confidence_handoff([], critical_unknowns=1)
    assert result["overall_confidence"] == 0
