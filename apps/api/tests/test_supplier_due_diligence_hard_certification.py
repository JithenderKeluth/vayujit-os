from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

import pytest
from helpers.due_diligence_owners import OWNER_B, create_test_owner
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence import due_diligence_service
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceAssessment,
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
    SupplierResearchPlan,
    SupplierResearchTask,
)
from vayujit_api.intelligence.due_diligence_schemas import (
    DueDiligenceContextCreate,
    ResearchPlanCreate,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _db() -> Session:
    import test_ai_integration

    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def _seed_context(client: Any, suffix: str, *, product_id: str | None = None) -> dict[str, Any]:
    if product_id is None:
        brand = client.post("/api/v1/brands", json={"name": f"Due Brand {suffix}"}, headers=ORIGIN)
        assert brand.status_code == 201, brand.text
        product = client.post(
            "/api/v1/products",
            json={
                "name": f"Due Product {suffix}",
                "product_type": "physical",
                "short_description": "Disposable due-diligence fixture product",
                "description": "Used only for deterministic certification.",
                "category": "Test",
                "tags": ["fixture"],
                "price_amount": "10.00",
                "price_currency": "USD",
            },
            headers=ORIGIN,
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
    supplier = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": f"Due Supplier {suffix}",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "local due-diligence certification fixture",
        },
        headers=ORIGIN,
    )
    assert supplier.status_code == 201, supplier.text
    reconciled = client.post(
        "/api/v1/intelligence/cross-marketplace/suppliers/reconcile",
        json={"supplier_ids": [supplier.json()["id"]]},
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200, reconciled.text
    supplier_id = reconciled.json()[0]["id"]
    context = client.post(
        "/api/v1/intelligence/supplier-due-diligence/contexts",
        json={
            "supplier_id": supplier_id,
            "product_id": product_id,
            "idempotency_key": f"hard-cert-context-{suffix}",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 200, context.text
    context_id = context.json()["id"]
    assessed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/assess",
        headers=ORIGIN,
    )
    assert assessed.status_code == 200, assessed.text
    gaps = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/gaps",
        headers=ORIGIN,
    )
    assert gaps.status_code == 200, gaps.text
    return {
        "product_id": product_id,
        "supplier_id": supplier_id,
        "context_id": context_id,
        "gaps": gaps.json(),
    }


def _plan(client: Any, context_id: str, suffix: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        json={"idempotency_key": f"hard-cert-plan-{suffix}", "max_tasks": 3},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _owner(client: Any) -> User:
    context = setup_context(client)
    del context
    with _db() as db:
        value = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert value is not None
        return value


def _foreign_override(client: Any, owner: User) -> None:
    client.app.dependency_overrides[current_user] = lambda: owner


def _clear_override(client: Any) -> None:
    client.app.dependency_overrides.pop(current_user, None)


def _run_two_postgres_sessions(operation: Any) -> list[Any]:
    # Two independent PostgreSQL sessions synchronize before the operation.
    import test_ai_integration

    factory = test_ai_integration.factory
    assert factory is not None
    barrier = threading.Barrier(2)

    def worker(index: int) -> Any:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            barrier.wait(timeout=15)
            try:
                return operation(db, owner, index)
            except Exception as exc:
                db.rollback()
                return {"exception": str(type(exc).__name__) + ": " + str(exc)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(worker, (0, 1)))


def _create_context_concurrently(
    db: Session, owner: User, _worker: int, *, payload: DueDiligenceContextCreate
) -> Any:
    return due_diligence_service.create_context(db, owner, payload)


def _create_plan_concurrently(
    db: Session,
    owner: User,
    _worker: int,
    *,
    context_id: uuid.UUID,
    payload: ResearchPlanCreate,
) -> Any:
    context = db.get(SupplierDueDiligenceContext, context_id)
    assert context is not None
    return due_diligence_service.create_plan(db, owner, context, payload)


def test_two_owner_read_mutation_and_cross_owner_persistence_isolation(client: Any) -> None:
    owner_a = _owner(client)
    first = _seed_context(client, "owner-a")
    with _db() as db:
        owner_b = create_test_owner(db, owner_id=OWNER_B, email="due-diligence-owner-b@example.com")
    _foreign_override(client, owner_b)
    second = _seed_context(client, "owner-b")
    plan_b = _plan(client, second["context_id"], "owner-b")
    with _db() as db:
        mission_b = db.scalar(
            select(AutonomousResearchMission).where(
                AutonomousResearchMission.owner_id == owner_b.id,
                AutonomousResearchMission.scope["plan_id"].as_string() == plan_b["id"],
            )
        )
        assert mission_b is not None
        before = {
            "contexts": db.scalar(
                select(func.count())
                .select_from(SupplierDueDiligenceContext)
                .where(SupplierDueDiligenceContext.owner_id == owner_b.id)
            ),
            "plans": db.scalar(
                select(func.count())
                .select_from(SupplierResearchPlan)
                .where(SupplierResearchPlan.owner_id == owner_b.id)
            ),
            "tasks": db.scalar(
                select(func.count())
                .select_from(SupplierResearchTask)
                .where(SupplierResearchTask.owner_id == owner_b.id)
            ),
        }
    _clear_override(client)
    # Every foreign read is a safe 404 (or an empty owner-scoped projection).
    for path in (
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/gaps",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/history",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/report",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/sourcing-guard",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/plans",
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan_b['id']}/tasks",
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan_b['id']}/run",
        f"/api/v1/intelligence/autonomous/missions/{mission_b.id}",
        f"/api/v1/intelligence/autonomous/missions/{mission_b.id}/resume",
    ):
        response = client.get(path, headers=ORIGIN)
        if path.endswith("/run") or path.endswith("/resume"):
            response = client.post(path, json={}, headers=ORIGIN)
        assert response.status_code == 404, (path, response.text)
    gap_b = second["gaps"][0]["id"]
    for action in (
        "start_research",
        "research_selected_gaps",
        "request_more_research",
        "cancel_research",
        "waive_gap",
        "reopen_gap",
        "mark_for_human_review",
    ):
        response = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/gaps/{gap_b}/{action}",
            json={"reason": "foreign owner attempt", "selected_gap_ids": [gap_b]},
            headers=ORIGIN,
        )
        assert response.status_code == 404, (action, response.text)
    recovery = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/recovery",
        json={
            "failure_code": "source_unavailable",
            "action": "retry",
            "idempotency_key": "foreign",
        },
        headers=ORIGIN,
    )
    assert recovery.status_code == 404
    channel = client.get(
        f"/api/v1/intelligence/supplier-shortlisting/product-channel/{second['product_id']}",
        headers=ORIGIN,
    )
    assert channel.status_code in {200, 404}
    assert second["context_id"] not in channel.text and second["supplier_id"] not in channel.text
    calendar = client.get("/api/v1/intelligence/supplier-shortlisting/calendar", headers=ORIGIN)
    assert calendar.status_code == 200 and second["context_id"] not in calendar.text
    invalid_context = client.post(
        "/api/v1/intelligence/supplier-due-diligence/contexts",
        json={
            "supplier_id": second["supplier_id"],
            "product_id": second["product_id"],
            "idempotency_key": "foreign-context-write",
        },
        headers=ORIGIN,
    )
    assert invalid_context.status_code == 404
    invalid_plan = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{second['context_id']}/plans",
        json={"idempotency_key": "foreign-plan-write"},
        headers=ORIGIN,
    )
    assert invalid_plan.status_code == 404
    with _db() as db:
        after = {
            "contexts": db.scalar(
                select(func.count())
                .select_from(SupplierDueDiligenceContext)
                .where(SupplierDueDiligenceContext.owner_id == owner_b.id)
            ),
            "plans": db.scalar(
                select(func.count())
                .select_from(SupplierResearchPlan)
                .where(SupplierResearchPlan.owner_id == owner_b.id)
            ),
            "tasks": db.scalar(
                select(func.count())
                .select_from(SupplierResearchTask)
                .where(SupplierResearchTask.owner_id == owner_b.id)
            ),
        }
    assert after == before
    assert owner_a.id != owner_b.id
    assert first["context_id"] != second["context_id"]


