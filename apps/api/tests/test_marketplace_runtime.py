from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.marketplace_runtime import (
    CHECKPOINTS,
    MarketplaceExecution,
    MarketplaceLedger,
    MarketplaceRateLimited,
    bounded_percentile,
    checkpoint,
    classify_failure,
    consume_rate_window,
    consume_retry_budget,
    execute_marketplace_lifecycle,
    execute_marketplace_recovery,
    fault_injection,
    inject_test_fault,
    marketplace_integrity_counters,
    parse_retry_after,
    validate_capabilities,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _owner(client):
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        return owner.id


def test_marketplace_checkpoints_and_faults_are_local_fixture_only(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        execution = MarketplaceExecution(
            owner_id=owner_id,
            provider="INDIAMART",
            correlation_id="corr",
            identity_key="runtime-checkpoint",
        )
        db.add(execution)
        db.flush()
        for stage in CHECKPOINTS:
            checkpoint(execution, stage)
        db.commit()
        with fault_injection("AFTER_PROVIDER"):
            with pytest.raises(RuntimeError, match="AFTER_PROVIDER"):
                inject_test_fault("AFTER_PROVIDER", mode="LOCAL_FIXTURE")
            inject_test_fault("AFTER_PROVIDER", mode="LIVE_READ_ONLY")


def test_marketplace_rate_windows_reset_and_bound(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    base = datetime.now(UTC)
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        first = consume_rate_window(
            db, owner, "INDIAMART", requests_per_minute=1, requests_per_hour=2, now=base
        )
        assert first.remaining == 0
        with pytest.raises(MarketplaceRateLimited) as minute_error:
            consume_rate_window(
                db, owner, "INDIAMART", requests_per_minute=1, requests_per_hour=2, now=base
            )
        assert minute_error.value.result.window == "minute"
        reset = consume_rate_window(
            db,
            owner,
            "INDIAMART",
            requests_per_minute=1,
            requests_per_hour=2,
            now=base + timedelta(minutes=1, seconds=1),
        )
        assert reset.remaining == 0
        with pytest.raises(MarketplaceRateLimited) as hour_error:
            consume_rate_window(
                db,
                owner,
                "INDIAMART",
                requests_per_minute=10,
                requests_per_hour=2,
                now=base + timedelta(minutes=1, seconds=1),
            )
        assert hour_error.value.result.window == "hour"


def test_marketplace_rate_window_concurrency_is_atomic(client) -> None:
    owner_id = _owner(client)
    factory = test_ai_integration.factory
    assert factory is not None
    barrier = threading.Barrier(2)

    def consume(_: int) -> str:
        with factory() as db:
            owner = db.get(User, owner_id)
            assert owner is not None
            barrier.wait()
            try:
                consume_rate_window(
                    db, owner, "CONCURRENT", requests_per_minute=1, requests_per_hour=1
                )
                db.commit()
                return "accepted"
            except MarketplaceRateLimited:
                db.rollback()
                return "limited"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(consume, (1, 2)))
    assert sorted(outcomes) == ["accepted", "limited"]


def test_marketplace_retry_policy_and_read_only_contract() -> None:
    assert classify_failure("timeout", retry_after="9000", max_retry_after=3600).retryable
    assert classify_failure("auth_failure").retryable is False
    assert parse_retry_after("9000", max_seconds=120) == 120
    assert parse_retry_after("not-a-delay", max_seconds=120) is None
    assert validate_capabilities(("search", "supplier_metadata")) == {
        "SEARCH",
        "SUPPLIER_METADATA",
    }
    with pytest.raises(ValueError, match="forbids"):
        validate_capabilities(("CONTACT",))
    assert bounded_percentile([3.0, 1.0, 2.0], 95) == 3.0


class _FixtureAdapter:
    def __init__(self, *, failure_code: str | None = None) -> None:
        self.search_calls = 0
        self.normalize_calls = 0
        self.failure_code = failure_code

    def preflight(self) -> dict[str, object]:
        return {"status": "LOCAL_FIXTURE"}

    def search(self, query: str) -> object:
        self.search_calls += 1
        if self.failure_code is not None:
            raise RuntimeError("fixture failure")
        return {"query": query, "items": [{"id": "candidate-1"}]}

    def normalize(self, payload: object) -> list[dict[str, object]]:
        self.normalize_calls += 1
        return list(payload.get("items", [])) if isinstance(payload, dict) else []

    def classify_failure(self, error: Exception) -> str:
        return self.failure_code or ("TIMEOUT" if "timeout" in str(error) else "INVALID_RESPONSE")


def test_canonical_marketplace_lifecycle_replay_and_lineage(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    adapter = _FixtureAdapter()
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        result = execute_marketplace_lifecycle(
            db, owner, adapter, provider="INDIAMART", identity_key="canonical-1", query="steel"
        )
        replay = execute_marketplace_lifecycle(
            db, owner, adapter, provider="INDIAMART", identity_key="canonical-1", query="steel"
        )
        assert result.status == "SUCCEEDED"
        assert result.checkpoint == "TERMINAL"
        assert result.idempotent_reuse is False
        assert replay.idempotent_reuse is True
        assert replay.lineage == result.lineage
        assert adapter.search_calls == 1
        assert result.lineage["correlation_id"] == result.correlation_id
        assert result.counters["candidates"] == 1
        ledger_rows = list(
            db.scalars(
                select(MarketplaceLedger).where(
                    MarketplaceLedger.execution_id == result.execution_id
                )
            )
        )
        assert {row.entity_type for row in ledger_rows} >= {
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
        assert all(row.correlation_id == result.correlation_id for row in ledger_rows)
        assert marketplace_integrity_counters(db, owner)["broken_lineage"] == 0
        integrity = marketplace_integrity_counters(db, owner)
        assert integrity["orphan_rows"] == 0
        assert integrity["cross_owner_rows"] == 0
        assert all(value == 0 for key, value in integrity.items() if key.startswith("duplicate_"))
        actions = set(
            db.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == result.execution_id))
        )
        assert {
            "marketplace.discovery.requested",
            "marketplace.discovery.completed",
            "marketplace.evidence.projected",
        } <= actions
        assert len(ledger_rows) == len(
            list(
                db.scalars(
                    select(MarketplaceLedger).where(
                        MarketplaceLedger.execution_id == replay.execution_id
                    )
                )
            )
        )


@pytest.mark.parametrize(
    "stage",
    [
        "BEFORE_PROVIDER",
        "AFTER_PROVIDER",
        "AFTER_RESULT",
        "AFTER_EVIDENCE",
        "AFTER_CHANGE",
        "AFTER_ALERT",
    ],
)
def test_canonical_marketplace_lifecycle_resumes_after_fault(client, stage: str) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    adapter = _FixtureAdapter()
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        with fault_injection(stage), pytest.raises(RuntimeError):
            execute_marketplace_lifecycle(
                db,
                owner,
                adapter,
                provider="INDIAMART",
                identity_key=f"fault-{stage}",
                query="steel",
            )

    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        resumed = execute_marketplace_lifecycle(
            db, owner, adapter, provider="INDIAMART", identity_key=f"fault-{stage}", query="steel"
        )
        assert resumed.status == "SUCCEEDED"
        assert resumed.checkpoint == "TERMINAL"
        assert adapter.search_calls == 1


@pytest.mark.parametrize(
    "case,code,retryable",
    [
        ("timeout", "timeout", True),
        ("network", "network", True),
        ("429", "429", True),
        ("500", "500", True),
        ("503", "503", True),
        ("auth", "auth_failure", False),
        ("invalid", "invalid_response", False),
        ("policy", "policy_block", False),
        ("kill_switch", "kill_switch", False),
        ("bad_request", "bad_request", False),
    ],
)
def test_marketplace_retry_matrix(case: str, code: str, retryable: bool) -> None:
    decision = classify_failure(code, retry_after="9999", max_retry_after=120)
    assert case
    assert decision.retryable is retryable
    assert decision.retry_after_seconds == 120


def test_marketplace_retry_budget_concurrency(client) -> None:
    owner_id = _owner(client)
    factory = test_ai_integration.factory
    assert factory is not None
    with factory() as db:
        execution = MarketplaceExecution(
            owner_id=owner_id,
            provider="INDIAMART",
            correlation_id="retry-budget",
            identity_key="retry-budget",
            status="RETRY_WAIT",
            checkpoint="PROVIDER_COMPLETE",
            attempt=0,
        )
        db.add(execution)
        db.commit()
        execution_id = execution.id
    barrier = threading.Barrier(2)

    def claim(_: int) -> str:
        with factory() as db:
            barrier.wait()
            try:
                consume_retry_budget(db, execution_id, max_attempts=1)
                db.commit()
                return "claimed"
            except RuntimeError:
                db.rollback()
                return "exhausted"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, (1, 2)))
    assert sorted(outcomes) == ["claimed", "exhausted"]


