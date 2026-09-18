"""Focused 9A Product Opportunity foundation integration coverage."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
    ProductOpportunityInputSnapshot,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _setup_owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Opportunity Owner",
            "email": "opportunity@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_product_opportunity_lifecycle_constraints_and_assessment_are_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    assert api.get("/api/v1/intelligence/product-opportunities").status_code == 401
    _setup_owner(api)
    payload = {
        "name": "Reusable kitchen organizer",
        "product_concept": "Stackable organizer for compact kitchens",
        "category": "Home",
        "target_marketplace": "amazon",
        "target_region": "IN",
        "research_objective": "Validate demand and sourcing feasibility.",
        "origin": "manual",
        "idempotency_key": "opportunity-foundation-1",
    }
    first = api.post("/api/v1/intelligence/product-opportunities", json=payload, headers=ORIGIN)
    assert first.status_code == 201, first.text
    repeated = api.post("/api/v1/intelligence/product-opportunities", json=payload, headers=ORIGIN)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == first.json()["id"]
    opportunity_id = first.json()["id"]

    constraints = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={
            "available_capital": "100000.00",
            "maximum_landed_cost": "250.00",
            "currency": "INR",
            "minimum_evidence_confidence": "0.70",
            "idempotency_key": "constraints-1",
        },
        headers=ORIGIN,
    )
    assert constraints.status_code == 201, constraints.text
    assert constraints.json()["version"] == 1
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"sources": [], "missing": ["demand"]}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    assert assessment.json()["version"] == 1
    detail = api.get(f"/api/v1/intelligence/product-opportunities/{opportunity_id}", headers=ORIGIN)
    assert detail.status_code == 200
    assert len(detail.json()["constraints"]) == 1
    assert len(detail.json()["assessments"]) == 1
    assert detail.json()["evidence_state"] == "unknown"

    updated = api.patch(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}",
        json={"notes": "Review with human decision maker."},
        headers=ORIGIN,
    )
    assert updated.status_code == 200
    archived = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/archive",
        headers=ORIGIN,
    )
    assert archived.status_code == 200
    assert archived.json()["lifecycle_status"] == "archived"

    assert api.get(f"/api/v1/intelligence/product-opportunities/{'0' * 32}").status_code == 404
    doctor = api.get("/api/v1/intelligence/product-opportunities/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["status"] == "PASS"
    operations = api.get("/api/v1/intelligence/product-opportunities/operations", headers=ORIGIN)
    assert operations.json()["archived"] == 1
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        assert db.scalar(select(ProductOpportunity)) is not None
        assert db.scalar(select(ProductOpportunityConstraintVersion)) is not None
        assert db.scalar(select(ProductOpportunityInputSnapshot)) is not None
        assert db.scalar(select(ProductOpportunityAssessment)) is not None
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "intelligence.opportunity_created" in actions
        assert "intelligence.opportunity_constraints_changed" in actions
        assert "intelligence.opportunity_assessment_created" in actions
        assert "intelligence.opportunity_archived" in actions
