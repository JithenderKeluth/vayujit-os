import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.image_provider import deterministic_png
from vayujit_api.ai.image_service import decide_output
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.identity.router import attempts
from vayujit_api.main import create_app

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"


@pytest.fixture
def context() -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, str]], None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session_override() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as client:
        setup = client.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "Image Owner",
                "email": "image@example.com",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
            headers=ORIGIN,
        )
        assert setup.status_code == 201, setup.text
        brand = client.post("/api/v1/brands", json={"name": "Image Brand"}, headers=ORIGIN).json()
        product = client.post(
            "/api/v1/products",
            json={
                "name": "Image Product",
                "product_type": "physical",
                "description": "A safe product",
                "category": "Home",
            },
            headers=ORIGIN,
        ).json()
        yield client, factory, {"brand_id": brand["id"], "product_id": product["id"]}
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def upload_source(client: TestClient) -> str:
    response = client.post(
        "/api/v1/media",
        files={"file": ("source.png", deterministic_png(16, 16, "source"), "image/png")},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_image_generation_preserves_source_and_supports_review_readiness(
    context: tuple[TestClient, sessionmaker[Session], dict[str, str]],
) -> None:
    client, factory, ids = context
    source_id = upload_source(client)
    queued = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": ids["brand_id"],
            "product_id": ids["product_id"],
            "source_media_ids": [source_id],
            "operation": "white_background",
            "channel": "amazon",
            "width": 64,
            "height": 64,
            "idempotency_key": "image-e2e-1",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    generation_id = queued.json()["generation_id"]
    with factory() as db:
        run_ai_jobs_once(db, "image-test-worker")
    result = client.get(f"/api/v1/ai/images/generations/{generation_id}", headers=ORIGIN)
    assert result.status_code == 200, result.text
    output = result.json()["outputs"][0]
    assert output["status"] == "needs_review"
    assert output["media_id"] != source_id
    approved = client.post(
        f"/api/v1/ai/images/outputs/{output['id']}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text
    ready = client.get(f"/api/v1/ai/images/outputs/{output['id']}/readiness/amazon", headers=ORIGIN)
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    original = client.get(f"/api/v1/media/{source_id}", headers=ORIGIN)
    assert original.status_code == 200
    assert original.json()["width"] == 16


def test_image_generation_idempotency_and_safe_failure(
    context: tuple[TestClient, sessionmaker[Session], dict[str, str]],
) -> None:
    client, factory, ids = context
    source_id = upload_source(client)
    payload = {
        "brand_id": ids["brand_id"],
        "product_id": ids["product_id"],
        "source_media_ids": [source_id],
        "operation": "remove_background",
        "width": 64,
        "height": 64,
        "idempotency_key": "image-idem",
    }
    first = client.post("/api/v1/ai/images/generate", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/ai/images/generate", json=payload, headers=ORIGIN)
    assert first.status_code == second.status_code == 202
    assert first.json()["generation_id"] == second.json()["generation_id"]
    failed = client.post(
        "/api/v1/ai/images/generate",
        json={**payload, "idempotency_key": "image-invalid", "scenario": "invalid_image"},
        headers=ORIGIN,
    )
    assert failed.status_code == 202
    with factory() as db:
        run_ai_jobs_once(db, "image-failure-worker")
    detail = client.get(
        f"/api/v1/ai/images/generations/{failed.json()['generation_id']}", headers=ORIGIN
    )
    assert detail.status_code == 200
    assert "traceback" not in detail.text.casefold()


def test_review_rejection_and_regeneration_preserve_exact_lineage(
    context: tuple[TestClient, sessionmaker[Session], dict[str, str]],
) -> None:
    client, factory, ids = context
    source_id = upload_source(client)
    source_before = client.get(f"/api/v1/media/{source_id}", headers=ORIGIN).json()
    queued = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": ids["brand_id"],
            "product_id": ids["product_id"],
            "source_media_ids": [source_id],
            "operation": "white_background",
            "channel": "amazon",
            "width": 64,
            "height": 64,
            "idempotency_key": "image-lineage-v1",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    with factory() as db:
        run_ai_jobs_once(db, "image-lineage-worker")
    original = client.get(
        f"/api/v1/ai/images/generations/{queued.json()['generation_id']}", headers=ORIGIN
    ).json()["outputs"][0]
    detail = client.get(f"/api/v1/ai/images/outputs/{original['id']}", headers=ORIGIN)
    assert detail.status_code == 200, detail.text
    assert detail.json()["media_id"] != source_id
    rejected = client.post(
        f"/api/v1/ai/images/outputs/{original['id']}/reject",
        json={"category": "image_quality", "feedback": "Use a cleaner composition."},
        headers=ORIGIN,
    )
    assert rejected.status_code == 200, rejected.text
    regen = client.post(
        f"/api/v1/ai/images/outputs/{original['id']}/regenerate",
        json={
            "reason": "rejected_feedback",
            "feedback": "Use a cleaner composition.",
            "idempotency_key": "image-lineage-v2",
        },
        headers=ORIGIN,
    )
    assert regen.status_code == 202, regen.text
    with factory() as db:
        child = db.scalar(
            select(AIImageOutput).where(AIImageOutput.generation_id == regen.json()["id"])
        )
        assert child is not None
        assert str(child.parent_output_id) == original["id"]
        assert str(child.parent_media_id) == original["media_id"]
        assert child.regeneration_reason == "rejected_feedback"
        run_ai_jobs_once(db, "image-lineage-worker-2")
    after = client.get(f"/api/v1/ai/images/outputs/{original['id']}", headers=ORIGIN)
    assert after.status_code == 200
    assert after.json()["status"] == "rejected"
    assert after.json()["media_id"] == original["media_id"]
    source = client.get(f"/api/v1/media/{source_id}", headers=ORIGIN).json()
    assert source["checksum_sha256"] == source_before["checksum_sha256"]


def test_approval_concurrency_uses_row_lock(
    context: tuple[TestClient, sessionmaker[Session], dict[str, str]],
) -> None:
    client, factory, ids = context
    source_id = upload_source(client)
    queued = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": ids["brand_id"],
            "product_id": ids["product_id"],
            "source_media_ids": [source_id],
            "operation": "white_background",
            "channel": "amazon",
            "width": 64,
            "height": 64,
            "idempotency_key": "image-concurrency",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    with factory() as db:
        run_ai_jobs_once(db, "image-concurrency-worker")
    output = client.get(
        f"/api/v1/ai/images/generations/{queued.json()['generation_id']}", headers=ORIGIN
    ).json()["outputs"][0]

    def approve_once() -> str:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "image@example.com"))
            assert owner is not None
            return decide_output(db, owner, output["id"], "approved", None).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: approve_once(), range(2)))
    assert statuses == ["approved", "approved"]
    with factory() as db:
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "ai.image_approved",
                    AuditEvent.entity_id == output["id"],
                )
            )
        )
        assert len(events) == 1
        row = db.get(AIImageOutput, output["id"])
        assert row is not None and row.status == "approved"
        assert row.approved_by is not None and row.approved_at is not None
