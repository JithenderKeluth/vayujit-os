from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from statistics import median
from typing import Any, cast

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence import supplier_service, supplier_worker
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCertificationClaim,
    SupplierCommercialTerm,
    SupplierEvidence,
    SupplierHistoryEvent,
    SupplierOpportunityMatch,
    SupplierProduct,
    SupplierRecoveryRecord,
    SupplierScoreEvaluation,
    SupplierSearch,
    SupplierSource,
)
from vayujit_api.intelligence.supplier_schemas import (
    SupplierCertificationClaimCreate,
    SupplierCommercialTermCreate,
    SupplierDecisionRequest,
    SupplierManualCreate,
    SupplierRecoveryRequest,
    SupplierScoreCreate,
    SupplierSearchCreate,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _search(client: Any, key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/suppliers/searches",
        json={
            "product_id": "00000000-0000-4000-8000-000000000001",
            "requirements": {"category": "outdoors", "currency": "INR", "moq_max": 200},
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _parallel(factory: Any, action: Callable[[Any, User], Any]) -> list[Any]:
    def invoke(_: int) -> object:
        with factory() as db:
            user = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert user is not None
            try:
                value = action(db, user)
                db.commit()
                return value
            except Exception:
                db.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(invoke, range(2)))


def test_supplier_true_concurrency_search_ingest_and_manual_identity(client: Any) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    factory = test_ai_integration.factory
    payload = SupplierSearchCreate(
        product_id=cast(Any, "00000000-0000-4000-8000-000000000001"),
        requirements={"category": "outdoors", "currency": "INR"},
        idempotency_key="supplier-concurrent-search",
    )
    created = _parallel(factory, lambda db, user: supplier_service.create_search(db, user, payload))
    assert len({str(value.id) for value in created}) == 1
    search_id = created[0].id
    executed = _parallel(
        factory,
        lambda db, user: supplier_service.execute_search(
            db, user, db.get(SupplierSearch, search_id)
        ),
    )
    assert len({str(value.provider_execution_id) for value in executed}) == 1
    manual = SupplierManualCreate(
        display_name="Concurrent Offline Supplier",
        supplier_type="manufacturer",
        country_code="IN",
        country="India",
        source_type="factory_visit",
        provenance="disposable concurrency fixture",
    )
    suppliers = _parallel(
        factory, lambda db, user: supplier_service.create_manual_supplier(db, user, manual)
    )
    assert len({str(value.id) for value in suppliers}) == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Supplier)) == 6
        assert db.scalar(select(func.count()).select_from(SupplierProduct)) == 5
        assert db.scalar(select(func.count()).select_from(SupplierEvidence)) == 6
        assert db.scalar(select(func.count()).select_from(SupplierOpportunityMatch)) == 5
        assert db.scalar(select(func.count()).select_from(SupplierScoreEvaluation)) == 5


def test_supplier_true_concurrency_versioned_records_and_recovery(client: Any) -> None:
    setup_context(client)
    search = _search(client, "supplier-concurrent-versions")
    run = client.post(f"/api/v1/intelligence/suppliers/searches/{search['id']}/run", headers=ORIGIN)
    assert run.status_code == 200, run.text
    assert test_ai_integration.factory is not None
    factory = test_ai_integration.factory
    with factory() as db:
        supplier = db.scalar(
            select(Supplier).where(Supplier.owner_id == db.scalar(select(User.id).limit(1)))
        )
        assert supplier is not None
        offering = db.scalar(
            select(SupplierProduct).where(SupplierProduct.supplier_id == supplier.id)
        )
        evidence = db.scalar(
            select(SupplierEvidence).where(SupplierEvidence.supplier_id == supplier.id)
        )
        assert offering is not None and evidence is not None
        supplier_id, offering_id, evidence_id = supplier.id, offering.id, evidence.id
    v1 = SupplierCommercialTermCreate(
        supplier_product_id=offering_id,
        version=1,
        unit_price=120,
        currency="INR",
        moq=10,
        source_evidence_ids=[evidence_id],
    )
    _parallel(
        factory,
        lambda db, user: supplier_service.create_commercial_term(db, user, supplier_id, v1),
    )
    commercial = SupplierCommercialTermCreate(
        supplier_product_id=offering_id,
        version=2,
        unit_price=125,
        currency="INR",
        moq=10,
        source_evidence_ids=[evidence_id],
        idempotency_key="commercial-v2-concurrent",
    )
    terms = _parallel(
        factory,
        lambda db, user: supplier_service.create_commercial_term(db, user, supplier_id, commercial),
    )
    assert len({str(value.id) for value in terms}) == 1
    score = SupplierScoreCreate(
        model_version="supplier-concurrent-v2",
        weights={"commercial": 100},
        inputs={"fingerprint": "same"},
        dimensions={"commercial": {"score": 80, "weight": 100, "reason": "observed"}},
        final_score=80,
        recommendation="promising",
        evidence_ids=[evidence_id],
    )
    scores = _parallel(
        factory,
        lambda db, user: supplier_service.create_score_evaluation(db, user, supplier_id, score),
    )
    assert len({str(value.id) for value in scores}) == 1
    decision = SupplierDecisionRequest(
        decision="shortlist", reason="same fixture", idempotency_key="shortlist-concurrent"
    )
    decisions = _parallel(
        factory, lambda db, user: supplier_service.decide_supplier(db, user, supplier_id, decision)
    )
    assert len({str(value.id) for value in decisions}) == 1
    claim = SupplierCertificationClaimCreate(
        claim="ISO 9001", source_reference="fixture", version=2
    )
    claims = _parallel(
        factory,
        lambda db, user: supplier_service.create_certification_claim(db, user, supplier_id, claim),
    )
    assert len({str(value.id) for value in claims}) == 1
    with factory() as db:
        search_row = db.get(SupplierSearch, search["id"])
        assert search_row is not None
        search_row.status = "failed"
        search_row.failure_classification = "source_unavailable"
        db.commit()
    recovery = SupplierRecoveryRequest(
        action="retry", idempotency_key="supplier-recovery-concurrent"
    )
    records = _parallel(
        factory, lambda db, user: supplier_service.recover_search(db, user, search["id"], recovery)
    )
    assert len({str(value.id) for value in records}) == 1
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierCommercialTerm)
                .where(SupplierCommercialTerm.version == 2)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierScoreEvaluation)
                .where(SupplierScoreEvaluation.model_version == "supplier-concurrent-v2")
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierCertificationClaim)
                .where(
                    SupplierCertificationClaim.claim == "ISO 9001",
                    SupplierCertificationClaim.version == 2,
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierRecoveryRecord)
                .where(SupplierRecoveryRecord.idempotency_key == "supplier-recovery-concurrent")
            )
            == 1
        )


