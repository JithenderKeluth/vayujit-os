# mypy: ignore-errors
from vayujit_api.intelligence.website_intelligence import materiality


def test_material_change_is_reviewable() -> None:
    assert materiality("price", 100, 125) == "MATERIAL"
