from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_changed_source_content_produces_new_observation_fingerprint() -> None:
    first = extract_website_intelligence(url="https://example.org", text="Price: $10")
    second = extract_website_intelligence(url="https://example.org", text="Price: $12")
    assert first["content_hash"] != second["content_hash"]
