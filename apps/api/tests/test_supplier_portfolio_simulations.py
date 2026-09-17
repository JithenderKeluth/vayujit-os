"""Focused 8E.4 bounded supplier portfolio simulation coverage."""

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
from vayujit_api.intelligence.simulation_models import (
    PortfolioSimulation,
    PortfolioSimulationResult,
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


def _setup(
    api: TestClient, factory: sessionmaker[Session]
) -> tuple[str, list[uuid.UUID], list[uuid.UUID]]:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Simulation Owner",
            "email": "simulation@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        rows = [
            CrossMarketplaceSupplier(
                owner_id=owner.id,
                canonical_key=f"simulation-{index}",
                display_name=f"Simulation Supplier {index}",
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
        supplier_ids = [row.id for row in rows]
    portfolio = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "Simulation portfolio", "idempotency_key": "simulation-portfolio-1"},
        headers=ORIGIN,
    )
    assert portfolio.status_code == 201, portfolio.text
    portfolio_id = portfolio.json()["id"]
    products = [uuid.uuid4(), uuid.uuid4()]
    for supplier, allocation, country, product_ids in (
        (supplier_ids[0], 60, "CN", products),
        (supplier_ids[1], 25, "IN", [products[0]]),
        (supplier_ids[2], 15, "VN", [products[0]]),
        (supplier_ids[3], 0, "IN", [products[1]]),
    ):
        member = api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members",
            json={
                "supplier_id": str(supplier),
                "allocation_percent": allocation,
                "associated_products": [str(value) for value in product_ids],
                "country_region": country,
                "evidence_freshness": "fresh",
                "confidence": 90,
                "risk": "low",
                "capabilities": ["precision manufacturing"],
                "alternate_source_status": "qualified",
            },
            headers=ORIGIN,
        )
        assert member.status_code == 201, member.text
    assessment = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json={"idempotency_key": "simulation-assessment-1"},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return portfolio_id, supplier_ids, products


def test_supplier_unavailable_is_bounded_replayable_and_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    portfolio_id, suppliers, products = _setup(api, factory)
    payload = {
        "simulation_type": "SUPPLIER_UNAVAILABLE",
        "assumptions": {"supplier_id": str(suppliers[0])},
        "idempotency_key": "simulation-unavailable-1",
    }
    first = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
        json=payload,
        headers=ORIGIN,
    )
    repeated = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    assert repeated.status_code == 201, repeated.text
    first_payload = first.json()
    repeated_payload = repeated.json()
    assert first_payload["reused"] is False
    assert repeated_payload["reused"] is True
    first_payload.pop("reused")
    repeated_payload.pop("reused")
    assert first_payload == repeated_payload
    result = first.json()["result"]
    assert result["status"] == "CALCULATED"
    assert result["allocation_exposed"] == 60.0
    assert result["affected_supplier_ids"] == [str(suppliers[0])]
    assert str(products[0]) in result["affected_product_ids"]
    assert result["simulated"]["allocation_by_supplier"] == {
        str(suppliers[1]): 25.0,
        str(suppliers[2]): 15.0,
    }
    assert result["delta"]["resilience_score"] <= 0
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
            headers=ORIGIN,
        ).json()[0]["id"]
        == first.json()["id"]
    )
    with factory() as db:
        assert len(list(db.scalars(select(PortfolioSimulation)))) == 1
        assert len(list(db.scalars(select(PortfolioSimulationResult)))) == 1


def test_country_and_insufficient_evidence_simulations_are_explicit(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    portfolio_id, suppliers, _ = _setup(api, factory)
    country = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
        json={
            "simulation_type": "COUNTRY_DISRUPTION",
            "assumptions": {"country": "CN"},
            "idempotency_key": "simulation-country-1",
        },
        headers=ORIGIN,
    )
    assert country.status_code == 201, country.text
    assert country.json()["result"]["affected_supplier_ids"] == [str(suppliers[0])]
    incomplete = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
        json={
            "simulation_type": "SUPPLIER_CAPACITY_REDUCTION",
            "assumptions": {"supplier_id": str(suppliers[0])},
            "idempotency_key": "simulation-capacity-1",
        },
        headers=ORIGIN,
    )
    assert incomplete.status_code == 201, incomplete.text
    assert incomplete.json()["status"] == "INSUFFICIENT_EVIDENCE"
    assert incomplete.json()["result"]["missing_evidence"]
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{'0' * 32}/simulations",
            headers=ORIGIN,
        ).status_code
        == 404
    )
