# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import confidence_handoff


def test_confidence_handoff_safety_rules():
    one = [
        {
            "url": "https://a.example",
            "content_hash": "a",
            "verification_status": "VERIFIED",
            "freshness_status": "FRESH",
        }
    ]
    many = one + [
        {
            "url": "https://b.example",
            "content_hash": "b",
            "verification_status": "SUPPORTED",
            "freshness_status": "FRESH",
        }
    ]
    assert confidence_handoff(one)["overall_confidence"] < 0.8
    assert (
        confidence_handoff(many)["overall_confidence"]
        >= confidence_handoff(one)["overall_confidence"]
    )