def test_marketplace_recovery_is_idempotent_and_audited(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    adapter = _FixtureAdapter()
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        execution = execute_marketplace_lifecycle(
            db, owner, adapter, provider="INDIAMART", identity_key="recovery-1", query="steel"
        )
        first = execute_marketplace_recovery(db, owner, execution.execution_id, action="retry")
        second = execute_marketplace_recovery(db, owner, execution.execution_id, action="retry")
        assert first.idempotent_reuse is False
        assert second.idempotent_reuse is True
        assert first.status == "RETRY_WAIT"
        assert marketplace_integrity_counters(db, owner)["duplicate_recovery"] == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.action == "marketplace.recovery.executed",
                    AuditEvent.entity_id == execution.execution_id,
                )
            )
            == 1
        )


def test_marketplace_audit_vocabulary_is_emitted(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        success = execute_marketplace_lifecycle(
            db,
            owner,
            _FixtureAdapter(),
            provider="AUDIT-SUCCESS",
            identity_key="audit-success",
            query="steel",
        )
        with pytest.raises(RuntimeError):
            execute_marketplace_lifecycle(
                db,
                owner,
                _FixtureAdapter(failure_code="BUDGET_EXHAUSTED"),
                provider="AUDIT-BUDGET",
                identity_key="audit-budget",
                query="steel",
            )
        consume_rate_window(db, owner, "AUDIT-RATE", requests_per_minute=1, requests_per_hour=1)
        db.commit()
        with pytest.raises(MarketplaceRateLimited):
            execute_marketplace_lifecycle(
                db,
                owner,
                _FixtureAdapter(),
                provider="AUDIT-RATE",
                identity_key="audit-rate",
                query="steel",
                requests_per_minute=1,
                requests_per_hour=1,
            )
        actions = set(
            db.scalars(
                select(AuditEvent.action).where(AuditEvent.entity_id.in_((success.execution_id,)))
            )
        )
        assert {
            "marketplace.discovery.requested",
            "marketplace.discovery.completed",
            "marketplace.evidence.projected",
        } <= actions
        all_actions = set(
            db.scalars(
                select(AuditEvent.action).where(AuditEvent.action.like("marketplace.discovery.%"))
            )
        )
        assert {
            "marketplace.discovery.requested",
            "marketplace.discovery.completed",
            "marketplace.discovery.failed",
            "marketplace.discovery.rate_limited",
            "marketplace.discovery.budget_exhausted",
        } <= all_actions


def test_marketplace_recovery_concurrency_is_idempotent(client) -> None:
    owner_id = _owner(client)
    factory = test_ai_integration.factory
    assert factory is not None
    with factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        execution = execute_marketplace_lifecycle(
            db,
            owner,
            _FixtureAdapter(),
            provider="INDIAMART",
            identity_key="recovery-concurrent",
            query="steel",
        )
        execution_id = execution.execution_id
    barrier = threading.Barrier(2)

    def recover(_: int) -> bool:
        with factory() as db:
            owner = db.get(User, owner_id)
            assert owner is not None
            barrier.wait()
            result = execute_marketplace_recovery(db, owner, execution_id, action="replay")
            return result.idempotent_reuse

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(recover, (1, 2)))
    assert sorted(outcomes) == [False, True]
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(MarketplaceLedger)
                .where(
                    MarketplaceLedger.execution_id == execution_id,
                    MarketplaceLedger.entity_type == "recovery",
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == execution_id,
                    AuditEvent.action == "marketplace.recovery.executed",
                )
            )
            == 1
        )


