import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
import test_ai_integration
from sqlalchemy import UniqueConstraint, event, func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.core.database import Base
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import (
    IntelligenceEvidence,
    IntelligenceOpportunity,
    IntelligenceRecoveryRecord,
    IntelligenceResearchCandidate,
    IntelligenceResearchCheckpoint,
    IntelligenceResearchMission,
    IntelligenceResearchProject,
    IntelligenceResearchRun,
    IntelligenceResearchSignal,
    IntelligenceRule,
    IntelligenceRuleCategory,
    IntelligenceRuleEvaluation,
    IntelligenceScoreEvaluation,
)
from vayujit_api.intelligence.research_engine import execute_research_run
from vayujit_api.intelligence.service import now

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def _db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def _create_mission(client) -> str:
    project = client.post(
        "/api/v1/intelligence/projects",
        json={"name": "Concurrency Project", "description": "local", "target_market": "IN"},
        headers=ORIGIN,
    )
    assert project.status_code == 201, project.text
    mission = client.post(
        "/api/v1/intelligence/missions",
        json={
            "project_id": project.json()["id"],
            "name": "Concurrent Mission",
            "market": "IN",
            "minimum_score_threshold": 45,
        },
        headers=ORIGIN,
    )
    assert mission.status_code == 201, mission.text
    return mission.json()["id"]


def _run(client, mission_id: str, key: str):
    return client.post(
        f"/api/v1/intelligence/missions/{mission_id}/run-now",
        params={"idempotency_key": key},
        headers=ORIGIN,
    )


def _count(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _all_intelligence_counts(db):
    return {
        name: int(db.scalar(select(func.count()).select_from(table)) or 0)
        for name, table in Base.metadata.tables.items()
        if name.startswith("intelligence_")
    }


def _runtime_integrity_matrix(db) -> dict[str, int]:
    tables = {
        name: table
        for name, table in Base.metadata.tables.items()
        if name.startswith("intelligence_")
    }
    counters: dict[str, int] = {}
    for table_name, table in tables.items():
        for constraint in table.constraints:
            if not isinstance(constraint, UniqueConstraint):
                continue
            columns = list(constraint.columns)
            grouped = (
                select(*columns)
                .where(*(column.is_not(None) for column in columns))
                .group_by(*columns)
                .having(func.count() > 1)
                .subquery()
            )
            counters[f"duplicate:{table_name}:{constraint.name}"] = int(
                db.scalar(select(func.count()).select_from(grouped)) or 0
            )
        for foreign_key in table.foreign_keys:
            local_column = foreign_key.parent
            target_column = foreign_key.column
            target = target_column.table
            parent_exists = (
                select(1).select_from(target).where(target_column == local_column).exists()
            )
            counters[f"orphan:{table_name}:{local_column.name}"] = int(
                db.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(local_column.is_not(None), ~parent_exists)
                )
                or 0
            )
            if "owner_id" in table.c and "owner_id" in target.c:
                parent = target.alias(f"{target.name}_owner_integrity")
                owner_match = (
                    select(1)
                    .select_from(parent)
                    .where(
                        parent.c[target_column.name] == local_column,
                        parent.c.owner_id == table.c.owner_id,
                    )
                    .exists()
                )
                counters[f"cross_owner:{table_name}:{local_column.name}"] = int(
                    db.scalar(
                        select(func.count())
                        .select_from(table)
                        .where(local_column.is_not(None), ~owner_match)
                    )
                    or 0
                )
    return counters


def test_full_runtime_integrity_matrix_is_zero(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    run = _run(client, mission_id, "runtime-integrity")
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]
    for report_format in ("json", "markdown", "html"):
        report = client.post(
            f"/api/v1/intelligence/runs/{run_id}/reports",
            params={"format": report_format},
            headers=ORIGIN,
        )
        assert report.status_code == 200, report.text
    with _db_session() as db:
        counters = _runtime_integrity_matrix(db)
    assert counters and all(value == 0 for value in counters.values()), counters
    print(f"INTELLIGENCE_INTEGRITY_COUNTERS={counters}")


