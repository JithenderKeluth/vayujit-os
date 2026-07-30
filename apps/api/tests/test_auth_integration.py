import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import AuthSession, User
from vayujit_api.identity.router import attempts
from vayujit_api.identity.service import now
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
test_factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    global test_factory
    assert TEST_DATABASE_URL is not None, "VAYUJIT_TEST_DATABASE_URL is required."
    assert TEST_DATABASE_URL.startswith("postgresql"), "Auth tests require PostgreSQL."
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    test_factory = factory

    def test_session():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def test_complete_owner_session_flow(client: TestClient) -> None:
    assert client.get("/api/v1/auth/setup-status").json() == {"ownerExists": False}
    payload = {
        "full_name": "Local Owner",
        "email": "Owner@Example.com",
        "password": "correct horse battery staple",
        "password_confirmation": "correct horse battery staple",
    }
    setup = client.post("/api/v1/auth/setup-owner", json=payload, headers=ORIGIN)
    assert setup.status_code == 201
    assert "password" not in setup.text
    assert "HttpOnly" in setup.headers["set-cookie"]
    assert "SameSite=strict" in setup.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "OWNER@example.COM", "password": payload["password"]},
        headers=ORIGIN,
    )
    assert login.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_duplicate_setup_and_hashed_storage(client: TestClient) -> None:
    payload = {
        "full_name": "Local Owner",
        "email": "owner@example.com",
        "password": "correct horse battery staple",
        "password_confirmation": "correct horse battery staple",
    }
    assert client.post("/api/v1/auth/setup-owner", json=payload, headers=ORIGIN).status_code == 201
    assert client.post("/api/v1/auth/setup-owner", json=payload, headers=ORIGIN).status_code == 409

    assert test_factory is not None
    with test_factory() as db:
        user = db.scalar(select(User))
        auth_session = db.scalar(select(AuthSession))
        assert user is not None and user.normalized_email == "owner@example.com"
        assert user.password_hash.startswith("$argon2id$")
        assert payload["password"] not in user.password_hash
        assert auth_session is not None and len(auth_session.token_hash) == 64


def test_invalid_login_is_generic_and_throttled(client: TestClient) -> None:
    payload = {
        "full_name": "Local Owner",
        "email": "owner@example.com",
        "password": "correct horse battery staple",
        "password_confirmation": "correct horse battery staple",
    }
    client.post("/api/v1/auth/setup-owner", json=payload, headers=ORIGIN)
    for index in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "missing@example.com" if index == 0 else payload["email"],
                "password": "wrong password",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."
    throttled = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
        headers=ORIGIN,
    )
    assert throttled.status_code == 429


def test_expired_session_and_disabled_owner_are_rejected(client: TestClient) -> None:
    payload = {
        "full_name": "Local Owner",
        "email": "owner@example.com",
        "password": "correct horse battery staple",
        "password_confirmation": "correct horse battery staple",
    }
    client.post("/api/v1/auth/setup-owner", json=payload, headers=ORIGIN)
    assert test_factory is not None
    with test_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        auth_session.expires_at = now()
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.clear()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
        headers=ORIGIN,
    )
    assert login.status_code == 200
    with test_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        user.is_active = False
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
