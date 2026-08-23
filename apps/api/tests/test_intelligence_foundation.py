from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.policy import (
    FreshnessPolicy,
    UnsafeURL,
    enforce_access_method,
    freshness_status,
    normalize_quantity,
    safe_external_content,
    validate_source_url,
)


def test_source_url_policy_rejects_unsafe_targets() -> None:
    for value in (
        "file:///tmp/evidence.txt",
        "http://localhost/private",
        "http://127.0.0.1:8000/",
        "https://user:secret@example.com/",
        "ftp://example.com/data",
    ):
        with pytest.raises(UnsafeURL):
            validate_source_url(value)


def test_source_url_policy_accepts_public_https() -> None:
    assert validate_source_url("https://example.com/catalog") == "https://example.com/catalog"


def test_source_access_policy_rejects_arbitrary_scraping() -> None:
    with pytest.raises(HTTPException):
        enforce_access_method("scrape")
    assert enforce_access_method("manual_entry") == "manual_entry"


def test_freshness_is_policy_driven() -> None:
    observed = datetime.now(UTC) - timedelta(hours=10)
    policy = FreshnessPolicy(fresh_seconds=3600, aging_seconds=12 * 3600, stale_seconds=48 * 3600)
    assert freshness_status(observed, policy=policy) == "aging"
    assert freshness_status(observed, ttl_seconds=1) == "expired"


def test_evidence_content_is_bounded() -> None:
    with pytest.raises(HTTPException):
        safe_external_content("x" * 101, max_length=100)
    assert safe_external_content("observed price") == "observed price"


def test_opportunity_status_model_is_local_and_explicit() -> None:
    row = IntelligenceOpportunity.__table__
    assert IntelligenceOpportunity.__tablename__ == "intelligence_opportunities"
    assert "owner_id" in row.c
    assert "hard_blocked" in row.c


def test_measurements_are_normalized() -> None:
    assert normalize_quantity(500, "g") == (0.5, "kg")


def test_metadata_rejects_sensitive_payloads() -> None:
    from vayujit_api.intelligence.policy import validate_metadata

    with pytest.raises(HTTPException):
        validate_metadata({"provider_token": "never-store"})
