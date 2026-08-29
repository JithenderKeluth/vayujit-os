from vayujit_api.intelligence.website_intelligence import match_offering


def test_possible_offering_match_remains_reviewable() -> None:
    result = match_offering(website_name="Bamboo Storage Box", product_name="Bamboo Box")
    assert result["state"] == "MATCH"
    assert result["requires_review"] is False
