"""Focused 11E Review Change Intelligence coverage."""

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
from vayujit_api.intelligence.review_models import ReviewChangeComparison, ReviewChangeEvent
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


def _context(api: TestClient, name: str = "Change context", setup_owner: bool = True) -> str:
    if setup_owner:
        owner = api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "Change Owner",
                "email": f"change-{uuid4()}@example.com",
                "password": "correct horse battery staple",
                "password_confirmation": "correct horse battery staple",
            },
            headers=ORIGIN,
        )
        assert owner.status_code == 201, owner.text
    response = api.post(
        "/api/v1/intelligence/reviews/contexts",
        json={
            "name": name,
            "marketplace": "amazon",
            "market": "IN",
            "status": "ACTIVE",
            "idempotency_key": f"change-context-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


def _analysis(
    api: TestClient, context_id: str, suffix: str, changed: bool = False, identity_suffix: str = ""
) -> str:
    records: list[dict[str, Any]] = [
        {
            "id": "battery-1",
            "rating": "2" if changed else "5",
            "rating_scale": "5",
            "title": "Battery issue" if changed else "Great battery",
            "body": "Poor battery and broken casing" if changed else "Great durable battery",
            "language": "en",
        },
        {
            "id": "feature-1",
            "rating": "4",
            "rating_scale": "5",
            "title": "Need USB C",
            "body": "Please add USB-C charging and a travel case",
            "language": "en",
        },
        {
            "id": "praise-1",
            "rating": "5",
            "rating_scale": "5",
            "title": "Comfortable",
            "body": "Love the comfort and easy setup",
            "language": "en",
        },
        {
            "id": f"new-{suffix}",
            "rating": "1" if changed else "3",
            "rating_scale": "5",
            "title": "Fragile",
            "body": "Poor fragile packaging" if changed else "The color is okay",
            "language": "en",
        },
    ]
    if identity_suffix:
        for record in records:
            record["id"] = f"{record['id']}-{identity_suffix}"
    ingestion = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/ingestions",
        json={
            "provider": "LOCAL_FIXTURE",
            "mode": "LOCAL_FIXTURE",
            "records": records,
            "idempotency_key": f"change-ingestion-{suffix}-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert ingestion.status_code == 201, ingestion.text
    payload = cast(dict[str, Any], ingestion.json())
    analysis = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/analyses",
        json={"snapshot_id": payload["snapshot"]["id"], "mode": "LOCAL_FIXTURE"},
        headers=ORIGIN,
    )
    assert analysis.status_code == 201, analysis.text
    return cast(str, analysis.json()["analysis"]["id"])


def test_change_comparison_is_evidence_backed_replayable_and_filterable(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    context_id = _context(api)
    baseline = _analysis(api, context_id, "baseline")
    current = _analysis(api, context_id, "current", changed=True)
    response = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons",
        json={"baseline_analysis_id": baseline, "current_analysis_id": current},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["comparison"]["status"] == "COMPLETED"
    assert payload["events"]
    assert any(event["change_type"] == "REVIEW_COUNT_CHANGE" for event in payload["events"])
    assert any(event["change_type"] == "PAIN_POINT_APPEARED" for event in payload["events"])
    assert all("review evidence" in event["explanation"].lower() for event in payload["events"])
    assert "demand trend" not in response.text.lower()
    assert "revenue" not in response.text.lower()
    assert "sales" not in response.text.lower()
    comparison_id = payload["comparison"]["id"]
    replay_signatures = []
    for _ in range(3):
        repeated = api.post(
            f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons",
            json={"baseline_analysis_id": baseline, "current_analysis_id": current},
            headers=ORIGIN,
        )
        assert repeated.status_code == 201, repeated.text
        assert repeated.json()["comparison"]["id"] == comparison_id
        replay_signatures.append(
            [
                (
                    event["change_type"],
                    event["subject_key"],
                    event["absolute_delta"],
                    event["relative_delta"],
                    event["materiality"],
                    event["status"],
                    event["alert_eligibility"],
                )
                for event in repeated.json()["events"]
            ]
        )
    assert replay_signatures[0] == replay_signatures[1] == replay_signatures[2]
    events = api.get(
        f"/api/v1/intelligence/reviews/change-comparisons/{comparison_id}/events",
        params={"change_type": "REVIEW_COUNT_CHANGE"},
        headers=ORIGIN,
    )
    assert events.status_code == 200, events.text
    assert events.json()["total"] == 1
    history = api.get(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons",
        headers=ORIGIN,
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    with factory() as db:
        assert db.scalar(select(func.count(ReviewChangeComparison.id))) == 1
        assert db.scalar(select(func.count(ReviewChangeEvent.id))) == len(payload["events"])
        assert "review.change_comparison_created" in set(db.scalars(select(AuditEvent.action)))


def test_change_comparison_rejects_invalid_pair_and_exposes_doctor_counters(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _ = client
    context_id = _context(api)
    baseline = _analysis(api, context_id, "baseline")
    same = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons",
        json={"baseline_analysis_id": baseline, "current_analysis_id": baseline},
        headers=ORIGIN,
    )
    assert same.status_code == 409, same.text
    other_context = _context(api, "Unrelated context", setup_owner=False)
    other_current = _analysis(
        api, other_context, "other-current", changed=True, identity_suffix="other"
    )
    cross_context = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons",
        json={"baseline_analysis_id": baseline, "current_analysis_id": other_current},
        headers=ORIGIN,
    )
    assert cross_context.status_code == 404, cross_context.text
    doctor = api.get("/api/v1/intelligence/reviews/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS", doctor.text
    assert doctor.json()["counts"]["duplicate_change_comparison_fingerprints"] == 0
    change_doctor = api.get(
        "/api/v1/intelligence/reviews/system-doctor/change-intelligence", headers=ORIGIN
    )
    assert change_doctor.status_code == 200, change_doctor.text
    assert change_doctor.json()["status"] == "PASS", change_doctor.text


def test_change_research_gap_and_current_endpoints_are_bounded(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _ = client
    context_id = _context(api)
    baseline = _analysis(api, context_id, "baseline")
    current = _analysis(api, context_id, "current", changed=True)
    created = api.post(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons",
        json={"baseline_analysis_id": baseline, "current_analysis_id": current},
        headers=ORIGIN,
    )
    assert created.status_code == 201
    current_response = api.get(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/change-comparisons/current",
        headers=ORIGIN,
    )
    assert current_response.status_code == 200
    gaps = api.get(
        f"/api/v1/intelligence/reviews/contexts/{context_id}/research-gaps",
        headers=ORIGIN,
    )
    assert gaps.status_code == 200, gaps.text
    assert set(gaps.json()) >= {"items", "total", "limit", "offset"}
