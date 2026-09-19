"""Focused Slice 10D competitive change intelligence certification."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.intelligence.competitor_change_models import (
    CompetitorChangeAlertEligibility,
    CompetitorChangeComparison,
    CompetitorChangeEvent,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session():
        with factory() as value:
            yield value

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _setup(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Change Intelligence Owner",
            "email": f"change-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _opportunity(api: TestClient) -> str:
    response = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "Change fixture opportunity",
            "description": "Fixture",
            "product_concept": "Storage organizer",
            "category": "Home",
            "target_marketplace": "amazon",
            "target_region": "IN",
            "research_objective": "Compare",
            "origin": "competitor_research",
            "idempotency_key": f"change-opportunity-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _context(api: TestClient) -> str:
    response = api.post(
        "/api/v1/intelligence/competitors/contexts",
        json={
            "subject_type": "PRODUCT_OPPORTUNITY",
            "subject_reference": _opportunity(api),
            "marketplace": "amazon",
            "market": "IN",
            "category": "Home",
            "currency": "INR",
            "status": "ACTIVE",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _product(api: TestClient, context_id: str, index: int) -> str:
    response = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context_id}/products",
        json={
            "title": f"Change competitor {index}",
            "brand_reference": f"Brand {index}",
            "seller_reference": f"Seller {index}",
            "marketplace": "amazon",
            "external_identifier": f"change-{index}",
            "category": "Home",
            "identity_state": "CONFIRMED",
            "evidence_state": "AVAILABLE",
            "idempotency_key": f"change-product-{index}-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _observation(
    api: TestClient,
    product_id: str,
    kind: str,
    value: str,
    key: str,
    *,
    currency: str | None = "INR",
    when: datetime | None = None,
) -> None:
    timestamp = (when or datetime.now(UTC)).isoformat()
    response = api.post(
        f"/api/v1/intelligence/competitors/products/{product_id}/observations",
        json={
            "observation_type": kind,
            "numeric_value": value,
            "currency": currency,
            "source_reference": "local-change-fixture",
            "observed_at": timestamp,
            "retrieved_at": timestamp,
            "freshness_state": "CURRENT",
            "observation_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _analysis(api: TestClient, context_id: str, key: str) -> dict[str, object]:
    response = api.post(
        f"/api/v1/intelligence/competitors/commercial-analysis/contexts/{context_id}/analyses",
        json={"idempotency_key": key},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_change_comparison_is_replayable_and_tracks_price_entry_and_alerts(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup(api)
    context_id = _context(api)
    first_product = _product(api, context_id, 1)
    _observation(api, first_product, "price", "100", "price-before")
    _observation(api, first_product, "rating", "4.0", "rating-before")
    baseline = _analysis(api, context_id, "change-analysis-before")
    second_product = _product(api, context_id, 2)
    _observation(api, first_product, "price", "125", "price-after")
    _observation(api, first_product, "rating", "4.6", "rating-after")
    _observation(api, second_product, "price", "80", "price-new")
    current = _analysis(api, context_id, "change-analysis-after")
    response = api.post(
        f"/api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/comparisons",
        json={
            "baseline_analysis_id": baseline["id"],
            "current_analysis_id": current["id"],
            "idempotency_key": "comparison-1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    types = {item["change_type"] for item in body["events"]}
    assert "PRICE_INCREASED" in types
    assert "COMPETITOR_ADDED" in types
    assert any(item["materiality"] in {"LOW", "MODERATE", "HIGH"} for item in body["events"])
    replay = api.post(
        f"/api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/comparisons",
        json={
            "baseline_analysis_id": baseline["id"],
            "current_analysis_id": current["id"],
            "idempotency_key": "comparison-1",
        },
        headers=ORIGIN,
    )
    assert replay.status_code == 201
    assert replay.json()["comparison"]["id"] == body["comparison"]["id"]
    timeline = api.get(
        f"/api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/changes",
        headers=ORIGIN,
    )
    assert timeline.status_code == 200
    with factory() as db:
        assert db.scalar(
            select(CompetitorChangeComparison).where(
                CompetitorChangeComparison.id == UUID(body["comparison"]["id"])
            )
        )
        assert db.scalar(
            select(CompetitorChangeEvent).where(
                CompetitorChangeEvent.comparison_id == UUID(body["comparison"]["id"])
            )
        )
        assert db.scalar(
            select(CompetitorChangeAlertEligibility).where(
                CompetitorChangeAlertEligibility.context_id == UUID(context_id)
            )
        )
        assert db.scalar(
            select(AuditEvent).where(AuditEvent.entity_id == UUID(body["comparison"]["id"]))
        )


def test_change_comparison_keeps_currency_unknown_and_zero_denominator_safe(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _factory = client
    _setup(api)
    context_id = _context(api)
    product_id = _product(api, context_id, 1)
    _observation(api, product_id, "price", "0", "price-zero", currency="INR")
    baseline = _analysis(api, context_id, "change-analysis-zero-before")
    _observation(api, product_id, "price", "10", "price-usd", currency="USD")
    current = _analysis(api, context_id, "change-analysis-zero-after")
    response = api.post(
        f"/api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/comparisons/run",
        json={"baseline_analysis_id": baseline["id"], "current_analysis_id": current["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    price_events = [
        item for item in response.json()["events"] if item["change_type"].startswith("PRICE_")
    ]
    assert price_events
    assert all(item["percentage_delta"] is None for item in price_events)
    assert all(item["status"] == "UNRESOLVED" for item in price_events)


def test_change_system_doctor_is_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _factory = client
    _setup(api)
    response = api.get(
        "/api/v1/intelligence/competitors/change-intelligence/system-doctor", headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "healthy"
