# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_certification_state_is_source_derived() -> None:
    result = extract_website_intelligence(url="https://example.org", text="ISO certificate")
    assert result["certifications"][0]["state"] == "DOCUMENT_REFERENCED"
