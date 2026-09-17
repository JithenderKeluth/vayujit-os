"""Focused 8E hard-gate certification coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from statistics import median
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioContext,
    SupplierPortfolioHumanAction,
    SupplierPortfolioMembership,
)
from vayujit_api.intelligence.resilience_models import (
    SupplierPortfolioRecommendation,
)
from vayujit_api.intelligence.simulation_models import (
    PortfolioSimulation,
    PortfolioSimulationResult,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def harness() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None, "VAYUJIT_TEST_DATABASE_URL is required."
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _setup(api: TestClient, factory: sessionmaker[Session]) -> tuple[str, list[uuid.UUID]]:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Portfolio Certification Owner",
            "email": "portfolio-hard-gates@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    brand = api.post("/api/v1/brands", json={"name": "Hard Gate Brand"}, headers=ORIGIN)
    assert brand.status_code == 201, brand.text
    brand_id = brand.json()["id"]
    activated = api.post(f"/api/v1/brands/{brand_id}/activate", headers=ORIGIN)
    assert activated.status_code == 200, activated.text
    product = api.post(
        "/api/v1/products",
        json={
            "name": "Hard Gate Product",
            "product_type": "physical",
            "short_description": "A disposable certification product.",
            "description": "A disposable product used by the portfolio hard-gate fixture.",
            "price_amount": "19.99",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        suppliers = [
            CrossMarketplaceSupplier(
                owner_id=owner.id,
                canonical_key=f"hard-gate-{index}",
                display_name=f"Hard Gate Supplier {index}",
                identity_state="MATCH",
                aliases=[],
                view_json={"capabilities": ["assembly"]},
                confidence_score=90,
                source_diversity_score=2,
                freshness_status="fresh",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for index in range(4)
        ]
        db.add_all(suppliers)
        db.commit()
        supplier_ids = [row.id for row in suppliers]
    portfolio = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "Hard-gate portfolio", "idempotency_key": "hard-gate-portfolio"},
        headers=ORIGIN,
    )
    assert portfolio.status_code == 201, portfolio.text
    portfolio_id = portfolio.json()["id"]
    product_ids = [product_id, product_id]
    for index, supplier_id in enumerate(supplier_ids):
        member = api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members",
            json={
                "supplier_id": str(supplier_id),
                "allocation_percent": [60, 25, 15, 0][index],
                "associated_products": [str(product_ids[0 if index < 3 else 1])],
                "country_region": ["CN", "IN", "VN", "IN"][index],
                "evidence_freshness": "fresh",
                "confidence": 90,
                "risk": "low",
                "capabilities": ["assembly"],
                "alternate_source_status": "qualified",
            },
            headers=ORIGIN,
        )
        assert member.status_code == 201, member.text
    assessed = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json={"idempotency_key": "hard-gate-assessment"},
        headers=ORIGIN,
    )
    assert assessed.status_code == 201, assessed.text
    return portfolio_id, supplier_ids


SIMULATION_CASES = [
    ("SUPPLIER_UNAVAILABLE", {"supplier_id": "supplier0"}),
    ("SUPPLIER_CAPACITY_REDUCTION", {"supplier_id": "supplier0", "capacity_reduction_percent": 20}),
    ("COUNTRY_DISRUPTION", {"country": "CN"}),
    ("REGION_DISRUPTION", {"region": "CN"}),
    ("LEAD_TIME_INCREASE", {"supplier_id": "supplier0", "increase_days": 5}),
    ("LANDED_COST_INCREASE", {"supplier_id": "supplier0", "increase_percent": 5}),
    ("FX_SHOCK", {"supplier_id": "supplier0", "increase_percent": 5, "currency_pair": "USD/EUR"}),
    ("MOQ_INCREASE", {"supplier_id": "supplier0", "increase_percent": 5}),
    ("AVAILABILITY_REDUCTION", {"supplier_id": "supplier0", "availability_reduction_percent": 20}),
    ("MULTI_SUPPLIER_DISRUPTION", {"supplier_ids": ["supplier0", "supplier1"]}),
    ("CUSTOM", {"primitives": [{"type": "supplier_unavailable"}]}),
]


def _replace_supplier_tokens(value: object, suppliers: list[uuid.UUID]) -> object:
    if isinstance(value, str) and value.startswith("supplier"):
        suffix = value.removeprefix("supplier")
        if suffix.isdigit():
            return str(suppliers[int(suffix)])
    if isinstance(value, list):
        return [_replace_supplier_tokens(item, suppliers) for item in value]
    if isinstance(value, dict):
        return {key: _replace_supplier_tokens(item, suppliers) for key, item in value.items()}
    return value


@pytest.mark.parametrize(("simulation_type", "assumptions"), SIMULATION_CASES)
def test_all_simulation_types_are_typed_bounded_deterministic_and_replay_safe(
    harness: tuple[TestClient, sessionmaker[Session]],
    simulation_type: str,
    assumptions: dict[str, object],
) -> None:
    api, factory = harness
    portfolio_id, suppliers = _setup(api, factory)
    payload = {
        "simulation_type": simulation_type,
        "assumptions": _replace_supplier_tokens(assumptions, suppliers),
        "idempotency_key": f"simulation-{simulation_type.casefold()}",
    }
    before = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members", headers=ORIGIN
    ).json()
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
    assert first.status_code == repeated.status_code == 201, first.text
    assert first.json()["reused"] is False
    assert repeated.json()["reused"] is True
    first_body = {key: value for key, value in first.json().items() if key != "reused"}
    repeated_body = {key: value for key, value in repeated.json().items() if key != "reused"}
    assert first_body == repeated_body
    assert first.json()["result"]["status"] in {"CALCULATED", "INSUFFICIENT_EVIDENCE"}
    assert "allocation_by_supplier" in first.json()["result"]["baseline"]
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members", headers=ORIGIN
        ).json()
        == before
    )
    with factory() as db:
        assert len(list(db.scalars(select(PortfolioSimulation)))) == 1
        assert len(list(db.scalars(select(PortfolioSimulationResult)))) == 1


def test_custom_simulation_rejects_executable_expressions_and_numeric_boundaries(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _ = harness
    portfolio_id, _ = _setup(api, harness[1])
    base = f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations"
    for assumptions in (
        {"primitives": [{"type": "__import__"}]},
        {"primitives": "import os"},
        {"increase_percent": -1},
        {"increase_percent": 101},
        {"increase_percent": "NaN"},
    ):
        response = api.post(
            base,
            json={
                "simulation_type": (
                    "CUSTOM" if "primitives" in assumptions else "LANDED_COST_INCREASE"
                ),
                "assumptions": assumptions,
                "idempotency_key": f"invalid-{uuid.uuid4()}",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 422, response.text


def test_all_human_actions_are_owner_scoped_idempotent_and_non_mutating(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    portfolio_id, suppliers = _setup(api, factory)
    resilience = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience", headers=ORIGIN
    )
    assert resilience.status_code == 200, resilience.text
    recommendation_id = resilience.json()["recommendations"][0]["id"]
    actions = (
        ("ACKNOWLEDGE_RISK", {"recommendation_id": recommendation_id}),
        ("REQUEST_MORE_RESEARCH", {"supplier_id": str(suppliers[0])}),
        ("REQUEST_DUE_DILIGENCE", {"supplier_id": str(suppliers[0])}),
        ("CREATE_BACKUP_SCENARIO", {"supplier_id": str(suppliers[0])}),
        ("KEEP_UNDER_REVIEW", {"recommendation_id": recommendation_id}),
        ("ACCEPT_CONCENTRATION", {}),
        ("ARCHIVE_RECOMMENDATION", {"recommendation_id": recommendation_id}),
    )
    before_members = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members", headers=ORIGIN
    ).json()
    before_resilience = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience", headers=ORIGIN
    ).json()
    for action, extra in actions:
        payload = {
            "action": action,
            "rationale": f"Certification action {action}",
            "idempotency_key": f"human-{action.casefold()}",
            **extra,
        }
        first = api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/actions",
            json=payload,
            headers=ORIGIN,
        )
        repeated = api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/actions",
            json=payload,
            headers=ORIGIN,
        )
        assert first.status_code == repeated.status_code == 200, first.text
        assert first.json()["idempotent_reuse"] is False
        assert repeated.json()["idempotent_reuse"] is True
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members", headers=ORIGIN
        ).json()
        == before_members
    )
    after_resilience = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience", headers=ORIGIN
    ).json()
    for key in before_resilience:
        if key != "recommendations":
            assert after_resilience[key] == before_resilience[key]
    before_recommendations = {
        item["id"]: {key: value for key, value in item.items() if key != "status"}
        for item in before_resilience["recommendations"]
    }
    after_recommendations = {item["id"]: item for item in after_resilience["recommendations"]}
    assert set(after_recommendations) == set(before_recommendations)
    for recommendation_key, before_item in before_recommendations.items():
        assert {
            key: value
            for key, value in after_recommendations[recommendation_key].items()
            if key != "status"
        } == before_item
    assert after_recommendations[recommendation_id]["status"] == "ARCHIVED"
    with factory() as db:
        assert len(list(db.scalars(select(SupplierPortfolioHumanAction)))) == 7
        portfolio = db.scalar(select(SupplierPortfolioContext))
        membership = db.scalar(select(SupplierPortfolioMembership))
        assert portfolio is not None and membership is not None
        assert portfolio.status == "active"
        assert membership.allocation_percent == 60
        assert db.scalar(select(SupplierPortfolioRecommendation)) is not None


def test_simulation_race_converges_to_one_logical_row_and_result(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    portfolio_id, suppliers = _setup(api, factory)
    payload = {
        "simulation_type": "SUPPLIER_UNAVAILABLE",
        "assumptions": {"supplier_id": str(suppliers[0])},
        "idempotency_key": "concurrent-simulation-race",
    }

    def invoke(_: int) -> int:
        return api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
            json=payload,
            headers=ORIGIN,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(invoke, (1, 2)))
    assert statuses == [201, 201]
    with factory() as db:
        assert len(list(db.scalars(select(PortfolioSimulation)))) == 1
        assert len(list(db.scalars(select(PortfolioSimulationResult)))) == 1


def _normalize_repeatability(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _normalize_repeatability(item)
            for key, item in value.items()
            if key not in {"id", "created_at", "updated_at"} and not key.endswith(("_id", "_at"))
        }
    if isinstance(value, list):
        return [_normalize_repeatability(item) for item in value]
    return value


def test_repeatability_owner_random_id_integrity_and_system_doctor(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    engine = factory.kw["bind"]
    normalized_outputs = []
    for _ in range(3):
        reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
        portfolio_id, _ = _setup(api, factory)
        response = api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience", headers=ORIGIN
        )
        assert response.status_code == 200, response.text
        normalized_outputs.append(_normalize_repeatability(response.json()))
    assert normalized_outputs[0] == normalized_outputs[1] == normalized_outputs[2]
    for endpoint in (
        "",
        "/assessment",
        "/concentration",
        "/dependencies",
        "/alternates",
        "/history",
        "/resilience",
        "/operations",
    ):
        url = f"/api/v1/intelligence/supplier-portfolios/{uuid.uuid4()}{endpoint}"
        assert api.get(url, headers=ORIGIN).status_code == 404
    integrity = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/integrity", headers=ORIGIN
    )
    assert integrity.status_code == 200, integrity.text
    assert all(value == 0 for value in integrity.json().values())
    doctor = api.get("/api/v1/intelligence/supplier-portfolios/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["status"] == "PASS"
    with factory() as db:
        assert db.scalar(select(SupplierPortfolioContext)) is not None


def _assert_safe_json(value: object) -> None:
    forbidden = {
        "password",
        "password_hash",
        "token",
        "secret",
        "credential",
        "api_key",
        "cookie",
        "database_url",
        "traceback",
        "sql",
        "local_path",
        "environment",
        "provider_output",
    }
    if isinstance(value, dict):
        assert not forbidden.intersection(str(key).casefold() for key in value)
        for item in value.values():
            _assert_safe_json(item)
    elif isinstance(value, list):
        for item in value:
            _assert_safe_json(item)


def test_recovery_retry_converges_to_one_authoritative_assessment(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    portfolio_id, _ = _setup(api, factory)
    with factory() as db:
        portfolio = db.get(SupplierPortfolioContext, uuid.UUID(portfolio_id))
        assert portfolio is not None
        portfolio.status = "stale"
        db.commit()
    payload = {
        "action": "RECALCULATE_STALE_PORTFOLIO_ASSESSMENT",
        "reason": "Hard-certification retry convergence.",
        "idempotency_key": "hard-certification-recovery-retry",
        "confirm": True,
    }
    first = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    retry = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == retry.status_code == 200, first.text
    assert first.json()["idempotent_reuse"] is False
    assert retry.json()["idempotent_reuse"] is True
    _assert_safe_json(first.json())
    with factory() as db:
        assert len(list(db.scalars(select(SupplierPortfolioAssessmentVersion)))) == 2
        assert len(list(db.scalars(select(SupplierPortfolioHumanAction)))) == 0


def test_storage_ledger_owner_isolation_and_endpoint_performance(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    portfolio_id, suppliers = _setup(api, factory)
    simulation = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
        json={
            "simulation_type": "SUPPLIER_UNAVAILABLE",
            "assumptions": {"supplier_id": str(suppliers[0])},
            "idempotency_key": "ledger-simulation",
        },
        headers=ORIGIN,
    )
    assert simulation.status_code == 201, simulation.text
    endpoints = [
        "/api/v1/intelligence/supplier-portfolios",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assessment",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/concentration",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/dependencies",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/alternates",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recommendations",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/history",
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/simulations",
        "/api/v1/intelligence/supplier-portfolios/operations",
        "/api/v1/intelligence/supplier-portfolios/system-doctor",
    ]
    metrics: dict[str, dict[str, float | int]] = {}
    engine = factory.kw["bind"]
    for endpoint in endpoints:
        query_samples: list[int] = []
        latency_samples: list[float] = []
        for _ in range(3):
            queries = 0

            def count_query(*_: object, **__: object) -> None:
                nonlocal queries
                queries += 1

            event.listen(engine, "before_cursor_execute", count_query)
            started = perf_counter()
            response = api.get(endpoint, headers=ORIGIN)
            elapsed_ms = (perf_counter() - started) * 1000
            event.remove(engine, "before_cursor_execute", count_query)
            assert response.status_code == 200, response.text
            _assert_safe_json(response.json())
            query_samples.append(queries)
            latency_samples.append(elapsed_ms)
        assert all(value < 200 for value in query_samples)
        assert all(value < 10_000 for value in latency_samples)
        metrics[endpoint] = {
            "sample_count": len(query_samples),
            "queries_max": max(query_samples),
            "latency_median_ms": round(median(latency_samples), 2),
            "latency_max_ms": round(max(latency_samples), 2),
        }
    operations = api.get(
        "/api/v1/intelligence/supplier-portfolios/operations", headers=ORIGIN
    ).json()
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        assert operations["portfolio_contexts"] == 1
        assert operations["current_assessments"] == 1
        assert operations["simulations"] == 1
        assert operations["integrity_issues"] == 0
        integrity = api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/integrity", headers=ORIGIN
        ).json()
        assert all(value == 0 for value in integrity.values())
    print({"8E_STORAGE_LEDGER": "PASS", "8E_ENDPOINT_METRICS": metrics})
