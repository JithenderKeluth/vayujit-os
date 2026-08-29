# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import normalize_identity


def test_identity_keys_are_deterministic_per_source() -> None:
    assert normalize_identity("Fixture Ltd") == "fixture"
