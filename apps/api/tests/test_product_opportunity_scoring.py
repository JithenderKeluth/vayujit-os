"""Focused Slice 9F deterministic score, safety, and owner-boundary coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from test_product_opportunity_feasibility import ORIGIN, _assessment, _setup

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


pytestmark = pytest.mark.integration


def test_score_is_explicitly_insufficient_and_replayable(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _factory = client
    product_id = _setup(api, _factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    path = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{assessment_id}/score"
    )
    response = api.post(path, json={}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["eligibility"] == "INSUFFICIENT_EVIDENCE"
    assert body["overall_score"] is None
    assert body["classification"] == "UNAVAILABLE"
    assert len(body["unavailable_dimensions"]) == 7
    assert sum(float(value) for value in body["weights"].values()) == 100
    assert "provider" not in response.text.lower()
    repeated = api.post(path, json={"idempotency_key": "different"}, headers=ORIGIN)
    assert repeated.status_code == 201
    assert repeated.json() == body
    assert api.get(path, headers=ORIGIN).json() == body
    assert api.get(path + "/explanation", headers=ORIGIN).json() == body["dimensions"]
    assert api.get(path + "/drivers", headers=ORIGIN).json() == body["positive_drivers"]
    doctor = api.get(
        "/api/v1/intelligence/product-opportunities/score-system-doctor", headers=ORIGIN
    )
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS", doctor.text


def test_scoring_model_and_bounded_comparison_are_safe(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup(api, factory)
    model = api.get("/api/v1/intelligence/product-opportunities/scoring-model", headers=ORIGIN)
    assert model.status_code == 200
    assert model.json()["version"] == "winning-product-score-v1"
    assert sum(float(value) for value in model.json()["weights"].values()) == 100
    assert (
        api.post(
            "/api/v1/intelligence/product-opportunities/score/compare",
            json={"assessment_ids": [str(uuid.uuid4())]},
            headers=ORIGIN,
        ).status_code
        == 422
    )


def test_human_decision_requires_a_persisted_score(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _factory = client
    product_id = _setup(api, _factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    decision = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{assessment_id}/decision",
        json={"action": "shortlist", "rationale": "Review manually after evidence refresh."},
        headers=ORIGIN,
    )
    assert decision.status_code == 404
    assert "password" not in decision.text.lower()
