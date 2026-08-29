# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.website_models import (
    WebsiteObservation,
    WebsiteOffering,
    WebsiteSourceProfile,
)

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_canonical_e2e_retains_profile_observation_and_correlation_lineage(
    client, db_session
) -> None:
    result = run_website_research(
        client,
        content="Company Name: Canonical Fixture. Product: Fixture Tray. OEM. ISO certificate.",
        key="canonical-e2e",
    )
    profile = db_session.scalar(select(WebsiteSourceProfile))
    observations = list(db_session.scalars(select(WebsiteObservation)))
    offering = db_session.scalar(select(WebsiteOffering))
    assert profile is not None and offering is not None
    assert offering.source_profile_id == profile.id
    assert offering.observation_ids
    assert set(offering.observation_ids).issubset({str(item.id) for item in observations})
    assert offering.correlation_id
    assert result["mission_id"]
