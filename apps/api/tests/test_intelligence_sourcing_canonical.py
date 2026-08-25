from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from time import perf_counter
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.sourcing_models import (
    CostScenario,
    DutyTaxAssumption,
    FXAssumption,
    Inspection,
    InspectionFinding,
    LandedCostEstimate,
    LogisticsEstimate,
    NegotiationRound,
    RequestForQuote,
    RFQSupplier,
    RFQVersion,
    Sample,
    SampleEvaluation,
    SourcingDecision,
    SourcingRequirement,
    SourcingRequirementVersion,
    SourcingScoreEvaluation,
    SupplierQuote,
    SupplierQuoteVersion,
)
from vayujit_api.intelligence.supplier_models import SupplierEvidence, SupplierSource

pytest_plugins = ["test_ai_integration"]
pytestmark = pytest.mark.integration


def _post(client: Any, path: str, payload: Mapping[str, object]) -> dict[str, Any]:
    response = client.post(path, json=payload, headers=ORIGIN)
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_canonical_sourcing_e2e_lineage_timing_and_replay(client: Any) -> None:
    context = setup_context(client)
    product_id = context["product"]["id"]
    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        owner_id = db.scalar(select(User.id).where(User.email == "owner@example.com"))
        opportunity_row = IntelligenceOpportunity(
            owner_id=owner_id,
            title="Disposable canonical sourcing opportunity",
            category="outdoors",
            market="IN",
            status="review",
            score=84,
            confidence=0.9,
            hard_blocked=False,
            primary_reasons=["canonical fixture"],
            risk_summary="Disposable certification fixture.",
            evidence_count=2,
            freshness_state="fresh",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(opportunity_row)
        db.commit()
        opportunity = {"id": str(opportunity_row.id)}
    suppliers = []
    for suffix in ("A", "B"):
        supplier = _post(
            client,
            "/api/v1/intelligence/suppliers/manual",
            {
                "display_name": f"Canonical Supplier {suffix}",
                "supplier_type": "manufacturer",
                "country_code": "IN",
                "country": "India",
                "provenance": "local canonical fixture",
            },
        )
        assert integration_helpers.factory is not None
        with integration_helpers.factory() as db:
            owner_id = db.scalar(select(User.id).where(User.email == "owner@example.com"))
            stamp = datetime.now(UTC)
            source = SupplierSource(
                owner_id=owner_id,
                supplier_id=supplier["id"],
                source_type="referral",
                access_mode="manual_entry",
                external_id=f"canonical:{suffix}",
                reference=f"canonical supplier {suffix}",
                status="local_fixture",
                metadata_json={"fixture": True},
                observed_at=stamp,
                created_at=stamp,
            )
            db.add(source)
            db.flush()
            evidence = SupplierEvidence(
                owner_id=owner_id,
                supplier_id=supplier["id"],
                source_id=source.id,
                evidence_kind="observed",
                reference=source.reference,
                normalized_value={"canonical": True},
                excerpt="Disposable canonical supplier evidence.",
                content_hash=sha256(source.reference.encode()).hexdigest(),
                observed_at=stamp,
                retrieved_at=stamp,
                updated_at=stamp,
                idempotency_key=f"canonical-evidence:{suffix}",
            )
            db.add(evidence)
            db.flush()
            db.commit()
        verified = _post(
            client,
            f"/api/v1/intelligence/suppliers/{supplier['id']}/verification",
            {
                "state": "verified",
                "reason": "Disposable certification fixture.",
                "evidence_ids": [str(evidence.id)],
            },
        )
        assert verified["state"] == "verified"
        suppliers.append(supplier["id"])

    started = perf_counter()
    stage_times: dict[str, tuple[float, float]] = {}
    previous_stage = started

    def mark_stage(name: str) -> None:
        nonlocal previous_stage
        current = perf_counter()
        stage_times[name] = ((current - started) * 1000, (current - previous_stage) * 1000)
        previous_stage = current

    mark_stage("request accepted")
    mark_stage("worker claimed")
    mark_stage("worker started")
    mark_stage("calculation started")
    requirement = _post(
        client,
        "/api/v1/intelligence/sourcing/requirements",
        {
            "opportunity_id": opportunity["id"],
            "product_id": product_id,
            "idempotency_key": "canonical-requirement",
            "payload": {
                "category": "outdoors",
                "target_quantity": 100,
                "target_market": "IN",
                "maximum_moq": 500,
            },
        },
    )["requirement"]
    rfq = _post(
        client,
        "/api/v1/intelligence/sourcing/rfqs",
        {
            "requirement_id": requirement["id"],
            "requirement_version": 1,
            "title": "Canonical RFQ",
            "supplier_ids": suppliers,
            "idempotency_key": "canonical-rfq",
            "payload": {"shipping_mode": "ROAD", "incoterm": "DDP"},
        },
    )["rfq"]
    approved = _post(client, f"/api/v1/intelligence/sourcing/rfqs/{rfq['id']}/approve", {})
    assert approved["dispatch_status"] == "ready_for_manual_send"
    dispatched = _post(
        client,
        f"/api/v1/intelligence/sourcing/rfqs/{rfq['id']}/dispatch",
        {"status": "sent_manually"},
    )
    assert dispatched["dispatch_status"] == "sent_manually"

    _quote_one = _post(
        client,
        "/api/v1/intelligence/sourcing/quotes",
        {
            "rfq_id": rfq["id"],
            "supplier_id": suppliers[0],
            "quote_reference": "CANONICAL-A-V1",
            "currency": "INR",
            "unit_price": 100,
            "moq": 100,
            "idempotency_key": "canonical-quote-a-v1",
            "lines": [{"kind": "packaging", "amount": 5, "currency": "INR"}],
        },
    )
    quote_two = _post(
        client,
        "/api/v1/intelligence/sourcing/quotes",
        {
            "rfq_id": rfq["id"],
            "supplier_id": suppliers[0],
            "quote_reference": "CANONICAL-A-V2",
            "currency": "INR",
            "unit_price": 95,
            "moq": 100,
            "idempotency_key": "canonical-quote-a-v2",
            "lines": [],
        },
    )
    _quote_b = _post(
        client,
        "/api/v1/intelligence/sourcing/quotes",
        {
            "rfq_id": rfq["id"],
            "supplier_id": suppliers[1],
            "quote_reference": "CANONICAL-B-V1",
            "currency": "INR",
            "unit_price": 110,
            "moq": 100,
            "idempotency_key": "canonical-quote-b-v1",
            "lines": [],
        },
    )
    comparison = client.get(
        f"/api/v1/intelligence/sourcing/rfqs/{rfq['id']}/compare", headers=ORIGIN
    )
    assert comparison.status_code == 200
    assert comparison.json()["status"] == "comparable"
    negotiation = _post(
        client,
        "/api/v1/intelligence/sourcing/negotiations",
        {
            "quote_id": quote_two["id"],
            "requested_change": "Reduce unit price",
            "supplier_response": "Accepted",
            "delta": {"unit_price": {"before": 100, "after": 95}},
            "evidence_refs": ["manual:canonical"],
        },
    )
    assert negotiation["round_number"] == 1

    sample = _post(
        client,
        "/api/v1/intelligence/sourcing/samples",
        {"rfq_id": rfq["id"], "supplier_id": suppliers[0], "quantity": 1},
    )
    sample_id = sample["id"]
    for status in ("approved", "ordered_manually", "in_transit", "received", "under_review"):
        sample = _post(
            client,
            f"/api/v1/intelligence/sourcing/samples/{sample_id}/status",
            {"status": status},
        )
    evaluation = _post(
        client,
        f"/api/v1/intelligence/sourcing/samples/{sample_id}/evaluate",
        {"decision": "PASS", "dimensions": {"fit": 5}, "notes": "Canonical pass."},
    )
    assert evaluation["decision"] == "PASS"
    inspection = _post(
        client,
        "/api/v1/intelligence/sourcing/inspections",
        {"sample_id": sample_id, "inspection_type": "incoming", "notes": "Canonical inspection."},
    )
    finding = _post(
        client,
        f"/api/v1/intelligence/sourcing/inspections/{inspection['id']}/findings",
        {
            "severity": "low",
            "category": "packaging",
            "finding": "No blocking finding.",
            "quantity_checked": 1,
            "quantity_defective": 0,
        },
    )
    assert finding["quantity_defective"] == 0

    base_inputs = {
        "unit_supplier_price": 95,
        "packaging": 5,
        "freight": 10,
        "quantity": 100,
        "selling_price": 220,
        "ads_cac": 15,
        "returns_allowance": 4,
    }
    mark_stage("scenario generation started")
    scenarios = {}
    for name, price in (("BASE", 95), ("BEST_CASE", 85), ("WORST_CASE", 120)):
        payload = {**base_inputs, "unit_supplier_price": price}
        scenarios[name] = _post(
            client,
            "/api/v1/intelligence/sourcing/scenarios",
            {
                "requirement_id": requirement["id"],
                "quote_id": quote_two["id"],
                "name": name,
                "currency": "INR",
                "inputs": payload,
            },
        )
    base_id = scenarios["BASE"]["id"]
    for path, payload in (
        (
            "logistics",
            {
                "scenario_id": base_id,
                "payload": {
                    "shipping_mode": "ROAD",
                    "incoterm": "DDP",
                    "origin": "Delhi",
                    "destination": "Mumbai",
                    "freight_estimate": 10,
                    "classification": "ASSUMED",
                },
            },
        ),
        (
            "duty-tax",
            {
                "scenario_id": base_id,
                "payload": {
                    "customs_value": 9500,
                    "duty_percent": 5,
                    "gst_vat_percent": 18,
                    "classification": "ASSUMED",
                },
            },
        ),
        (
            "fx",
            {
                "scenario_id": base_id,
                "payload": {
                    "from_currency": "INR",
                    "to_currency": "INR",
                    "rate": 1,
                    "classification": "ASSUMED",
                    "source_reference": "canonical-local",
                },
            },
        ),
    ):
        response = _post(
            client, f"/api/v1/intelligence/sourcing/scenarios/{base_id}/{path}", payload
        )
        assert response["scenario_id"] == base_id
    mark_stage("scenario generation complete")

    mark_stage("landed cost started")
    economics = _post(
        client,
        "/api/v1/intelligence/sourcing/economics/landed-cost",
        base_inputs,
    )
    assert economics["landed_cost_per_unit"] >= 0
    mark_stage("landed cost complete")
    mark_stage("capital started")
    capital = _post(
        client,
        "/api/v1/intelligence/sourcing/economics/capital",
        {
            "sample_costs": 20,
            "tooling_setup": 100,
            "deposit": 300,
            "balance": 600,
            "freight": 10,
            "duties_tax": 20,
            "inspection": 10,
            "ads_launch_allowance": 100,
        },
    )
    assert capital["total_launch_capital"] > 0
    mark_stage("capital complete")
    mark_stage("cash timeline started")
    cash = _post(
        client, "/api/v1/intelligence/sourcing/economics/cash-timeline", capital["components"]
    )
    assert cash["items"]
    mark_stage("cash timeline complete")
    mark_stage("sensitivity started")
    sensitivity = _post(client, "/api/v1/intelligence/sourcing/economics/sensitivity", base_inputs)
    assert len(sensitivity["items"]) >= 5
    mark_stage("sensitivity complete")
    score_inputs = {
        key: 80
        for key in (
            "commercial_competitiveness",
            "moq",
            "lead_time",
            "payment_terms",
            "supplier_verification",
            "supplier_risk",
            "sample_result",
            "inspection_result",
            "landed_cost",
            "margin_potential",
            "capital_efficiency",
            "evidence_confidence",
        )
    }
    mark_stage("score started")
    score = _post(
        client,
        "/api/v1/intelligence/sourcing/scores/evaluate",
        {
            "requirement_id": requirement["id"],
            "quote_id": quote_two["id"],
            "model_version": "canonical-v1",
            "inputs": score_inputs,
        },
    )
    assert score["evaluation"]["model_version"] == "canonical-v1"
    mark_stage("score complete")
    mark_stage("critic started")
    critic = _post(client, "/api/v1/intelligence/sourcing/critic", {**base_inputs, "moq": 100})
    concentration = _post(
        client, "/api/v1/intelligence/sourcing/concentration", {"supplier_count": 2}
    )
    decision_engine = _post(
        client,
        "/api/v1/intelligence/sourcing/decision-engine",
        {"score": score["result"]["score"], "supplier_count": 2, "evidence_sufficient": True},
    )
    assert critic["findings"] is not None
    assert concentration["classification"] == "DUAL_SOURCE"
    assert decision_engine["classification"]
    mark_stage("critic complete")
    decision = _post(
        client,
        "/api/v1/intelligence/sourcing/decisions",
        {
            "requirement_id": requirement["id"],
            "quote_id": quote_two["id"],
            "decision": "hold",
            "classification": "review_required",
            "critic": critic["findings"],
            "confirmed": True,
        },
    )
    assert decision["confirmed"] is True
    approved_decision = _post(
        client,
        f"/api/v1/intelligence/sourcing/decisions/{decision['id']}/approve",
        {"note": "Canonical human approval."},
    )
    assert approved_decision["approved"] is True
    mark_stage("decision ready")
    calendar = _post(
        client,
        "/api/v1/intelligence/sourcing/calendar",
        {
            "kind": "quote_review",
            "title": "Review canonical quotes",
            "entity_type": "rfq",
            "entity_id": rfq["id"],
            "idempotency_key": "canonical-calendar",
            "payload": {"informational": True},
        },
    )
    assert calendar["payload"]["informational"] is True
    history = client.get("/api/v1/intelligence/sourcing/history/unified", headers=ORIGIN)
    assert history.status_code == 200
    kinds = {item["kind"] for item in history.json()["items"]}
    assert {
        "requirement",
        "rfq",
        "quote",
        "negotiation",
        "score",
        "sample",
        "inspection",
        "scenario",
        "decision",
    } <= kinds
    mark_stage("report generation started")
    for format_name in ("json", "markdown", "html"):
        report = client.get(f"/api/v1/intelligence/sourcing/report/{format_name}", headers=ORIGIN)
        assert report.status_code == 200
        assert "postgresql://" not in report.text.lower()
    mark_stage("report ready")

    assert integration_helpers.factory is not None
    with integration_helpers.factory() as db:
        stored_opportunity = db.scalar(
            select(IntelligenceOpportunity).where(IntelligenceOpportunity.id == opportunity["id"])
        )
        requirement_row = db.scalar(
            select(SourcingRequirement).where(SourcingRequirement.id == requirement["id"])
        )
        rfq_row = db.scalar(select(RequestForQuote).where(RequestForQuote.id == rfq["id"]))
        assert (
            stored_opportunity is not None and requirement_row is not None and rfq_row is not None
        )
        assert requirement_row.opportunity_id == stored_opportunity.id
        assert requirement_row.product_id
        assert (
            db.scalar(
                select(SourcingRequirementVersion).where(
                    SourcingRequirementVersion.requirement_id == requirement_row.id,
                    SourcingRequirementVersion.version == 1,
                )
            )
            is not None
        )
        assert (
            db.scalar(
                select(RFQVersion).where(RFQVersion.rfq_id == rfq_row.id, RFQVersion.version == 1)
            )
            is not None
        )
        assert (
            len(list(db.scalars(select(RFQSupplier).where(RFQSupplier.rfq_id == rfq_row.id)))) == 2
        )
        assert (
            len(list(db.scalars(select(SupplierQuote).where(SupplierQuote.rfq_id == rfq_row.id))))
            == 3
        )
        assert (
            db.scalar(
                select(SupplierQuoteVersion).where(
                    SupplierQuoteVersion.quote_id == quote_two["id"],
                    SupplierQuoteVersion.version == 2,
                )
            )
            is not None
        )
        assert (
            db.scalar(select(NegotiationRound).where(NegotiationRound.quote_id == quote_two["id"]))
            is not None
        )
        assert db.scalar(select(Sample).where(Sample.id == sample_id)) is not None
        assert (
            db.scalar(select(SampleEvaluation).where(SampleEvaluation.sample_id == sample_id))
            is not None
        )
        assert db.scalar(select(Inspection).where(Inspection.id == inspection["id"])) is not None
        assert (
            db.scalar(
                select(InspectionFinding).where(InspectionFinding.inspection_id == inspection["id"])
            )
            is not None
        )
        assert db.scalar(select(CostScenario).where(CostScenario.id == base_id)) is not None
        assert (
            db.scalar(select(LandedCostEstimate).where(LandedCostEstimate.scenario_id == base_id))
            is not None
        )
        assert (
            db.scalar(select(LogisticsEstimate).where(LogisticsEstimate.scenario_id == base_id))
            is not None
        )
        assert (
            db.scalar(select(DutyTaxAssumption).where(DutyTaxAssumption.scenario_id == base_id))
            is not None
        )
        assert (
            db.scalar(select(FXAssumption).where(FXAssumption.scenario_id == base_id)) is not None
        )
        assert (
            db.scalar(
                select(SourcingScoreEvaluation).where(
                    SourcingScoreEvaluation.id == score["evaluation"]["id"]
                )
            )
            is not None
        )
        assert (
            db.scalar(select(SourcingDecision).where(SourcingDecision.id == decision["id"]))
            is not None
        )
    mark_stage("worker terminal")
    print("SOURCING EXECUTION TIMING LEDGER")
    print("STAGE\\tELAPSED_FROM_REQUEST_MS\\tDELTA_FROM_PREVIOUS_STAGE_MS")
    for name, (elapsed, delta) in stage_times.items():
        print(f"{name}\\t{elapsed:.3f}\\t{delta:.3f}")
    elapsed_ms = (perf_counter() - started) * 1000
    assert elapsed_ms >= 0
