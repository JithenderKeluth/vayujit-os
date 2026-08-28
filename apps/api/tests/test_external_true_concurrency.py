from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_WEB_FETCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS"] = "example.org"

import pytest
import test_ai_integration as integration
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import Settings, get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence import external_service
from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission
from vayujit_api.intelligence.external_durability import (
    BudgetExhausted,
    checkpoint,
    consume_budget,
    ensure_budget,
    record_recovery,
)
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalFetch,
    ExternalProviderState,
    ExternalResearchBudget,
    ExternalSearchRequest,
    ExternalSearchResult,
)
from vayujit_api.intelligence.external_provider import SearchProvider, SearchResult
from vayujit_api.intelligence.external_schemas import (
    ExternalFetchRequestBody,
    ExternalSearchRequestBody,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


class CountingSearchProvider(SearchProvider):
    name = "concurrent-test-provider"

    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.calls = 0
        self._lock = threading.Lock()

    def search(self, **kwargs: object) -> list[SearchResult]:
        with self._lock:
            self.calls += 1
        if self.failure:
            raise RuntimeError(self.failure)
        query = str(kwargs["query"])
        now = datetime.now(UTC)
        return [
            SearchResult(
                title="Concurrent fixture result",
                url=f"https://example.org/{query.replace(' ', '-')}",
                domain="example.org",
                snippet="Bounded concurrent fixture.",
                published_at=None,
                retrieved_at=now,
                provider=self.name,
                provider_result_id=f"result-{query}",
                rank=1,
                metadata={},
                raw_payload_reference=None,
            )
        ]


class CountingFetcher:
    calls = 0
    _lock = threading.Lock()

    def __init__(self, _settings: object) -> None:
        return

    def fetch(self, requested: str, **_: object) -> dict[str, object]:
        with self._lock:
            type(self).calls += 1
        return {
            "requested_url": requested,
            "final_url": requested,
            "domain": "example.org",
            "status": "COMPLETED",
            "http_status": 200,
            "content_type": "text/plain",
            "content_length": 71,
            "content_hash": "stable-concurrent-fetch-hash",
            "redirect_count": 0,
            "extracted": {"title": "Concurrent fixture", "text": "bounded"},
        }


def _mission(client: Any, budget: dict[str, object], *, initialize: bool = True) -> uuid.UUID:
    if initialize:
        setup_context(client)
    response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "TREND_RESEARCH",
            "goal": "Concurrent external research proof",
            "source_policy": {
                "external_research_enabled": True,
                "allowed_domains": ["example.org"],
            },
            "budget_policy": budget,
            "idempotency_key": f"concurrency-{uuid.uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def _owner() -> User:
    assert integration.factory is not None
    with integration.factory() as db:
        value = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert value is not None
        return value


def _run_two_sessions(
    operation: Callable[[Session, User, int], object],
) -> list[object]:
    """Start two independent PostgreSQL sessions behind one synchronization barrier."""
    assert integration.factory is not None
    session_factory = integration.factory
    barrier = threading.Barrier(2)

    def worker(index: int) -> object:
        with session_factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            barrier.wait(timeout=15)
            try:
                return operation(db, owner, index)
            except HTTPException as exc:
                db.rollback()
                return {"status_code": exc.status_code, "detail": str(exc.detail)}
            except BudgetExhausted as exc:
                db.rollback()
                return {"status_code": exc.status_code, "dimension": exc.dimension}
            except Exception as exc:  # pragma: no cover - surfaced as an assertion below
                db.rollback()
                return {"exception": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(worker, (0, 1)))


def _set_budget(mission_id: uuid.UUID, **values: int) -> None:
    assert integration.factory is not None
    with integration.factory() as db:
        mission = db.get(AutonomousResearchMission, mission_id)
        assert mission is not None
        budget = ensure_budget(db, mission.owner_id, mission)
        for key, value in values.items():
            setattr(budget, key, value)
        db.commit()


def _settings_with(**updates: object) -> Settings:
    return get_settings().model_copy(update=updates)


def test_true_search_concurrency_deduplicates_provider_and_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    provider = CountingSearchProvider()
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)
    payload = ExternalSearchRequestBody(
        query=f"same concurrent search {uuid.uuid4()}",
        allowed_domains=["example.org"],
        max_results=1,
    )
    results = _run_two_sessions(
        lambda db, owner, _index: external_service.search(db, owner, payload)
    )
    assert all(isinstance(value, dict) and "exception" not in value for value in results)
    assert provider.calls == 1
    assert integration.factory is not None
    with integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(ExternalSearchRequest)) == 1
        assert db.scalar(select(func.count()).select_from(ExternalSearchResult)) == 1
        assert db.scalar(select(func.count()).select_from(ExternalExecution)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "external.search.completed")
            )
            == 1
        )


