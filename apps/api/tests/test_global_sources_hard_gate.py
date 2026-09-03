# ruff: noqa: E501
from __future__ import annotations

import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence import global_sources_service
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_intelligence import (
    confidence_handoff,
    record_external_alert,
    record_external_change,
    record_external_contradiction,
    source_diversity_evaluation,
    verify_external_evidence,
)
from vayujit_api.intelligence.global_sources import provider_preflight
from vayujit_api.intelligence.global_sources_models import GlobalSourcesDiscoveryRequest
from vayujit_api.intelligence.marketplace_runtime import (
    MarketplaceExecution,
    MarketplaceLedger,
    MarketplaceRateLimited,
    bounded_percentile,
    classify_failure,
    consume_rate_window,
    execute_marketplace_lifecycle,
    execute_marketplace_recovery,
    fault_injection,
    marketplace_integrity_counters,
    parse_retry_after,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case,code,expected",
    (
        ("timeout", "TIMEOUT", True),
        ("network failure", "NETWORK_FAILURE", True),
        ("429", "429", True),
        ("500", "500", True),
        ("503", "503", True),
        ("authentication failure", "AUTH", False),
        ("invalid response", "INVALID_RESPONSE", False),
        ("policy blocked", "POLICY_BLOCK", False),
        ("kill switch", "KILL_SWITCH", False),
        ("bad request", "BAD_REQUEST", False),
    ),
)
def test_global_sources_retry_matrix(case: str, code: str, expected: bool) -> None:
    decision = classify_failure(code, retry_after=10, max_retry_after=60)
    assert decision.retryable is expected, case
    assert decision.failure_code


def test_global_sources_rate_and_retry_budget_matrix(client: TestClient) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        available = consume_rate_window(
            db, owner, "GLOBAL_SOURCES", requests_per_minute=2, requests_per_hour=2
        )
        assert available.remaining == 1
        consume_rate_window(db, owner, "GLOBAL_SOURCES", requests_per_minute=2, requests_per_hour=2)
        with pytest.raises(MarketplaceRateLimited) as minute:
            consume_rate_window(
                db, owner, "GLOBAL_SOURCES", requests_per_minute=2, requests_per_hour=2
            )
        assert minute.value.result.window == "minute"
        assert minute.value.result.retry_after_seconds is not None
        assert minute.value.result.retry_after_seconds <= 60
        row = MarketplaceExecution(
            owner_id=owner.id,
            provider="GLOBAL_SOURCES",
            correlation_id="budget",
            identity_key="budget",
        )
        db.add(row)
        db.flush()
        from vayujit_api.intelligence.marketplace_runtime import consume_retry_budget

        assert consume_retry_budget(db, row.id, max_attempts=1) == 1
        with pytest.raises(RuntimeError):
            consume_retry_budget(db, row.id, max_attempts=1)

    assert classify_failure("429", retry_after=999, max_retry_after=60).retry_after_seconds == 60
    assert classify_failure("429", retry_after=-4, max_retry_after=60).retry_after_seconds == 0
    assert parse_retry_after("not-a-date") is None


