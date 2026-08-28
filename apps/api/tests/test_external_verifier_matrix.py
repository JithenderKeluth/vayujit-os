# ruff: noqa: E501
from copy import deepcopy

import pytest

from vayujit_api.intelligence.external_intelligence import verify_external_evidence

BASE = {
    "owner_id": "owner-a",
    "source_profile": "approved",
    "fetch_id": "fetch-a",
    "search_result_id": "result-a",
    "requested_url": "https://example.org/a",
    "final_url": "https://example.org/a",
    "content_hash": "hash-a",
    "content": "valid evidence",
    "freshness_status": "FRESH",
    "provider": "fixture",
}

CASES = {
    "valid fresh VERIFIED": ({"verification_method": "manual"}, "VERIFIED"),
    "valid fresh SUPPORTED": ({}, "SUPPORTED"),
    "AGING": ({"freshness_status": "AGING"}, "SUPPORTED"),
    "STALE": ({"freshness_status": "STALE"}, "REJECTED"),
    "EXPIRED": ({"freshness_status": "EXPIRED"}, "REJECTED"),
    "UNKNOWN freshness": ({"freshness_status": "UNKNOWN"}, "REJECTED"),
    "missing source profile": ({"source_profile": None}, "REJECTED"),
    "missing fetch": ({"fetch_id": None}, "REJECTED"),
    "missing search-result lineage": ({"search_result_id": None}, "REJECTED"),
    "missing requested URL": ({"requested_url": None}, "REJECTED"),
    "missing final URL": ({"final_url": None}, "REJECTED"),
    "missing content hash": ({"content_hash": None}, "REJECTED"),
    "incorrect content hash": ({"expected_content_hash": "other"}, "REJECTED"),
    "cross-owner fetch": ({"owner_id": "owner-b"}, "REJECTED"),
    "cross-owner mission": ({"mission_owner_id": "owner-b"}, "REJECTED"),
    "cross-owner task": ({"task_owner_id": "owner-b"}, "REJECTED"),
    "blocked source": ({"blocked": True}, "REJECTED"),
    "unsafe provenance URL": ({"unsafe_provenance": True}, "REJECTED"),
    "empty content": ({"content": ""}, "REJECTED"),
    "malformed content": ({"malformed": True}, "REJECTED"),
    "prompt-injection content": ({"prompt_injection_detected": True}, "REJECTED"),
    "unsupported claim type": ({"claim_type": "SECRET"}, "REJECTED"),
    "duplicate Evidence": ({"duplicate": True}, "REJECTED"),
    "wrong correlation ID": ({"correlation_id": "wrong"}, "REJECTED"),
    "wrong provider/source lineage": ({"provider": "other"}, "REJECTED"),
}


@pytest.mark.parametrize("label,case", CASES.items(), ids=CASES.keys())
def test_external_verifier_matrix_has_explicit_cases(label, case):
    changes, expected = case
    candidate = deepcopy(BASE)
    candidate.update(changes)
    kwargs = {"expected_owner_id": "owner-a"}
    if label == "wrong correlation ID":
        kwargs["expected_correlation_id"] = "expected"
    if label == "wrong provider/source lineage":
        kwargs["expected_provider"] = "expected"
    result = verify_external_evidence(candidate, **kwargs)
    assert result["verification_state"] == expected
    assert result["method"]
    assert "content" not in result
