from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence.external_intelligence import verify_external_evidence

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_indiamart_malicious_claims_are_inert_and_responses_are_private(client: TestClient) -> None:
    context = setup_context(client)
    malicious = (
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg/onload=alert(1)>",
        "&lt;script&gt;",
        '"><iframe src=evil></iframe>',
        "{{constructor.constructor('alert(1)')()}}",
    )
    for value in malicious:
        decision = verify_external_evidence(
            {
                "owner_id": "owner",
                "source_profile": "indiamart-local",
                "fetch_id": "fetch",
                "search_result_id": "result",
                "requested_url": "https://www.indiamart.com/item",
                "final_url": "https://www.indiamart.com/item",
                "content_hash": "hash",
                "correlation_id": "corr",
                "provider": "INDIAMART",
                "content": value,
                "freshness_status": "FRESH",
                "malformed": True,
            },
            expected_owner_id="owner",
        )
        assert decision["verification_state"] == "REJECTED"
    response = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "privacy-safe", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    payload = json.dumps(response.json()).lower()
    forbidden = (
        "authorization",
        "bearer ",
        "cookie",
        "dsn",
        "c:\\",
        "traceback",
        "raw_payload",
        "customer_email",
        "private_phone",
    )
    assert all(term not in payload for term in forbidden)
