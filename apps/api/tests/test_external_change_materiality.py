# ruff: noqa: E501
from vayujit_api.intelligence.external_intelligence import record_external_change


def test_rejected_external_data_cannot_create_change():
    assert (
        record_external_change(
            None,
            None,
            change_type="PRICE",
            entity_id="x",
            field_key="price",
            previous={"value": 1},
            current={"value": 2},
            evidence_ids=[],
            accepted=False,
        )
        is None
    )
