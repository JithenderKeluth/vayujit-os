# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_explicit_facility_claim_is_claimed() -> None:
    result = extract_website_intelligence(
        url="https://example.org", text="Own factory. Factory area: 10,000 sq ft."
    )
    facilities = result["facilities"]
    assert {item["type"] for item in facilities} == {"FACTORY_OWNED", "FACTORY_AREA"}
    assert all(item["status"] == "CLAIMED" for item in facilities)