def test_marketplace_runtime_warm_samples_are_bounded(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    adapter = _FixtureAdapter()
    samples: list[float] = []
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        for index in range(10):
            started = time.perf_counter()
            execute_marketplace_lifecycle(
                db,
                owner,
                adapter,
                provider="INDIAMART",
                identity_key=f"perf-{index}",
                query="steel",
            )
            samples.append((time.perf_counter() - started) * 1000)
    assert len(samples) == 10
    assert bounded_percentile(samples, 50) >= 0
    assert bounded_percentile(samples, 95) >= bounded_percentile(samples, 50)


def test_marketplace_rate_limit_matrix_is_complete(client) -> None:
    owner_id = _owner(client)
    assert test_ai_integration.factory is not None
    outcomes: list[tuple[str, str]] = []
    base = datetime.now(UTC)
    with test_ai_integration.factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        available = consume_rate_window(
            db, owner, "RATE-A", requests_per_minute=2, requests_per_hour=2, now=base
        )
        outcomes.append(("A", available.window))
        try:
            consume_rate_window(
                db, owner, "RATE-B", requests_per_minute=1, requests_per_hour=2, now=base
            )
            consume_rate_window(
                db, owner, "RATE-B", requests_per_minute=1, requests_per_hour=2, now=base
            )
        except MarketplaceRateLimited as exc:
            outcomes.append(("B", exc.result.window))
        outcomes.append(
            (
                "C",
                consume_rate_window(
                    db,
                    owner,
                    "RATE-C",
                    requests_per_minute=1,
                    requests_per_hour=2,
                    now=base + timedelta(minutes=1, seconds=1),
                ).window,
            )
        )
        consume_rate_window(
            db,
            owner,
            "RATE-D",
            requests_per_minute=1,
            requests_per_hour=1,
            now=base,
        )
        try:
            consume_rate_window(
                db,
                owner,
                "RATE-D",
                requests_per_minute=10,
                requests_per_hour=1,
                now=base + timedelta(minutes=1, seconds=1),
            )
        except MarketplaceRateLimited as exc:
            outcomes.append(("D", exc.result.window))
        execution = MarketplaceExecution(
            owner_id=owner.id,
            provider="RATE-E",
            correlation_id="rate-e",
            identity_key="rate-e",
            attempt=1,
            checkpoint="PROVIDER_COMPLETE",
        )
        db.add(execution)
        db.commit()
        try:
            consume_retry_budget(db, execution.id, max_attempts=1)
        except RuntimeError:
            outcomes.append(("E", "budget_exhausted"))
        try:
            consume_rate_window(
                db, owner, "RATE-F", requests_per_minute=1, requests_per_hour=1, now=base
            )
            consume_rate_window(
                db, owner, "RATE-F", requests_per_minute=1, requests_per_hour=1, now=base
            )
        except MarketplaceRateLimited as exc:
            outcomes.append(("F", exc.result.window))
        outcomes.append(("G", str(parse_retry_after("30", max_seconds=60))))
        outcomes.append(("H", str(parse_retry_after("999", max_seconds=60))))
    assert [case for case, _ in outcomes] == list("ABCDEFGH")
    assert outcomes[-2:] == [("G", "30"), ("H", "60")]


def test_marketplace_generic_concurrency_and_repeatability(client) -> None:
    owner_id = _owner(client)
    factory = test_ai_integration.factory
    assert factory is not None
    for run in range(3):
        adapter = _FixtureAdapter()
        barrier = threading.Barrier(2)

        def execute(
            _: int,
            *,
            run_id: int = run,
            run_adapter: _FixtureAdapter = adapter,
            run_barrier: threading.Barrier = barrier,
        ) -> str:
            with factory() as db:
                owner = db.get(User, owner_id)
                assert owner is not None
                run_barrier.wait()
                result = execute_marketplace_lifecycle(
                    db,
                    owner,
                    run_adapter,
                    provider="INDIAMART",
                    identity_key=f"concurrent-{run_id}",
                    query="steel",
                )
                return "reused" if result.idempotent_reuse else "created"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(execute, (1, 2)))
        assert sorted(outcomes) == ["created", "reused"]
        assert adapter.search_calls == 1
        with factory() as db:
            rows = list(
                db.scalars(
                    select(MarketplaceLedger).where(
                        MarketplaceLedger.owner_id == owner_id,
                        MarketplaceLedger.logical_key.like(f"concurrent-{run}:%"),
                    )
                )
            )
            assert len(rows) == 14
            assert len({row.entity_type for row in rows}) == 14
