"""Focused 11C deterministic Review Intelligence analysis coverage."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewAnalysisAnnotation,
    ReviewAnalysisItem,
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

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def setup_context(api: TestClient) -> str:
    owner = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Analysis Owner",
            "email": f"analysis-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert owner.status_code == 201, owner.text
    context = api.post(
        "/api/v1/intelligence/reviews/contexts",
        json={
            "name": "Analysis context",
            "marketplace": "amazon",
            "market": "IN",
            "status": "ACTIVE",
            "idempotency_key": f"analysis-context-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    return cast(str, context.json()["id"])


def ingest_fixture(api: TestClient, context_id: str, suffix: str = "one") -> dict[str, Any]:
    response = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
        json={
            "provider": "LOCAL_FIXTURE",
            "mode": "LOCAL_FIXTURE",
            "records": [
                {
                    "id": f"positive-{suffix}",
                    "rating": "5",
                    "rating_scale": "5",
                    "title": "Great design",
                    "body": "I love this easy and durable product",
                    "language": "en",
                },
                {
                    "id": f"negative-{suffix}",
                    "rating": "1",
                    "rating_scale": "5",
                    "title": "Battery issue",
                    "body": "Poor battery and broken packaging",
                    "language": "en",
                },
                {
                    "id": f"mixed-{suffix}",
                    "rating": "4",
                    "rating_scale": "5",
                    "title": "Good but slow",
                    "body": "Great product but slow delivery; wish it had a travel case",
                    "language": "en",
                },
                {
                    "id": f"unrated-{suffix}",
                    "title": "Neutral",
                    "body": "The color is okay",
                    "language": "en",
                },
                {
                    "id": f"unsupported-{suffix}",
                    "title": "Non English",
                    "body": "Buena calidad",
                    "language": "es",
                },
                {"id": f"empty-{suffix}", "rating": "3", "rating_scale": "5", "language": "en"},
            ],
            "idempotency_key": f"analysis-ingestion-{suffix}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_deterministic_analysis_is_evidence_backed_and_idempotent(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    context_id = setup_context(api)
    ingestion = ingest_fixture(api, context_id)
    snapshot_id = ingestion["snapshot"]["id"]
    response = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": snapshot_id, "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    analysis = payload["analysis"]
    assert analysis["status"] == "COMPLETED"
    assert analysis["included_records"] == 4
    assert analysis["excluded_records"] == 2
    assert {entry["reason"] for entry in analysis["cohort_json"]["excluded"]} == {
        "UNSUPPORTED_LANGUAGE",
        "INSUFFICIENT_TEXT",
    }
    assert set(analysis["sentiment_distribution"]) == {
        "POSITIVE",
        "NEGATIVE",
        "MIXED",
        "NEUTRAL",
        "UNKNOWN",
    }
    assert "sales" not in str(payload).lower()
    item_types = {item["item_type"] for item in payload["items"]}
    assert {"PAIN_POINT", "PRAISED_ATTRIBUTE", "FEATURE_REQUEST", "QUALITY_ISSUE"} <= item_types
    assert any(item["canonical_label"] == "BATTERY_LIFE" for item in payload["items"])
    repeated = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": snapshot_id, "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    assert repeated.json()["analysis"]["id"] == analysis["id"]
    with factory() as db:
        assert db.scalar(select(func.count(ReviewAnalysis.id))) == 1
        assert db.scalar(select(func.count(ReviewAnalysisAnnotation.id))) == 4
        assert (db.scalar(select(func.count(ReviewAnalysisItem.id))) or 0) >= 4
        assert "review.analysis_created" in set(db.scalars(select(AuditEvent.action)))


def test_changed_snapshot_creates_new_analysis_and_modes_fail_closed(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    context_id = setup_context(api)
    first = ingest_fixture(api, context_id, "first")
    first_analysis = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": first["snapshot"]["id"], "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert first_analysis.status_code == 201
    second = ingest_fixture(api, context_id, "second")
    changed = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": second["snapshot"]["id"], "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert changed.status_code == 201
    assert changed.json()["analysis"]["id"] != first_analysis.json()["analysis"]["id"]
    for mode in ("DISABLED", "LIVE_READ_ONLY"):
        failed = api.post(
            f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
            json={"snapshot_id": second["snapshot"]["id"], "mode": mode},
            headers=ORIGIN,
        )
        assert failed.status_code == 201, failed.text
        assert failed.json()["analysis"]["status"] == "FAILED"
        assert "provider" not in failed.text.lower()
    with factory() as db:
        assert db.scalar(select(func.count(ReviewAnalysis.id))) == 4


def test_analysis_current_and_system_doctor_expose_safe_integrity_counters(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _ = client
    context_id = setup_context(api)
    ingest_fixture(api, context_id)
    current = api.get(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses/current", headers=ORIGIN
    )
    assert current.status_code == 200
    assert current.json() is None
    doctor = api.get("/api/v1/intelligence/reviews/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["status"] == "PASS"
    assert "orphan_analyses" in doctor.json()["counts"]
