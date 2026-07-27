import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import Base, get_session
from vayujit_api.identity.router import attempts
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set VAYUJIT_TEST_DATABASE_URL to an isolated PostgreSQL database.",
)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"
test_factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    global test_factory
    assert TEST_DATABASE_URL is not None and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    attempts.clear()
    test_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        assert test_factory is not None
        with test_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    Base.metadata.drop_all(engine)
    engine.dispose()


def authenticate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Brand Owner",
            "email": "owner@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201


def create_brand(client: TestClient, name: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "tagline": f"{name} tagline",
        "description": f"Description for {name}",
        "website_url": "https://example.com",
        "primary_color": "#112233",
        "secondary_color": "#AABBCC",
        **overrides,
    }
    response = client.post("/api/v1/brands", json=payload, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


def test_unauthenticated_brand_access_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/brands").status_code == 401
    assert client.get("/api/v1/brands/active").status_code == 401
    assert client.post("/api/v1/brands", json={"name": "Nope"}, headers=ORIGIN).status_code == 401


def test_complete_active_archive_restore_flow_and_audit(client: TestClient) -> None:
    authenticate(client)
    first = create_brand(client, "First Brand")
    assert first["slug"] == "first-brand"
    assert first["is_active_context"] is True
    second = create_brand(client, "Second Brand", slug="second-custom")
    assert second["is_active_context"] is False

    activate = client.post(f"/api/v1/brands/{second['id']}/activate", headers=ORIGIN)
    assert activate.status_code == 200
    assert activate.json()["is_active_context"] is True
    assert client.get(f"/api/v1/brands/{first['id']}").json()["is_active_context"] is False

    archived = client.post(f"/api/v1/brands/{second['id']}/archive", headers=ORIGIN)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["is_active_context"] is False
    assert client.post(f"/api/v1/brands/{second['id']}/archive", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/brands/active").json() is None
    assert client.post(f"/api/v1/brands/{second['id']}/activate", headers=ORIGIN).status_code == 409

    restored = client.post(f"/api/v1/brands/{second['id']}/restore", headers=ORIGIN)
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["is_active_context"] is False
    assert client.post(f"/api/v1/brands/{second['id']}/restore", headers=ORIGIN).status_code == 200
    assert client.post(f"/api/v1/brands/{second['id']}/activate", headers=ORIGIN).status_code == 200

    details = client.get(f"/api/v1/brands/{second['id']}").json()
    assert {event["action"] for event in details["recent_audit_events"]} >= {
        "brand.created",
        "brand.archived",
        "brand.restored",
        "brand.active_changed",
    }
    assert test_factory is not None
    with test_factory() as db:
        assert db.scalar(select(func.count(AuditEvent.id))) == 6
        assert db.scalar(select(func.count(Brand.id)).where(Brand.is_active_context.is_(True))) == 1


def test_uniqueness_validation_and_partial_update(client: TestClient) -> None:
    authenticate(client)
    first = create_brand(client, "  Acme   Labs  ")
    duplicate_name = client.post("/api/v1/brands", json={"name": "acme labs"}, headers=ORIGIN)
    assert duplicate_name.status_code == 409
    duplicate_slug = client.post(
        "/api/v1/brands",
        json={"name": "Different", "slug": first["slug"]},
        headers=ORIGIN,
    )
    assert duplicate_slug.status_code == 409

    invalid_url = client.post(
        "/api/v1/brands", json={"name": "Bad URL", "website_url": "file:///secret"}, headers=ORIGIN
    )
    invalid_color = client.post(
        "/api/v1/brands", json={"name": "Bad Color", "primary_color": "red"}, headers=ORIGIN
    )
    invalid_slug = client.post(
        "/api/v1/brands", json={"name": "Bad Slug", "slug": "../escape"}, headers=ORIGIN
    )
    assert invalid_url.status_code == invalid_color.status_code == invalid_slug.status_code == 422

    updated = client.patch(
        f"/api/v1/brands/{first['id']}",
        json={"tagline": "Updated only", "primary_color": "#abcdef"},
        headers=ORIGIN,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == first["name"]
    assert updated.json()["tagline"] == "Updated only"
    assert updated.json()["primary_color"] == "#ABCDEF"
    assert (
        client.patch(
            f"/api/v1/brands/{first['id']}",
            json={"name": None},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert client.get("/api/v1/brands/not-a-uuid").status_code == 422
    assert client.get("/api/v1/brands/00000000-0000-0000-0000-000000000000").status_code == 404


def test_list_search_filter_pagination_and_default_archive_exclusion(
    client: TestClient,
) -> None:
    authenticate(client)
    alpha = create_brand(client, "Alpha")
    create_brand(client, "Beta")
    create_brand(client, "Gamma")
    client.post(f"/api/v1/brands/{alpha['id']}/archive", headers=ORIGIN)

    default_list = client.get("/api/v1/brands").json()
    assert default_list["total"] == 2
    assert [brand["name"] for brand in default_list["items"]] == ["Beta", "Gamma"]

    page = client.get("/api/v1/brands?include_archived=true&page=2&page_size=2").json()
    assert page["total"] == 3 and page["pages"] == 2
    assert [brand["name"] for brand in page["items"]] == ["Gamma"]
    assert client.get("/api/v1/brands?search=bet").json()["items"][0]["name"] == "Beta"
    archived = client.get("/api/v1/brands?include_archived=true&status=archived").json()
    assert [brand["name"] for brand in archived["items"]] == ["Alpha"]


def test_write_origin_protection_applies_to_brands(client: TestClient) -> None:
    authenticate(client)
    assert client.post("/api/v1/brands", json={"name": "Missing Origin"}).status_code == 403
    assert (
        client.post(
            "/api/v1/brands",
            json={"name": "Bad Origin"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