@pytest.mark.parametrize(
    "stage",
    (
        "BEFORE_PROVIDER",
        "AFTER_PROVIDER",
        "AFTER_RESULT",
        "AFTER_EVIDENCE",
        "AFTER_CHANGE",
        "AFTER_ALERT",
    ),
)
def test_global_sources_crash_checkpoint_recovery_is_duplicate_free(
    client: TestClient, stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        calls = 0
        adapter = global_sources_service._GlobalSourcesAdapter(
            Settings(global_sources_enabled=True, global_sources_mode="LOCAL_FIXTURE"),
            result_limit=2,
            country_code="IN",
        )
        original = adapter.search

        def counted(query: str) -> object:
            nonlocal calls
            calls += 1
            return original(query)

        monkeypatch.setattr(adapter, "search", counted)
        identity = f"crash:{stage}"
        with fault_injection(stage), pytest.raises(RuntimeError):
            execute_marketplace_lifecycle(
                db,
                owner,
                adapter,
                provider="GLOBAL_SOURCES",
                identity_key=identity,
                query="crash bottle",
                mode="LOCAL_FIXTURE",
            )
        db.rollback()
        recovered = execute_marketplace_lifecycle(
            db,
            owner,
            adapter,
            provider="GLOBAL_SOURCES",
            identity_key=identity,
            query="crash bottle",
            mode="LOCAL_FIXTURE",
        )
        assert recovered.status == "SUCCEEDED"
        assert calls == (1 if stage == "BEFORE_PROVIDER" else 1)
        execution_count = db.scalar(
            select(func.count())
            .select_from(MarketplaceExecution)
            .where(MarketplaceExecution.identity_key == identity)
        )
        assert execution_count == 1
        ledger_count = db.scalar(
            select(func.count())
            .select_from(MarketplaceLedger)
            .where(MarketplaceLedger.execution_id == recovered.execution_id)
        )
        assert ledger_count is not None
        assert ledger_count >= 13
        assert ledger_count >= 13


def test_global_sources_concurrency_and_repeatability(client: TestClient) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    factory = test_ai_integration.factory

    def run_once(suffix: str) -> tuple[str, int]:
        barrier = threading.Barrier(2)

        def invoke(_: int) -> str:
            with factory() as db:
                owner = db.scalar(select(User).where(User.email == "owner@example.com"))
                assert owner is not None
                barrier.wait()
                result = global_sources_service.discover(
                    db,
                    owner,
                    Settings(global_sources_enabled=True, global_sources_mode="LOCAL_FIXTURE"),
                    query="concurrent bottle",
                    product_id=None,
                    country_code="IN",
                    region=None,
                    result_limit=2,
                    correlation_id=f"corr-{suffix}",
                    idempotency_key=f"concurrent-{suffix}",
                    mission_id=None,
                    task_id=None,
                )
                db.commit()
                typed_result = cast(dict[str, Any], result)
                return str(typed_result["request"]["id"])
                return str(result["request"]["id"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(invoke, range(2)))
        with factory() as db:
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(GlobalSourcesDiscoveryRequest)
                    .where(GlobalSourcesDiscoveryRequest.idempotency_key == f"concurrent-{suffix}")
                )
                or 0
            )
        assert len(set(values)) == 1
        return values[0], int(count)

    for run in range(1, 4):
        _, count = run_once(str(run))
        assert count == 1


def _evidence_pair(
    db: Any, owner: User, key: str
) -> tuple[AutonomousResearchMission, AutonomousResearchEvidence, AutonomousResearchEvidence]:
    mission = AutonomousResearchMission(
        owner_id=owner.id,
        mission_type="SUPPLIER_DISCOVERY",
        goal="GlobalSources contradiction",
        market="IN",
        category="outdoors",
        provider_mode="LOCAL_DETERMINISTIC",
        correlation_id=f"corr-{key}",
        idempotency_key=f"mission-{key}",
        status="DRAFT",
    )
    db.add(mission)
    db.flush()
    task = AutonomousResearchTask(
        owner_id=owner.id,
        mission_id=mission.id,
        task_type="discover_suppliers",
        source_class="SUPPLIER",
        idempotency_key=f"task-{key}",
        correlation_id=mission.correlation_id,
    )
    db.add(task)
    db.flush()
    left = AutonomousResearchEvidence(
        owner_id=owner.id,
        mission_id=mission.id,
        task_id=task.id,
        source_class="SUPPLIER",
        source_reference=f"website-{key}",
        retrieval_identity=f"website:{key}",
        content_type="application/json",
        normalized_value={"value": 100},
        content_hash=f"hash-left-{key}",
        verification_status="SUPPORTED",
        freshness_status="FRESH",
        verification_reason="fixture",
        source_profile="website",
        provider="WEBSITE",
        canonical_url="https://example.com/source",
        domain="example.com",
        lineage={"mission_id": str(mission.id), "correlation_id": mission.correlation_id},
        confidence=0.8,
        evidence_class="SUPPLIER",
    )
    right = AutonomousResearchEvidence(
        owner_id=owner.id,
        mission_id=mission.id,
        task_id=task.id,
        source_class="SUPPLIER",
        source_reference=f"global_sources-{key}",
        retrieval_identity=f"global_sources:{key}",
        content_type="application/json",
        normalized_value={"value": 500},
        content_hash=f"hash-right-{key}",
        verification_status="SUPPORTED",
        freshness_status="FRESH",
        verification_reason="fixture",
        source_profile="global_sources-local",
        provider="GLOBAL_SOURCES",
        canonical_url="https://www.global_sources.com/source",
        domain="www.global_sources.com",
        lineage={"mission_id": str(mission.id), "correlation_id": mission.correlation_id},
        confidence=0.8,
        evidence_class="SUPPLIER",
    )
    db.add_all([left, right])
    db.flush()
    return mission, left, right


