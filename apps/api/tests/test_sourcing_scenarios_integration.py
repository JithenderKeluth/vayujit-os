"""Disposable PostgreSQL proof for scenario lineage, replay, and independent transactions."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from threading import Barrier
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context
from test_sourcing_scenarios import inputs

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence import scenario_service as service
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_schemas import DueDiligenceContextCreate
from vayujit_api.intelligence.due_diligence_service import assess
from vayujit_api.intelligence.due_diligence_service import create_context as due_context
from vayujit_api.intelligence.scenario_generation import generate
from vayujit_api.intelligence.scenario_models import (
    InternalSourcingHandoff,
    ScenarioSupplierAllocation,
    SourcingScenario,
    SourcingScenarioContext,
    SourcingScenarioDecision,
    SourcingScenarioEvent,
    SourcingScenarioRecommendation,
    SourcingScenarioVersion,
)
from vayujit_api.intelligence.scenario_research import request_research
from vayujit_api.intelligence.scenario_schemas import (
    Command,
    ContextCreate,
    DecisionRequest,
    GenerateRequest,
    ScenarioCreate,
    VersionCommand,
)
from vayujit_api.intelligence.shortlisting_schemas import ShortlistContextCreate, ShortlistRequest
from vayujit_api.intelligence.shortlisting_service import create_context as shortlist_context
from vayujit_api.intelligence.shortlisting_service import generate_shortlist

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
BASE = "/api/v1/intelligence/sourcing-scenarios"


def factory() -> Any:
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory


def seed(client: Any) -> tuple[uuid.UUID, dict, dict]:
    product = setup_context(client)["product"]
    with factory()() as db:
        owner = db.scalar(select(User))
        stamp = datetime.now(UTC)
        supplier = CrossMarketplaceSupplier(
            owner_id=owner.id,
            canonical_key=str(uuid.uuid4()),
            display_name="Disposable scenario supplier",
            identity_state="MATCH",
            freshness_status="fresh",
            confidence_score=90,
            source_diversity_score=3,
            view_json={
                "capabilities": ["assembly"],
                "certifications": ["fixture certification"],
                "facilities": ["fixture facility"],
                "risk": "low",
                "risk_score": 10,
                "manufacturer_id": "fixture-manufacturer",
                "country_code": "IN",
            },
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(supplier)
        db.commit()
        shortlist, _ = shortlist_context(
            db,
            owner,
            ShortlistContextCreate(
                product_id=product["id"],
                budget_currency="INR",
                idempotency_key="scenario-shortlist",
            ),
        )
        version = generate_shortlist(
            db, owner, shortlist, ShortlistRequest(idempotency_key="scenario-shortlist-version")
        )
        diligence, _ = due_context(
            db,
            owner,
            DueDiligenceContextCreate(
                supplier_id=supplier.id,
                product_id=product["id"],
                shortlist_context_id=shortlist.id,
                shortlist_version_id=uuid.UUID(str(version["id"])),
                idempotency_key="scenario-diligence",
            ),
        )
        assess(db, owner, diligence)
        settings, request, _ = inputs()
        settings["shortlist_version_id"] = str(version["id"])
        request["allocations"][0]["supplier_id"] = str(supplier.id)
        request["allocations"][0]["due_diligence_id"] = str(diligence.id)
        request["allocations"][0]["unit_price"] = "10"
        return owner.id, settings, request


def seed_three(client: Any) -> tuple[dict, dict]:
    product = setup_context(client)["product"]
    with factory()() as db:
        owner = db.scalar(select(User))
        stamp = datetime.now(UTC)
        supplier_specs = [
            ("A", "IN", 60, "8", 20),
            ("B", "IN", 5, "13", 3),
            ("C", "VN", 15, "10", 8),
        ]
        suppliers = []
        for label, country, risk, _, _ in supplier_specs:
            supplier = CrossMarketplaceSupplier(
                owner_id=owner.id,
                canonical_key=str(uuid.uuid4()),
                display_name=f"Disposable scenario supplier {label}",
                identity_state="MATCH",
                freshness_status="fresh",
                confidence_score=90,
                source_diversity_score=3,
                view_json={
                    "capabilities": ["assembly"],
                    "certifications": ["fixture certification"],
                    "facilities": ["fixture facility"],
                    "risk": "medium",
                    "risk_score": risk,
                    "manufacturer_id": f"fixture-manufacturer-{label}",
                    "country_code": country,
                },
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(supplier)
            suppliers.append(supplier)
        db.commit()
        shortlist, _ = shortlist_context(
            db,
            owner,
            ShortlistContextCreate(
                product_id=product["id"],
                budget_currency="INR",
                idempotency_key="scenario-three-shortlist",
            ),
        )
        version = generate_shortlist(
            db,
            owner,
            shortlist,
            ShortlistRequest(idempotency_key="scenario-three-shortlist-version"),
        )
        settings, request, _ = inputs()
        settings["shortlist_version_id"] = str(version["id"])
        request["idempotency_key"] = "three-supplier-basis"
        request["allocations"] = []
        for (label, _, _, price, lead), supplier, quantity in zip(
            supplier_specs, suppliers, (40, 30, 30), strict=True
        ):
            diligence, _ = due_context(
                db,
                owner,
                DueDiligenceContextCreate(
                    supplier_id=supplier.id,
                    product_id=product["id"],
                    shortlist_context_id=shortlist.id,
                    shortlist_version_id=uuid.UUID(str(version["id"])),
                    idempotency_key=f"scenario-three-diligence-{label}",
                ),
            )
            assess(db, owner, diligence)
            request["allocations"].append(
                {
                    **inputs()[1]["allocations"][0],
                    "supplier_id": str(supplier.id),
                    "due_diligence_id": str(diligence.id),
                    "quantity": quantity,
                    "unit_price": price,
                    "lead_time_days": lead,
                }
            )
        return settings, request


def ledger() -> dict[str, int]:
    with factory()() as db:
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model)) or 0
            for model in (
                SourcingScenarioContext,
                SourcingScenario,
                SourcingScenarioVersion,
                ScenarioSupplierAllocation,
                SourcingScenarioRecommendation,
                SourcingScenarioDecision,
                SourcingScenarioEvent,
                InternalSourcingHandoff,
            )
        }


def test_scenario_real_api_replay_lineage_and_stale_guard(client: Any) -> None:
    owner_id, settings, request = seed(client)
    created = client.post(f"{BASE}/contexts", json=settings, headers=ORIGIN)
    assert created.status_code == 201, created.text
    context_id = created.json()["id"]
    response = client.post(f"{BASE}/contexts/{context_id}/scenarios", json=request, headers=ORIGIN)
    assert response.status_code == 201, response.text
    scenario_id = response.json()["id"]
    with factory()() as db:
        context_product_id = db.get(SourcingScenarioContext, uuid.UUID(context_id)).product_id
    product_channel = client.get(
        f"/api/v1/intelligence/sourcing/product-channel/{context_product_id}"
    )
    assert product_channel.status_code == 200, product_channel.text
    assert product_channel.json()["sourcing_scenarios"]["scenario_count"] == 1
    assert product_channel.json()["sourcing_scenarios"]["external_dispatch"] is False
    operations = client.get(f"{BASE}/operations")
    assert operations.status_code == 200, operations.text
    assert operations.json()["scenario_count"] == 1
    doctor = client.get(f"{BASE}/system-doctor")
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS"
    assert all(value == 0 for value in doctor.json()["integrity"].values())
    calendar = client.get(f"{BASE}/calendar")
    assert calendar.status_code == 200, calendar.text
    assert all(item["external_action"] is False for item in calendar.json())
    assert response.json()["result"]["cost"]["total_landed_cost"] == "1000.000000"
    before = ledger()
    repeated = client.post(f"{BASE}/contexts/{context_id}/scenarios", json=request, headers=ORIGIN)
    assert repeated.json()["idempotent_reuse"] is True
    assert before == ledger()
    changed = {**request, "name": "Changed request"}
    assert (
        client.post(
            f"{BASE}/contexts/{context_id}/scenarios", json=changed, headers=ORIGIN
        ).status_code
        == 409
    )
    assert before == ledger()
    approve = {
        "idempotency_key": "approval-fixture",
        "expected_version": 1,
        "reason": "Human fixture review",
        "action": "approve",
        "confirm": True,
    }
    assert (
        client.post(
            f"{BASE}/scenarios/{scenario_id}/decisions", json=approve, headers=ORIGIN
        ).status_code
        == 200
    )
    handoff = {
        "idempotency_key": "handoff-fixture",
        "expected_version": 1,
        "reason": "Internal only",
    }
    sent = client.post(f"{BASE}/scenarios/{scenario_id}/handoffs", json=handoff, headers=ORIGIN)
    assert sent.status_code == 200, sent.text
    assert sent.json()["external_dispatch"] is False
    before = ledger()
    assert client.post(
        f"{BASE}/scenarios/{scenario_id}/handoffs", json=handoff, headers=ORIGIN
    ).json()["idempotent_reuse"]
    assert before == ledger()
    with factory()() as db:
        supplier = db.get(
            CrossMarketplaceSupplier, uuid.UUID(request["allocations"][0]["supplier_id"])
        )
        supplier.view_json = {**supplier.view_json, "risk_score": 30}
        supplier.updated_at = datetime.now(UTC)
        db.commit()
    stale = client.get(f"{BASE}/scenarios/{scenario_id}")
    assert stale.json()["freshness"] == "RECALCULATION_REQUIRED"
    approve["idempotency_key"] = "new-approval-fixture"
    assert (
        client.post(
            f"{BASE}/scenarios/{scenario_id}/decisions", json=approve, headers=ORIGIN
        ).status_code
        == 409
    )
    recovery_body = {
        "confirm": True,
        "scenario_id": scenario_id,
        "expected_version": 1,
        "reason": "Recalculate stale fixture scenario",
        "idempotency_key": "recovery-stale-fixture",
    }
    recovery_url = "/api/v1/operations/recovery/actions?action=RECALCULATE_STALE_SCENARIO"
    recovered = client.post(recovery_url, json=recovery_body, headers=ORIGIN)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["version"] == 2
    with factory()() as db:
        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "operations.sourcing_scenario_recovery")
        )
    repeated_recovery = client.post(recovery_url, json=recovery_body, headers=ORIGIN)
    assert repeated_recovery.status_code == 200, repeated_recovery.text
    assert repeated_recovery.json()["idempotent_reuse"] is True
    with factory()() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "operations.sourcing_scenario_recovery")
            )
            == audit_count
        )
    unsupported = client.post(
        "/api/v1/operations/recovery/actions?action=REPAIR_SCENARIO_PROJECTION",
        json=recovery_body,
        headers=ORIGIN,
    )
    assert unsupported.status_code == 409
    assert client.get(f"{BASE}/contexts/{uuid.uuid4()}").status_code == 404
    assert (
        client.post(
            f"{BASE}/contexts",
            json={**settings, "idempotency_key": "bad-origin-test"},
            headers={"Origin": "https://example.invalid"},
        ).status_code
        == 403
    )
    assert owner_id


def test_three_rounds_seven_independent_transaction_races(client: Any) -> None:
    owner_id, settings, request = seed(client)

    def race(operation: Any) -> dict:
        barrier = Barrier(2)

        def invoke() -> dict:
            with factory()() as db:
                owner = db.get(User, owner_id)
                barrier.wait(timeout=15)
                return operation(db, owner)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke), pool.submit(invoke)]
            values = [f.result(timeout=60) for f in futures]
        assert values[0] | {"idempotent_reuse": True} == values[1] | {"idempotent_reuse": True}
        assert sum(bool(v["idempotent_reuse"]) for v in values) == 1
        return values[0]

    def run_round(round_number: int) -> None:
        setting = {**settings, "idempotency_key": f"context-round-{round_number}"}
        context = race(
            lambda db, owner: service.create_context(
                db, owner, ContextCreate.model_validate(setting)
            )
        )
        context_id = uuid.UUID(context["id"])
        basis = deepcopy(request)
        basis["idempotency_key"] = f"scenario-round-{round_number}"
        generation = GenerateRequest(
            idempotency_key=f"generation-round-{round_number}",
            basis=ScenarioCreate.model_validate(basis),
        )
        scenario = race(lambda db, owner: generate(db, owner, context_id, generation))
        scenario_id = uuid.UUID(scenario["generated"][0]["id"])
        version_command = VersionCommand(
            expected_version=1,
            reason="Local race",
            idempotency_key=f"recalc-round-{round_number}",
        )
        race(lambda db, owner: service.recalculate(db, owner, scenario_id, version_command))
        recommendation = Command(idempotency_key=f"recommend-round-{round_number}")
        race(lambda db, owner: service.recommend(db, owner, context_id, recommendation))
        decision = DecisionRequest(
            expected_version=2,
            reason="Human fixture approval",
            action="approve",
            confirm=True,
            idempotency_key=f"approve-round-{round_number}",
        )
        race(lambda db, owner: service.decide(db, owner, scenario_id, decision))
        research = VersionCommand(
            expected_version=2,
            reason="Research fixture",
            idempotency_key=f"research-round-{round_number}",
        )
        race(lambda db, owner: request_research(db, owner, scenario_id, research))
        handoff = VersionCommand(
            expected_version=2,
            reason="Internal fixture",
            idempotency_key=f"handoff-round-{round_number}",
        )
        race(lambda db, owner: service.handoff(db, owner, scenario_id, handoff))

    for round_number in range(3):
        run_round(round_number)
    counts = ledger()
    assert counts["intelligence_scenario_contexts"] == 3
    assert counts["intelligence_scenarios"] == 3
    assert counts["intelligence_scenario_versions"] == 6
    assert counts["intelligence_scenario_handoffs"] == 3


def test_generation_is_evidence_gated_and_replay_safe(client: Any) -> None:
    owner_id, settings, request = seed(client)
    with factory()() as db:
        owner = db.get(User, owner_id)
        context = service.create_context(db, owner, ContextCreate.model_validate(settings))
        command = GenerateRequest(
            idempotency_key="generation-fixture",
            basis=ScenarioCreate.model_validate(request),
        )
        result = generate(db, owner, uuid.UUID(context["id"]), command)
        assert len(result["generated"]) == 1
        assert "LOWEST_COST" in result["generated"][0]["labels"]
        assert result["external_dispatch"] is False
        before = ledger()
        replayed = generate(db, owner, uuid.UUID(context["id"]), command)
        assert replayed["idempotent_reuse"] is True
        assert before == ledger()


def test_three_supplier_generation_real_api_e2e(client: Any) -> None:
    settings, request = seed_three(client)
    context = client.post(f"{BASE}/contexts", json=settings, headers=ORIGIN)
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    body = {"idempotency_key": "three-supplier-generation", "basis": request}
    response = client.post(f"{BASE}/contexts/{context_id}/generate", json=body, headers=ORIGIN)
    assert response.status_code == 201, response.text
    generated = response.json()["generated"]
    assert len(generated) == 4
    labels = {label for item in generated for label in item["labels"]}
    assert {
        "LOWEST_COST",
        "LOWEST_CAPITAL",
        "FASTEST_SUPPLY",
        "LOWEST_RISK",
        "MAXIMUM_RESILIENCE",
        "BALANCED",
    } <= labels
    selected = next(
        item
        for item in generated
        if item["version_id"] == response.json()["recommended_version_id"]
    )
    assert selected["result"]["missing_dimensions"] == []
    before = ledger()
    repeated = client.post(f"{BASE}/contexts/{context_id}/generate", json=body, headers=ORIGIN)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["idempotent_reuse"] is True
    assert before == ledger()
    compare_response = client.get(f"{BASE}/contexts/{context_id}/comparison")
    assert compare_response.status_code == 200
    assert len(compare_response.json()["scenarios"]) == 4
    sensitivity = client.post(
        f"{BASE}/scenarios/{selected['id']}/sensitivity",
        json={
            "idempotency_key": "three-supplier-sensitivity",
            "expected_version": 1,
            "reason": "Check cost sensitivity",
            "dimension": "purchase",
            "change_percent": "10",
        },
        headers=ORIGIN,
    )
    assert sensitivity.status_code == 200, sensitivity.text
    approval = client.post(
        f"{BASE}/scenarios/{selected['id']}/decisions",
        json={
            "idempotency_key": "three-supplier-approval",
            "expected_version": 1,
            "reason": "Human-reviewed internal sourcing choice",
            "action": "approve",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert approval.status_code == 200, approval.text
    handoff = client.post(
        f"{BASE}/scenarios/{selected['id']}/handoffs",
        json={
            "idempotency_key": "three-supplier-handoff",
            "expected_version": 1,
            "reason": "Internal planning only",
        },
        headers=ORIGIN,
    )
    assert handoff.status_code == 200, handoff.text
    assert handoff.json()["external_dispatch"] is False
    doctor = client.get(f"{BASE}/system-doctor")
    assert doctor.status_code == 200
    assert all(value == 0 for value in doctor.json()["integrity"].values())


def test_owner_boundary_rejects_foreign_scenario_reads_and_mutations(client: Any) -> None:
    owner_b_id, settings, request = seed(client)
    context = client.post(f"{BASE}/contexts", json=settings, headers=ORIGIN)
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    created = client.post(f"{BASE}/contexts/{context_id}/scenarios", json=request, headers=ORIGIN)
    assert created.status_code == 201, created.text
    scenario_id = created.json()["id"]
    version_id = created.json()["version_id"]
    before = ledger()
    owner_a = User(id=uuid.uuid4())
    assert owner_a.id != owner_b_id
    client.app.dependency_overrides[current_user] = lambda: owner_a
    try:
        reads = [
            f"{BASE}/contexts/{context_id}",
            f"{BASE}/contexts/{context_id}/comparison",
            f"{BASE}/contexts/{context_id}/history",
            f"{BASE}/contexts/{context_id}/report",
            f"{BASE}/scenarios/{scenario_id}",
            f"{BASE}/scenarios/{scenario_id}/versions",
            f"{BASE}/versions/{version_id}",
        ]
        assert all(client.get(path, headers=ORIGIN).status_code == 404 for path in reads)
        assert client.get(f"{BASE}/contexts", headers=ORIGIN).json() == []
        assert client.get(f"{BASE}/calendar", headers=ORIGIN).json() == []
        assert client.get(f"{BASE}/operations", headers=ORIGIN).json()["scenario_count"] == 0
        command = {
            "idempotency_key": "foreign-owner-command",
            "expected_version": 1,
            "reason": "Cross-owner request must be rejected",
        }
        mutations = [
            (f"{BASE}/scenarios/{scenario_id}/recalculate", command),
            (
                f"{BASE}/scenarios/{scenario_id}/decisions",
                {**command, "action": "approve", "confirm": True},
            ),
            (
                f"{BASE}/scenarios/{scenario_id}/decisions",
                {**command, "action": "reject", "confirm": True},
            ),
            (
                f"{BASE}/scenarios/{scenario_id}/decisions",
                {**command, "action": "archive", "confirm": True},
            ),
            (f"{BASE}/scenarios/{scenario_id}/research", command),
            (f"{BASE}/scenarios/{scenario_id}/handoffs", command),
            (f"{BASE}/contexts/{context_id}/scenarios", request),
            (
                f"{BASE}/contexts/{context_id}/generate",
                {"idempotency_key": "foreign-generation", "basis": request},
            ),
        ]
        for path, body in mutations:
            response = client.post(path, json=body, headers=ORIGIN)
            assert response.status_code == 404, (path, response.text)
            assert "Sourcing reference not found." in response.text
        foreign_context = client.post(
            f"{BASE}/contexts",
            json={**settings, "idempotency_key": "foreign-shortlist"},
            headers=ORIGIN,
        )
        assert foreign_context.status_code == 404, foreign_context.text
        assert client.get(f"{BASE}/contexts/{uuid.uuid4()}", headers=ORIGIN).status_code == 404
    finally:
        client.app.dependency_overrides.pop(current_user, None)
    assert ledger() == before
