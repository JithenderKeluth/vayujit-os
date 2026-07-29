import os
import struct
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.router import attempts
from vayujit_api.main import create_app
from vayujit_api.media.service import owned_media

URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
factory: sessionmaker[Session] | None = None


def png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", 2, 3)
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\x00\x00\x00\x00"
    )


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    global factory
    assert URL and URL.startswith("postgresql")
    engine = create_engine(URL)
    reset_test_schema(engine, Base.metadata, database_url=URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = get_settings()
    old_storage = settings.media_storage_directory
    old_marker = settings.maintenance_marker
    settings.media_storage_directory = str(tmp_path / "media")
    settings.maintenance_marker = str(tmp_path / "maintenance")

    def session() -> Generator[Session, None, None]:
        assert factory is not None
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value
    settings.media_storage_directory = old_storage
    settings.maintenance_marker = old_marker
    reset_test_schema(engine, Base.metadata, database_url=URL)
    engine.dispose()


def authenticate(client: TestClient) -> None:
    result = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Owner",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert result.status_code == 201


def test_media_upload_duplicate_preview_archive_scope_and_maintenance(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/media").status_code == 401
    authenticate(client)
    first = client.post(
        "/api/v1/media",
        files={"file": ("safe.png", png(), "image/png")},
        headers=ORIGIN,
    )
    assert first.status_code == 201
    media = first.json()
    assert media["width"] == 2 and media["height"] == 3
    assert "storage" not in first.text and "\\" not in first.text
    duplicate = client.post(
        "/api/v1/media",
        files={"file": ("copy.png", png(), "image/png")},
        headers=ORIGIN,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == media["id"]
    assert duplicate.json()["duplicate_reused"] is True
    preview = client.get(f"/api/v1/media/{media['id']}/preview")
    assert preview.content == png()
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert (
        client.post(f"/api/v1/media/{media['id']}/archive", headers=ORIGIN).json()["status"]
        == "archived"
    )
    assert (
        client.post(f"/api/v1/media/{media['id']}/restore", headers=ORIGIN).json()["status"]
        == "ready"
    )
    assert factory is not None
    with factory() as db, pytest.raises(HTTPException):
        owned_media(db, uuid.uuid4(), uuid.UUID(media["id"]))
    marker = get_settings().maintenance_marker
    with open(marker, "w", encoding="utf-8") as stream:
        stream.write("enabled")
    blocked = client.post(
        "/api/v1/media",
        files={"file": ("blocked.png", png(), "image/png")},
        headers=ORIGIN,
    )
    assert blocked.status_code == 503
    os.unlink(marker)
