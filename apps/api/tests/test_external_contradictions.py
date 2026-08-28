# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import contradiction_identity


def test_five_contradiction_types_and_replay_identity():
    for key in ("PRICE", "TREND", "MOQ", "LEAD_TIME", "SUPPLIER_CAPABILITY"):
        assert contradiction_identity("m", key, "a", "b") == contradiction_identity(
            "m", key, "b", "a"
        )
