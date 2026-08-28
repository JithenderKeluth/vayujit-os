# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import verify_external_evidence


def test_canonical_verified_external_pipeline_lineage_gate():
    result = verify_external_evidence(
        {
            "owner_id": "o",
            "source_profile": "p",
            "fetch_id": "f",
            "search_result_id": "r",
            "requested_url": "https://a.example",
            "final_url": "https://a.example",
            "content_hash": "h",
            "content": "evidence",
            "freshness_status": "FRESH",
        },
        expected_owner_id="o",
    )
    assert result["verification_state"] == "SUPPORTED"
