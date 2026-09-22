"""Focused 12F Trend-to-Winning-Product integration coverage."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session() -> Generator[Session, None, None]:
        with factory() as value:
            yield value

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value
    engine.dispose()


def _setup(api: TestClient) -> tuple[str, str]:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Trend 12F Owner",
            "email": "trend-12f@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    opportunity = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "12F evidence fixture",
            "product_concept": "A disposable evidence fixture",
            "origin": "trend_research",
            "idempotency_key": "trend-12f-opportunity",
        },
        headers=ORIGIN,
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = opportunity.json()["id"]
    constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={"idempotency_key": "trend-12f-constraint", "currency": "INR"},
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "12F"}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return opportunity_id, assessment.json()["id"]


def test_trend_projection_is_versioned_idempotent_and_evidence_only(
    client: TestClient,
) -> None:
    opportunity_id, assessment_id = _setup(client)
    context = client.post(
        "/api/v1/intelligence/trends/contexts",
        json={
            "name": "12F exact opportunity context",
            "subject_type": "PRODUCT_OPPORTUNITY",
            "product_opportunity_id": opportunity_id,
            "status": "ACTIVE",
            "idempotency_key": "trend-12f-context",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    first = client.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/trend-projection",
        json={},
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    payload = first.json()
    assert payload["readiness"] == "INSUFFICIENT_EVIDENCE"
    assert payload["context_id"] == context.json()["id"]
    assert payload["signal_summaries"] == []
    assert payload["evidence_confidence"]["state"] == "UNKNOWN"
    assert "demand" in payload["projection"]["demand_interest_proxy_contract"]
    assert "score" not in str(payload["projection"]).lower()
    repeated = client.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/trend-projection",
        json={},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == payload["id"]
    current = client.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/trend-projection",
        headers=ORIGIN,
    )
    assert current.status_code == 200, current.text
    assert current.json()["projection_version"] == 1
    history = client.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/trend-projections",
        headers=ORIGIN,
    )
    assert history.status_code == 200, history.text
    assert history.json()["total"] == 1
    by_id = client.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/trend-projection/{payload['id']}",
        headers=ORIGIN,
    )
    assert by_id.status_code == 200, by_id.text
    foreign_path = (
        f"/api/v1/intelligence/product-opportunities/{'0' * 32}/"
        f"assessments/{assessment_id}/trend-projection"
    )
    foreign = client.get(foreign_path, headers=ORIGIN)
    assert foreign.status_code == 404
