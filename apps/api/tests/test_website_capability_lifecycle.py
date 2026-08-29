# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_capability_claim_is_explicit() -> None:
    result = extract_website_intelligence(url="https://example.org", text="PRIVATE LABEL OEM")
    assert "PRIVATE_LABEL" in result["capabilities"]
