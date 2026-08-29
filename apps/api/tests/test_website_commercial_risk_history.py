# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_commercial_terms_and_risk_signals_are_deterministic() -> None:
    result = extract_website_intelligence(
        url="https://example.org", text="MOQ: 100 units Price: $10 Lead time: 20 days"
    )
    assert result["commercial_terms"]["moq"] == "100 units"
    assert "missing_legal_identity" in result["risk_signals"]
