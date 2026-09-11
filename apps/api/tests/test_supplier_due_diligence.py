from __future__ import annotations

import uuid

from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import (
    GAP_DIMENSIONS,
    GAP_STATES,
    SEVERITIES,
    SupplierDueDiligenceContext,
)
from vayujit_api.intelligence.due_diligence_service import _gap_spec


def _supplier(**kwargs: object) -> CrossMarketplaceSupplier:
    values = {
        "owner_id": uuid.uuid4(),
        "canonical_key": "fixture-supplier",
        "display_name": "Fixture Supplier",
        "identity_state": "UNKNOWN",
        "view_json": {},
        "freshness_status": "unknown",
        "source_diversity_score": 0,
        "confidence_score": 0,
    }
    values.update(kwargs)
    return CrossMarketplaceSupplier(**values)


def test_due_diligence_taxonomy_is_explicit() -> None:
    assert "IDENTITY" in GAP_DIMENSIONS
    assert "CONTRADICTION" in GAP_DIMENSIONS
    assert set(GAP_STATES) >= {"MISSING", "RESOLVED", "WAIVED_BY_HUMAN"}
    assert set(SEVERITIES) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_gap_detection_is_deterministic_and_fail_closed() -> None:
    context = SupplierDueDiligenceContext(
        owner_id=uuid.uuid4(), supplier_id=uuid.uuid4(), status="OPEN"
    )
    supplier = _supplier()
    first = _gap_spec(context, supplier)
    second = _gap_spec(context, supplier)
    assert first == second
    assert {item["dimension"] for item in first} >= {
        "IDENTITY",
        "MANUFACTURING_CAPABILITY",
        "CERTIFICATION",
    }
    assert all(item["status"] != "RESOLVED" for item in first)


def test_qualifying_supplier_has_no_false_material_gap() -> None:
    context = SupplierDueDiligenceContext(
        owner_id=uuid.uuid4(), supplier_id=uuid.uuid4(), status="OPEN"
    )
    supplier = _supplier(
        identity_state="MATCH",
        view_json={
            "capabilities": ["assembly"],
            "certifications": ["ISO 9001"],
            "facilities": ["owned facility"],
        },
        source_diversity_score=3,
        freshness_status="fresh",
    )
    assert _gap_spec(context, supplier) == []
