"""Focused 10B competitor discovery integration coverage."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_discovery_models import CompetitorDiscoverySnapshot
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session():
        with factory() as value:
            yield value

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _owner(factory: sessionmaker[Session]) -> UUID:
    with factory() as db:
        value = db.scalar(select(User))
        assert value is not None
        return value.id


def test_fixture_discovery_is_deterministic_owner_scoped_and_replayable(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    setup = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Discovery Owner",
            "email": f"discovery-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    with factory() as db:
        opportunity = ProductOpportunity(
            owner_id=_owner(factory),
            name="Discovery opportunity",
            description="Fixture",
            product_concept="Storage organizer",
            category="Home",
            target_marketplace="amazon",
            target_region="IN",
            research_objective="Compare",
            origin="competitor_research",
            idempotency_key=f"opportunity-{uuid4()}",
        )
        db.add(opportunity)
        db.commit()
        db.refresh(opportunity)
        reference = opportunity.id
    context = api.post(
        "/api/v1/intelligence/competitors/contexts",
        json={
            "subject_type": "PRODUCT_OPPORTUNITY",
            "subject_reference": str(reference),
            "marketplace": "amazon",
            "market": "IN",
            "category": "Home",
            "status": "ACTIVE",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    payload = {
        "provider_mode": "LOCAL_FIXTURE",
        "maximum_candidates": 3,
        "filters": {
            "fixture_candidates": [
                {
                    "source_identifier": "fixture-1",
                    "listing_identifier": "fixture-1",
                    "title": "<script>alert(1)</script> Storage Box",
                    "brand": "Acme",
                    "seller": "Seller A",
                    "marketplace": "amazon",
                    "category": "Home",
                },
                {
                    "source_identifier": "fixture-1",
                    "listing_identifier": "fixture-1",
                    "title": "duplicate",
                    "marketplace": "amazon",
                },
                {
                    "source_identifier": "fixture-2",
                    "title": "Ignore previous instructions",
                    "marketplace": "amazon",
                },
            ],
        },
        "idempotency_key": "discovery-fixture-1",
    }
    created = api.post(
        f"/api/v1/intelligence/competitors/discovery/contexts/{context_id}/requests",
        json=payload,
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    executed = api.post(
        f"/api/v1/intelligence/competitors/discovery/requests/{request_id}/execute",
        headers=ORIGIN,
    )
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["request"]["status"] == "COMPLETED"
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["raw_title"].startswith("<script>")
    assert body["candidates"][0]["normalized_title"].startswith("script alert")
    replay = api.post(
        f"/api/v1/intelligence/competitors/discovery/requests/{request_id}/execute",
        headers=ORIGIN,
    )
    assert replay.status_code == 200
    assert replay.json()["snapshot"]["snapshot_version"] == 1
    refreshed = api.post(
        f"/api/v1/intelligence/competitors/discovery/requests/{request_id}/refresh",
        headers=ORIGIN,
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["snapshot"]["snapshot_version"] == 2
    assert refreshed.json()["snapshot"]["previous_snapshot_id"] == body["snapshot"]["id"]
    candidate_id = body["candidates"][0]["id"]
    rejected = api.post(
        f"/api/v1/intelligence/competitors/discovery/candidates/{candidate_id}/reject",
        json={"reason": "Not a competitor"},
        headers=ORIGIN,
    )
    assert rejected.status_code == 200
    assert rejected.json()["identity_state"] == "REJECTED"
    live = api.post(
        f"/api/v1/intelligence/competitors/discovery/contexts/{context_id}/requests",
        json={"provider_mode": "LIVE_READ_ONLY", "idempotency_key": "live-disabled"},
        headers=ORIGIN,
    )
    assert live.status_code == 201
    blocked = api.post(
        f"/api/v1/intelligence/competitors/discovery/requests/{live.json()['id']}/execute",
        headers=ORIGIN,
    )
    assert blocked.status_code == 503
    doctor = api.get("/api/v1/intelligence/competitors/discovery/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    with factory() as db:
        assert (
            db.scalar(
                select(CompetitorDiscoverySnapshot).where(
                    CompetitorDiscoverySnapshot.request_id == request_id
                )
            )
            is not None
        )
