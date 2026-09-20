"""Focused 11D product-gap and opportunity-signal certification."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _context(api: TestClient) -> str:
    owner = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Gap Owner",
            "email": f"gap-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert owner.status_code == 201, owner.text
    context = api.post(
        "/api/v1/intelligence/reviews/contexts",
        json={
            "name": "Gap context",
            "marketplace": "amazon",
            "market": "IN",
            "status": "ACTIVE",
            "idempotency_key": f"gap-context-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    return cast(str, context.json()["id"])


def _analysis(api: TestClient, context_id: str) -> str:
    ingestion = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
        json={
            "provider": "LOCAL_FIXTURE",
            "mode": "LOCAL_FIXTURE",
            "records": [
                {
                    "id": "feature-1",
                    "title": "Wish it had USB-C",
                    "body": "Please add USB-C charging",
                    "language": "en",
                },
                {
                    "id": "feature-2",
                    "title": "Need USB-C",
                    "body": "Would like USB-C and a travel case",
                    "language": "en",
                },
                {
                    "id": "quality-1",
                    "title": "Broken battery",
                    "body": "Poor battery and broken casing",
                    "language": "en",
                },
                {
                    "id": "quality-2",
                    "title": "Great but fragile",
                    "body": "Great product but fragile casing",
                    "language": "en",
                },
                {
                    "id": "praise-1",
                    "title": "Very comfortable",
                    "body": "Love the comfort and easy setup",
                    "language": "en",
                },
                {"id": "other-1", "title": "Plain", "body": "The color is okay", "language": "en"},
            ],
            "idempotency_key": f"gap-ingestion-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert ingestion.status_code == 201, ingestion.text
    result: dict[str, Any] = cast(dict[str, Any], ingestion.json())
    analysis = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": result["snapshot"]["id"], "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert analysis.status_code == 201, analysis.text
    return cast(str, analysis.json()["analysis"]["id"])


def test_gap_analysis_is_evidence_backed_versioned_and_safe(client: TestClient) -> None:
    context_id = _context(client)
    review_analysis_id = _analysis(client, context_id)
    response = client.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/gap-analyses",
        json={"review_analysis_id": review_analysis_id},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["analysis"]["status"] == "COMPLETED"
    assert payload["product_gaps"]
    assert payload["opportunity_signals"]
    assert any(item["gap_type"] == "MISSING_FEATURE" for item in payload["product_gaps"])
    assert any(item["signal_type"] == "FEATURE_ADDITION" for item in payload["opportunity_signals"])
    assert any(
        item["signal_type"] == "PRESERVE_STRENGTH" for item in payload["opportunity_signals"]
    )
    feature = next(
        item for item in payload["product_gaps"] if item["gap_type"] == "MISSING_FEATURE"
    )
    assert feature["support_count"] <= feature["cohort_count"]
    assert "DEMAND_VALIDATION_REQUIRED" in feature["required_validations"]
    assert feature["supporting_review_ids"]
    assert feature["limitations"]
    assert "winning" not in response.text.lower()
    assert "revenue" not in response.text.lower()
    assert "sales" not in response.text.lower()
    repeated = client.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/gap-analyses",
        json={"review_analysis_id": review_analysis_id},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    assert repeated.json()["analysis"]["id"] == payload["analysis"]["id"]
    detail = client.get(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/gap-analyses/current",
        headers=ORIGIN,
    )
    assert detail.status_code == 200


def test_gap_analysis_system_doctor_and_storage(client: TestClient) -> None:
    context_id = _context(client)
    review_analysis_id = _analysis(client, context_id)
    created = client.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/gap-analyses",
        json={"review_analysis_id": review_analysis_id},
        headers=ORIGIN,
    )
    assert created.status_code == 201
    doctor = client.get("/api/v1/intelligence/reviews/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["status"] == "PASS", doctor.text
