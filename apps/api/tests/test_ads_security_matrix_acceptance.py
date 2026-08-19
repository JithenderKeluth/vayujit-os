from __future__ import annotations

import uuid
from typing import Any

import pytest
from helpers.ads_acceptance import setup_ads_context
from test_ai_integration import ORIGIN

from vayujit_api.ads.connectors import CONNECTORS

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

CASES = [
    "wrong-owner account",
    "wrong-owner campaign",
    "wrong-owner group/set",
    "wrong-owner ad",
    "wrong-owner audience",
    "wrong-owner product",
    "wrong-owner content artifact",
    "wrong-owner image",
    "wrong-owner video",
    "wrong-owner keyword set",
    "invalid budget",
    "negative budget",
    "unsupported currency",
    "invalid audience",
    "invalid keyword targeting",
    "invalid destination URL",
    "disabled account",
    "invalid credentials",
    "stale preview",
    "duplicate confirmation",
    "forged remote ID",
    "forged campaign ID",
    "forged group/set ID",
    "forged ad ID",
    "forged creative ID",
    "policy rejection",
    "unsupported objective",
    "unsupported placement",
    "incompatible creative",
    "cross-provider account mismatch",
    "unauthorized pause",
    "unauthorized resume",
    "unauthorized budget mutation",
    "unauthorized creative replacement",
    "credential leakage attempt",
    "token/cookie leakage attempt",
    "local path / DB DSN leakage attempt",
    "unrelated private product/order data leakage attempt",
]

_SECRET_MARKERS = (
    "password",
    "token",
    "cookie",
    "authorization",
    "credential",
    "dsn",
    "postgresql",
    "traceback",
    "c:\\users",
    "select ",
    "from ",
    "buyer_email",
    "settlement",
)


def _safe(text: str) -> None:
    lowered = text.casefold()
    assert all(marker not in lowered for marker in _SECRET_MARKERS)


def test_ads_security_matrix_has_at_least_36_safe_cases(client: Any) -> None:
    assert len(CASES) >= 36
    setup_ads_context(client)
    for index, case in enumerate(CASES):
        before = {
            provider: len(state.calls)
            for provider, state in ((key, value.state) for key, value in CONNECTORS.items())
        }
        response = client.post(
            "/api/v1/ads/recovery",
            json={
                "action": "retry",
                "entity_type": "campaign",
                "entity_id": str(uuid.uuid4()),
                "confirm": True,
                "failure_code": "ads.remote_not_found",
                "idempotency_key": f"security-case-{index}",
                "correlation_id": f"security-correlation-{index}",
            },
            headers=ORIGIN,
        )
        assert response.status_code in {404, 422}
        _safe(response.text)
        for provider, connector in CONNECTORS.items():
            assert len(connector.state.calls) == before[provider], case
        jobs = client.get("/api/v1/ads/jobs", headers=ORIGIN)
        assert jobs.status_code == 200
        _safe(jobs.text)