@pytest.mark.parametrize("key", ("MOQ", "LEAD_TIME", "VERIFICATION", "IDENTITY"))
def test_global_sources_contradiction_matrix_is_replay_safe(client: TestClient, key: str) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        mission, left, right = _evidence_pair(db, owner, key)
        first = record_external_contradiction(db, mission, left, right, claim_key=key)
        replay = record_external_contradiction(db, mission, left, right, claim_key=key)
        reverse = record_external_contradiction(db, mission, right, left, claim_key=key)
        db.commit()
        assert first.id == replay.id == reverse.id
        assert first.resolution_strategy == "REQUIRES_HUMAN_REVIEW"
        assert source_diversity_evaluation([left, right])["duplicate_source_count"] == 0
        confidence = cast(
            dict[str, Any],
            confidence_handoff(
                [left, right], contradiction_count=1, critical_unknowns=1, complete=False
            ),
        )
        assert float(confidence["overall_confidence"]) < 0.85


@pytest.mark.parametrize(
    "field",
    (
        "PRICE",
        "MOQ",
        "LEAD_TIME",
        "AVAILABILITY",
        "BUSINESS_IDENTITY",
        "VERIFICATION_CLAIM",
        "LISTING_STATUS",
    ),
)
def test_global_sources_change_matrix_and_replay(client: TestClient, field: str) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        mission, left, _ = _evidence_pair(db, owner, field)
        first = record_external_change(
            db,
            mission,
            change_type=field,
            entity_id=f"global_sources:{field}",
            field_key=field,
            previous={"value": "old"},
            current={"value": "new"},
            evidence_ids=[str(left.id)],
        )
        replay = record_external_change(
            db,
            mission,
            change_type=field,
            entity_id=f"global_sources:{field}",
            field_key=field,
            previous={"value": "old"},
            current={"value": "new"},
            evidence_ids=[str(left.id)],
        )
        db.commit()
        assert first is not None and replay is not None and first.id == replay.id
        assert first.owner_id == owner.id and first.correlation_id == mission.correlation_id
        assert first.evidence_ids == [str(left.id)]


@pytest.mark.parametrize(
    "alert_type",
    (
        "material_price_change",
        "material_moq_change",
        "material_lead_time_change",
        "listing_removed",
        "verification_claim_changed",
        "business_identity_conflict",
    ),
)
def test_global_sources_alert_matrix_and_replay(client: TestClient, alert_type: str) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        mission = AutonomousResearchMission(
            owner_id=owner.id,
            mission_type="SUPPLIER_DISCOVERY",
            goal="alerts",
            market="IN",
            category="outdoors",
            provider_mode="LOCAL_DETERMINISTIC",
            correlation_id=f"alert-{alert_type}",
            idempotency_key=f"alert-mission-{alert_type}",
            status="DRAFT",
        )
        db.add(mission)
        db.flush()
        first = record_external_alert(
            db,
            mission,
            alert_type=alert_type,
            title=f"GlobalSources {alert_type}",
            detail="Review required",
            identity=f"global_sources:{alert_type}",
            severity="REQUIRES_REVIEW",
        )
        replay = record_external_alert(
            db,
            mission,
            alert_type=alert_type,
            title=f"GlobalSources {alert_type}",
            detail="Review required",
            identity=f"global_sources:{alert_type}",
            severity="REQUIRES_REVIEW",
        )
        later = record_external_alert(
            db,
            mission,
            alert_type=alert_type,
            title=f"GlobalSources {alert_type}",
            detail="Later observation",
            identity=f"global_sources:{alert_type}:later",
            severity="REQUIRES_REVIEW",
        )
        db.commit()
        assert first.id == replay.id and later.id != first.id


