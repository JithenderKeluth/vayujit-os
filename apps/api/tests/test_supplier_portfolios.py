"""Basic owner-scoped API coverage for the 8E.1 portfolio foundation."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioContext,
    SupplierPortfolioInputSnapshot,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None, "VAYUJIT_TEST_DATABASE_URL is required."
    engine = create_engine(TEST_DATABASE_URL)
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


def _setup_owner(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Portfolio Owner",
            "email": "portfolio@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_portfolio_creation_is_idempotent_and_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    assert api.get("/api/v1/intelligence/supplier-portfolios").status_code == 401
    _setup_owner(api)
    payload = {
        "name": "Core sourcing portfolio",
        "description": "Foundation test",
        "scope_type": "manual",
        "idempotency_key": "portfolio-foundation-1",
    }
    first = api.post("/api/v1/intelligence/supplier-portfolios", json=payload, headers=ORIGIN)
    assert first.status_code == 201, first.text
    second = api.post("/api/v1/intelligence/supplier-portfolios", json=payload, headers=ORIGIN)
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["reused"] is True
    portfolio_id = first.json()["id"]
    assert api.get(f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}").status_code == 200
    assert api.get(f"/api/v1/intelligence/supplier-portfolios/{'0' * 32}").status_code == 404
    with factory() as db:
        assert db.scalar(select(User)) is not None
        assert db.scalar(select(SupplierPortfolioContext)) is not None


def test_assessment_creates_append_only_version_and_snapshot(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    created = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "Assessment portfolio", "idempotency_key": "assessment-portfolio-1"},
        headers=ORIGIN,
    )
    portfolio_id = created.json()["id"]
    payload = {"idempotency_key": "assessment-1", "input_snapshot": {"source": "test"}}
    assessment = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json=payload,
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    assert assessment.json()["version"] == 1
    assert (
        api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
            json=payload,
            headers=ORIGIN,
        ).json()["reused"]
        is True
    )
    assert (
        api.get(f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assessment").json()[
            "version"
        ]
        == 1
    )
    with factory() as db:
        assert db.scalar(select(SupplierPortfolioAssessmentVersion)) is not None
        assert db.scalar(select(SupplierPortfolioInputSnapshot)) is not None
