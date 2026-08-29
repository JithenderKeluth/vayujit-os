# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_canonical_observation_contains_lineage_inputs() -> None:
    result = extract_website_intelligence(
        url="https://example.org", source_type="SUPPLIER_WEBSITE", text="Company Name: Fixture"
    )
    assert result["domain"] == "example.org"
    assert result["content_hash"]
