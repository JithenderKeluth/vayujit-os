from __future__ import annotations

import uuid

import pytest

from vayujit_api.intelligence.external_projection import product_channel_projection

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_product_channel_is_server_derived_and_refresh_aware(db_session, owner):
    value = product_channel_projection(db_session, owner, uuid.uuid4())
    assert value["website_observation_count"] == 0
    assert value["website_offering_count"] == 0
    assert value["actions"] == [
        "view_external_research",
        "refresh_external_research",
        "review_conflicts",
        "review_evidence",
    ]