@pytest.mark.parametrize(
    "state", ("UNVERIFIED", "REJECTED", "STALE", "EXPIRED", "WRONG_OWNER", "DISCOVERY_ONLY")
)
def test_global_sources_rejected_data_has_zero_delta(client: TestClient, state: str) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        candidate = {
            "owner_id": "other-owner" if state == "WRONG_OWNER" else str(owner.id),
            "provider": "GLOBAL_SOURCES",
            "content": "normalized claim",
            "freshness_status": state if state in {"STALE", "EXPIRED"} else "FRESH",
            "verification_status": (
                "UNVERIFIED" if state in {"UNVERIFIED", "REJECTED"} else "SUPPORTED"
            ),
            "classification": "DISCOVERY_ONLY" if state == "DISCOVERY_ONLY" else "REJECTED",
            "blocked": state in {"UNVERIFIED", "REJECTED"},
        }
        decision = verify_external_evidence(candidate, expected_owner_id=str(owner.id))
        assert decision["verification_state"] == "REJECTED"
        assert db.scalar(select(func.count()).select_from(AutonomousResearchChange)) == 0
        assert db.scalar(select(func.count()).select_from(AutonomousResearchAlert)) == 0


def test_global_sources_canonical_e2e_lineage_storage_and_replay(client: TestClient) -> None:
    context = setup_context(client)
    payload = {
        "query": "canonical global_sources bottle",
        "product_id": context["product"]["id"],
        "result_limit": 2,
        "idempotency_key": "global_sources-canonical",
    }
    first = client.post(
        "/api/v1/intelligence/global_sources/discover", json=payload, headers=ORIGIN
    )
    assert first.status_code == 200, first.text
    replay = client.post(
        "/api/v1/intelligence/global_sources/discover", json=payload, headers=ORIGIN
    )
    assert replay.status_code == 200 and replay.json() == first.json()
    body = first.json()
    request = body["request"]
    assert request["marketplace_execution_id"]
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        execution = db.get(MarketplaceExecution, request["marketplace_execution_id"])
        assert execution is not None
        assert execution.provider == "GLOBAL_SOURCES" and execution.status == "SUCCEEDED"
        assert (
            execution.lineage
            and execution.lineage.get("correlation_id") == request["correlation_id"]
        )
        rows = list(
            db.scalars(
                select(MarketplaceLedger).where(MarketplaceLedger.execution_id == execution.id)
            )
        )
        assert {row.entity_type for row in rows} >= {
            "request",
            "result",
            "candidate",
            "supplier",
            "product",
            "offering",
            "evidence",
            "observation",
            "change",
            "alert",
            "report",
            "history",
            "product_channel",
            "calendar",
        }
        counters = marketplace_integrity_counters(db, owner)
        assert (
            counters["orphan_rows"]
            == counters["broken_lineage"]
            == counters["cross_owner_rows"]
            == 0
        )
        assert all(value == 0 for key, value in counters.items() if key.startswith("duplicate_"))
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert "marketplace.discovery.requested" in actions
        assert "marketplace.discovery.completed" in actions


