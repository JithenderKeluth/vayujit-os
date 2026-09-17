"""Focused 8E.2 concentration, dependency, and alternate-readiness coverage."""

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
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAlternateReadiness,
    SupplierPortfolioConcentrationMetric,
    SupplierPortfolioDependencyFinding,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None
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
            "full_name": "8E.2 Owner",
            "email": "portfolio-analysis@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _suppliers(factory: sessionmaker[Session], count: int) -> list[uuid.UUID]:
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        rows = [
            CrossMarketplaceSupplier(
                owner_id=owner.id,
                canonical_key=f"portfolio-analysis-{index}",
                display_name=f"Supplier {index}",
                identity_state="MATCH",
                aliases=[],
                view_json={},
                confidence_score=90,
                source_diversity_score=2,
                freshness_status="fresh",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for index in range(count)
        ]
        db.add_all(rows)
        db.commit()
        return [row.id for row in rows]


def _portfolio(api: TestClient) -> str:
    response = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "Analysis portfolio", "idempotency_key": "analysis-portfolio-1"},
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
    products: list[uuid.UUID],
    country: str,
    status: str,
    dd: bool = False,
    freshness: str = "fresh",
) -> None:
    response = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members",
        json={
            "supplier_id": str(supplier_id),
            "allocation_percent": allocation,
            "associated_products": [str(value) for value in products],
            "country_region": country,
            "evidence_freshness": freshness,
            "confidence": 90,
            "risk": "low",
            "capabilities": ["precision manufacturing"],
            "alternate_source_status": status,
            "due_diligence_lineage_id": str(uuid.uuid4()) if dd else None,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _assessment(api: TestClient, portfolio_id: str) -> None:
    response = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json={"idempotency_key": "analysis-assessment-1"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_concentration_hhi_and_replay_are_deterministic(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    portfolio_id = _portfolio(api)
    product_one, product_two, product_three = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    supplier_a, supplier_b, supplier_c, supplier_d = _suppliers(factory, 4)
    _member(
        api,
        portfolio_id,
        supplier_a,
        allocation=60,
        products=[product_one, product_two],
        country="CN",
        status="qualified",
        dd=True,
    )
    _member(
        api,
        portfolio_id,
        supplier_b,
        allocation=25,
        products=[product_one],
        country="IN",
        status="qualified",
        dd=True,
    )
    _member(
        api,
        portfolio_id,
        supplier_c,
        allocation=15,
        products=[product_one, product_three],
        country="VN",
        status="shortlisted",
    )
    _member(
        api,
        portfolio_id,
        supplier_d,
        allocation=0,
        products=[product_three],
        country="IN",
        status="candidate",
        freshness="stale",
    )
    _assessment(api, portfolio_id)

    first = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/concentration", headers=ORIGIN
    )
    repeated = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/concentration", headers=ORIGIN
    )
    assert first.status_code == 200, first.text
    assert repeated.status_code == 200, repeated.text
    assert first.json() == repeated.json()
    metrics = {(row["dimension"], row["metric_type"]): row for row in first.json()["results"]}
    assert metrics[("supplier", "largest_supplier_share")]["value"] == 60.0
    assert metrics[("supplier", "supplier_allocation_hhi")]["value"] == pytest.approx(0.445)
    assert metrics[("product", "single_source_percentage")]["value"] == pytest.approx(
        66.666666, rel=1e-5
    )
    assert metrics[("product", "multi_source_percentage")]["value"] == pytest.approx(
        33.333333, rel=1e-5
    )
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{'0' * 32}/concentration", headers=ORIGIN
        ).status_code
        == 404
    )
    with factory() as db:
        assert len(list(db.scalars(select(SupplierPortfolioConcentrationMetric)))) == len(metrics)


def test_dependencies_and_readiness_are_explainable_and_versioned(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    portfolio_id = _portfolio(api)
    product_id = uuid.uuid4()
    supplier_a, supplier_b = _suppliers(factory, 2)
    _member(
        api,
        portfolio_id,
        supplier_a,
        allocation=100,
        products=[product_id],
        country="CN",
        status="qualified",
        dd=True,
    )
    _member(
        api,
        portfolio_id,
        supplier_b,
        allocation=0,
        products=[product_id],
        country="IN",
        status="shortlisted",
    )
    _assessment(api, portfolio_id)

    dependencies = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/dependencies", headers=ORIGIN
    )
    alternates = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/alternates", headers=ORIGIN
    )
    assert dependencies.status_code == 200, dependencies.text
    assert alternates.status_code == 200, alternates.text
    dependency_types = {row["dependency_type"] for row in dependencies.json()["results"]}
    assert "ONLY_SUPPLIER_FOR_PRODUCT" in dependency_types
    readiness = {row["supplier_id"]: row for row in alternates.json()["results"]}
    assert readiness[str(supplier_a)]["readiness_state"] == "READY"
    assert readiness[str(supplier_b)]["readiness_state"] == "DUE_DILIGENCE_REQUIRED"
    assert all(row["reasons"] is not None for row in readiness.values())
    with factory() as db:
        assert db.scalar(select(SupplierPortfolioDependencyFinding)) is not None
        assert db.scalar(select(SupplierPortfolioAlternateReadiness)) is not None
