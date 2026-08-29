# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.identity.models import User
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteClaim,
    WebsiteObservation,
    WebsiteOffering,
    WebsiteSourceProfile,
)

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_eight_owner_scoped_reads_return_only_authenticated_owner(
    client, db_session, owner
) -> None:
    run_website_research(
        client, content="Company Name: Owner Fixture. Product: Fixture Tray. OEM. ISO certificate."
    )
    profiles = client.get("/api/v1/intelligence/websites/profiles", headers=ORIGIN)
    assert profiles.json()["profiles"]
    assert (
        client.get("/api/v1/intelligence/websites/manufacturers", headers=ORIGIN).status_code == 200
    )
    assert client.get("/api/v1/intelligence/websites/history", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/intelligence/websites/overview", headers=ORIGIN).json()[
        "owner_id"
    ] == str(owner.id)
    assert all(
        item.owner_id == owner.id for item in db_session.scalars(select(WebsiteSourceProfile))
    )
    assert all(
        item.owner_id == owner.id for item in db_session.scalars(select(ManufacturerCandidate))
    )
    assert all(
        item.owner_id == owner.id for item in db_session.scalars(select(SupplierWebsiteCandidate))
    )
    assert all(item.owner_id == owner.id for item in db_session.scalars(select(WebsiteObservation)))
    assert all(item.owner_id == owner.id for item in db_session.scalars(select(WebsiteOffering)))
    assert all(item.owner_id == owner.id for item in db_session.scalars(select(WebsiteClaim)))
    assert db_session.scalar(select(User.id).where(User.id == owner.id)) == owner.id
