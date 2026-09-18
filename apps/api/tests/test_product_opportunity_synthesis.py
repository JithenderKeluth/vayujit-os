"""Focused Slice 9E synthesis coverage."""

from __future__ import annotations

import os
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


def test_synthesis_is_assessment_bound_safe_and_replayable(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    product_id = _setup(api, factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    path = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{assessment_id}/risk-evidence-synthesis"
    )
    first = api.post(path, json={"idempotency_key": "9e-empty"}, headers=ORIGIN)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["summary"]["assessment_readiness"] == "RESEARCH_REQUIRED"
    assert body["summary"]["confidence"] == "UNKNOWN"
    assert body["risks"] == []
    assert body["research_gaps"] == []
    assert "WINNING_PRODUCT" not in first.text
    repeated = api.post(path, json={"idempotency_key": "different"}, headers=ORIGIN)
    assert repeated.status_code == 201
    assert repeated.json() == body
    assert api.get(path, headers=ORIGIN).json() == body
    assert api.get(path + "/confidence", headers=ORIGIN).json()["confidence"] == "UNKNOWN"
    assert api.get(path + "/readiness", headers=ORIGIN).json()["DEMAND"] == "UNKNOWN"
    assert api.get(path + "/history", headers=ORIGIN).status_code == 200
    doctor = api.get(
        "/api/v1/intelligence/product-opportunities/risk-evidence-system-doctor", headers=ORIGIN
    )
    assert doctor.status_code == 200 and doctor.json()["status"] == "PASS"
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{__import__('uuid').uuid4()}/assessments/{assessment_id}/risk-evidence-synthesis",
            headers=ORIGIN,
        ).status_code
        == 404
    )