def test_repeatability_and_replay_have_stable_logical_output(client: Any) -> None:
    _owner(client)
    runs: list[tuple[Any, ...]] = []
    for index in range(3):
        seeded = _seed_context(client, f"repeat-{index}")
        plan = _plan(client, seeded["context_id"], f"repeat-{index}")
        replay = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/contexts/{seeded['context_id']}/plans",
            json={"idempotency_key": f"hard-cert-plan-repeat-{index}", "max_tasks": 3},
            headers=ORIGIN,
        )
        assert replay.status_code == 200 and replay.json()["reused"] is True
        runs.append(
            (
                tuple(
                    sorted(
                        (gap["dimension"], gap["classification"], gap["status"], gap["severity"])
                        for gap in seeded["gaps"]
                    )
                ),
                plan["status"],
                tuple(plan["prohibited_methods"]),
            )
        )
    assert runs[0] == runs[1] == runs[2]


def test_crash_checkpoints_recover_without_duplicate_evidence(client: Any) -> None:
    _owner(client)
    evidence_counts: list[int] = []
    for index, stage in enumerate(("before_source", "after_evidence")):
        seeded = _seed_context(client, f"crash-{index}")
        plan = _plan(client, seeded["context_id"], f"crash-{index}")
        with _db() as db:
            mission = db.scalar(
                select(AutonomousResearchMission).where(
                    AutonomousResearchMission.scope["plan_id"].as_string() == plan["id"]
                )
            )
            assert mission is not None
            mission_id = str(mission.id)
        crashed = client.post(
            f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
            json={"confirm": True, "crash_stage": stage},
            headers=ORIGIN,
        )
        assert crashed.status_code == 200, crashed.text
        recovered = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/plans/{plan['id']}/run",
            headers=ORIGIN,
        )
        assert recovered.status_code == 200, recovered.text
        with _db() as db:
            evidence = list(
                db.scalars(
                    select(AutonomousResearchEvidence).where(
                        AutonomousResearchEvidence.mission_id == uuid.UUID(mission_id)
                    )
                )
            )
            assert evidence
            assert len({item.retrieval_identity for item in evidence}) == len(evidence)
            evidence_counts.append(len(evidence))
    assert all(value > 0 for value in evidence_counts)


