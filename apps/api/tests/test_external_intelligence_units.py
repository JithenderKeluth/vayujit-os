# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import (
    confidence_handoff,
    contradiction_identity,
    source_diversity_evaluation,
)


def test_reverse_pair_identity_is_order_independent():
    assert contradiction_identity("m", "PRICE", "a", "b") == contradiction_identity(
        "m", "PRICE", "b", "a"
    )


def test_source_diversity_does_not_count_mirrors_as_independent():
    rows = [
        {
            "url": "https://a.example/x",
            "content_hash": "same",
            "provider": "p",
            "verification_status": "SUPPORTED",
            "freshness_status": "FRESH",
        },
        {
            "url": "https://b.example/x",
            "content_hash": "same",
            "provider": "p",
            "verification_status": "SUPPORTED",
            "freshness_status": "FRESH",
        },
    ]
    result = source_diversity_evaluation(rows)
    assert result["mirrored_source_count"] == 1
    assert result["independent_source_count"] == 2


def test_confidence_blocks_single_unverified_and_expired_evidence():
    result = confidence_handoff(
        [
            {
                "url": "https://a.example",
                "content_hash": "x",
                "verification_status": "UNVERIFIED",
                "freshness_status": "EXPIRED",
            }
        ]
    )
    assert result["overall_confidence"] < 0.8
