from vayujit_api.intelligence.website_intelligence import materiality


def test_material_changes_are_server_classified() -> None:
    assert materiality("price", 100, 125) == "MATERIAL"
    assert materiality("moq", 100, 1000) == "MATERIAL"