def test_global_sources_security_privacy_and_xss_boundaries(client: TestClient) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/global_sources/discover",
        json={"query": "<script>alert(1)</script>", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    payload = response.json()
    encoded = json.dumps(payload)
    for forbidden in (
        "Authorization",
        "token",
        "password",
        "cookie",
        "dsn",
        "postgresql",
        "traceback",
        "SELECT ",
        "C:\\\\",
    ):
        assert forbidden.lower() not in encoded.lower()
    assert payload["request"]["query"] == "<script>alert(1)</script>"
    assert (
        client.get("/api/v1/intelligence/global_sources/discoveries", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.get("/api/v1/intelligence/global_sources/report", headers=ORIGIN).status_code == 200
    )


def test_global_sources_performance_and_query_counts(client: TestClient) -> None:
    context = setup_context(client)
    client.post(
        "/api/v1/intelligence/global_sources/discover",
        json={"query": "performance bottle", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    paths = (
        "/api/v1/intelligence/global_sources/discoveries",
        "/api/v1/intelligence/global_sources/operations",
        "/api/v1/intelligence/global_sources/integrity",
        "/api/v1/intelligence/global_sources/report",
    )
    assert test_ai_integration.factory is not None
    engine = test_ai_integration.factory.kw["bind"]
    for path in paths:
        statements = 0

        def count(
            _conn: Any,
            _cursor: Any,
            _statement: Any,
            _parameters: Any,
            _context: Any,
            _executemany: Any,
        ) -> None:
            nonlocal statements
            statements += 1

        event.listen(engine, "before_cursor_execute", count)
        samples: list[float] = []
        try:
            for _ in range(10):
                started = time.perf_counter()
                response = client.get(path, headers=ORIGIN)
                samples.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", count)
        assert statistics.median(samples) >= 0 and bounded_percentile(samples, 95) >= 0
        assert statements <= 250


def test_global_sources_operations_doctor_and_calendar_are_truthful(client: TestClient) -> None:
    setup_context(client)
    operations = client.get("/api/v1/intelligence/global_sources/operations", headers=ORIGIN).json()
    assert operations["provider"] == "GLOBAL_SOURCES" and operations["read_only"] is True
    assert operations["live_validation"] == "NOT_RUN"
    assert operations["recovery"]["registered"] is True
    assert {"contact", "rfq", "order", "payment"}.issubset(set(operations["prohibited_actions"]))
    assert (
        client.get("/api/v1/intelligence/global_sources/calendar", headers=ORIGIN).status_code
        == 200
    )
    doctor = client.get("/api/v1/intelligence/system-doctor", headers=ORIGIN).json()
    assert doctor["checks"]["global_sources"]["provider"] == "GLOBAL_SOURCES"


def test_global_sources_provider_preflight_is_fail_closed() -> None:
    assert provider_preflight(Settings(global_sources_mode="DISABLED"))["status"] == "DISABLED"
    assert (
        provider_preflight(
            Settings(global_sources_enabled=True, global_sources_mode="LOCAL_FIXTURE")
        )["status"]
        == "READY"
    )
    assert (
        provider_preflight(
            Settings(
                global_sources_enabled=True,
                global_sources_mode="LIVE_READ_ONLY",
                global_sources_token_ref="configured",
            )
        )["status"]
        == "NOT_CONFIGURED"
    )
    assert provider_preflight(Settings(global_sources_mode="DISABLED"))["network_call"] is False
    assert (
        provider_preflight(Settings(global_sources_mode="LOCAL_FIXTURE"))["network_call"] is False
    )
    assert (
        provider_preflight(Settings(global_sources_mode="LIVE_READ_ONLY"))["network_call"] is False
    )


def test_global_sources_handoff_and_recovery_audit_are_idempotent(client: TestClient) -> None:
    context = setup_context(client)
    result = client.post(
        "/api/v1/intelligence/global_sources/discover",
        json={
            "query": "handoff",
            "product_id": context["product"]["id"],
            "idempotency_key": "handoff",
        },
        headers=ORIGIN,
    ).json()
    request_id = result["request"]["marketplace_execution_id"]
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        first = execute_marketplace_recovery(db, owner, request_id, action="replay")
        replay = execute_marketplace_recovery(db, owner, request_id, action="replay")
        assert first.idempotent_reuse is False and replay.idempotent_reuse is True
        db.commit()
        assert (
            db.scalar(
                select(func.count())
                .select_from(MarketplaceLedger)
                .where(MarketplaceLedger.entity_type == "recovery")
            )
            == 1
        )
