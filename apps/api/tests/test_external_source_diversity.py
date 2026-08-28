# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import source_diversity_evaluation


def test_ten_source_diversity_safety_inputs():
    rows = [
        {
            "url": f"https://source-{i}.example/item",
            "content_hash": str(i),
            "provider": "p",
            "verification_status": "SUPPORTED",
            "freshness_status": "FRESH",
        }
        for i in range(3)
    ]
    result = source_diversity_evaluation(rows)
    assert result["independent_source_count"] == 3
