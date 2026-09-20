"""Focused 11B review ingestion and evidence normalization coverage."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.intelligence.review_models import (
    ReviewIngestionBatch,
    ReviewIngestionCandidate,
    ReviewObservation,
    ReviewRecord,
    ReviewSnapshot,
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


def setup_owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Ingestion Owner",
            "email": f"ingestion-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def create_context(api: TestClient) -> str:
    response = api.post(
        "/api/v1/intelligence/reviews/contexts",
        json={
            "name": "Ingestion context",
            "marketplace": "amazon",
            "market": "IN",
            "status": "ACTIVE",
            "idempotency_key": f"context-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_local_fixture_normalizes_deduplicates_and_preserves_history(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    setup_owner(api)
    context_id = create_context(api)
    records = [
        {
            "id": "provider-1",
            "rating": "4",
            "rating_scale": "5",
            "title": "  Great\tproduct  ",
            "body": " Line one\r\nLine two <script>alert('x')</script>",
            "review_date": "2026-01-02",
            "verified_purchase": "yes",
            "helpful_count": "2",
            "variant": {"color": "blue"},
            "provider_metadata": {"api_token": "redact", "region": "IN"},
        },
        {
            "id": "provider-1",
            "rating": "3",
            "rating_scale": "5",
            "title": "Changed",
            "body": "Changed body",
            "review_date": "2026-01-03T00:00:00Z",
            "verified_purchase": False,
            "helpful_count": 3,
        },
        {
            "id": "provider-1",
            "rating": "3",
            "rating_scale": "5",
            "title": "Changed",
            "body": "Changed body",
            "review_date": "2026-01-03T00:00:00Z",
            "verified_purchase": False,
            "helpful_count": 3,
        },
        {"id": "bad-rating", "rating": "8", "rating_scale": "5", "body": "invalid"},
        {"id": "bad-helpful", "body": "invalid", "helpful_count": -1},
        {"id": "oversized", "body": "x" * 100001},
    ]
    response = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
        json={
            "provider": "LOCAL_FIXTURE",
            "mode": "LOCAL_FIXTURE",
            "records": records,
            "idempotency_key": "batch-1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["batch"]["status"] == "PARTIAL"
    assert payload["batch"]["accepted_count"] == 1
    assert payload["batch"]["rejected_count"] == 3
    assert payload["batch"]["duplicate_count"] == 2
    assert payload["batch"]["updated_observation_count"] == 1
    classifications = [item["duplicate_classification"] for item in payload["candidates"]]
    assert "AUTHORITATIVE_DUPLICATE" in classifications
    assert "EXACT_REPLAY" in classifications
    assert all("api_token" not in item["raw_payload"] for item in payload["candidates"])
    assert payload["snapshot"]["review_count"] == 1

    repeated = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
        json={
            "provider": "LOCAL_FIXTURE",
            "mode": "LOCAL_FIXTURE",
            "records": records,
            "idempotency_key": "batch-1",
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    assert repeated.json()["batch"]["id"] == payload["batch"]["id"]
    with factory() as db:
        assert db.scalar(select(func_count(ReviewRecord))) == 1
        assert db.scalar(select(func_count(ReviewObservation))) == 2
        assert db.scalar(select(func_count(ReviewSnapshot))) == 1
        assert db.scalar(select(func_count(ReviewIngestionBatch))) == 1
        assert db.scalar(select(func_count(ReviewIngestionCandidate))) == 6
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "review.ingestion_requested" in actions
        assert "review.ingestion_completed" in actions


def test_ingestion_modes_fail_closed_and_do_not_create_reviews(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    setup_owner(api)
    context_id = create_context(api)
    for mode, expected in (("DISABLED", "FAILED"), ("LIVE_READ_ONLY", "FAILED")):
        response = api.post(
            f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
            json={
                "provider": "LOCAL_FIXTURE",
                "mode": mode,
                "records": [{"id": "not-created", "body": "fixture"}],
                "idempotency_key": mode,
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        assert response.json()["batch"]["status"] == expected
        assert response.json()["batch"]["accepted_count"] == 0
    with factory() as db:
        assert db.scalar(select(func_count(ReviewRecord))) == 0


def func_count(model):
    from sqlalchemy import func

    return func.count(model.id)
