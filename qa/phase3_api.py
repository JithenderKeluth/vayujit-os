"""Persisted operational HTTP journeys. Writes only via canonical, guarded APIs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, cast

import httpx

from qa.operational_oracle import reconcile
from qa.phase2_api import JsonResult

OUTPUT = Path(os.environ["QA_RUN_DIR"])
ORIGIN = os.environ["QA_ORIGIN"]
EMAIL = "qa-phase3-owner@example.com"
PASSWORD = "SyntheticPhase3Only123!"
MANIFEST: dict[str, Any] = {}
ACTION = "/api/v1/operations/action-center"


class OperationalScenarios(unittest.TestCase):
    api: ClassVar[httpx.Client]

    @classmethod
    def setUpClass(cls) -> None:
        cls.api = httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=45)
        witness = cls.api.get("/__qa/witness").json()
        assert witness["token"] == os.environ["QA_TOKEN"] and witness["disposable"]
        setup = cls.api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "[QA SYNTHETIC] Operational Seller",
                "email": EMAIL,
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        assert setup.status_code == 201
        brand = cls.api.post(
            "/api/v1/brands", json={"name": "[QA SYNTHETIC] Operations", "slug": "qa3-operations"}
        )
        assert brand.status_code == 201
        MANIFEST["brand_id"] = brand.json()["id"]
        for marketplace in ("amazon", "flipkart"):
            response = cls.api.post(
                "/api/v1/marketplaces/accounts",
                json={
                    "marketplace": marketplace,
                    "display_name": "[QA SYNTHETIC] " + marketplace,
                    "seller_account_id": "qa3-" + marketplace,
                    "environment": "sandbox",
                    "credentials": {},
                },
            )
            assert response.status_code == 201
            account = response.json()
            assert not account["enabled"] and account["credential_status"] == "missing"
            MANIFEST[marketplace + "_account"] = account["id"]

    @classmethod
    def tearDownClass(cls) -> None:
        (OUTPUT / "phase3-manifest.json").write_text(
            json.dumps(MANIFEST, indent=2), encoding="utf-8"
        )
        cls.api.close()

    def ok(self, method: str, route: str, data: Any = None) -> Any:
        response = self.api.request(method, route, json=data)
        self.assertLess(response.status_code, 300, f"{method} {route} HTTP {response.status_code}")
        return response.json()

    def evidence(self, name: str, data: Any) -> None:
        (OUTPUT / (name + ".json")).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def item(self, label: str, quantity: int = 10, threshold: int = 2) -> dict[str, Any]:
        key = "QA3-" + label + "-" + uuid.uuid4().hex[:6]
        product = self.ok(
            "POST",
            "/api/v1/products",
            {
                "brand_id": MANIFEST["brand_id"],
                "name": "[QA SYNTHETIC] " + label,
                "sku": key,
                "product_type": "physical",
                "category": "Kids",
                "price_amount": "100.00",
                "price_currency": "INR",
            },
        )
        item = self.ok(
            "POST",
            "/api/v1/inventory/items",
            {
                "product_id": product["id"],
                "internal_sku": key,
                "opening_quantity": quantity,
                "low_stock_threshold": threshold,
                "idempotency_key": key + "-open",
            },
        )
        self.ok(
            "POST",
            "/api/v1/inventory/mappings",
            {
                "inventory_item_id": item["id"],
                "account_id": MANIFEST["flipkart_account"],
                "external_sku": key,
                "idempotency_key": key + "-map",
            },
        )
        return cast(dict[str, Any], item)

    def balance(self, item: dict[str, Any]) -> dict[str, Any]:
        return next(x for x in self.ok("GET", "/api/v1/inventory") if x["id"] == item["id"])

    def event(
        self,
        item: dict[str, Any],
        label: str,
        kind: str = "new_order",
        version: int = 1,
        quantity: int = 2,
    ) -> dict[str, Any]:
        return {
            "account_id": MANIFEST["flipkart_account"],
            "external_order_id": label,
            "event_id": f"{label}-{kind}-{version}",
            "event_type": kind,
            "event_version": version,
            "lines": (
                [
                    {
                        "external_sku": item["internal_sku"],
                        "quantity": quantity,
                        "unit_price": "100.125",
                    }
                ]
                if kind == "new_order"
                else []
            ),
        }

    def financial_event(
        self,
        label: str,
        kind: str,
        amount: str,
        *,
        product_id: str | None = None,
        effective: str = "2026-01-15T00:00:00Z",
    ) -> dict[str, Any]:
        return {
            "account_id": MANIFEST["amazon_account"],
            "source_event_id": label,
            "marketplace": "amazon",
            "event_type": kind,
            "amount": amount,
            "product_id": product_id,
            "source_type": "synthetic_fixture",
            "evidence_status": "reported",
            "effective_at": effective,
        }

    def finance(self, **params: str) -> dict[str, Any]:
        response = self.api.get(
            "/api/v1/financial/summary", params={"marketplace": "amazon", **params}
        )
        self.assertEqual(response.status_code, 200)
        return cast(dict[str, Any], response.json())

    def test_01_stock_adjustment_replay_stale_and_negative(self) -> None:
        item = self.item("Adjustment")
        url = f"/api/v1/inventory/{item['id']}/adjust"
        payload = {
            "delta": 3,
            "reason": "[QA SYNTHETIC] receipt",
            "expected_version": 1,
            "idempotency_key": "qa3-adjust",
        }
        result = self.ok("POST", url, payload)
        self.assertEqual((result["on_hand_quantity"], result["available_to_promise"]), (13, 13))
        self.assertEqual(self.ok("POST", url, payload)["version"], result["version"])
        self.assertEqual(
            self.api.post(url, json={**payload, "idempotency_key": "qa3-stale"}).status_code, 409
        )
        self.assertEqual(
            self.api.post(
                url,
                json={
                    **payload,
                    "expected_version": 2,
                    "delta": -99,
                    "idempotency_key": "qa3-negative",
                },
            ).status_code,
            409,
        )
        ledger = self.ok("GET", f"/api/v1/inventory/{item['id']}/ledger")
        self.assertEqual(len(ledger), 2)
        self.evidence("stock-adjustment", {"balance": self.balance(item), "ledger": ledger})
        MANIFEST["inventory"] = item

    def test_02_reservation_release_consume_and_invalid_transition(self) -> None:
        item = self.item("Reservations", 5)
        url = f"/api/v1/inventory/{item['id']}/reserve"
        payload = {"order_line_key": "qa3-reserve", "quantity": 3, "idempotency_key": "qa3-reserve"}
        reserved = self.ok("POST", url, payload)
        self.assertEqual(self.ok("POST", url, payload)["id"], reserved["id"])
        self.assertEqual(self.balance(item)["available_to_promise"], 2)
        self.assertEqual(
            self.api.post(
                url,
                json={
                    **payload,
                    "order_line_key": "over",
                    "idempotency_key": "over",
                    "quantity": 3,
                },
            ).status_code,
            409,
        )
        route = f"/api/v1/inventory/reservations/{reserved['id']}"
        self.assertEqual(self.ok("POST", route + "/release")["state"], "released")
        self.assertEqual(self.ok("POST", route + "/release")["state"], "released")
        self.assertEqual(self.api.post(route + "/consume").status_code, 409)
        second = self.ok(
            "POST",
            url,
            {**payload, "order_line_key": "consume", "idempotency_key": "consume", "quantity": 2},
        )
        self.ok("POST", f"/api/v1/inventory/reservations/{second['id']}/consume")
        self.assertEqual(self.balance(item)["on_hand_quantity"], 3)

    def test_03_order_cancel_ship_return_and_no_automatic_refund(self) -> None:
        item = self.item("Lifecycle", 10)
        route = "/api/v1/orders/fake/events"
        cancelled = self.ok("POST", route, self.event(item, "QA3-CANCEL"))
        self.ok("POST", route, self.event(item, "QA3-CANCEL", "cancel", 2))
        self.assertEqual(self.balance(item)["on_hand_quantity"], 10)
        self.assertEqual(self.balance(item)["reserved_quantity"], 0)
        self.assertEqual(
            self.api.post(route, json=self.event(item, "QA3-CANCEL", "ship", 3)).status_code, 409
        )
        order = self.ok("POST", route, self.event(item, "QA3-RETURN"))
        self.ok("POST", route, self.event(item, "QA3-RETURN", "ship", 2))
        self.assertEqual(self.balance(item)["on_hand_quantity"], 8)
        returned = self.ok("POST", route, self.event(item, "QA3-RETURN", "return", 3))
        self.assertEqual(returned["status"], "returned")
        self.assertEqual(
            self.balance(item)["on_hand_quantity"],
            8,
            "Return must not silently restock sellable units",
        )
        refund = self.api.get(
            "/api/v1/financial/refund-impact", params={"marketplace": "flipkart"}
        ).json()
        self.evidence(
            "order-lifecycle", {"cancelled": cancelled, "returned": returned, "refund": refund}
        )
        MANIFEST.update(order=order, order_item=item)
        self.assertEqual(
            refund["total_refunds"], "UNKNOWN", "No refund evidence must remain UNKNOWN, not zero"
        )

    def test_04_concurrent_final_unit_duplicate_delivery_and_multiline_rollback(self) -> None:
        item = self.item("Final unit", 1)

        def post(data: dict[str, Any]) -> httpx.Response:
            return self.api.post("/api/v1/orders/fake/events", json=data)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    post,
                    [
                        self.event(item, "QA3-RACE-A", quantity=1),
                        self.event(item, "QA3-RACE-B", quantity=1),
                    ],
                )
            )
        self.assertEqual(sorted(r.status_code for r in results), [201, 409])
        winner = next(r.json() for r in results if r.status_code == 201)
        payload = self.event(item, winner["remote_order_id"], quantity=1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            replay = list(pool.map(post, [payload] * 4))
        self.assertTrue(
            all(r.status_code == 200 and r.json()["id"] == winner["id"] for r in replay)
        )
        self.assertEqual(self.balance(item)["reserved_quantity"], 1)
        spare = self.item("Atomic", 10)
        invalid = self.event(spare, "QA3-ATOMIC", quantity=1)
        invalid["lines"].append({"external_sku": "NO-MAPPING", "quantity": 1, "unit_price": "1"})
        self.assertEqual(post(invalid).status_code, 409)
        self.assertEqual(self.balance(spare)["reserved_quantity"], 0)
        self.evidence(
            "order-concurrency",
            {
                "codes": [r.status_code for r in results],
                "replay_codes": [r.status_code for r in replay],
                "balance": self.balance(item),
            },
        )

    def test_05_conflicting_stock_key_is_not_silently_accepted(self) -> None:
        item = self.item("Conflict")
        route = f"/api/v1/inventory/{item['id']}/adjust"
        payload = {
            "delta": 1,
            "reason": "Receipt",
            "expected_version": 1,
            "idempotency_key": "qa3-conflict",
        }
        first = self.ok("POST", route, payload)
        conflicting = self.api.post(route, json={**payload, "delta": 99})
        self.evidence(
            "stock-conflicting-key",
            {
                "first": first,
                "changed_delta": 99,
                "conflict_status": conflicting.status_code,
                "response": conflicting.json(),
            },
        )
        self.assertEqual(
            conflicting.status_code,
            409,
            "Same key with a different stock delta must not report success",
        )

    def test_06_financial_event_rounding_loss_and_reconciliation_oracle(self) -> None:
        item = self.item("Financial evidence")
        pid = item["product_id"]
        for kind, amount in [
            ("sale", "100.005"),
            ("discount", "0.005"),
            ("refund", "1.005"),
            ("fee", "2.005"),
            ("shipping", "0.005"),
        ]:
            data = self.financial_event("qa3-" + kind, kind, amount, product_id=pid)
            first = self.ok("POST", "/api/v1/financial/events", data)
            self.assertEqual(
                self.ok("POST", "/api/v1/financial/events", data)["event"]["id"],
                first["event"]["id"],
            )
        cost = self.ok(
            "POST",
            "/api/v1/financial/costs",
            {
                "product_id": pid,
                "marketplace": "amazon",
                "cost_key": "qa3-cost",
                "cost_type": "acquisition",
                "amount": "200.005",
                "effective_from": "2026-01-01T00:00:00Z",
                "source_type": "synthetic_fixture",
            },
        )
        expected = reconcile(
            sale="100.005",
            discount="0.005",
            refund="1.005",
            fees=["2.005", "0.005"],
            cost="200.005",
        )
        actual = self.finance(date_to="2026-01-31T23:59:59Z")
        for key, value in expected.items():
            self.assertEqual(actual[key], value, key)
        self.assertTrue(actual["synthetic_provider"])
        alerts = self.api.get(
            "/api/v1/financial/alerts",
            params={"marketplace": "amazon", "date_to": "2026-01-31T23:59:59Z"},
        ).json()
        self.assertIn("negative_contribution", [a["code"] for a in alerts["alerts"]])
        self.evidence(
            "financial-oracle",
            {"expected": expected, "actual": actual, "cost": cost, "alerts": alerts},
        )
        MANIFEST.update(financial_product=pid, financial_expected=expected)

    def test_07_conflicting_financial_event_is_rejected(self) -> None:
        payload = self.financial_event(
            "qa3-sale", "sale", "999999", product_id=MANIFEST["financial_product"]
        )
        response = self.api.post("/api/v1/financial/events", json=payload)
        self.evidence(
            "financial-conflicting-key",
            {
                "changed_amount": "999999",
                "status": response.status_code,
                "response": response.json(),
            },
        )
        self.assertEqual(
            response.status_code,
            409,
            "Conflicting monetary evidence must not be acknowledged as an identical replay",
        )

    def test_08_unknown_cost_revision_does_not_resurrect_old_known_cost(self) -> None:
        # Explicit UNKNOWN is the supported contract; no invented stale enum.
        self.ok(
            "POST",
            "/api/v1/financial/costs",
            {
                "product_id": MANIFEST["financial_product"],
                "marketplace": "amazon",
                "cost_key": "qa3-cost",
                "cost_type": "acquisition",
                "amount": None,
                "evidence_status": "unknown",
                "effective_from": "2026-02-01T00:00:00Z",
                "source_type": "synthetic_fixture",
            },
        )
        result = self.finance(date_to="2026-02-28T23:59:59Z")
        self.evidence("unknown-cost-revision", result)
        self.assertEqual(
            result["contribution"],
            "UNKNOWN",
            "A newer UNKNOWN revision must not silently fall back to superseded cost evidence",
        )

    def test_09_current_financial_snapshot_and_later_refund(self) -> None:
        prefix = "/api/v1/financial/calculations"
        first = self.ok("POST", prefix + "/recalculate")
        replay = self.ok("POST", prefix + "/recalculate")
        self.assertEqual(replay["id"], first["id"])
        self.ok(
            "POST",
            "/api/v1/financial/events",
            self.financial_event(
                "qa3-later-refund",
                "refund",
                "2.50",
                product_id=MANIFEST["financial_product"],
                effective="2026-03-01T00:00:00Z",
            ),
        )
        new = self.ok("POST", prefix + "/recalculate")
        history = self.ok("GET", prefix)
        self.evidence(
            "financial-snapshot-history", {"before": first, "after": new, "history": history}
        )
        # PR-SOS-05 implements a mutable current projection per scope, not an
        # append-only history API. Test that supported contract; record the
        # unavailable historical calculation/complete cost-lineage flow as a gap.
        self.assertEqual(new["id"], first["id"])
        self.assertEqual(
            Decimal(new["metrics"]["net_sales"]),
            Decimal(first["metrics"]["net_sales"]) - Decimal("2.50"),
        )
        persisted = next(h for h in history if h["id"] == first["id"])
        self.assertEqual(persisted["metrics"], new["metrics"])
        self.assertIn("event_ids", new["lineage"])

    def test_10_settlement_unknown_mismatch_revision_and_precision(self) -> None:
        payload = {
            "account_id": MANIFEST["amazon_account"],
            "marketplace": "amazon",
            "settlement_key": "QA3-SETTLEMENT",
            "provenance": {"source_type": "synthetic_fixture"},
        }
        first = self.ok("POST", "/api/v1/financial/settlements/reconcile", payload)
        self.assertEqual(first["status"], "unknown")
        next_row = self.ok(
            "POST",
            "/api/v1/financial/settlements/reconcile",
            {**payload, "expected_amount": "98.005", "reported_amount": "95.505"},
        )
        self.assertEqual(next_row["difference_amount"], "-2.50")
        self.assertEqual(next_row["status"], "mismatch")
        matched = self.ok(
            "POST",
            "/api/v1/financial/settlements/reconcile",
            {**payload, "expected_amount": "98.005", "reported_amount": "98.005"},
        )
        self.assertEqual(matched["status"], "matched")
        self.assertEqual(matched["id"], first["id"])
        self.evidence(
            "settlement-revisions",
            {
                "initial": first,
                "mismatch": next_row,
                "matched": matched,
                "persisted": self.ok("GET", "/api/v1/financial/settlements"),
            },
        )
        # Keep explicit missing and mismatch rows available for UI assertions.
        for key, amounts in [
            ("QA3-UNKNOWN", {}),
            ("QA3-MISMATCH", {"expected_amount": "98.00", "reported_amount": "95.50"}),
        ]:
            self.ok(
                "POST",
                "/api/v1/financial/settlements/reconcile",
                {**payload, "settlement_key": key, **amounts},
            )

    def test_11_business_agent_unknowns_loss_and_default_deny(self) -> None:
        agent = self.ok("GET", "/api/v1/financial/business-agent")
        self.assertEqual(agent["authority"], "read_only")
        self.assertFalse(agent["external_writes"])
        self.assertIn("payout_action", agent["human_approval_required_for"])
        self.assertTrue(agent["summary"]["synthetic_provider"])
        self.assertGreater(len(agent["actions"]), 0)
        self.evidence("financial-agent", agent)
        MANIFEST["agent"] = agent

    def test_12_action_center_persisted_replay_concurrency_and_history(self) -> None:
        item = self.item("Action low stock", 0, 5)
        self.ok("POST", ACTION + "/scan")
        signals = self.ok("GET", ACTION)["signals"]
        signal = next(s for s in signals if s["source_resource_id"] == item["id"])
        MANIFEST.update(signal=signal, signal_inventory=item)
        self.assertEqual(signal["source_authority"], "InventoryItem")
        self.assertEqual(signal["evidence"]["available"], 0)
        self.assertIn("fresh_until", signal)
        route = ACTION + f"/signals/{signal['id']}/acknowledge"
        payload = {"idempotency_key": "qa3-acknowledge", "note": "[QA SYNTHETIC] reviewed"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.api.post(route, json=payload), range(4)))
        detail = self.ok("GET", ACTION + f"/signals/{signal['id']}")
        self.evidence(
            "action-center-replay",
            {"signal": signal, "detail": detail, "statuses": [r.status_code for r in results]},
        )
        self.assertTrue(
            all(r.status_code == 200 for r in results),
            f"Concurrent replay statuses: {[r.status_code for r in results]}",
        )
        self.assertEqual(len({r.json()["transition_id"] for r in results}), 1)

    def test_13_conflicting_signal_transition_key_rejected(self) -> None:
        signal = MANIFEST["signal"]
        response = self.api.post(
            ACTION + f"/signals/{signal['id']}/resolve",
            json={"idempotency_key": "qa3-acknowledge", "note": "Different action"},
        )
        self.evidence(
            "action-conflicting-key", {"status": response.status_code, "response": response.json()}
        )
        self.assertEqual(
            response.status_code,
            409,
            "Resolve cannot reuse an acknowledge identity and report successful resolution",
        )

    def test_14_human_impersonation_external_action_and_unauthorized_resources(self) -> None:
        signal = MANIFEST["signal"]
        route = ACTION + f"/signals/{signal['id']}/action"
        ai = self.api.post(
            route,
            json={"actor_type": "AI", "action_type": "review", "idempotency_key": "qa3-ai-blocked"},
        )
        self.assertEqual(ai.status_code, 403)
        # This route can never dispatch; canonical service explicitly default-denies these verbs.
        forbidden = self.api.post(
            route,
            json={"actor_type": "HUMAN", "action_type": "PUBLISH", "idempotency_key": "qa3-denied"},
        )
        self.assertEqual(forbidden.status_code, 403)
        local = self.ok(
            "POST",
            route,
            {"actor_type": "HUMAN", "action_type": "review", "idempotency_key": "qa3-review"},
        )
        self.assertFalse(local["external_writes"])
        self.assertEqual(local["status"], "approval_required")
        with httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}) as guest:
            for url in ("/api/v1/inventory", "/api/v1/orders", "/api/v1/financial/summary", ACTION):
                self.assertEqual(guest.get(url).status_code, 401)
        self.assertEqual(self.api.get(ACTION + f"/signals/{uuid.uuid4()}").status_code, 404)
        self.evidence(
            "human-authority",
            {"ai": ai.status_code, "external": forbidden.status_code, "local": local},
        )

    def test_15_source_changes_rescan_and_signal_resolution(self) -> None:
        item = MANIFEST["signal_inventory"]
        current = self.balance(item)
        self.ok(
            "POST",
            f"/api/v1/inventory/{item['id']}/adjust",
            {
                "delta": 20,
                "reason": "[QA SYNTHETIC] replenishment",
                "expected_version": current["version"],
                "idempotency_key": "qa3-replenish",
            },
        )
        self.ok("POST", ACTION + "/scan")
        detail = self.ok("GET", ACTION + f"/signals/{MANIFEST['signal']['id']}")
        self.evidence("signal-after-replenishment", detail)
        self.assertIn(
            detail["signal"]["status"],
            {"RESOLVED", "STALE"},
            "A replenished source must not leave an old out-of-stock signal authoritative",
        )

    def test_16_fresh_process_database_reconstruction(self) -> None:
        run = subprocess.run(
            [sys.executable, "-m", "qa.operational_probe"],
            capture_output=True,
            timeout=45,
            check=False,
        )
        self.assertEqual(
            run.returncode,
            0,
            "Fresh-process read-only reconstruction failed; raw subprocess output not logged",
        )
        proof = json.loads((OUTPUT / "fresh-process-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(proof["counts"]["users"], 1)
        self.assertEqual(proof["counts"]["invalid_inventory_balances"], 0)
        self.assertGreater(proof["counts"]["financial_events"], 0)
        events = {row["id"]: row for row in self.ok("GET", "/api/v1/financial/events")}
        for stored in proof["financial_amounts"]:
            self.assertEqual(Decimal(stored["amount"]), Decimal(events[stored["id"]]["amount"]))
            self.assertEqual(stored["source_event_id"], events[stored["id"]]["source_event_id"])
        balances = {row["id"]: row for row in self.ok("GET", "/api/v1/inventory")}
        for stored in proof["balances"]:
            for field in ("on_hand_quantity", "reserved_quantity", "damaged_quantity"):
                self.assertEqual(stored[field], balances[stored["id"]][field])

    def test_17_canonical_order_synthetic_provenance_and_state_change(self) -> None:
        data = self.api.get("/api/v1/financial/summary", params={"marketplace": "flipkart"}).json()
        self.evidence("canonical-order-financial-source", data)
        self.assertTrue(data["canonical_order_fallback"])
        self.assertTrue(
            data["synthetic_provider"],
            "Fake order fallback must not be labelled non-synthetic canonical evidence",
        )

    def test_18_prepare_original_mobile_states_and_operational_browser_data(self) -> None:
        # Reuse existing canonical fixtures and assertions, not copied supplier/economic rows.
        from qa import phase2_api

        helper = phase2_api.SellerScenarios()
        phase2_api.SellerScenarios.api = self.api
        helper.test_01_selection_supplier_due_diligence_decision()
        helper.test_06_changed_readiness_does_not_silently_accept_old_cost()
        helper.test_11_prepare_current_browser_review_after_fixture_changes()
        MANIFEST["phase2"] = phase2_api.MANIFEST
        # Leave a NEW low-stock issue for the browser, independent of earlier defect tests.
        item = self.item("Browser warning", 1, 5)
        self.ok("POST", ACTION + "/scan")
        MANIFEST["browser_signal"] = next(
            s for s in self.ok("GET", ACTION)["signals"] if s["source_resource_id"] == item["id"]
        )
        MANIFEST["financial_summary"] = self.api.get(
            "/api/v1/financial/summary", params={"marketplace": "amazon"}
        ).json()
        self.evidence("browser-fixture", MANIFEST)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OperationalScenarios)
    result = cast(
        JsonResult, unittest.TextTestRunner(resultclass=JsonResult, verbosity=1).run(suite)
    )
    (OUTPUT / "api-results.json").write_text(
        json.dumps(
            {
                "tests": result.rows,
                "passed": sum(r["status"] == "PASS" for r in result.rows),
                "failed": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    raise SystemExit(not result.wasSuccessful())