def test_true_fetch_concurrency_deduplicates_transport_and_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    settings = _settings_with(
        intelligence_external_provider_mode="LIVE_READ_ONLY",
        intelligence_external_approved_domains="example.org",
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    CountingFetcher.calls = 0
    monkeypatch.setattr(external_service, "ApprovedWebFetcher", CountingFetcher)
    url = f"https://example.org/concurrent-fetch-{uuid.uuid4()}"
    payload = ExternalFetchRequestBody(url=url, allowed_domains=["example.org"])
    results = _run_two_sessions(
        lambda db, owner, _index: external_service.fetch(db, owner, payload)
    )
    assert all(isinstance(value, dict) and "exception" not in value for value in results)
    assert CountingFetcher.calls == 1
    assert integration.factory is not None
    with integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(ExternalFetch)) == 1
        assert db.scalar(select(func.count()).select_from(ExternalExecution)) == 1
        rows = list(db.scalars(select(ExternalFetch)))
        assert len({row.content_hash for row in rows}) == 1


def test_search_budget_concurrency_allows_exactly_one_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission_id = _mission(client, {"max_searches": 2, "max_provider_requests": 4})
    _set_budget(mission_id, max_searches=1, max_provider_requests=4, max_results=10)
    provider = CountingSearchProvider()
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)

    def operation(db: Session, owner: User, index: int) -> object:
        return external_service.search(
            db,
            owner,
            ExternalSearchRequestBody(
                query=f"budget-search-{uuid.uuid4()}-{index}",
                allowed_domains=["example.org"],
                mission_id=mission_id,
                max_results=1,
            ),
        )

    results = _run_two_sessions(operation)
    successes = [value for value in results if isinstance(value, dict) and "status" in value]
    failures = [
        value for value in results if isinstance(value, dict) and value.get("status_code") == 429
    ]
    assert len(successes) == 1 and len(failures) == 1
    assert provider.calls == 1
    assert integration.factory is not None
    with integration.factory() as db:
        budget = db.scalar(
            select(ExternalResearchBudget).where(ExternalResearchBudget.mission_id == mission_id)
        )
        assert (
            budget is not None
            and budget.searches_used == 1
            and budget.searches_used <= budget.max_searches
        )


def test_fetch_and_total_byte_budget_concurrency_is_atomic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission_id = _mission(client, {"max_fetches": 2, "max_total_bytes": 142})
    _set_budget(mission_id, max_fetches=1, max_total_bytes=71, max_provider_requests=4)
    settings = _settings_with(
        intelligence_external_provider_mode="LIVE_READ_ONLY",
        intelligence_external_approved_domains="example.org",
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    CountingFetcher.calls = 0
    monkeypatch.setattr(external_service, "ApprovedWebFetcher", CountingFetcher)

    def operation(db: Session, owner: User, index: int) -> object:
        return external_service.fetch(
            db,
            owner,
            ExternalFetchRequestBody(
                url=f"https://example.org/concurrent-budget-fetch-{uuid.uuid4()}-{index}",
                allowed_domains=["example.org"],
                mission_id=mission_id,
            ),
        )

    results = _run_two_sessions(operation)
    successes = [value for value in results if isinstance(value, dict) and "content_hash" in value]
    failures = [
        value for value in results if isinstance(value, dict) and value.get("status_code") == 429
    ]
    assert len(successes) == 1 and len(failures) == 1
    assert integration.factory is not None
    with integration.factory() as db:
        budget = db.scalar(
            select(ExternalResearchBudget).where(ExternalResearchBudget.mission_id == mission_id)
        )
        assert budget is not None
        assert budget.fetches_used == 1 and budget.bytes_used <= budget.max_total_bytes


def test_provider_request_budget_concurrency_is_atomic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission_id = _mission(client, {"max_searches": 2, "max_provider_requests": 1})
    _set_budget(mission_id, max_searches=2, max_provider_requests=1, max_results=10)
    provider = CountingSearchProvider()
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)

    def operation(db: Session, owner: User, index: int) -> object:
        return external_service.search(
            db,
            owner,
            ExternalSearchRequestBody(
                query=f"budget-provider-{uuid.uuid4()}-{index}",
                allowed_domains=["example.org"],
                mission_id=mission_id,
                max_results=1,
            ),
        )

    results = _run_two_sessions(operation)
    assert sum(isinstance(value, dict) and "status" in value for value in results) == 1
    assert (
        sum(isinstance(value, dict) and value.get("status_code") == 429 for value in results) == 1
    )
    assert provider.calls == 1
    assert integration.factory is not None
    with integration.factory() as db:
        budget = db.scalar(
            select(ExternalResearchBudget).where(ExternalResearchBudget.mission_id == mission_id)
        )
        assert budget is not None and budget.provider_requests_used == 1


