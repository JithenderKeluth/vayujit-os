# mypy: ignore-errors
from __future__ import annotations

import pytest

from vayujit_api.intelligence import external_provider
from vayujit_api.intelligence.website_intelligence import (
    WEBSITE_SOURCE_TYPES,
    classify_identity,
    extract_website_intelligence,
    match_offering,
    materiality,
    normalize_domain,
    normalize_identity,
)


def test_source_types_are_bounded() -> None:
    assert len(WEBSITE_SOURCE_TYPES) == 8
    assert "MANUFACTURER_WEBSITE" in WEBSITE_SOURCE_TYPES
    assert "SUPPLIER_WEBSITE" in WEBSITE_SOURCE_TYPES


def test_extracts_source_provided_business_catalog_and_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_provider, "_resolved_addresses", lambda host: [])
    result = extract_website_intelligence(
        url="https://example.org/about",
        source_type="MANUFACTURER_WEBSITE",
        text=(
            "Company Name: Fixture Manufacturing Ltd. Address: 10 Factory Road, Pune. "
            "Email sales@example.org Phone +91 98765 43210. Product: Bamboo Organizer. "
            "MOQ: 100 units Price: ₹1499 INR Lead time: 20 days OEM private label. "
            "ISO certificate."
        ),
    )
    assert result["domain"] == "example.org"
    assert result["verification_state"] == "UNVERIFIED"
    assert result["classification"] == "UNTRUSTED_EXTERNAL_DATA"
    assert result["business_identity"]["state"] == "SOURCE_PROVIDED"
    assert result["products"] == ["Bamboo Organizer"]
    assert result["certifications"][0]["state"] == "DOCUMENT_REFERENCED"
    assert "OEM" in result["capabilities"]


def test_normalization_and_matching_are_deterministic() -> None:
    assert normalize_domain("https://WWW.Example.Org/path") == "example.org"
    assert normalize_identity("Fixture Manufacturing Ltd.") == "fixture manufacturing"
    assert (
        match_offering(website_name="Bamboo Organizer", product_name="Bamboo Organizer")["state"]
        == "MATCH"
    )
    assert (
        classify_identity(
            left={"domain": "example.org", "business_name": "Fixture"},
            right={"domain": "example.org", "business_name": "Fixture"},
        )
        == "MATCH"
    )
    assert materiality("moq", 100, 1000) == "MATERIAL"
    assert materiality("price", 100, 102) == "NON_MATERIAL"


@pytest.mark.parametrize(
    "value",
    [
        "http://example.org",
        "ftp://example.org",
        "file:///tmp/a",
        "javascript:alert(1)",
        "data:text/plain,x",
        "https://localhost",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://172.16.0.1",
        "https://192.168.1.1",
        "https://169.254.169.254",
        "https://[::1]",
        "https://[fd00::1]",
        "https://[fe80::1]",
        "https://example.org:22",
        "https://user:pass@example.org",
        "https://example.org:8080",
        "https://example.org:3000",
        "https://example.org:5432",
        "https://example.org:9200",
        "https://example.org:2375",
        "https://example.org:6443",
        "https://example.org:8500",
        "https://example.org:27017",
        "https://example.org:11211",
        "https://example.org:5000",
        "https://example.org:9000",
        "https://example.org:10000",
        "https://example.org:15672",
        "https://example.org:6379",
        "https://example.org:9201",
        "https://example.org:4444",
        "https://example.org:8888",
        "https://example.org:9090",
        "https://example.org:8081",
        "https://example.org:1234",
        "https://example.org:4321",
        "https://example.org:9999",
        "https://example.org:81",
        "https://example.org:444",
        "https://example.org:8443",
        "https://example.org:9443",
        "https://example.org:10443",
        "https://example.org:65535",
        "https://example.org:0",
        "https://example.org:1",
        "https://example.org:21",
        "https://example.org:25",
        "https://example.org:110",
        "https://example.org:143",
        "https://example.org:465",
        "https://example.org:587",
        "https://example.org:993",
        "https://example.org:995",
        "https://example.org:3128",
        "https://example.org:8000",
        "https://example.org:8088",
        "https://example.org:8880",
        "https://example.org:18080",
        "https://example.org:20000",
        "https://example.org:27018",
        "https://example.org:5001",
        "https://example.org:7001",
        "https://example.org:7070",
        "https://example.org:8181",
        "https://example.org:10001",
        "https://example.org:12000",
        "https://example.org:16000",
        "https://example.org:32768",
        "https://example.org:49152",
        "https://example.org:61000",
        "https://example.org:62000",
        "https://example.org:63000",
        "https://example.org:64000",
        "https://example.org:65000",
    ],
)
def test_website_security_inputs_are_rejected_or_bounded(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(external_provider, "_resolved_addresses", lambda host: [])
    if "://example.org:" in value and value.rsplit(":", 1)[-1] in {"443", "80"}:
        pytest.skip("standard port")
    with pytest.raises((ValueError, Exception)):
        extract_website_intelligence(url=value, text="Company Name: Fixture")


def test_website_security_rejects_embedded_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external_provider, "_resolved_addresses", lambda host: [])
    with pytest.raises(ValueError):
        extract_website_intelligence(
            url="https://user:password@example.org", text="Company Name: Fixture"
        )


def test_website_security_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError):
        extract_website_intelligence(url="ftp://example.org", text="Company Name: Fixture")


def test_website_security_bounds_large_content() -> None:
    with pytest.raises(ValueError, match="response_too_large"):
        extract_website_intelligence(
            url="https://example.org", text="Company Name: Fixture " * 10000
        )


def test_website_certification_logo_remains_claimed() -> None:
    result = extract_website_intelligence(url="https://example.org", text="ISO 9001 logo")
    assert result["certifications"][0]["state"] == "CLAIMED"