def test_storage_integrity_lineage_privacy_and_xss_are_safe(client: Any) -> None:
    _owner(client)
    seeded = _seed_context(client, "privacy")
    with _db() as db:
        gap = db.scalar(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.context_id == uuid.UUID(seeded["context_id"])
            )
        )
        assert gap is not None
        gap.reason = "<script>alert('xss')</script>"
        db.commit()
    for format_name in ("json", "markdown", "html"):
        response = client.get(
            f"/api/v1/intelligence/supplier-due-diligence/contexts/{seeded['context_id']}/report?format={format_name}",
            headers=ORIGIN,
        )
        assert response.status_code == 200
        body = response.text.casefold()
        assert "database_url" not in body
        assert "authorization" not in body
        assert "bearer " not in body
        assert "traceback" not in body
        if format_name == "html":
            assert "&lt;script&gt;" in body and "<script>" not in body
    integrity = client.get("/api/v1/intelligence/supplier-due-diligence/integrity", headers=ORIGIN)
    assert integrity.status_code == 200
    assert all(value == 0 for value in integrity.json().values())
    assert (
        client.get(
            f"/api/v1/intelligence/supplier-due-diligence/contexts/{uuid.uuid4()}", headers=ORIGIN
        ).status_code
        == 404
    )
    malformed = client.get(
        "/api/v1/intelligence/supplier-due-diligence/contexts/not-a-uuid", headers=ORIGIN
    )
    assert malformed.status_code == 422


