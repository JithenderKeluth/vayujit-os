# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import extract_website_intelligence


def test_t1_t2_fingerprint_is_append_oriented() -> None:
    t1 = extract_website_intelligence(url="https://example.org", text="MOQ: 100 units")
    t2 = extract_website_intelligence(url="https://example.org", text="MOQ: 1000 units")
    assert t1["content_hash"] != t2["content_hash"]