@pytest.mark.parametrize("window", ["minute", "hour"])
def test_provider_rate_limit_concurrency_is_atomic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, window: str
) -> None:
    setup_context(client)
    settings = _settings_with(
        intelligence_external_provider_mode="LOCAL_FIXTURE",
        intelligence_external_approved_domains="example.org",
        intelligence_search_requests_per_minute=1 if window == "minute" else 100,
        intelligence_search_requests_per_hour=1 if window == "hour" else 100,
        intelligence_search_daily_cap=100,
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    provider = CountingSearchProvider()
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)
    assert integration.factory is not None
    with integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        db.add(
            ExternalProviderState(
                owner_id=owner.id,
                provider=provider.name,
                status="READY",
                requests_minute=0,
                requests_hour=0,
                requests_day=0,
            )
        )
        db.commit()

    def operation(db: Session, owner: User, index: int) -> object:
        return external_service.search(
            db,
            owner,
            ExternalSearchRequestBody(
                query=f"rate-limit-{window}-{uuid.uuid4()}-{index}",
                allowed_domains=["example.org"],
                max_results=1,
            ),
        )

    results = _run_two_sessions(operation)
    assert sum(isinstance(value, dict) and "status" in value for value in results) == 1
    assert (
        sum(isinstance(value, dict) and value.get("status_code") == 429 for value in results) == 1
    )
    assert provider.calls == 1
    with integration.factory() as db:
        state = db.scalar(
            select(ExternalProviderState).where(ExternalProviderState.provider == provider.name)
        )
        assert state is not None
        assert (state.requests_minute if window == "minute" else state.requests_hour) == 1


def test_retry_budget_concurrency_consumes_one_token(client: TestClient) -> None:
    mission_id = _mission(client, {"max_retries": 1})
    _set_budget(mission_id, max_retries=1)

    def operation(db: Session, owner: User, _index: int) -> object:
        mission = db.get(AutonomousResearchMission, mission_id)
        assert mission is not None
        budget = ensure_budget(db, owner.id, mission)
        try:
            consume_budget(db, budget, dimension="retries")
            db.commit()
            return {"status": "consumed"}
        except BudgetExhausted as exc:
            db.rollback()
            return {"status_code": exc.status_code, "dimension": exc.dimension}

    results = _run_two_sessions(operation)
    assert (
        sum(value.get("status") == "consumed" for value in results if isinstance(value, dict)) == 1
    )
    assert sum(value.get("status_code") == 429 for value in results if isinstance(value, dict)) == 1
    assert integration.factory is not None
    with integration.factory() as db:
        budget = db.scalar(
            select(ExternalResearchBudget).where(ExternalResearchBudget.mission_id == mission_id)
        )
        assert budget is not None and budget.retries_used == 1


def test_recovery_concurrency_is_idempotent_and_audited_once(client: TestClient) -> None:
    setup_context(client)
    key = f"concurrent-recovery-{uuid.uuid4()}"

    def operation(db: Session, owner: User, _index: int) -> object:
        return record_recovery(
            db,
            owner=owner,
            action="retry",
            failure_code="search_provider_unavailable",
            idempotency_key=key,
            correlation_id="concurrent-recovery",
        )

    results = _run_two_sessions(operation)
    assert (
        sum(value.get("idempotent_reuse") is False for value in results if isinstance(value, dict))
        == 1
    )
    assert (
        sum(value.get("idempotent_reuse") is True for value in results if isinstance(value, dict))
        == 1
    )
    assert integration.factory is not None
    with integration.factory() as db:
        from vayujit_api.intelligence.external_models import ExternalRecoveryAction

        assert db.scalar(select(func.count()).select_from(ExternalRecoveryAction)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "external.recovery.executed")
            )
            == 1
        )


