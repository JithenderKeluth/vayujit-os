"""Focused 8E.3 resilience scoring and recommendation coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.resilience_models import (
    SupplierPortfolioConfidenceProjection,
    SupplierPortfolioRecommendation,
    SupplierPortfolioResilienceDimensionResult,
    SupplierPortfolioResilienceScore,
    SupplierPortfolioRiskProjection,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None, "VAYUJIT_TEST_DATABASE_URL is required."
    engine = create_engine(TEST_DATABASE_URL)
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


def _setup_owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Resilience Owner",
            "email": "resilience@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _suppliers(factory: sessionmaker[Session]) -> list[uuid.UUID]:
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        rows = [
            CrossMarketplaceSupplier(
                owner_id=owner.id,
                canonical_key=f"resilience-{index}",
                display_name=f"Resilience Supplier {index}",
                identity_state="MATCH",
                aliases=[],
                view_json={},
                confidence_score=90,
                source_diversity_score=2,
                freshness_status="fresh",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for index in range(4)
        ]
        db.add_all(rows)
        db.commit()
        return [row.id for row in rows]


def _portfolio(api: TestClient) -> str:
    response = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "Resilience portfolio", "idempotency_key": "resilience-portfolio-1"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _member(
    api: TestClient,
    portfolio_id: str,
    supplier_id: uuid.UUID,
    *,
    allocation: float,
    product_ids: list[uuid.UUID],
    country: str,
    status: str,
    due_diligence: bool,
    freshness: str,
) -> None:
    response = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members",
        json={
            "supplier_id": str(supplier_id),
            "allocation_percent": allocation,
            "associated_products": [str(value) for value in product_ids],
            "country_region": country,
            "evidence_freshness": freshness,
            "confidence": 90,
            "risk": "low",
            "capabilities": ["precision manufacturing"],
            "alternate_source_status": status,
            "due_diligence_lineage_id": str(uuid.uuid4()) if due_diligence else None,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _assess(api: TestClient, portfolio_id: str, key: str) -> str:
    response = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json={"idempotency_key": key},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_resilience_is_deterministic_explainable_and_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    portfolio_id = _portfolio(api)
    supplier_a, supplier_b, supplier_c, supplier_d = _suppliers(factory)
    products = [uuid.uuid4(), uuid.uuid4()]
    _member(
        api,
        portfolio_id,
        supplier_a,
        allocation=70,
        product_ids=products,
        country="CN",
        status="qualified",
        due_diligence=True,
        freshness="fresh",
    )
    _member(
        api,
        portfolio_id,
        supplier_b,
        allocation=25,
        product_ids=[products[0]],
        country="IN",
        status="qualified",
        due_diligence=True,
        freshness="fresh",
    )
    _member(
        api,
        portfolio_id,
        supplier_c,
        allocation=15,
        product_ids=[products[0]],
        country="VN",
        status="shortlisted",
        due_diligence=False,
        freshness="fresh",
    )
    _member(
        api,
        portfolio_id,
        supplier_d,
        allocation=0,
        product_ids=[products[1]],
        country="IN",
        status="candidate",
        due_diligence=False,
        freshness="stale",
    )
    assessment_id = _assess(api, portfolio_id, "resilience-assessment-1")

    first = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience", headers=ORIGIN
    )
    repeated = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience", headers=ORIGIN
    )
    assert first.status_code == 200, first.text
    assert repeated.status_code == 200, repeated.text
    assert first.json() == repeated.json()
    bundle = first.json()
    assert bundle["assessment_version_id"] == assessment_id
    assert len(bundle["dimensions"]) == 12
    assert {row["dimension"] for row in bundle["dimensions"]} == {
        "SUPPLIER_DIVERSITY",
        "GEOGRAPHIC_DIVERSITY",
        "QUALIFIED_ALTERNATIVE_COVERAGE",
        "VERIFIED_ALTERNATIVE_COVERAGE",
        "COMMERCIAL_FLEXIBILITY",
        "LEAD_TIME_RESILIENCE",
        "COST_RESILIENCE",
        "CAPABILITY_REDUNDANCY",
        "EVIDENCE_CONFIDENCE",
        "FRESHNESS",
        "CONTRADICTION_RISK",
        "DUE_DILIGENCE_COVERAGE",
    }
    assert 0 <= bundle["score"]["score"] <= 100
    assert bundle["score"]["evidence_status"] == "PARTIAL"
    assert bundle["confidence"]["value"] == 90.0
    assert bundle["risk"]["classification"] == "LOW"
    assert any(
        row["recommendation_type"] == "QUALIFY_SECOND_SUPPLIER" for row in bundle["recommendations"]
    )
    assert all(row["status"] == "OPEN" for row in bundle["recommendations"])

    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience/dimensions",
            headers=ORIGIN,
        ).json()
        == bundle["dimensions"]
    )
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recommendations",
            headers=ORIGIN,
        ).json()
        == bundle["recommendations"]
    )
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/risk", headers=ORIGIN
        ).json()
        == bundle["risk"]
    )
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/confidence", headers=ORIGIN
        ).json()
        == bundle["confidence"]
    )
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{'0' * 32}/resilience", headers=ORIGIN
        ).status_code
        == 404
    )

    with factory() as db:
        assert len(list(db.scalars(select(SupplierPortfolioResilienceDimensionResult)))) == 12
        assert db.scalar(select(SupplierPortfolioResilienceScore)) is not None
        assert db.scalar(select(SupplierPortfolioConfidenceProjection)) is not None
        assert db.scalar(select(SupplierPortfolioRiskProjection)) is not None
        assert db.scalar(select(SupplierPortfolioRecommendation)) is not None


def test_resilience_keeps_historical_assessment_projection(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    portfolio_id = _portfolio(api)
    supplier_a, supplier_b, supplier_c, supplier_d = _suppliers(factory)
    product_id = uuid.uuid4()
    _member(
        api,
        portfolio_id,
        supplier_a,
        allocation=100,
        product_ids=[product_id],
        country="IN",
        status="qualified",
        due_diligence=True,
        freshness="fresh",
    )
    _member(
        api,
        portfolio_id,
        supplier_b,
        allocation=0,
        product_ids=[product_id],
        country="CN",
        status="candidate",
        due_diligence=False,
        freshness="stale",
    )
    _member(
        api,
        portfolio_id,
        supplier_c,
        allocation=0,
        product_ids=[product_id],
        country="VN",
        status="shortlisted",
        due_diligence=False,
        freshness="fresh",
    )
    _member(
        api,
        portfolio_id,
        supplier_d,
        allocation=0,
        product_ids=[product_id],
        country="IN",
        status="candidate",
        due_diligence=False,
        freshness="stale",
    )
    first_assessment = _assess(api, portfolio_id, "resilience-assessment-a")
    first = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience",
        headers=ORIGIN,
    )
    assert first.status_code == 200, first.text
    second_assessment = _assess(api, portfolio_id, "resilience-assessment-b")
    second = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience",
        headers=ORIGIN,
    )
    assert second.status_code == 200, second.text
    assert first_assessment != second_assessment
    historical = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience",
        params={"assessment_version_id": first_assessment},
        headers=ORIGIN,
    )
    assert historical.status_code == 200, historical.text
    assert historical.json()["assessment_version_id"] == first_assessment
    with factory() as db:
        assert len(list(db.scalars(select(SupplierPortfolioResilienceScore)))) == 2
