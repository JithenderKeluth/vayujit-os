from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_canonical_bounded_observation_contains_expected_lineage_inputs() -> None:
    result = extract_website_intelligence(
        url="https://example.org",
        source_type="SUPPLIER_WEBSITE",
        text=(
            "Company Name: Fixture Supply Ltd. Address: 10 Factory Road. "
            "Product: Bamboo Organizer. OEM. ISO certificate. MOQ: 100 units."
        ),
    )
    assert result["domain"] == "example.org"
    assert result["products"] == ["Bamboo Organizer"]
    assert result["capabilities"]
    assert result["certifications"]
    assert result["content_hash"]
