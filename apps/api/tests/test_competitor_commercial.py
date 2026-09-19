"""Focused Slice 10C deterministic commercial analysis certification."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_commercial_models import (
    CompetitorCommercialAnalysis,
    CompetitorComparableCohortEntry,
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


def _setup(api: TestClient, *, email: str | None = None) -> None:
    value = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Commercial Analysis Owner",
            "email": email or f"commercial-{uuid4()}@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert value.status_code == 201, value.text


def _owner(factory: sessionmaker[Session]) -> UUID:
    with factory() as db:
        value = db.scalar(select(User))
        assert value is not None
        return value.id


def _opportunity(api: TestClient) -> str:
    value = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "Commercial fixture opportunity",
            "description": "Fixture",
            "product_concept": "Storage organizer",
            "category": "Home",
            "target_marketplace": "amazon",
            "target_region": "IN",
            "research_objective": "Compare",
            "origin": "competitor_research",
            "idempotency_key": f"commercial-opportunity-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert value.status_code == 201, value.text
    return value.json()["id"]


def _context(api: TestClient, opportunity_id: str) -> str:
    value = api.post(
        "/api/v1/intelligence/competitors/contexts",
        json={
            "subject_type": "PRODUCT_OPPORTUNITY",
            "subject_reference": opportunity_id,
            "marketplace": "amazon",
            "market": "IN",
            "category": "Home",
            "currency": "INR",
            "status": "ACTIVE",
        },
        headers=ORIGIN,
    )
    assert value.status_code == 201, value.text
    return value.json()["id"]


def _product(api: TestClient, context_id: str, *, state: str, index: int) -> str:
    value = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context_id}/products",
        json={
            "title": f"Fixture competitor {index}",
            "brand_reference": "Acme" if index == 0 else None,
            "seller_reference": "Seller A" if index == 0 else None,
            "marketplace": "amazon",
            "external_identifier": f"fixture-{index}",
            "category": "Home",
            "identity_state": state,
            "evidence_state": "AVAILABLE",
            "idempotency_key": f"commercial-product-{index}-{uuid4()}",
        },
        headers=ORIGIN,
    )
    assert value.status_code == 201, value.text
    return value.json()["id"]


def _observation(
    api: TestClient,
    product_id: str,
    *,
    kind: str,
    value: str,
    currency: str | None = "INR",
    key: str,
    freshness: str = "CURRENT",
) -> None:
    now = datetime.now(UTC).isoformat()
    response = api.post(
        f"/api/v1/intelligence/competitors/products/{product_id}/observations",
        json={
            "observation_type": kind,
            "numeric_value": value,
            "currency": currency,
            "source_reference": "local-commercial-fixture",
            "observed_at": now,
            "retrieved_at": now,
            "freshness_state": freshness,
            "observation_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_commercial_analysis_is_decimal_safe_explainable_and_idempotent(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup(api)
    context_id = _context(api, _opportunity(api))
    first = _product(api, context_id, state="CONFIRMED", index=0)
    second = _product(api, context_id, state="PROBABLE", index=1)
    ambiguous = _product(api, context_id, state="AMBIGUOUS", index=2)
    rejected = _product(api, context_id, state="REJECTED", index=3)
    for product_id, price in (
        (first, "100.10"),
        (second, "200.20"),
        (ambiguous, "999"),
        (rejected, "1"),
    ):
        _observation(api, product_id, kind="price", value=price, key=f"price-{product_id}")
    _observation(api, first, kind="rating", value="4.5", key="rating-first")
    _observation(api, first, kind="review_count", value="100", currency=None, key="reviews-first")
    response = api.post(
        f"/api/v1/intelligence/competitors/commercial-analysis/contexts/{context_id}/analyses",
        json={"idempotency_key": "commercial-analysis-1"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["cohort_summary"]["included_count"] == 2
    distribution = body["pricing_analysis"]["distribution"]
    assert distribution["sample_count"] == 2
    assert distribution["minimum"] == "100.100000"
    assert distribution["maximum"] == "200.200000"
    assert body["concentration_analysis"]["brand"]["unknown_count"] == 1
    assert body["review_analysis"]["limitations"]
    assert all(
        item["identity_state"] not in {"AMBIGUOUS", "REJECTED"}
        for item in body["cohort_summary"]["entries"]
        if item["included"]
    )
    replay = api.post(
        f"/api/v1/intelligence/competitors/commercial-analysis/contexts/{context_id}/analyses",
        json={"idempotency_key": "commercial-analysis-1"},
        headers=ORIGIN,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == body["id"]
    cohort = api.get(
        f"/api/v1/intelligence/competitors/commercial-analysis/analyses/{body['id']}/cohort",
        headers=ORIGIN,
    )
    assert cohort.status_code == 200
    assert len(cohort.json()) == 4
    with factory() as db:
        assert db.scalar(
            select(CompetitorCommercialAnalysis).where(
                CompetitorCommercialAnalysis.id == body["id"]
            )
        )
        assert db.scalar(
            select(CompetitorComparableCohortEntry).where(
                CompetitorComparableCohortEntry.analysis_id == body["id"]
            )
        )
        assert db.scalar(select(AuditEvent).where(AuditEvent.entity_id == body["id"]))


def test_multi_currency_is_not_comparable_and_unknown_is_not_zero(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _factory = client
    _setup(api)
    context_id = _context(api, _opportunity(api))
    first = _product(api, context_id, state="CONFIRMED", index=0)
    second = _product(api, context_id, state="CONFIRMED", index=1)
    _observation(api, first, kind="price", value="10", currency="INR", key="inr")
    _observation(api, second, kind="price", value="10", currency="USD", key="usd")
    response = api.post(
        f"/api/v1/intelligence/competitors/commercial-analysis/contexts/{context_id}/analyses",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    pricing = response.json()["pricing_analysis"]
    assert pricing["status"] == "MULTI_CURRENCY_NOT_COMPARABLE"
    assert pricing["currency"] is None
    assert set(pricing["currencies"]) == {"INR", "USD"}
    assert "CURRENCY_COMPARABILITY_REQUIRED" in {
        item["code"] for item in response.json()["research_gaps"]
    }


def test_commercial_system_doctor_is_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _factory = client
    _setup(api)
    response = api.get(
        "/api/v1/intelligence/competitors/commercial-analysis/system-doctor", headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "healthy"


def test_analysis_query_count_is_bounded_for_a_small_cohort(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup(api)
    context_id = _context(api, _opportunity(api))
    _product(api, context_id, state="CONFIRMED", index=0)
    engine = factory.kw["bind"]
    statements: list[str] = []

    def count_statement(*_args: object) -> None:
        statements.append("sql")

    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        response = api.post(
            f"/api/v1/intelligence/competitors/commercial-analysis/contexts/{context_id}/analyses",
            json={"idempotency_key": "commercial-query-count"},
            headers=ORIGIN,
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)
    assert response.status_code == 201, response.text
    assert len(statements) <= 20
