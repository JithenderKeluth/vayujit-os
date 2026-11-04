"""Canonical acquisition lineage regressions; no database connection or writes."""

from __future__ import annotations

import copy
import unittest
import uuid

from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.landed_cost_service import landed_readiness_issue


def snapshot() -> CommercialReadinessSnapshot:
    values = {
        "supplier_unit_price": ("100", "per_unit"),
        "supplier_currency": ("INR", None),
        "freight_cost": ("10", "per_shipment"),
        "freight_currency": ("INR", None),
        "origin": ("IN", None),
        "destination": ("IN", None),
    }
    return CommercialReadinessSnapshot(
        id=uuid.uuid4(),
        supplier_id=uuid.UUID(int=1),
        scenario_key="QA_SYNTHETIC",
        readiness={"calculations": {"LANDED_UNIT_COST": {"status": "READY"}}},
        known_inputs=[],
        contradictions=[],
        assumptions=[
            {
                "key": k,
                "value": v,
                "unit": u,
                "provenance": "ASSUMED",
                "freshness": "UNKNOWN",
                "source_references": [],
            }
            for k, (v, u) in values.items()
        ],
    )


class LineageTests(unittest.TestCase):
    def test_unchanged_snapshot_is_current(self) -> None:
        row = snapshot()
        self.assertIsNone(landed_readiness_issue(row, row))

    def test_equivalent_new_snapshot_decimal_spelling_order_and_note(self) -> None:
        old = snapshot()
        new = snapshot()
        new.assumptions[0]["value"] = "100.00000000"
        new.assumptions[0]["reason"] = "A changed explanation does not change acquisition cost."
        new.assumptions.reverse()
        self.assertIsNone(landed_readiness_issue(new, old))

    def test_material_price_change(self) -> None:
        old = snapshot()
        new = snapshot()
        new.assumptions[0]["value"] = "200"
        self.assertEqual(landed_readiness_issue(new, old), "LANDED_COST_INPUTS_CHANGED")

    def test_supplier_currency_basis_provenance_and_source_changes(self) -> None:
        old = snapshot()
        for field, value in [
            ("unit", "per_shipment"),
            ("currency", "USD"),
            ("provenance", "SOURCE_PROVIDED_CLAIM"),
            ("source_references", [{"id": "new-source"}]),
        ]:
            new = snapshot()
            new.assumptions[0][field] = value
            self.assertEqual(landed_readiness_issue(new, old), "LANDED_COST_INPUTS_CHANGED", field)
        new = snapshot()
        new.supplier_id = uuid.uuid4()
        self.assertEqual(landed_readiness_issue(new, old), "LANDED_COST_INPUTS_CHANGED")

    def test_missing_unknown_gate_and_contradiction_fail_closed(self) -> None:
        old = snapshot()
        new = snapshot()
        new.assumptions[0]["value"] = None
        self.assertEqual(landed_readiness_issue(new, old), "LANDED_COST_INPUTS_REQUIRED")
        new = snapshot()
        new.readiness = {"calculations": {"LANDED_UNIT_COST": {"status": "NEEDS_INPUT"}}}
        self.assertEqual(landed_readiness_issue(new, old), "LANDED_COST_INPUTS_REQUIRED")
        new = snapshot()
        new.contradictions = [{"code": "CONFLICT"}]
        self.assertEqual(landed_readiness_issue(new, old), "LANDED_COST_INPUTS_REQUIRED")

    def test_expired_and_stale_source_cannot_support_ready(self) -> None:
        for freshness in ["STALE", "expired"]:
            old = snapshot()
            old.assumptions[0]["freshness"] = freshness
            self.assertEqual(landed_readiness_issue(old, old), "LANDED_COST_INPUTS_STALE")

    def test_missing_original_lineage_not_inferred(self) -> None:
        self.assertEqual(landed_readiness_issue(snapshot(), None), "LANDED_COST_LINEAGE_UNKNOWN")
        self.assertEqual(landed_readiness_issue(None, snapshot()), "LANDED_COST_LINEAGE_UNKNOWN")

    def test_known_evidence_remains_authoritative_over_assumptions(self) -> None:
        old = snapshot()
        old.known_inputs = [copy.deepcopy(old.assumptions[0])]
        new = snapshot()
        new.known_inputs = copy.deepcopy(old.known_inputs)
        new.assumptions[0]["value"] = "999"
        self.assertIsNone(landed_readiness_issue(new, old))
