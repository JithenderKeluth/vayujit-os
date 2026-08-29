# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.website_models import WebsiteClaim

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_certification_lifecycle_persists_nine_claims_and_removal(client, db_session) -> None:
    names = "ISO CE RoHS FCC BIS UL FDA GMP BSCI"
    run_website_research(
        client,
        content=f"Company Name: Certification Fixture. Product: Fixture Tray. {names} certificate.",
    )
    claims = list(db_session.scalars(select(WebsiteClaim)))
    certs = [item for item in claims if item.claim_type == "CERTIFICATION"]
    assert len(certs) == 9
    assert all(item.status == "DOCUMENT_REFERENCED" for item in certs)
    run_website_research(
        client,
        content="Company Name: Certification Fixture. Product: Fixture Tray.",
    )
    db_session.expire_all()
    refreshed = [
        item
        for item in db_session.scalars(select(WebsiteClaim))
        if item.claim_type == "CERTIFICATION"
    ]
    assert len(refreshed) == 9
    assert all(item.status == "NO_LONGER_OBSERVED" for item in refreshed)


def test_single_certification_identity_preserves_nine_state_history(db_session, owner) -> None:
    from uuid import uuid4

    from vayujit_api.intelligence.website_models import WebsiteObservation

    statuses = [
        "CLAIMED",
        "CLAIMED",
        "DOCUMENT_REFERENCED",
        "DOCUMENT_REFERENCED",
        "DOCUMENT_REFERENCED",
        "EXPIRED",
        "NO_LONGER_OBSERVED",
        "SUPPORTED",
        "VERIFIED",
    ]
    previous = None
    for step, status in enumerate(statuses, start=1):
        row = WebsiteObservation(
            owner_id=owner.id,
            observation_type="CERTIFICATION",
            claim_type="ISO_9001",
            normalized_value={"name": "ISO_9001", "status": status, "step": step},
            source_provided_state="SOURCE_PROVIDED",
            verification=status,
            freshness="FRESH",
            confidence=0.9,
            content_hash=str(uuid4()),
            evidence_ids=[],
            previous_observation_id=previous.id if previous else None,
            observation_identity=f"cert-lifecycle:ISO_9001:{step}",
            domain="example.org",
            page_url="https://example.org",
            correlation_id="cert-lifecycle",
        )
        db_session.add(row)
        db_session.flush()
        previous = row
    rows = list(
        db_session.scalars(
            select(WebsiteObservation)
            .where(WebsiteObservation.claim_type == "ISO_9001")
            .order_by(WebsiteObservation.created_at)
        )
    )
    assert len(rows) == 9
    assert rows[-1].verification == "VERIFIED"
    assert all(rows[index].previous_observation_id == rows[index - 1].id for index in range(1, 9))
    assert len(rows) == len({row.observation_identity for row in rows})
