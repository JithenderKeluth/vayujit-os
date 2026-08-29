# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_missing_identity_is_deterministic_risk() -> None:
    result = extract_website_intelligence(url="https://example.org", text="Product: Fixture")
    assert "missing_legal_identity" in result["risk_signals"]