def test_context_and_operations_queries_are_bounded(client: Any) -> None:
    _owner(client)
    for index in range(3):
        _seed_context(client, f"perf-{index}")
    import test_ai_integration

    assert test_ai_integration.factory is not None
    engine = test_ai_integration.factory.kw["bind"]
    statements: list[str] = []

    def count_queries(*_: Any) -> None:
        statements.append("query")

    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        contexts = client.get(
            "/api/v1/intelligence/supplier-due-diligence/contexts", headers=ORIGIN
        )
        assert contexts.status_code == 200
        for context in contexts.json():
            detail = client.get(
                f"/api/v1/intelligence/supplier-due-diligence/contexts/{context['id']}",
                headers=ORIGIN,
            )
            assert detail.status_code == 200
        operations = client.get(
            "/api/v1/intelligence/supplier-due-diligence/operations", headers=ORIGIN
        )
        assert operations.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)
    assert len(statements) < 250


def test_storage_ledger_replay_has_no_current_state_duplication(client: Any) -> None:
    _owner(client)
    seeded = _seed_context(client, "ledger")
    plan = _plan(client, seeded["context_id"], "ledger")
    run = client.post(
        "/api/v1/intelligence/supplier-due-diligence/plans/" + plan["id"] + "/run",
        headers=ORIGIN,
    )
    assert run.status_code == 200, run.text

    def counts() -> dict[str, int]:
        with _db() as db:
            return {
                "contexts": int(
                    db.scalar(select(func.count()).select_from(SupplierDueDiligenceContext)) or 0
                ),
                "assessments": int(
                    db.scalar(select(func.count()).select_from(SupplierDueDiligenceAssessment)) or 0
                ),
                "gaps": int(db.scalar(select(func.count()).select_from(SupplierEvidenceGap)) or 0),
                "plans": int(
                    db.scalar(select(func.count()).select_from(SupplierResearchPlan)) or 0
                ),
                "tasks": int(
                    db.scalar(select(func.count()).select_from(SupplierResearchTask)) or 0
                ),
                "missions": int(
                    db.scalar(select(func.count()).select_from(AutonomousResearchMission)) or 0
                ),
                "research_tasks": int(
                    db.scalar(select(func.count()).select_from(AutonomousResearchTask)) or 0
                ),
                "evidence": int(
                    db.scalar(select(func.count()).select_from(AutonomousResearchEvidence)) or 0
                ),
            }

    first = counts()
    replay = client.post(
        "/api/v1/intelligence/supplier-due-diligence/plans/" + plan["id"] + "/run",
        headers=ORIGIN,
    )
    assert replay.status_code == 200, replay.text
    assert counts() == first


def test_true_postgresql_context_and_plan_concurrency_is_idempotent(client: Any) -> None:
    """Certify the two implemented advisory-lock boundaries with real sessions."""
    _owner(client)
    for index in range(3):
        seeded = _seed_context(client, f"postgres-concurrency-{index}")
        context_payload = DueDiligenceContextCreate(
            supplier_id=uuid.UUID(seeded["supplier_id"]),
            product_id=uuid.UUID(seeded["product_id"]),
            idempotency_key=f"concurrent-context-{index}-{uuid.uuid4()}",
        )
        context_results = _run_two_postgres_sessions(
            partial(_create_context_concurrently, payload=context_payload)
        )
        assert all("exception" not in value for value in context_results)
        contexts = [value[0] for value in context_results]
        assert contexts[0].id == contexts[1].id
        with _db() as db:
            context = db.get(SupplierDueDiligenceContext, contexts[0].id)
            assert context is not None
            owner = db.get(User, context.owner_id)
            assert owner is not None
            due_diligence_service.assess(db, owner, context)
            context_id = context.id
        plan_payload = ResearchPlanCreate(
            idempotency_key=f"concurrent-plan-{index}-{uuid.uuid4()}", max_tasks=3
        )
        plan_results = _run_two_postgres_sessions(
            partial(
                _create_plan_concurrently,
                context_id=context_id,
                payload=plan_payload,
            )
        )
        assert all("exception" not in value for value in plan_results)
        assert plan_results[0][0]["id"] == plan_results[1][0]["id"]
        with _db() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(SupplierResearchPlan)
                    .where(SupplierResearchPlan.context_id == context_id)
                )
                == 1
            )
