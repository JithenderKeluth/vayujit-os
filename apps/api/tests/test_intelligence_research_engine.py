from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from vayujit_api.intelligence.policy import (
    FreshnessPolicy,
    UnsafeURL,
    enforce_access_method,
    freshness_status,
    normalize_quantity,
    safe_external_content,
    validate_metadata,
    validate_source_url,
)
from vayujit_api.intelligence.research_engine import DEFAULT_WEIGHTS, FIXTURES, _key, _norm


@pytest.mark.parametrize(
    "value",
    [
        "file:///tmp/a",
        "ftp://example.com",
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://169.254.169.254/latest",
        "http://10.0.0.1/x",
        "http://192.168.1.2/x",
        "http://172.16.0.1/x",
        "https://user:pass@example.com",
        "https://example.com:8080/x",
        "https://[::1]/",
        "http://0.0.0.0",
        "http://metadata.google.internal/x",
        "http://localhost.localdomain/x",
        "https://.localHost/x",
    ],
)
def test_security_matrix_rejects_unsafe_sources(value: str) -> None:
    with pytest.raises(UnsafeURL):
        validate_source_url(value)


@pytest.mark.parametrize("method", ["scrape", "browser", "shell", "file", "proxy", "crawler"])
def test_security_matrix_rejects_unapproved_access(method: str) -> None:
    with pytest.raises(HTTPException):
        enforce_access_method(method)


@pytest.mark.parametrize(
    "payload",
    [
        {"token": "x"},
        {"password": "x"},
        {"api_key": "x"},
        {"secret": "x"},
        {"credentials": {"value": "x"}},
        {"headers": {"authorization": "x"}},
        {"nested": [{"cookie": "x"}]},
        {"provider_secret": {"key": "x"}},
        {"raw_token_value": "x"},
    ],
)
def test_security_matrix_rejects_sensitive_metadata(payload: dict[str, object]) -> None:
    with pytest.raises(HTTPException):
        validate_metadata(payload)


def test_security_matrix_rejects_oversized_content_and_invalid_units() -> None:
    with pytest.raises(HTTPException):
        safe_external_content("x" * 20_001)
    with pytest.raises(HTTPException):
        normalize_quantity(1, "inch")


def test_deterministic_provider_is_diverse_and_weights_are_complete() -> None:
    assert len(FIXTURES) >= 8
    assert {fixture.trend_state for fixture in FIXTURES} >= {"emerging", "declining", "seasonal"}
    assert any(fixture.review_moat for fixture in FIXTURES)
    assert any(not fixture.prices for fixture in FIXTURES)
    assert any(fixture.restrictions for fixture in FIXTURES)
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_candidate_identity_uses_source_reference_market_and_normalized_title() -> None:
    fixture = FIXTURES[0]
    assert _norm("  Bamboo-Drawer   Organizer ") == "bamboo drawer organizer"
    assert _key("source-a", fixture) == _key("source-a", fixture)
    assert _key("source-a", fixture) != _key("source-b", fixture)


def test_freshness_and_observation_policies_are_explicit() -> None:
    observed = datetime.now(UTC) - timedelta(hours=10)
    policy = FreshnessPolicy(fresh_seconds=3600, aging_seconds=12 * 3600, stale_seconds=48 * 3600)
    assert freshness_status(observed, policy=policy) == "aging"
    assert freshness_status(observed, ttl_seconds=1) == "expired"
    assert validate_source_url("https://example.com/catalog") == "https://example.com/catalog"
