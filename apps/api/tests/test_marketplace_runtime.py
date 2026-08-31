from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
import test_ai_integration
from sqlalchemy import select
from test_ai_integration import setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.marketplace_runtime import (
    CHECKPOINTS,
    MarketplaceExecution,
    MarketplaceRateLimited,
    bounded_percentile,
    checkpoint,
    classify_failure,
    consume_rate_window,
    execute_marketplace_lifecycle,
    fault_injection,
    inject_test_fault,
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
    def __init__(self) -> None:
        self.search_calls = 0
        self.normalize_calls = 0

    def preflight(self) -> dict[str, object]:
        return {"status": "LOCAL_FIXTURE"}

    def search(self, query: str) -> object:
        self.search_calls += 1
        return {"query": query, "items": [{"id": "candidate-1"}]}

    def normalize(self, payload: object) -> list[dict[str, object]]:
        self.normalize_calls += 1
        return list(payload.get("items", [])) if isinstance(payload, dict) else []

    def classify_failure(self, error: Exception) -> str:
        return "TIMEOUT" if "timeout" in str(error) else "INVALID_RESPONSE"


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