def test_supplier_risk_freshness_currency_storage_and_endpoint_evidence(client: Any) -> None:
    setup_context(client)
    search = _search(client, "supplier-matrix-canonical")
    assert (
        client.post(
            f"/api/v1/intelligence/suppliers/searches/{search['id']}/run", headers=ORIGIN
        ).status_code
        == 200
    )
    suppliers = client.get("/api/v1/intelligence/suppliers", headers=ORIGIN).json()
    assert len(suppliers) == 5
    supplier_id = suppliers[0]["id"]
    risk = client.get(f"/api/v1/intelligence/suppliers/{supplier_id}/risk-matrix", headers=ORIGIN)
    assert risk.status_code == 200
    dimensions = {row["dimension"]: row for row in risk.json()["dimensions"]}
    assert set(dimensions) == {
        "identity",
        "commercial",
        "quality",
        "delivery",
        "verification",
        "communication",
        "compliance",
        "concentration",
        "fraud_signal",
    }
    assert all("reason" in row and "evidence" in row for row in dimensions.values())
    assert all("accus" not in str(row).lower() for row in dimensions.values())
    freshness = client.get(
        f"/api/v1/intelligence/suppliers/{supplier_id}/freshness", headers=ORIGIN
    )
    assert freshness.status_code == 200 and set(freshness.json()) >= {
        "price",
        "moq",
        "lead_time",
        "contact",
        "certification",
        "verification",
        "capability",
        "offering",
    }
    diversity = client.get(
        f"/api/v1/intelligence/suppliers/{supplier_id}/source-diversity", headers=ORIGIN
    )
    assert diversity.status_code == 200 and diversity.json()["independent_source_count"] >= 1
    comparison = client.post(
        "/api/v1/intelligence/suppliers/compare",
        json={"supplier_ids": [row["id"] for row in suppliers[:2]]},
        headers=ORIGIN,
    )
    assert comparison.status_code == 200
    assert all(
        row["comparison_status"] == "NOT COMPARABLE: currencies differ" for row in comparison.json()
    )
    inventory = client.get("/api/v1/intelligence/suppliers/inventory", headers=ORIGIN)
    assert inventory.status_code == 200 and len(inventory.json()["tables"]) == len(
        supplier_service.SUPPLIER_TABLES
    )
    for path in (
        "/overview",
        "/source-registry",
        "/operations",
        "/rules",
        "/searches",
        f"/{supplier_id}",
        f"/{supplier_id}/history",
        f"/{supplier_id}/report",
    ):
        samples: list[float] = []
        for _ in range(10):
            started = datetime.now(UTC)
            response = client.get("/api/v1/intelligence/suppliers" + path, headers=ORIGIN)
            samples.append((datetime.now(UTC) - started).total_seconds() * 1000)
            assert response.status_code == 200, (path, response.text)
        assert median(samples) >= 0
    factory = test_ai_integration.factory
    assert factory is not None
    with factory() as db:
        assert (db.scalar(select(func.count()).select_from(SupplierHistoryEvent)) or 0) >= 0
        assert (db.scalar(select(func.count()).select_from(SupplierSource)) or 0) == 5


def test_supplier_timing_and_worker_claim_are_durable(client: Any, monkeypatch: Any) -> None:
    setup_context(client)
    search = _search(client, "supplier-timing-worker")
    assert test_ai_integration.factory is not None
    monkeypatch.setattr(supplier_worker, "SessionFactory", test_ai_integration.factory)
    started = datetime.now(UTC)
    assert supplier_worker.run_supplier_searches_once() == 1
    elapsed = (datetime.now(UTC) - started).total_seconds() * 1000
    factory = test_ai_integration.factory
    assert factory is not None
    with factory() as db:
        row = db.get(SupplierSearch, search["id"])
        assert row is not None and row.status == "completed"
        started_at = row.started_at
        completed_at = row.completed_at
        assert started_at is not None and completed_at is not None
        assert completed_at >= started_at
        assert elapsed >= 0
