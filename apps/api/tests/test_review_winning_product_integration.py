"""Focused 11F Review Intelligence -> Winning Product projection coverage."""

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
from vayujit_api.intelligence.review_winning_product_models import ReviewWinningProductProjection
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


def _owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Review Winner Owner",
            "email": f"review-winner-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _opportunity(api: TestClient) -> tuple[str, str]:
    opportunity = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={"name": "Disposable review winner", "target_marketplace": "amazon"},
        headers=ORIGIN,
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = cast(str, opportunity.json()["id"])
    constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={"currency": "INR", "idempotency_key": f"constraint-{uuid4()}"},
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"evidence_state": "partial", "status": "created"},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return opportunity_id, cast(str, assessment.json()["id"])


def _review_analysis(api: TestClient, opportunity_id: str) -> str:
    context = api.post(
        "/api/v1/intelligence/reviews/contexts",
        json={
            "name": "Linked review context",
            "product_opportunity_id": opportunity_id,
            "marketplace": "amazon",
            "market": "IN",
            "status": "ACTIVE",
            "idempotency_key": f"review-context-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    context_id = cast(str, context.json()["id"])
    ingestion = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
        json={
            "provider": "LOCAL_FIXTURE",
            "mode": "LOCAL_FIXTURE",
            "records": [
                {
                    "id": "r1",
                    "rating": "5",
                    "rating_scale": "5",
                    "title": "Great",
                    "body": "Love the comfort",
                },
                {
                    "id": "r2",
                    "rating": "2",
                    "rating_scale": "5",
                    "title": "Battery issue",
                    "body": "Poor battery and broken casing",
                },
            ],
            "idempotency_key": f"review-ingestion-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert ingestion.status_code == 201, ingestion.text
    snapshot_id = ingestion.json()["snapshot"]["id"]
    analysis = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": snapshot_id, "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert analysis.status_code == 201, analysis.text
    return context_id


def test_review_projection_is_linked_replayable_and_does_not_score(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _owner(api)
    opportunity_id, assessment_id = _opportunity(api)
    _review_analysis(api, opportunity_id)
    first = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/review-projection",
        json={},
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    payload = cast(dict[str, Any], first.json())
    assert payload["readiness"] in {"AVAILABLE", "PARTIAL", "RESEARCH_REQUIRED"}
    assert payload["context_id"] is not None
    assert payload["feedback_evidence"]["pain_points"]
    assert "overall_score" not in first.text
    assert "high_demand" not in first.text.lower()
    repeated = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/review-projection",
        json={},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == payload["id"]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ReviewWinningProductProjection)) == 1
        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "intelligence.REVIEW_WINNING_PRODUCT_PROJECTION_CREATED"
            )
        )
        assert event is not None


def test_unlinked_opportunity_returns_insufficient_evidence_without_fabrication(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _ = client
    _owner(api)
    opportunity_id, assessment_id = _opportunity(api)
    response = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/review-projection",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["readiness"] == "INSUFFICIENT_EVIDENCE"
    assert payload["context_id"] is None
    assert payload["research_gaps"]
    assert payload["limitations"]
