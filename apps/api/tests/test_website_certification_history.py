# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_logo_only_certification_is_not_verified() -> None:
    result = extract_website_intelligence(url="https://example.org", text="ISO logo")
    assert result["certifications"][0]["state"] == "CLAIMED"