def test_concurrent_run_now_is_single_idempotent_run_and_ledger_is_unique(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: _run(client, mission_id, "same-run"), range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert len({response.json()["id"] for response in responses}) == 1
    with _db_session() as db:
        assert _count(db, IntelligenceResearchRun) == 1
        assert _count(db, IntelligenceResearchCandidate) == 8
        assert _count(db, IntelligenceEvidence) == 40
        assert _count(db, IntelligenceResearchSignal) == 64
        assert _count(db, IntelligenceScoreEvaluation) == 8
        assert _count(db, IntelligenceOpportunity) == 6
        assert _count(db, IntelligenceRecoveryRecord) == 0


def test_concurrent_recovery_is_idempotent(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    run = _run(client, mission_id, "recovery-run")
    assert run.status_code == 200, run.text
    payload = {
        "failure_classification": "checkpoint_invalid",
        "action": "reconcile",
        "idempotency_key": "recovery-once",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    f"/api/v1/intelligence/runs/{run.json()['id']}/recover",
                    json=payload,
                    headers=ORIGIN,
                ),
                range(2),
            )
        )
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    values = [response.json() for response in responses]
    assert len({value["id"] for value in values}) == 1
    assert sum(value["idempotent_reuse"] for value in values) == 1
    with _db_session() as db:
        assert _count(db, IntelligenceRecoveryRecord) == 1


def test_concurrent_candidate_evidence_and_scoring_are_deduplicated(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda key: _run(client, mission_id, key), ("parallel-a", "parallel-b"))
        )
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    with _db_session() as db:
        assert _count(db, IntelligenceResearchRun) == 2
        assert _count(db, IntelligenceResearchCandidate) == 8
        assert _count(db, IntelligenceEvidence) == 40
        assert _count(db, IntelligenceResearchSignal) == 64
        assert _count(db, IntelligenceScoreEvaluation) == 8
        assert _count(db, IntelligenceOpportunity) == 6


def test_concurrent_rule_evaluation_has_one_identity_per_rule(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    run = _run(client, mission_id, "rule-run")
    assert run.status_code == 200, run.text
    opportunity = client.get("/api/v1/intelligence/opportunities", headers=ORIGIN).json()[0]
    with _db_session() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        category = IntelligenceRuleCategory(
            owner_id=owner.id,
            category_key="test_rule_category",
            display_name="Test rules",
            enabled=True,
            created_at=now(),
            updated_at=now(),
        )
        db.add(category)
        db.flush()
        db.add(
            IntelligenceRule(
                owner_id=owner.id,
                category_id=category.id,
                logical_key="score-threshold",
                version=1,
                name="Score threshold",
                description="",
                enabled=True,
                priority=100,
                severity="warning",
                hard_block=False,
                operator="gte",
                conditions={"field": "score", "value": 0},
                parameters={"score_impact": 0},
                reason_template="Score threshold evaluated.",
                created_at=now(),
                updated_at=now(),
            )
        )
        db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    f"/api/v1/intelligence/opportunities/{opportunity['id']}/evaluate",
                    headers=ORIGIN,
                ),
                range(2),
            )
        )
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    with _db_session() as db:
        assert _count(db, IntelligenceRuleEvaluation) == 1


