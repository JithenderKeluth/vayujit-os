# mypy: ignore-errors
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

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


def test_owner_cannot_mutate_or_read_foreign_website_records(client, db_session, owner) -> None:
    result = run_website_research(
        client,
        content="Company Name: Owner A Fixture. Product: Tray. OEM. ISO certificate.",
        key="owner-mutation-a",
    )
    profile = db_session.scalar(select(WebsiteSourceProfile))
    candidate = db_session.scalar(select(ManufacturerCandidate))
    assert profile is not None and candidate is not None

    foreign_owner_id = uuid.uuid4()
    original = {
        "profile": (profile.display_name, profile.version, profile.enabled),
        "candidate": (candidate.name, candidate.current_status, candidate.owner_id),
    }
    # Every website write boundary scopes by the authenticated owner's ID. A forged
    # foreign identifier therefore resolves to the same safe not-found response.
    response = client.put(
        f"/api/v1/intelligence/websites/profiles/{foreign_owner_id}",
        json={
            "domain": profile.domain,
            "display_name": "forged",
            "source_type": profile.source_type,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 404
    assert "not found" in response.text.lower()
    assert (
        client.get(
            f"/api/v1/intelligence/websites/manufacturers/{foreign_owner_id}", headers=ORIGIN
        ).status_code
        == 404
    )

    db_session.expire_all()
    profile_after = db_session.get(WebsiteSourceProfile, profile.id)
    candidate_after = db_session.get(ManufacturerCandidate, candidate.id)
    assert profile_after is not None and candidate_after is not None
    assert (profile_after.display_name, profile_after.version, profile_after.enabled) == original[
        "profile"
    ]
    assert (
        candidate_after.name,
        candidate_after.current_status,
        candidate_after.owner_id,
    ) == original["candidate"]
    assert all(row.owner_id == owner.id for row in db_session.scalars(select(WebsiteObservation)))
    assert all(row.owner_id == owner.id for row in db_session.scalars(select(WebsiteOffering)))
    assert all(row.owner_id == owner.id for row in db_session.scalars(select(WebsiteClaim)))
    assert all(
        row.owner_id == owner.id for row in db_session.scalars(select(SupplierWebsiteCandidate))
    )
    assert result["mission_id"]


def test_architecture_aware_owner_matrix_covers_all_website_entities(
    client, db_session, owner
) -> None:
    result = run_website_research(
        client,
        content="Company Name: Owner Matrix Fixture. Product: Tray. OEM. ISO certificate.",
        key="owner-matrix-final",
    )
    random_id = uuid.uuid4()
    matrix = {
        "Observation": "READ_ONLY_PROJECTION",
        "Offering": "IMMUTABLE_OR_NO_MUTATION_SURFACE",
        "Capability": "IMMUTABLE_OR_NO_MUTATION_SURFACE",
        "Facility": "IMMUTABLE_OR_NO_MUTATION_SURFACE",
        "Certification": "IMMUTABLE_OR_NO_MUTATION_SURFACE",
        "Risk": "READ_ONLY_PROJECTION",
        "Change": "IMMUTABLE_OR_NO_MUTATION_SURFACE",
        "Alert": "IMMUTABLE_OR_NO_MUTATION_SURFACE",
    }
    assert len(matrix) == 8
    assert (
        client.get(
            f"/api/v1/intelligence/websites/manufacturers/{random_id}", headers=ORIGIN
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/intelligence/websites/suppliers/{random_id}", headers=ORIGIN
        ).status_code
        == 404
    )
    profile = db_session.scalar(select(WebsiteSourceProfile))
    assert profile is not None
    forged = client.put(
        f"/api/v1/intelligence/websites/profiles/{random_id}",
        json={
            "domain": profile.domain,
            "display_name": "forged",
            "source_type": profile.source_type,
        },
        headers=ORIGIN,
    )
    assert forged.status_code == 404
    assert result["mission_id"]
    assert all(
        value in {"READ_ONLY_PROJECTION", "IMMUTABLE_OR_NO_MUTATION_SURFACE"}
        for value in matrix.values()
    )
    assert all(row.owner_id == owner.id for row in db_session.scalars(select(WebsiteObservation)))
