from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence import supplier_worker
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierOpportunityMatch,
    SupplierProduct,
    SupplierScoreEvaluation,
    SupplierSearch,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _search(client: Any, key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/suppliers/searches",
        json={
            "product_id": "00000000-0000-4000-8000-000000000001",
            "requirements": {
                "category": "outdoors",
                "currency": "INR",
                "moq_max": 200,
                "lead_time_max_days": 45,
            },
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_supplier_search_idempotency_and_worker_crash_recovery(
    client: Any, monkeypatch: Any
) -> None:
    setup_context(client)
    first = _search(client, "supplier-cert-search-1")
    reused = _search(client, "supplier-cert-search-1")
    assert reused["id"] == first["id"]
    assert test_ai_integration.factory is not None
    monkeypatch.setattr(supplier_worker, "SessionFactory", test_ai_integration.factory)

    assert supplier_worker.run_supplier_searches_once(crash_stage="before_provider") == 0
    with test_ai_integration.factory() as db:
        value = db.get(SupplierSearch, first["id"])
        assert value is not None and value.status == "running"
        value.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert supplier_worker.run_supplier_searches_once() == 1
    assert supplier_worker.run_supplier_searches_once() == 0

    with test_ai_integration.factory() as db:
        search = db.get(SupplierSearch, first["id"])
        assert search is not None and search.status == "completed"
        assert search.provider_execution_id == f"supplier-provider:{search.id}"
        assert int(db.scalar(select(func.count()).select_from(Supplier))) == 5
        assert int(db.scalar(select(func.count()).select_from(SupplierProduct))) == 5
        assert int(db.scalar(select(func.count()).select_from(SupplierOpportunityMatch))) == 5
        assert int(db.scalar(select(func.count()).select_from(SupplierScoreEvaluation))) == 5


def test_supplier_after_provider_checkpoint_is_replay_safe(client: Any, monkeypatch: Any) -> None:
    setup_context(client)
    search = _search(client, "supplier-cert-search-after")
    assert test_ai_integration.factory is not None
    monkeypatch.setattr(supplier_worker, "SessionFactory", test_ai_integration.factory)
    assert supplier_worker.run_supplier_searches_once(crash_stage="after_provider") == 0
    with test_ai_integration.factory() as db:
        value = db.get(SupplierSearch, search["id"])
        assert value is not None and value.status == "completed"
        execution_id = value.provider_execution_id
        supplier_count = int(db.scalar(select(func.count()).select_from(Supplier)))
    assert supplier_worker.run_supplier_searches_once() == 0
    with test_ai_integration.factory() as db:
        value = db.get(SupplierSearch, search["id"])
        assert value is not None and value.provider_execution_id == execution_id
        assert int(db.scalar(select(func.count()).select_from(Supplier))) == supplier_count


def test_supplier_commercial_certification_and_score_versions_are_append_only(client: Any) -> None:
    setup_context(client)
    search = _search(client, "supplier-cert-commercial")
    run = client.post(f"/api/v1/intelligence/suppliers/searches/{search['id']}/run", headers=ORIGIN)
    assert run.status_code == 200
    suppliers = client.get("/api/v1/intelligence/suppliers", headers=ORIGIN).json()
    supplier = suppliers[0]
    offering_id = client.get(
        f"/api/v1/intelligence/suppliers/{supplier['id']}", headers=ORIGIN
    ).json()["offerings"][0]["id"]
    base = {
        "supplier_product_id": offering_id,
        "unit_price": 420,
        "currency": "INR",
        "moq": 50,
        "sample_price": 20,
        "tooling_fee": 10,
        "packaging_fee": 5,
        "branding_fee": 4,
        "payment_terms": "30/70",
        "deposit_percent": 30,
        "balance_percent": 70,
        "incoterm": "FOB",
        "lead_time_days": 14,
        "sample_lead_days": 7,
        "production_lead_days": 14,
        "dispatch_lead_days": 3,
    }
    v1 = client.post(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/commercial-terms",
        json={**base, "version": 1},
        headers=ORIGIN,
    )
    assert v1.status_code == 201, v1.text
    v2 = client.post(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/commercial-terms",
        json={**base, "version": 2, "unit_price": 430},
        headers=ORIGIN,
    )
    assert v2.status_code == 201
    historical = client.post(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/commercial-terms",
        json={**base, "version": 1, "unit_price": 999},
        headers=ORIGIN,
    )
    assert historical.status_code == 409
    detail = client.get(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/commercial-terms/{offering_id}/1",
        headers=ORIGIN,
    )
    assert detail.status_code == 200 and float(detail.json()["unit_price"]) == 420

    claim = client.post(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/certifications",
        json={"claim": "ISO 9001", "source_reference": "manual certificate note"},
        headers=ORIGIN,
    )
    assert claim.status_code == 201
    claim_v2 = client.post(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/certifications",
        json={"claim": "ISO 9001", "source_reference": "renewed note", "version": 2},
        headers=ORIGIN,
    )
    assert claim_v2.status_code == 201 and claim_v2.json()["version"] == 2

    score = {
        "model_version": "supplier-score-cert-v1",
        "weights": {"commercial": 50, "verification": 50},
        "dimensions": {
            "commercial": {"score": 80, "weight": 50, "reason": "observed quote"},
            "verification": {"score": 60, "weight": 50, "reason": "manual review"},
        },
        "final_score": 70,
        "recommendation": "review_required",
    }
    assert (
        client.post(
            f"/api/v1/intelligence/suppliers/{supplier['id']}/scores", json=score, headers=ORIGIN
        ).status_code
        == 201
    )
    score["model_version"] = "supplier-score-cert-v2"
    score["final_score"] = 72
    assert (
        client.post(
            f"/api/v1/intelligence/suppliers/{supplier['id']}/scores", json=score, headers=ORIGIN
        ).status_code
        == 201
    )
    scores = client.get(
        f"/api/v1/intelligence/suppliers/{supplier['id']}/scores", headers=ORIGIN
    ).json()
    assert len(scores) >= 2
    assert {value["model_version"] for value in scores[-2:]} == {
        "supplier-score-cert-v1",
        "supplier-score-cert-v2",
    }


def test_supplier_contact_communication_recovery_and_currency_safety(client: Any) -> None:
    setup_context(client)
    manual = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": "Offline Cert Supplier",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "source_type": "factory_visit",
            "provenance": "factory visit record",
        },
        headers=ORIGIN,
    )
    assert manual.status_code == 201
    supplier_id = manual.json()["id"]
    contact = client.post(
        f"/api/v1/intelligence/suppliers/{supplier_id}/contacts",
        json={
            "name": "Owner Contact",
            "role": "Sales",
            "business_email": "sales@example.test",
            "preferred_method": "email",
            "source": "factory visit record",
            "communication_status": "contact_drafted",
        },
        headers=ORIGIN,
    )
    assert contact.status_code == 201
    updated = client.patch(
        f"/api/v1/intelligence/suppliers/{supplier_id}/contacts/{contact.json()['id']}",
        json={"communication_status": "contact_approved"},
        headers=ORIGIN,
    )
    assert (
        updated.status_code == 200 and updated.json()["communication_status"] == "contact_approved"
    )
    archived = client.patch(
        f"/api/v1/intelligence/suppliers/{supplier_id}/contacts/{contact.json()['id']}",
        json={"archived": True},
        headers=ORIGIN,
    )
    assert archived.status_code == 200
    assert (
        client.get(f"/api/v1/intelligence/suppliers/{supplier_id}/contacts", headers=ORIGIN).json()
        == []
    )

    search = _search(client, "supplier-cert-recovery")
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        value = db.get(SupplierSearch, search["id"])
        assert value is not None
        value.status = "failed"
        value.failure_classification = "source_unavailable"
        db.commit()
    recovery = client.post(
        f"/api/v1/intelligence/suppliers/searches/{search['id']}/recovery",
        json={"action": "retry", "idempotency_key": "supplier-recovery-cert"},
        headers=ORIGIN,
    )
    assert recovery.status_code == 200 and recovery.json()["status"] == "completed"
    reused = client.post(
        f"/api/v1/intelligence/suppliers/searches/{search['id']}/recovery",
        json={"action": "retry", "idempotency_key": "supplier-recovery-cert"},
        headers=ORIGIN,
    )
    assert reused.status_code == 200 and reused.json()["idempotent_reuse"] is True
    assert (
        client.post(
            "/api/v1/intelligence/suppliers/compare",
            json={"supplier_ids": [supplier_id, supplier_id]},
            headers=ORIGIN,
        ).status_code
        == 422
    )