def test_crash_after_provider_checkpoint_replays_without_duplicate_ledger(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    with _db_session() as db:
        owner = db.scalar(select(User))
        mission = db.scalar(
            select(IntelligenceResearchMission).where(IntelligenceResearchMission.id == mission_id)
        )
        assert owner is not None and mission is not None
        project = db.scalar(
            select(IntelligenceResearchProject).where(
                IntelligenceResearchProject.id == mission.project_id
            )
        )
        assert project is not None
        stamp = now()
        run = IntelligenceResearchRun(
            owner_id=owner.id,
            project_id=project.id,
            status="pending",
            correlation_id="crash-after-provider-certification",
            ruleset_version=mission.ruleset_version,
            source_policy_reference="local-deterministic",
            summary_json={},
            idempotency_key="crash-after-provider",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        with pytest.raises(RuntimeError, match="crash after provider"):
            execute_research_run(db, owner, run, crash_after_stage="provider")
        db.rollback()
        recovered_run = db.scalar(
            select(IntelligenceResearchRun).where(IntelligenceResearchRun.id == run.id)
        )
        assert recovered_run is not None and recovered_run.status == "running"
        execute_research_run(db, owner, recovered_run)
        assert recovered_run.status == "completed"
        assert _count(db, IntelligenceResearchCandidate) == 8
        assert _count(db, IntelligenceEvidence) == 40
        assert _count(db, IntelligenceScoreEvaluation) == 8


def test_intelligence_storage_replay_and_endpoint_performance(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    first = _run(client, mission_id, "ledger-replay")
    assert first.status_code == 200, first.text
    run_id = first.json()["id"]
    candidates = client.get("/api/v1/intelligence/candidates", headers=ORIGIN).json()
    with _db_session() as db:
        before = {
            "runs": _count(db, IntelligenceResearchRun),
            "candidates": _count(db, IntelligenceResearchCandidate),
            "evidence": _count(db, IntelligenceEvidence),
            "signals": _count(db, IntelligenceResearchSignal),
            "scores": _count(db, IntelligenceScoreEvaluation),
            "opportunities": _count(db, IntelligenceOpportunity),
        }
        before_all = _all_intelligence_counts(db)
        before_scores = {
            str(row.candidate_id): (row.scoring_model_version, float(row.score), row.reason)
            for row in db.scalars(select(IntelligenceScoreEvaluation))
        }
    replay = _run(client, mission_id, "ledger-replay")
    assert replay.status_code == 200, replay.text
    with _db_session() as db:
        after = {
            "runs": _count(db, IntelligenceResearchRun),
            "candidates": _count(db, IntelligenceResearchCandidate),
            "evidence": _count(db, IntelligenceEvidence),
            "signals": _count(db, IntelligenceResearchSignal),
            "scores": _count(db, IntelligenceScoreEvaluation),
            "opportunities": _count(db, IntelligenceOpportunity),
        }
        assert after == before
        after_all = _all_intelligence_counts(db)
        after_scores = {
            str(row.candidate_id): (row.scoring_model_version, float(row.score), row.reason)
            for row in db.scalars(select(IntelligenceScoreEvaluation))
        }
        assert after_scores == before_scores
        print(f"INTELLIGENCE_STORAGE_BEFORE={before_all}")
        print(f"INTELLIGENCE_STORAGE_AFTER={after_all}")
        delta = {name: after_all[name] - before_all[name] for name in before_all}
        print(f"INTELLIGENCE_STORAGE_DELTA={delta}")
    projects = client.get("/api/v1/intelligence/projects", headers=ORIGIN).json()
    opportunities = client.get("/api/v1/intelligence/opportunities", headers=ORIGIN).json()
    evidence = client.get("/api/v1/intelligence/evidence", headers=ORIGIN).json()
    report = client.post(f"/api/v1/intelligence/runs/{run_id}/reports", headers=ORIGIN)
    assert report.status_code == 200, report.text
    report_id = report.json()["id"]
    project_id = projects[0]["id"]
    evidence_id = evidence[0]["id"]
    opportunity_id = opportunities[0]["id"]
    candidate_id = candidates[0]["id"]
    endpoints = [
        (
            "recovery_catalog",
            lambda: client.get("/api/v1/intelligence/recovery/catalog", headers=ORIGIN),
        ),
        ("overview", lambda: client.get("/api/v1/intelligence/overview", headers=ORIGIN)),
        ("projects", lambda: client.get("/api/v1/intelligence/projects", headers=ORIGIN)),
        (
            "project_detail",
            lambda: client.get(f"/api/v1/intelligence/projects/{project_id}", headers=ORIGIN),
        ),
        ("missions", lambda: client.get("/api/v1/intelligence/missions", headers=ORIGIN)),
        (
            "project_runs",
            lambda: client.get(f"/api/v1/intelligence/projects/{project_id}/runs", headers=ORIGIN),
        ),
        (
            "run_candidates",
            lambda: client.get(f"/api/v1/intelligence/runs/{run_id}/candidates", headers=ORIGIN),
        ),
        (
            "mission_history",
            lambda: client.get(f"/api/v1/intelligence/runs/{run_id}/history", headers=ORIGIN),
        ),
        ("candidates", lambda: client.get("/api/v1/intelligence/candidates", headers=ORIGIN)),
        (
            "candidate",
            lambda: client.get(f"/api/v1/intelligence/candidates/{candidate_id}", headers=ORIGIN),
        ),
        (
            "candidate_signals",
            lambda: client.get(
                f"/api/v1/intelligence/candidates/{candidate_id}/signals", headers=ORIGIN
            ),
        ),
        (
            "candidate_trends",
            lambda: client.get(
                f"/api/v1/intelligence/candidates/{candidate_id}/trends", headers=ORIGIN
            ),
        ),
        ("opportunities", lambda: client.get("/api/v1/intelligence/opportunities", headers=ORIGIN)),
        (
            "opportunity",
            lambda: client.get(
                f"/api/v1/intelligence/opportunities/{opportunity_id}", headers=ORIGIN
            ),
        ),
        (
            "ranking",
            lambda: client.get("/api/v1/intelligence/opportunities/ranked", headers=ORIGIN),
        ),
        (
            "compare",
            lambda: client.post(
                "/api/v1/intelligence/compare",
                json={"candidate_ids": [item["id"] for item in candidates[:2]]},
                headers=ORIGIN,
            ),
        ),
        ("sources", lambda: client.get("/api/v1/intelligence/sources", headers=ORIGIN)),
        ("claims", lambda: client.get("/api/v1/intelligence/claims", headers=ORIGIN)),
        ("rules", lambda: client.get("/api/v1/intelligence/rules", headers=ORIGIN)),
        (
            "restrictions_matrix",
            lambda: client.get("/api/v1/intelligence/restrictions/matrix", headers=ORIGIN),
        ),
        ("evidence", lambda: client.get("/api/v1/intelligence/evidence", headers=ORIGIN)),
        (
            "evidence_detail",
            lambda: client.get(f"/api/v1/intelligence/evidence/{evidence_id}", headers=ORIGIN),
        ),
        (
            "rules_categories",
            lambda: client.get("/api/v1/intelligence/rules/categories", headers=ORIGIN),
        ),
        (
            "rule_simulator",
            lambda: client.post(
                "/api/v1/intelligence/rules/simulate",
                json={"candidate_ids": [item["id"] for item in candidates[:5]]},
                headers=ORIGIN,
            ),
        ),
        ("profiles", lambda: client.get("/api/v1/intelligence/profiles", headers=ORIGIN)),
        (
            "recovery_matrix",
            lambda: client.get("/api/v1/intelligence/recovery/matrix", headers=ORIGIN),
        ),
        ("report", lambda: client.get(f"/api/v1/intelligence/reports/{report_id}", headers=ORIGIN)),
    ]
    timings = {}
    for name, call in endpoints:
        samples = []
        for _ in range(10):
            started = time.perf_counter()
            response = call()
            samples.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200, response.text
        timings[name] = {
            "samples": len(samples),
            "median_ms": round(statistics.median(samples), 2),
            "p95_ms": round(max(samples), 2),
            "classification": (
                "mutation" if name in {"report", "compare", "rule_simulator"} else "read"
            ),
        }
    print(f"INTELLIGENCE_ENDPOINT_TIMINGS={timings}")


def test_intelligence_endpoint_inventory(client) -> None:
    routes = []

    def iter_routes(items):
        for route in items:
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                yield from iter_routes(original_router.routes)
            else:
                yield route

    for route in iter_routes(client.app.routes):
        path = getattr(route, "path", "")
        if not isinstance(path, str) or not path.startswith("/api/v1/intelligence"):
            continue
        methods = sorted(getattr(route, "methods", set()))
        if not methods:
            continue
        if "/reports" in path and "POST" in methods:
            classification = "REPORT"
        elif "/run-now" in path or "/execute" in path or "/scheduler" in path:
            classification = "WORKER/SCHEDULER"
        elif "/recover" in path or "/recovery" in path:
            classification = "RECOVERY"
        elif any(method in methods for method in ("POST", "PATCH", "PUT", "DELETE")):
            classification = "MUTATION"
        else:
            classification = "READ"
        routes.append({"path": path, "methods": methods, "classification": classification})
    assert routes
    route_paths = [item.get("path") for item in routes]
    assert any(isinstance(path, str) and path.endswith("/overview") for path in route_paths)
    assert any(isinstance(path, str) and path.endswith("/compare") for path in route_paths)
    print(f"INTELLIGENCE_ENDPOINT_INVENTORY={routes}")


def test_query_count_heavy_intelligence_endpoints(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    run = _run(client, mission_id, "query-count")
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]
    candidates = client.get("/api/v1/intelligence/candidates", headers=ORIGIN).json()
    opportunities = client.get("/api/v1/intelligence/opportunities", headers=ORIGIN).json()
    evidence = client.get("/api/v1/intelligence/evidence", headers=ORIGIN).json()
    assert len(candidates) >= 2 and opportunities and evidence
    factory = test_ai_integration.factory
    assert factory is not None
    engine = factory.kw["bind"]

    def counted(call) -> int:
        count = 0

        def before_cursor_execute(*args):
            nonlocal count
            count += 1

        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        try:
            response = call()
            assert response.status_code == 200, response.text
        finally:
            event.remove(engine, "before_cursor_execute", before_cursor_execute)
        return count

    report_response = client.post(f"/api/v1/intelligence/runs/{run_id}/reports", headers=ORIGIN)
    assert report_response.status_code == 200, report_response.text
    report_id = report_response.json()["id"]
    counts = {
        "opportunity_detail": counted(
            lambda: client.get(
                f"/api/v1/intelligence/opportunities/{opportunities[0]['id']}", headers=ORIGIN
            )
        ),
        "comparison_2": counted(
            lambda: client.post(
                "/api/v1/intelligence/compare",
                json={"candidate_ids": [item["id"] for item in candidates[:2]]},
                headers=ORIGIN,
            )
        ),
        "comparison_5": counted(
            lambda: client.post(
                "/api/v1/intelligence/compare",
                json={"candidate_ids": [item["id"] for item in candidates[:5]]},
                headers=ORIGIN,
            )
        ),
        "history": counted(
            lambda: client.get(f"/api/v1/intelligence/runs/{run_id}/history", headers=ORIGIN)
        ),
        "report_retrieval": counted(
            lambda: client.get(f"/api/v1/intelligence/reports/{report_id}", headers=ORIGIN)
        ),
        "evidence_detail": counted(
            lambda: client.get(f"/api/v1/intelligence/evidence/{evidence[0]['id']}", headers=ORIGIN)
        ),
    }
    assert counts["comparison_5"] <= counts["comparison_2"] + 6
    print(f"INTELLIGENCE_QUERY_COUNTS={counts}")


def test_score_v1_v2_history_is_append_only_and_concurrent_v2_is_unique(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    run = _run(client, mission_id, "score-version")
    assert run.status_code == 200, run.text
    with _db_session() as db:
        owner = db.scalar(select(User))
        v1 = db.scalar(select(IntelligenceScoreEvaluation))
        assert owner is not None and v1 is not None
        v1_snapshot = (
            v1.scoring_model_version,
            dict(v1.weights),
            dict(v1.inputs),
            dict(v1.dimension_scores),
            list(v1.evidence_ids),
            float(v1.score),
            v1.recommendation,
        )
        v2 = IntelligenceScoreEvaluation(
            owner_id=owner.id,
            candidate_id=v1.candidate_id,
            scoring_model_version="winning-product-local-v2",
            weights={**v1.weights, "demand": 30, "economics": 20},
            inputs=dict(v1.inputs),
            dimension_scores=dict(v1.dimension_scores),
            weighted_contributions=dict(v1.weighted_contributions),
            score=float(v1.score) + 1,
            confidence=float(v1.confidence),
            recommendation=v1.recommendation,
            hard_blocked=v1.hard_blocked,
            risk_summary=dict(v1.risk_summary),
            critic_findings=list(v1.critic_findings),
            reason=v1.reason,
            evidence_ids=list(v1.evidence_ids),
            created_at=now(),
        )
        db.add(v2)
        db.commit()
        rows = list(
            db.scalars(
                select(IntelligenceScoreEvaluation)
                .where(
                    IntelligenceScoreEvaluation.owner_id == owner.id,
                    IntelligenceScoreEvaluation.candidate_id == v1.candidate_id,
                )
                .order_by(IntelligenceScoreEvaluation.created_at)
            )
        )
        assert [row.scoring_model_version for row in rows] == [
            "winning-product-local-v1",
            "winning-product-local-v2",
        ]
        persisted_v1 = rows[0]
        assert (
            persisted_v1.scoring_model_version,
            dict(persisted_v1.weights),
            dict(persisted_v1.inputs),
            dict(persisted_v1.dimension_scores),
            list(persisted_v1.evidence_ids),
            float(persisted_v1.score),
            persisted_v1.recommendation,
        ) == v1_snapshot
        assert rows[-1].scoring_model_version == "winning-product-local-v2"

    def insert_same_v2() -> str:
        with _db_session() as db:
            source = db.scalar(select(IntelligenceScoreEvaluation))
            assert source is not None
            duplicate = IntelligenceScoreEvaluation(
                owner_id=source.owner_id,
                candidate_id=source.candidate_id,
                scoring_model_version="winning-product-local-v2-concurrent",
                weights=dict(source.weights),
                inputs=dict(source.inputs),
                dimension_scores=dict(source.dimension_scores),
                weighted_contributions=dict(source.weighted_contributions),
                score=float(source.score),
                confidence=float(source.confidence),
                recommendation=source.recommendation,
                hard_blocked=source.hard_blocked,
                risk_summary=dict(source.risk_summary),
                critic_findings=list(source.critic_findings),
                reason=source.reason,
                evidence_ids=list(source.evidence_ids),
                created_at=now(),
            )
            db.add(duplicate)
            try:
                db.commit()
                return "created"
            except Exception:
                db.rollback()
                return "reused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: insert_same_v2(), range(2)))
    assert sorted(results) == ["created", "reused"]
    with _db_session() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(IntelligenceScoreEvaluation)
                .where(
                    IntelligenceScoreEvaluation.scoring_model_version
                    == "winning-product-local-v2-concurrent"
                )
            )
            == 1
        )


def test_historical_score_mutation_is_rejected(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    response = _run(client, mission_id, "immutable-score")
    assert response.status_code == 200, response.text
    with _db_session() as db:
        evaluation = db.scalar(select(IntelligenceScoreEvaluation))
        assert evaluation is not None
        snapshot = (
            evaluation.scoring_model_version,
            dict(evaluation.weights),
            dict(evaluation.inputs),
            list(evaluation.evidence_ids),
            float(evaluation.score),
            evaluation.recommendation,
        )
        evaluation.scoring_model_version = "tampered"
        evaluation.weights = {"tampered": 100}
        evaluation.inputs = {"tampered": True}
        evaluation.evidence_ids = ["tampered"]
        evaluation.score = 0
        evaluation.recommendation = "tampered"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        persisted = db.get(IntelligenceScoreEvaluation, evaluation.id)
        assert persisted is not None
        assert (
            persisted.scoring_model_version,
            dict(persisted.weights),
            dict(persisted.inputs),
            list(persisted.evidence_ids),
            float(persisted.score),
            persisted.recommendation,
        ) == snapshot


def test_historical_score_mutation_concurrency_does_not_corrupt_v2(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    response = _run(client, mission_id, "immutable-score-concurrency")
    assert response.status_code == 200, response.text
    with _db_session() as db:
        source = db.scalar(select(IntelligenceScoreEvaluation))
        assert source is not None
        source_id = source.id
        source_owner_id = source.owner_id
        source_candidate_id = source.candidate_id
        source_weights = dict(source.weights)
        source_inputs = dict(source.inputs)
        source_dimensions = dict(source.dimension_scores)
        source_contributions = dict(source.weighted_contributions)
        source_score = float(source.score)
        source_confidence = float(source.confidence)
        source_recommendation = source.recommendation
        source_hard_blocked = source.hard_blocked
        source_risk = dict(source.risk_summary)
        source_findings = list(source.critic_findings)
        source_reason = source.reason
        source_evidence = list(source.evidence_ids)

    def mutate() -> str:
        with _db_session() as db:
            value = db.get(IntelligenceScoreEvaluation, source_id)
            assert value is not None
            value.score = -1
            try:
                db.commit()
            except ValueError:
                db.rollback()
                return "rejected"
        return "unexpected"

    def create_v2() -> str:
        with _db_session() as db:
            value = IntelligenceScoreEvaluation(
                owner_id=source_owner_id,
                candidate_id=source_candidate_id,
                scoring_model_version="winning-product-local-v2-immutable-concurrency",
                weights=source_weights,
                inputs=source_inputs,
                dimension_scores=source_dimensions,
                weighted_contributions=source_contributions,
                score=source_score + 2,
                confidence=source_confidence,
                recommendation=source_recommendation,
                hard_blocked=source_hard_blocked,
                risk_summary=source_risk,
                critic_findings=source_findings,
                reason=source_reason,
                evidence_ids=source_evidence,
                created_at=now(),
            )
            db.add(value)
            db.commit()
            return "created"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda fn: fn(), (mutate, create_v2)))
    assert sorted(results) == ["created", "rejected"]
    with _db_session() as db:
        historical = db.get(IntelligenceScoreEvaluation, source_id)
        assert historical is not None
        assert float(historical.score) == source_score
        assert (
            db.scalar(
                select(func.count())
                .select_from(IntelligenceScoreEvaluation)
                .where(
                    IntelligenceScoreEvaluation.scoring_model_version
                    == "winning-product-local-v2-immutable-concurrency"
                )
            )
            == 1
        )


def test_report_ready_timing_ledger(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    run_response = _run(client, mission_id, "report-ready-timing")
    assert run_response.status_code == 200, run_response.text
    run_id = run_response.json()["id"]
    report = client.post(
        f"/api/v1/intelligence/runs/{run_id}/reports",
        params={"format": "json"},
        headers=ORIGIN,
    )
    assert report.status_code == 200, report.text
    with _db_session() as db:
        run = db.scalar(select(IntelligenceResearchRun).where(IntelligenceResearchRun.id == run_id))
        checkpoint = db.scalar(
            select(IntelligenceResearchCheckpoint).where(
                IntelligenceResearchCheckpoint.run_id == run_id
            )
        )
        assert run is not None and checkpoint is not None
        payload = checkpoint.payload
        fields = (
            "worker_claimed_at",
            "provider_started_at",
            "first_candidate_persisted_at",
            "candidate_processing_completed_at",
            "scoring_completed_at",
            "opportunity_promotion_completed_at",
            "report_generation_started_at",
            "report_ready_at",
        )
        stamps = {field: datetime.fromisoformat(payload[field]) for field in fields}
        ordered = [stamps[field] for field in fields[:6]]
        assert ordered == sorted(ordered)
        assert run.completed_at is not None
        assert stamps["opportunity_promotion_completed_at"] <= run.completed_at
        assert (
            run.completed_at <= stamps["report_generation_started_at"] <= stamps["report_ready_at"]
        )
        metrics = {
            field: round((stamps[field] - run.created_at).total_seconds() * 1000, 2)
            for field in fields
        }
        metrics["run_terminal_ms"] = round(
            (run.completed_at - run.created_at).total_seconds() * 1000, 2
        )
        print(f"INTELLIGENCE_REPORT_TIMING_LEDGER={metrics}")


def test_time_to_first_candidate_and_mission_timing_ledger(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    accepted = time.perf_counter()
    response = _run(client, mission_id, "timing-ledger")
    assert response.status_code == 200, response.text
    request_completed = time.perf_counter()
    run_id = response.json()["id"]
    with _db_session() as db:
        run = db.scalar(select(IntelligenceResearchRun).where(IntelligenceResearchRun.id == run_id))
        checkpoint = db.scalar(select(IntelligenceResearchCheckpoint))
        assert run is not None and checkpoint is not None
        payload = checkpoint.payload
        worker_claim = datetime.fromisoformat(payload["worker_claimed_at"])
        provider_start = datetime.fromisoformat(payload["provider_started_at"])
        first_candidate = datetime.fromisoformat(payload["first_candidate_persisted_at"])
        scoring_complete = datetime.fromisoformat(payload["scoring_completed_at"])
        assert worker_claim <= provider_start <= first_candidate <= scoring_complete
        assert run.started_at is not None and run.completed_at is not None
        request_to_worker_ms = (worker_claim - run.created_at).total_seconds() * 1000
        worker_to_first_candidate_ms = (first_candidate - worker_claim).total_seconds() * 1000
        request_wall_ms = (request_completed - accepted) * 1000
        run_total_ms = (run.completed_at - run.created_at).total_seconds() * 1000
        metrics = {
            "request_to_worker_ms": round(request_to_worker_ms, 2),
            "worker_to_first_candidate_ms": round(worker_to_first_candidate_ms, 2),
            "request_wall_ms": round(request_wall_ms, 2),
            "run_total_ms": round(run_total_ms, 2),
        }
        print(f"INTELLIGENCE_TIMING_LEDGER={metrics}")