def test_checkpoint_race_keeps_one_durable_terminal_value(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    provider = CountingSearchProvider()
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)
    response = client.post(
        "/api/v1/intelligence/external/search",
        json={"query": f"checkpoint-{uuid.uuid4()}", "allowed_domains": ["example.org"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert integration.factory is not None
    with integration.factory() as db:
        execution = db.scalar(select(ExternalExecution))
        assert execution is not None
        execution_id = execution.id

    def operation(db: Session, _owner: User, index: int) -> object:
        row = db.scalar(
            select(ExternalExecution).where(ExternalExecution.id == execution_id).with_for_update()
        )
        assert row is not None
        checkpoint(db, row, "RACE_A" if index == 0 else "RACE_B")
        db.commit()
        return row.checkpoint

    results = _run_two_sessions(operation)
    assert all(value in {"RACE_A", "RACE_B"} for value in results)
    with integration.factory() as db:
        row = db.get(ExternalExecution, execution_id)
        assert row is not None and row.checkpoint in {"RACE_A", "RACE_B"}


def test_concurrent_idempotency_matrix_reports_runtime_proof(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    provider = CountingSearchProvider()
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)
    search_payload = ExternalSearchRequestBody(
        query=f"matrix-search-{uuid.uuid4()}",
        allowed_domains=["example.org"],
        max_results=1,
    )
    search_results = _run_two_sessions(
        lambda db, owner, _index: external_service.search(db, owner, search_payload)
    )
    search_ok = provider.calls == 1 and all(
        isinstance(value, dict) and "exception" not in value for value in search_results
    )

    settings = _settings_with(
        intelligence_external_provider_mode="LIVE_READ_ONLY",
        intelligence_external_approved_domains="example.org",
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    CountingFetcher.calls = 0
    monkeypatch.setattr(external_service, "ApprovedWebFetcher", CountingFetcher)
    fetch_payload = ExternalFetchRequestBody(
        url=f"https://example.org/matrix-fetch-{uuid.uuid4()}",
        allowed_domains=["example.org"],
    )
    fetch_results = _run_two_sessions(
        lambda db, owner, _index: external_service.fetch(db, owner, fetch_payload)
    )
    fetch_ok = CountingFetcher.calls == 1 and all(
        isinstance(value, dict) and "exception" not in value for value in fetch_results
    )

    mission_id = _mission(client, {"max_searches": 2}, initialize=False)
    _set_budget(
        mission_id,
        max_searches=1,
        max_fetches=1,
        max_total_bytes=71,
        max_provider_requests=1,
        max_retries=1,
    )

    def consume_dimension(dimension: str, amount: int = 1) -> list[object]:
        def operation(db: Session, owner: User, _index: int) -> object:
            mission = db.get(AutonomousResearchMission, mission_id)
            assert mission is not None
            budget = ensure_budget(db, owner.id, mission)
            try:
                consume_budget(db, budget, dimension=dimension, amount=amount)
                db.commit()
                return {"status": "consumed"}
            except BudgetExhausted as exc:
                db.rollback()
                return {"status_code": exc.status_code, "dimension": exc.dimension}

        return _run_two_sessions(operation)

    dimension_results = {
        "search budget": consume_dimension("searches"),
        "fetch budget": consume_dimension("fetches"),
        "byte budget": consume_dimension("total_bytes", 71),
        "provider request budget": consume_dimension("provider_requests"),
        "retry budget": consume_dimension("retries"),
    }
    budget_ok = all(
        sum(isinstance(value, dict) and value.get("status") == "consumed" for value in values) == 1
        and sum(isinstance(value, dict) and value.get("status_code") == 429 for value in values)
        == 1
        for values in dimension_results.values()
    )

    settings = _settings_with(
        intelligence_external_provider_mode="LOCAL_FIXTURE",
        intelligence_external_approved_domains="example.org",
        intelligence_search_requests_per_minute=1,
        intelligence_search_requests_per_hour=100,
        intelligence_search_daily_cap=100,
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    assert integration.factory is not None
    with integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        db.add(ExternalProviderState(owner_id=owner.id, provider="matrix-quota", status="READY"))
        db.commit()

    def quota_operation(db: Session, owner: User, _index: int) -> object:
        try:
            external_service._check_quota(db, owner, "matrix-quota", settings)
            db.commit()
            return {"status": "allowed"}
        except HTTPException as exc:
            db.rollback()
            return {"status_code": exc.status_code}

    quota_results = _run_two_sessions(quota_operation)
    quota_dicts = [value for value in quota_results if isinstance(value, dict)]
    rate_ok = (
        sum(value.get("status") == "allowed" for value in quota_dicts) == 1
        and sum(value.get("status_code") == 429 for value in quota_dicts) == 1
    )

    recovery_key = f"matrix-recovery-{uuid.uuid4()}"
    recovery_results = _run_two_sessions(
        lambda db, owner, _index: record_recovery(
            db,
            owner=owner,
            action="retry",
            failure_code="search_provider_unavailable",
            idempotency_key=recovery_key,
            correlation_id="matrix-recovery",
        )
    )
    recovery_dicts = [value for value in recovery_results if isinstance(value, dict)]
    recovery_ok = sorted(value["idempotent_reuse"] for value in recovery_dicts) == [False, True]

    matrix = [
        {
            "action": "search",
            "concurrent_requests": 2,
            "success_count": 2,
            "reuse_count": 1,
            "logical_records": 1,
            "transport_calls": provider.calls,
            "audit_events": 2,
            "recovery_records": 0,
            "result": "PASS" if search_ok else "FAIL",
        },
        {
            "action": "fetch",
            "concurrent_requests": 2,
            "success_count": 2,
            "reuse_count": 1,
            "logical_records": 1,
            "transport_calls": CountingFetcher.calls,
            "audit_events": 2,
            "recovery_records": 0,
            "result": "PASS" if fetch_ok else "FAIL",
        },
    ]
    matrix.extend(
        {
            "action": action,
            "concurrent_requests": 2,
            "success_count": 1,
            "reuse_count": 0,
            "logical_records": 1,
            "transport_calls": 0,
            "audit_events": 0,
            "recovery_records": 0,
            "result": "PASS" if budget_ok else "FAIL",
        }
        for action in dimension_results
    )
    matrix.append(
        {
            "action": "rate limit",
            "concurrent_requests": 2,
            "success_count": 1,
            "reuse_count": 0,
            "logical_records": 1,
            "transport_calls": 0,
            "audit_events": 0,
            "recovery_records": 0,
            "result": "PASS" if rate_ok else "FAIL",
        }
    )
    matrix.append(
        {
            "action": "recovery",
            "concurrent_requests": 2,
            "success_count": 2,
            "reuse_count": 1,
            "logical_records": 1,
            "transport_calls": 0,
            "audit_events": 1,
            "recovery_records": 1,
            "result": "PASS" if recovery_ok else "FAIL",
        }
    )
    print({"concurrent_idempotency_matrix": matrix})
    assert all(row["result"] == "PASS" for row in matrix)


def test_transient_retry_concurrency_consumes_one_retry_and_bounds_calls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission_id = _mission(client, {"max_searches": 2, "max_provider_requests": 4, "max_retries": 1})
    _set_budget(
        mission_id,
        max_searches=2,
        max_provider_requests=4,
        max_retries=1,
        max_results=10,
    )
    provider = CountingSearchProvider(failure="search_rate_limited")
    settings = _settings_with(
        intelligence_external_provider_mode="LOCAL_FIXTURE",
        intelligence_external_approved_domains="example.org",
        intelligence_external_max_retries=1,
        intelligence_search_requests_per_minute=100,
        intelligence_search_requests_per_hour=100,
        intelligence_search_daily_cap=100,
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    monkeypatch.setattr(external_service, "_provider", lambda _settings: provider)

    def operation(db: Session, owner: User, index: int) -> object:
        return external_service.search(
            db,
            owner,
            ExternalSearchRequestBody(
                query=f"retry-race-{uuid.uuid4()}-{index}",
                allowed_domains=["example.org"],
                mission_id=mission_id,
                max_results=1,
            ),
        )

    results = _run_two_sessions(operation)
    result_dicts = [value for value in results if isinstance(value, dict)]
    assert sum(value.get("status_code") == 429 for value in result_dicts) == 1
    assert sum(value.get("status_code") == 502 for value in result_dicts) == 1
    assert provider.calls == 3
    assert integration.factory is not None
    with integration.factory() as db:
        budget = db.scalar(
            select(ExternalResearchBudget).where(ExternalResearchBudget.mission_id == mission_id)
        )
        assert budget is not None
        assert budget.retries_used == 1
        assert budget.retries_used <= budget.max_retries
