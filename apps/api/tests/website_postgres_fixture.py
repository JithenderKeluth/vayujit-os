# mypy: ignore-errors
"""Shared PostgreSQL fixture for website-intelligence certification tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.main import create_app

ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"
TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Reset only an explicitly marked disposable PostgreSQL database."""
    global factory
    if not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith("postgresql"):
        pytest.skip("VAYUJIT_TEST_DATABASE_URL is required for PostgreSQL certification tests")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        assert factory is not None
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        response = value.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "Website Certification Owner",
                "email": f"website-{uuid.uuid4().hex}@example.com",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()
    factory = None


@pytest.fixture
def db_session(client: TestClient) -> Generator[Session, None, None]:
    del client  # The client fixture owns schema setup and teardown.
    assert factory is not None
    with factory() as db:
        yield db


@pytest.fixture
def owner(db_session: Session) -> User:
    value = db_session.query(User).one()
    return value


def run_website_research(
    client: TestClient,
    *,
    content: str,
    key: str | None = None,
    url: str = "https://example.org",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/websites/research",
        json={
            "url": url,
            "content": content,
            "source_type": "SUPPLIER_WEBSITE",
            "idempotency_key": key or f"website-{uuid.uuid4().hex}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()
