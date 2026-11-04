"""Real HTTP + read-only PostgreSQL QA scenarios. Synthetic disposable data only."""

from __future__ import annotations

import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, cast

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from qa.financial_oracle import expected
from qa.fixture_server import require_target

OUTPUT = Path(os.environ["QA_RUN_DIR"])
ORIGIN = os.environ["QA_ORIGIN"]
MANIFEST: dict[str, Any] = {}
EMAIL = "qa-phase2-owner@example.com"
PASSWORD = "SyntheticPhase2Only123!"


class SellerScenarios(unittest.TestCase):
    api: ClassVar[httpx.Client]

    @classmethod
    def setUpClass(cls) -> None:
        cls.api = httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=40)
        witness = cls.api.get("/__qa/witness").json()
        assert witness["token"] == os.environ["QA_TOKEN"] and witness["disposable"] is True
        setup = cls.api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "[QA SYNTHETIC] Phase 2 Owner",
                "email": EMAIL,
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        assert setup.status_code == 201

    @classmethod
    def tearDownClass(cls) -> None:
        (OUTPUT / "phase2-manifest.json").write_text(
            json.dumps(MANIFEST, indent=2), encoding="utf-8"
        )
        cls.api.close()

    def ok(self, method: str, route: str, data: Any = None) -> Any:
        response = self.api.request(method, route, json=data)
        self.assertLess(
            response.status_code,
            300,
            f"{method} {route} HTTP {response.status_code}: {response.text[:600]}",
        )
        return response.json()

    def context(self, label: str) -> tuple[str, str]:
        key = f"qa2-{label}-{uuid.uuid4().hex[:8]}"
        op = self.ok(
            "POST",
            "/api/v1/intelligence/product-opportunities",
            {
                "name": f"[QA SYNTHETIC] {label} Water Bottle",
                "product_concept": "stainless steel insulated water bottles",
                "description": "Synthetic QA candidate, not discovered live market evidence.",
                "category": "Home & Kitchen",
                "target_marketplace": "AMAZON_IN",
                "target_region": "IN",
                "origin": "manual",
                "notes": "DETERMINISTIC_TEST / SYNTHETIC / NO LIVE EVIDENCE",
                "idempotency_key": key,
            },
        )
        oid = op["id"]
        constraint = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/constraints",
            {
                "available_capital": "300000",
                "currency": "INR",
                "marketplace": "AMAZON_IN",
                "country_region": "IN",
                "category_restrictions": ["Home & Kitchen"],
                "idempotency_key": key + "-constraint",
            },
        )
        assessment = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/assessments",
            {
                "constraint_version_id": constraint["id"],
                "evidence_state": "insufficient_evidence",
                "status": "created",
                "input_snapshot": {"evidence_environment": "DETERMINISTIC_TEST"},
            },
        )
        aid = assessment["id"]
        base = self.base(oid, aid)
        self.ok("POST", base + "/score", {"idempotency_key": key + "-score"})
        self.ok(
            "POST",
            base + "/decision",
            {
                "action": "shortlist",
                "rationale": "Explicit HUMAN synthetic product selection.",
                "idempotency_key": key + "-select",
            },
        )
        discovery = self.ok(
            "POST",
            "/api/v1/intelligence/suppliers/research",
            {
                "product_opportunity_id": oid,
                "product_query": "stainless steel insulated water bottles",
                "category": "Home & Kitchen",
                "country": "IN",
                "mode": "LOCAL_FIXTURE",
                "max_candidates": 1,
                "idempotency_key": key + "-supplier",
            },
        )
        (OUTPUT / f"supplier-{oid}.json").write_text(
            json.dumps(discovery, indent=2), encoding="utf-8"
        )
        self.assertEqual(discovery["result"]["accepted_candidate_count"], 1)
        self.assertIs(discovery["result"]["external_calls"], False)
        return oid, aid

    def base(self, oid: str, aid: str) -> str:
        return f"/api/v1/intelligence/product-opportunities/{oid}/assessments/{aid}"

    def readiness(self, oid: str, aid: str, price: str = "100.125", freight: str = "2500") -> Any:
        assumptions = [
            {
                "key": key,
                "value": value,
                "reason": "Explicit synthetic QA scenario; not a supplier quote.",
                **extra,
            }
            for key, value, extra in [
                ("supplier_unit_price", price, {"unit": "per_unit", "currency": "INR"}),
                ("supplier_currency", "INR", {}),
                ("freight_cost", freight, {"unit": "per_shipment", "currency": "INR"}),
                ("freight_currency", "INR", {}),
                ("origin", "IN", {}),
                ("destination", "IN", {}),
            ]
        ]
        return self.ok(
            "POST",
            self.base(oid, aid) + "/commercial-readiness",
            {
                "idempotency_key": "qa2-readiness-" + uuid.uuid4().hex,
                "scenario_key": "DETERMINISTIC_TEST",
                "assumptions": assumptions,
            },
        )

    def landed(self, oid: str, aid: str, q: str = "500") -> Any:
        return self.ok(
            "POST",
            self.base(oid, aid) + "/landed-cost",
            {
                "idempotency_key": "qa2-landed-" + uuid.uuid4().hex,
                "base_currency": "INR",
                "target_quantity": q,
                "quantity_unit": "unit",
            },
        )

    def unit_payload(
        self, selling: str = "250", q: str = "500", percent: str = "10", order: str = "50"
    ) -> dict[str, Any]:
        def component(key: str, basis: str, **values: Any) -> dict[str, Any]:
            return {
                "key": key,
                "basis": basis,
                "currency": "INR",
                "required": True,
                "provenance": "DETERMINISTIC_TEST",
                "marker": "DETERMINISTIC_TEST",
                "reason": "Hypothetical cost component; NOT an Amazon fee schedule.",
                **values,
            }

        return {
            "idempotency_key": "qa2-unit-" + uuid.uuid4().hex,
            "selling_price": selling,
            "selling_price_currency": "INR",
            "selling_price_provenance": "DETERMINISTIC_TEST",
            "quantity": q,
            "selling_cost_components": [
                component("scenario_percent", "PERCENT_OF_SELLING_PRICE", rate=percent),
                component("scenario_order", "PER_ORDER", amount=order),
            ],
        }

    def unit(self, oid: str, aid: str, payload: dict[str, Any]) -> Any:
        return self.ok("POST", self.base(oid, aid) + "/commercial/unit-economics", payload)

    def assert_oracle(self, result: Any, oracle: dict[str, Any]) -> None:
        self.assertEqual(result["status"], "READY")
        for key, value in oracle.items():
            if key == "landed_total":
                continue
            self.assertEqual(
                Decimal(result[key]) if isinstance(value, Decimal) else result[key], value, key
            )

    def test_01_selection_supplier_due_diligence_decision(self) -> None:
        oid, aid = self.context("Main journey")
        MANIFEST.update(opportunity_id=oid, assessment_id=aid)
        base = self.base(oid, aid)
        self.ok("POST", base + "/score", {"idempotency_key": "qa2-main-score"})
        selected = self.ok(
            "POST",
            base + "/decision",
            {
                "action": "shortlist",
                "rationale": "Explicit HUMAN synthetic product selection.",
                "idempotency_key": "qa2-product-select",
            },
        )
        self.assertEqual(selected["action"], "shortlist")
        research_payload = {
            "product_opportunity_id": oid,
            "product_query": "stainless steel insulated water bottles",
            "category": "Home & Kitchen",
            "country": "IN",
            "mode": "LOCAL_FIXTURE",
            "max_candidates": 1,
            "idempotency_key": "qa2-local-supplier",
        }
        discovery = self.ok("POST", "/api/v1/intelligence/suppliers/research", research_payload)
        (OUTPUT / "supplier-discovery.json").write_text(
            json.dumps(discovery, indent=2), encoding="utf-8"
        )
        self.assertIs(discovery["result"]["external_calls"], False)
        self.assertEqual(discovery["result"]["accepted_candidate_count"], 1)
        replay = self.ok("POST", "/api/v1/intelligence/suppliers/research", research_payload)
        self.assertEqual(replay["request"]["id"], discovery["request"]["id"])
        canonical = self.ok(
            "POST", "/api/v1/intelligence/cross-marketplace/suppliers/reconcile", {}
        )
        sid = canonical[0]["id"]
        MANIFEST["supplier_id"] = sid
        detail = self.ok("GET", f"/api/v1/intelligence/cross-marketplace/suppliers/{sid}")
        self.assertEqual(detail["evidence_lineage"][0]["verification"], "unverified")
        context = self.ok(
            "POST",
            "/api/v1/intelligence/supplier-shortlisting/contexts",
            {
                "opportunity_id": oid,
                "target_market": "AMAZON_IN",
                "budget": 300000,
                "budget_currency": "INR",
                "idempotency_key": "qa2-shortlist-context",
            },
        )
        shortlist = self.ok(
            "POST",
            f"/api/v1/intelligence/supplier-shortlisting/contexts/{context['id']}/shortlists",
            {"top_n": 1, "idempotency_key": "qa2-shortlist"},
        )
        decision_payload = {
            "shortlist_version_id": shortlist["id"],
            "supplier_id": sid,
            "decision": "KEEP_UNDER_REVIEW",
            "reason": "Synthetic supplier is NOT verified; due diligence needed.",
            "decision_key": "qa2-shortlist-decision",
        }
        durl = f"/api/v1/intelligence/supplier-shortlisting/contexts/{context['id']}/decisions"
        decision = self.ok("POST", durl, decision_payload)
        self.assertEqual(self.ok("POST", durl, decision_payload)["id"], decision["id"])
        due = self.ok("GET", "/api/v1/intelligence/supplier-due-diligence/contexts")
        self.assertEqual(due[0]["supplier_id"], sid)
        (OUTPUT / "due-diligence.json").write_text(json.dumps(due, indent=2), encoding="utf-8")
        MANIFEST["due_context_id"] = due[0]["id"]
        assessed = self.ok(
            "POST", f"/api/v1/intelligence/supplier-due-diligence/contexts/{due[0]['id']}/assess"
        )
        self.assertIn(
            assessed["readiness"], {"REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE", "SUFFICIENT"}
        )
        goal = self.ok(
            "POST",
            "/api/v1/intelligence/business-agent/goals",
            {
                "raw_goal": "I have INR 300000 and want a water bottle product on Amazon India.",
                "structured_goal": {
                    "marketplace": "AMAZON_IN",
                    "category": "Home & Kitchen",
                    "capital": 300000,
                    "currency": "INR",
                    "product_opportunity_id": oid,
                },
                "provenance": {
                    "mode": "LOCAL_FIXTURE",
                    "evidence_environment": "DETERMINISTIC_TEST",
                },
                "idempotency_key": "qa2-main-goal",
            },
        )
        MANIFEST["goal_id"] = goal["id"]
        self.ok("POST", f"/api/v1/intelligence/business-agent/goals/{goal['id']}/plan")
        self.readiness(oid, aid)
        landed = self.landed(oid, aid)
        unit = self.unit(oid, aid, self.unit_payload())
        self.assert_oracle(
            unit,
            expected(
                price="100.125",
                freight="2500",
                quantity="500",
                selling="250",
                percent="10",
                order_fee="50",
            ),
        )
        MANIFEST.update(landed=landed, unit=unit)
        rec = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/recommendation-assessment",
            {"decision_target": "COMMERCIAL_ASSESSMENT", "idempotency_key": "qa2-main-rec"},
        )
        MANIFEST["recommendation"] = rec
        self.assertTrue(rec["human_review_required"])
        self.assertEqual(rec["external_writes"], [])
        brand = self.ok(
            "POST",
            "/api/v1/brands",
            {"name": "[QA SYNTHETIC] Phase 2 Brand", "slug": "qa-phase2-brand"},
        )
        converted = self.ok(
            "POST",
            f"/api/v1/catalog/opportunities/{oid}/convert",
            {
                "brand_id": brand["id"],
                "goal_id": goal["id"],
                "sku": "QA-PHASE2-001",
                "idempotency_key": "qa2-convert",
            },
        )
        MANIFEST["product_id"] = converted.get("product", {}).get("id") or converted.get(
            "product_id"
        )

    def test_02_fractional_rounding_and_capital(self) -> None:
        oid, aid = self.context("Fractional")
        self.readiness(oid, aid, "1.25", "1")
        landed = self.landed(oid, aid, "501")
        self.assertEqual(Decimal(landed["calculation"]["per_unit_cost"]), Decimal("1.25199601"))
        result = self.unit(oid, aid, self.unit_payload("5", "501", "12.5", "0.1"))
        self.assert_oracle(
            result,
            expected(
                price="1.25",
                freight="1",
                quantity="501",
                selling="5",
                percent="12.5",
                order_fee="0.1",
            ),
        )

    def test_03_positive_negative_and_zero_margin(self) -> None:
        oid, aid = self.context("Margins")
        self.readiness(oid, aid, "100", "0")
        self.landed(oid, aid, "500")
        for selling, percent, order in [
            ("250", "10", "50"),
            ("90", "10", "50"),
            ("125", "20", "0"),
        ]:
            result = self.unit(oid, aid, self.unit_payload(selling, "500", percent, order))
            self.assert_oracle(
                result,
                expected(
                    price="100",
                    freight="0",
                    quantity="500",
                    selling=selling,
                    percent=percent,
                    order_fee=order,
                ),
            )

    def test_04_missing_invalid_currency_and_tax_unknown(self) -> None:
        oid, aid = self.context("Missing inputs")
        missing = self.ok(
            "POST",
            self.base(oid, aid) + "/commercial-readiness",
            {"idempotency_key": "qa2-missing"},
        )
        self.assertEqual(
            missing["readiness"]["calculations"]["LANDED_UNIT_COST"]["status"], "NEEDS_INPUT"
        )
        self.assertEqual(self.landed(oid, aid)["status"], "BLOCKED")
        self.readiness(oid, aid)
        self.landed(oid, aid)
        no_fee = self.unit_payload()
        no_fee["selling_cost_components"] = []
        self.assertEqual(self.unit(oid, aid, no_fee)["status"], "BLOCKED")
        self.assertEqual(self.unit(oid, aid, self.unit_payload("0"))["status"], "BLOCKED")
        invalid = self.unit_payload()
        invalid["selling_price_currency"] = "USD"
        self.assertEqual(self.unit(oid, aid, invalid)["status"], "BLOCKED")
        invalid["selling_price"] = "NaN"
        self.assertEqual(
            self.api.post(
                self.base(oid, aid) + "/commercial/unit-economics", json=invalid
            ).status_code,
            422,
        )
        result = self.unit(oid, aid, self.unit_payload())
        self.assertTrue(
            any(x["key"] == "tax" and "UNKNOWN" in x["status"] for x in result["unknown_excluded"])
        )
        self.assertTrue(any("not net profit" in x.lower() for x in result["limitations"]))

    def test_05_idempotency_history_and_reload(self) -> None:
        oid, aid = self.context("History")
        self.readiness(oid, aid)
        self.landed(oid, aid)
        data = self.unit_payload()
        first = self.unit(oid, aid, data)
        self.assertEqual(self.unit(oid, aid, data)["id"], first["id"])
        changed = self.unit_payload("90")
        second = self.unit(oid, aid, changed)
        self.assertNotEqual(first["id"], second["id"])
        history = self.ok("GET", self.base(oid, aid) + "/commercial/unit-economics/history")
        self.assertEqual(len(history), 2)
        self.assertEqual(
            self.ok("GET", self.base(oid, aid) + "/commercial/unit-economics")["id"], second["id"]
        )
        self.assertEqual(history[0]["per_unit_contribution"], first["per_unit_contribution"])
        self.readiness(oid, aid, "100.1250", "2500.0")
        equivalent = self.unit(oid, aid, self.unit_payload())
        self.assertEqual(equivalent["status"], "READY")
        self.assertEqual(equivalent["per_unit_landed_cost"], first["per_unit_landed_cost"])

    def test_06_changed_readiness_does_not_silently_accept_old_cost(self) -> None:
        oid, aid = self.context("Stale cost")
        previous_readiness = self.readiness(oid, aid, "100", "0")
        old = self.landed(oid, aid)
        historical_unit = self.unit(oid, aid, self.unit_payload())
        self.assertEqual(historical_unit["status"], "READY")
        changed_readiness = self.readiness(oid, aid, "200", "0")
        payload = self.unit_payload()
        payload["landed_cost_calculation_id"] = old["calculation"]["id"]
        result = self.unit(oid, aid, payload)
        (OUTPUT / "stale-input-observation.json").write_text(
            json.dumps(
                {
                    "previous_readiness": previous_readiness,
                    "changed_readiness": changed_readiness,
                    "old": old,
                    "result": result,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            result["status"] == "BLOCKED"
            or any(
                "stale" in str(item).lower()
                for item in result.get("limitations", []) + result.get("contradictions", [])
            ),
            "Old landed cost accepted against changed commercial readiness "
            "without stale-context warning",
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("LANDED_COST_INPUTS_CHANGED", result["missing_inputs"])
        historical_landed = self.ok("GET", self.base(oid, aid) + "/landed-cost")
        self.assertEqual(historical_landed["status"], "STALE")
        self.assertFalse(historical_landed["calculable"])
        self.assertEqual(historical_landed["calculation"]["id"], old["calculation"]["id"])
        latest = self.ok("GET", self.base(oid, aid) + "/commercial/unit-economics")
        self.assertEqual(latest["status"], "STALE")
        self.assertFalse(latest["calculable"])
        self.assertTrue(latest["freshness"]["recalculation_required"])
        history = self.ok("GET", self.base(oid, aid) + "/commercial/unit-economics/history")
        self.assertEqual(history[0]["id"], historical_unit["id"])
        self.assertEqual(history[0]["status"], "READY")
        self.assertEqual(
            history[0]["per_unit_landed_cost"], historical_unit["per_unit_landed_cost"]
        )
        recommendation = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/recommendation-assessment",
            {"decision_target": "COMMERCIAL_ASSESSMENT", "idempotency_key": "qa2-stale-rec"},
        )
        self.assertFalse(recommendation["recommendation_eligible"])
        self.assertTrue(
            any(row["code"] == "ECONOMIC_INPUTS_STALE" for row in recommendation["counter_reasons"])
        )
        MANIFEST["stale_opportunity_id"] = oid
        MANIFEST["stale_assessment_id"] = aid
        fresh = self.landed(oid, aid)
        fresh_payload = self.unit_payload()
        fresh_payload["landed_cost_calculation_id"] = fresh["calculation"]["id"]
        self.assertEqual(self.unit(oid, aid, fresh_payload)["per_unit_landed_cost"], "200.00000000")
        # Leave the stale scenario available for independent browser reload verification.
        self.readiness(oid, aid, "300", "0")

    def test_07_independent_database_reconstruction(self) -> None:
        self.assertIn("unit", MANIFEST, "Main journey failed before financial artifact creation")
        token = os.environ["QA_TOKEN"]
        database = f"vayujit_qa{token}_test"
        require_target(database, token)
        url = make_url(os.environ["QA_DATABASE_ADMIN_URL"]).set(database=database)
        self.assertEqual(url.host, "127.0.0.1")
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                self.assertEqual(connection.scalar(text("select current_database()")), database)
                self.assertEqual(
                    connection.scalar(
                        text("select suite_token from test_database_marker where marker_id=1")
                    ),
                    token,
                )
                row = (
                    connection.execute(
                        text(
                            "SELECT per_unit_landed_cost,per_unit_selling_cost,"
                            "per_unit_contribution,contribution_margin FROM "
                            "intelligence_product_opportunity_unit_economics WHERE id=:id"
                        ),
                        {"id": MANIFEST["unit"]["id"]},
                    )
                    .mappings()
                    .one()
                )
                for key, value in row.items():
                    self.assertEqual(value, Decimal(MANIFEST["unit"][key]), key)
                lineage = (
                    connection.execute(
                        text(
                            "SELECT opportunity_id, supplier_id FROM "
                            "intelligence_supplier_due_diligence_contexts WHERE id=:id"
                        ),
                        {"id": MANIFEST["due_context_id"]},
                    )
                    .mappings()
                    .one()
                )
                self.assertEqual(str(lineage["opportunity_id"]), MANIFEST["opportunity_id"])
                self.assertEqual(str(lineage["supplier_id"]), MANIFEST["supplier_id"])
                (OUTPUT / "database-proof.json").write_text(
                    json.dumps(
                        {
                            "process": "independent_from_api",
                            "read_only": True,
                            "values": {k: str(v) for k, v in row.items()},
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        finally:
            engine.dispose()

    def test_08_human_controls_and_business_decision_history(self) -> None:
        oid, _aid = self.context("Decision controls")
        rec = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/recommendation-assessment",
            {"decision_target": "COMMERCIAL_ASSESSMENT", "idempotency_key": "qa2-control-rec"},
        )
        route = f"/api/v1/intelligence/product-opportunities/{oid}/human-decision"
        payload = {
            "decision_target": "COMMERCIAL_ASSESSMENT",
            "decision": "KEEP_UNDER_REVIEW",
            "recommendation_id": rec["id"],
            "synthesis_id": rec["synthesis_id"],
            "reason": "Synthetic evidence incomplete; do not proceed.",
            "idempotency_key": "qa2-review",
        }
        impersonation = self.api.post(route, json={**payload, "provenance": "AI"})
        self.assertEqual(impersonation.status_code, 422)
        decision = self.ok("POST", route, payload)
        self.assertEqual(decision["provenance"], "HUMAN")
        self.assertEqual(self.ok("POST", route, payload)["id"], decision["id"])
        self.assertEqual(len(self.ok("GET", route + "/history")), 1)
        self.assertEqual(
            self.ok("GET", f"/api/v1/intelligence/product-opportunities/{oid}/decision-brief")[
                "human_decision"
            ]["id"],
            decision["id"],
        )
        with httpx.Client(base_url=ORIGIN) as guest:
            self.assertEqual(guest.get(route + "/history").status_code, 401)
        for change in [
            {"decision": "DO_NOT_PROCEED"},
            {"reason": "Different rationale"},
            {"supplier_id": str(uuid.uuid4())},
        ]:
            self.assertEqual(self.api.post(route, json={**payload, **change}).status_code, 409)
        # Fresh recommendation after projection changes; no forged HUMAN authorization.
        current = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/recommendation-assessment",
            {"decision_target": "COMMERCIAL_ASSESSMENT", "idempotency_key": "qa2-race-rec"},
        )
        race_payload = {
            **payload,
            "recommendation_id": current["id"],
            "synthesis_id": current["synthesis_id"],
            "idempotency_key": "qa2-concurrent-review",
        }
        cookies = dict(self.api.cookies)

        def submit(data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            with httpx.Client(
                base_url=ORIGIN, headers={"Origin": ORIGIN}, cookies=cookies, timeout=40
            ) as api:
                response = api.post(route, json=data)
                return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(submit, [race_payload] * 8))
        self.assertEqual([status for status, _ in responses], [201] * 8)
        self.assertEqual(len({body["id"] for _, body in responses}), 1)
        self.assertEqual(len(self.ok("GET", route + "/history")), 2)
        competing = [
            {**race_payload, "idempotency_key": "qa2-conflict-race", "reason": reason}
            for reason in ["First explicit HUMAN reason", "Different explicit HUMAN reason"]
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            conflicts = list(pool.map(submit, competing))
        self.assertEqual(sorted(status for status, _ in conflicts), [201, 409])
        self.assertEqual(len(self.ok("GET", route + "/history")), 3)
        (OUTPUT / "concurrent-human-replay.json").write_text(
            json.dumps(
                {
                    "same_request_statuses": [status for status, _ in responses],
                    "same_request_unique_decisions": len({body["id"] for _, body in responses}),
                    "conflict_statuses": sorted(status for status, _ in conflicts),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_09_explicit_tax_rate_arithmetic_and_unknown_basis(self) -> None:
        self.assertIn("product_id", MANIFEST)
        prefix = "/api/v1/intelligence/sourcing-economics"
        # Separate canonical context: PR-5B creates explicit UNKNOWN tax components
        # which legitimately take precedence under the 13A calculation contract.
        # Do not remove or override those components to force a tax result.
        economic_context = self.ok(
            "POST",
            prefix + "/contexts",
            {
                "product_id": MANIFEST["product_id"],
                "idempotency_key": "qa2-tax-economic",
                "origin_country": "IN",
                "destination_country": "IN",
                "base_currency": "INR",
                "target_quantity": "500",
                "quantity_unit": "unit",
            },
        )["context"]
        eid = economic_context["id"]
        context = self.ok(
            "POST",
            prefix + "/customs-tax/contexts",
            {
                "economic_context_id": eid,
                "idempotency_key": "qa2-tax-context",
                "origin_country": "IN",
                "destination_country": "IN",
                "reporting_currency": "INR",
                "status": "CURRENT",
            },
        )["context"]
        rate = self.ok(
            "POST",
            prefix + "/customs-tax/rates",
            {
                "context_id": context["id"],
                "idempotency_key": "qa2-tax-rate",
                "rate_kind": "IMPORT_TAX",
                "category": "IMPORT_TAX",
                "rate": "0.075",
                "basis": "EXPLICIT_TAXABLE_VALUE",
                "jurisdiction": "QA_SYNTHETIC_NOT_LEGAL",
                "source": "MANUAL",
                "provenance": "ASSUMED",
                "freshness": "CURRENT",
                "assumption_reason": "Arbitrary QA input; NOT an Indian GST determination.",
            },
        )
        self.assertEqual(Decimal(str(rate["rate"]["rate"])), Decimal("0.075"))
        economic = self.ok("POST", prefix + f"/snapshots?context_id={eid}", {})["snapshot"]
        observations = []
        for bases in [
            {
                "EXPLICIT_TAXABLE_VALUE": {
                    "basis_type": "EXPLICIT_TAXABLE_VALUE",
                    "amount": "1234.56",
                    "currency": "INR",
                }
            },
            {},
        ]:
            snapshot = self.ok(
                "POST",
                prefix + "/customs-tax/snapshots",
                {
                    "context_id": context["id"],
                    "basis_inputs": bases,
                },
            )["snapshot"]
            calc = self.ok(
                "POST",
                prefix + f"/snapshots/{economic['id']}/calculate",
                {
                    "customs_tax_snapshot_id": snapshot["id"],
                    "calculation_version": "landed-cost-v4",
                    "policy_version": "known-cost-customs-tax-v1",
                },
            )
            tax = next(x for x in calc["breakdown"] if x["source_kind"] == "customs_rate_evidence")
            if bases:
                self.assertEqual(Decimal(str(tax["included_amount"])), Decimal("92.592"))
                self.assertEqual(tax["provenance"], "ASSUMED")
            else:
                self.assertEqual(tax["inclusion_status"], "EXCLUDED")
                self.assertIsNone(tax["included_amount"])
                self.assertEqual(tax["exclusion_reason"], "UNKNOWN_BASIS")
            observations.append(calc)
        (OUTPUT / "hypothetical-tax.json").write_text(
            json.dumps(observations, indent=2), encoding="utf-8"
        )

    def test_10_capital_shortfall_is_not_zero(self) -> None:
        oid, aid = self.context("Capital shortfall")
        self.readiness(oid, aid, "100", "0")
        self.landed(oid, aid, "4000")
        result = self.unit(oid, aid, self.unit_payload("200", "4000", "0", "0"))
        self.assert_oracle(
            result, expected(price="100", freight="0", quantity="4000", selling="200")
        )
        self.assertEqual(Decimal(result["capital_shortfall"]), Decimal("100000"))

    def test_11_prepare_current_browser_review_after_fixture_changes(self) -> None:
        self.assertIn("product_id", MANIFEST)
        # Catalog conversion and subsequent synthetic evidence can legitimately stale a review.
        # Prepare a current recommendation, not a fake approval or a stale-context bypass.
        oid = MANIFEST["opportunity_id"]
        rec = self.ok(
            "POST",
            f"/api/v1/intelligence/product-opportunities/{oid}/recommendation-assessment",
            {
                "decision_target": "COMMERCIAL_ASSESSMENT",
                "goal_id": MANIFEST["goal_id"],
                "idempotency_key": "qa2-final-browser-rec",
            },
        )
        MANIFEST["recommendation"] = rec
        self.assertTrue(rec["human_review_required"])
        self.assertEqual(rec["external_writes"], [])


class JsonResult(unittest.TextTestResult):
    rows: list[dict[str, Any]]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.rows = []

    def addSuccess(self, test: Any) -> None:
        super().addSuccess(test)
        self.rows.append({"id": test.id().split(".")[-1], "status": "PASS"})

    def addFailure(self, test: Any, err: Any) -> None:
        super().addFailure(test, err)
        self.rows.append(
            {"id": test.id().split(".")[-1], "status": "FAIL", "error": str(err[1])[:1800]}
        )

    def addError(self, test: Any, err: Any) -> None:
        super().addError(test, err)
        # Don't serialize raw provider/SQL exceptions or environment secrets.
        self.rows.append(
            {"id": test.id().split(".")[-1], "status": "ERROR", "error_type": err[0].__name__}
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SellerScenarios)
    result = cast(
        JsonResult, unittest.TextTestRunner(resultclass=JsonResult, verbosity=1).run(suite)
    )
    (OUTPUT / "api-results.json").write_text(
        json.dumps(
            {
                "tests": result.rows,
                "passed": sum(row["status"] == "PASS" for row in result.rows),
                "failed": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    raise SystemExit(not result.wasSuccessful())
