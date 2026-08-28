# ruff: noqa: E501,E702,F401,I001
from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import Settings, get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_durability import (
    BudgetExhausted,
    checkpoint,
    claim_execution,
    consume_budget,
    ensure_budget,
    execution_identity,
)
from vayujit_api.intelligence.external_evidence import derive_freshness
from vayujit_api.intelligence.external_models import (
    ExternalFetch,
    ExternalProviderState,
    ExternalSearchRequest,
    ExternalSearchResult,
    ExternalSourceProfile,
)
from vayujit_api.intelligence.external_pipeline import verify_and_project
from vayujit_api.intelligence.external_provider import (
    ApprovedWebFetcher,
    BraveSearchProvider,
    HttpSearchProvider,
    LocalFixtureSearchProvider,
    SearchProvider,
    canonical_url,
    host_of,
)
from vayujit_api.intelligence.external_schemas import (
    ExternalFetchRequestBody,
    ExternalSearchRequestBody,
)

ALLOWED_MODES = ("DISABLED", "LOCAL_FIXTURE", "SANDBOX", "LIVE_READ_ONLY")
ALLOWED_MISSION_TYPES = {
    "PRODUCT_VALIDATION",
    "TREND_RESEARCH",
    "COMPETITOR_RESEARCH",
    "PRICING_RESEARCH",
    "SUPPLIER_VERIFICATION",
}


def _mission_context(
    db: Session,
    owner: User,
    *,
    mission_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    operation: str,
) -> tuple[AutonomousResearchMission | None, AutonomousResearchTask | None]:
    if task_id is not None and mission_id is None:
        raise HTTPException(422, "A task requires an owner-scoped mission.")
    mission = None
    task = None
    if mission_id is not None:
        mission = db.scalar(
            select(AutonomousResearchMission).where(
                AutonomousResearchMission.id == mission_id,
                AutonomousResearchMission.owner_id == owner.id,
            )
        )
        if mission is None:
            raise HTTPException(404, "Autonomous research mission not found.")
        if mission.mission_type not in ALLOWED_MISSION_TYPES:
            raise HTTPException(403, "External research is not allowed for this mission type.")
        if mission.source_policy.get("external_research_enabled") is not True:
            raise HTTPException(403, "External research is not enabled for this mission.")
    if task_id is not None:
        task = db.scalar(
            select(AutonomousResearchTask).where(
                AutonomousResearchTask.id == task_id,
                AutonomousResearchTask.owner_id == owner.id,
                AutonomousResearchTask.mission_id == mission_id,
            )
        )
        if task is None:
            raise HTTPException(404, "Autonomous research task not found.")
    if mission is not None:
        ensure_budget(db, owner.id, mission)
    return mission, task


def _settings() -> Settings:
    return get_settings()


def _domains(raw: str) -> tuple[str, ...]:
    return tuple(item.strip().lower().rstrip(".") for item in raw.split(",") if item.strip())


def _domain_matches(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _source_policy_allowed(
    host: str,
    *,
    profile: ExternalSourceProfile | None,
    settings: Settings,
) -> tuple[str, str]:
    robots = str(profile.robots_policy if profile is not None else "UNKNOWN").upper()
    terms = str(profile.terms_status if profile is not None else "UNKNOWN").upper()
    if robots == "MANUAL_REVIEW_REQUIRED":
        robots = "REVIEW_REQUIRED"
    if terms == "MANUAL_REVIEW_REQUIRED":
        terms = "REVIEW_REQUIRED"
    review_domains = _domains(settings.intelligence_external_review_required_domains)
    if _domain_matches(host, review_domains):
        raise HTTPException(403, "External source requires manual review.")
    if profile is not None and (
        robots in {"NOT_APPROVED", "REVIEW_REQUIRED", "MANUAL_REVIEW_REQUIRED"}
        or terms in {"NOT_APPROVED", "REVIEW_REQUIRED", "MANUAL_REVIEW_REQUIRED"}
    ):
        raise HTTPException(403, "External source policy does not permit this fetch.")
    if settings.intelligence_external_require_source_approval and (
        robots != "APPROVED" or terms != "APPROVED"
    ):
        raise HTTPException(403, "External source approval is required before fetching.")
    return robots, terms


def _effective_allowed(requested: tuple[str, ...], configured: tuple[str, ...]) -> tuple[str, ...]:
    if requested and configured:
        return tuple(item for item in requested if item in configured)
    return requested or configured


def _identity(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


def _provider(settings: Settings) -> SearchProvider:
    if settings.intelligence_external_provider_mode in {"LOCAL_FIXTURE", "SANDBOX"}:
        return LocalFixtureSearchProvider()
    if settings.intelligence_search_provider.lower() == "brave":
        return BraveSearchProvider(settings)
    return HttpSearchProvider(settings)


def provider_preflight(settings: Settings | None = None) -> dict[str, object]:
    """Return safe live-provider readiness without persisting payloads."""
    settings = settings or _settings()
    credential_status = (
        "CONFIGURED" if settings.intelligence_search_provider_api_key else "NOT_CONFIGURED"
    )
    base = {
        "provider": settings.intelligence_search_provider,
        "mode": settings.intelligence_external_provider_mode,
        "credential_status": credential_status,
        "live": False,
    }
    if settings.intelligence_external_provider_mode != "LIVE_READ_ONLY":
        return base | {
            "status": (
                "DISABLED"
                if settings.intelligence_external_provider_mode == "DISABLED"
                else "NOT_VALIDATED"
            )
        }
    if not (
        settings.intelligence_enabled
        and settings.intelligence_external_research_enabled
        and settings.intelligence_search_provider_enabled
    ):
        return base | {"status": "BLOCKED_BY_CONFIGURATION"}
    if not settings.intelligence_search_provider_api_key:
        return base | {"status": "BLOCKED_BY_EXTERNAL_CREDENTIALS"}
    if settings.intelligence_search_provider.lower() != "brave":
        return base | {"status": "UNAVAILABLE"}
    return BraveSearchProvider(settings).preflight()


def approved_fetch_preflight(settings: Settings | None = None) -> dict[str, object]:
    """Return a non-network readiness report for approved live web fetch."""
    settings = settings or _settings()
    approved = _domains(settings.intelligence_external_approved_domains)
    blocked = _domains(settings.intelligence_external_blocked_domains)
    review = _domains(settings.intelligence_external_review_required_domains)
    checks = {
        "mode": settings.intelligence_external_provider_mode == "LIVE_READ_ONLY",
        "global_external": settings.intelligence_external_research_enabled,
        "approved_fetch": settings.intelligence_web_fetch_enabled,
        "allowlist": bool(approved),
        "emergency_stop": not settings.external_mutations_emergency_stop,
        "kill_switch": not settings.intelligence_external_kill_switch,
        "tls": True,
        "byte_limit": settings.intelligence_fetch_max_bytes > 0,
        "redirect_limit": settings.intelligence_fetch_max_redirects >= 0,
    }
    if settings.intelligence_external_provider_mode != "LIVE_READ_ONLY":
        status = (
            "DISABLED"
            if settings.intelligence_external_provider_mode == "DISABLED"
            else "NOT_READY"
        )
    elif not all(checks.values()):
        status = "BLOCKED_BY_EXTERNAL_CONFIGURATION"
    else:
        status = "READY"
    return {
        "status": status,
        "mode": settings.intelligence_external_provider_mode,
        "approved_domains": list(approved),
        "blocked_domains": list(blocked),
        "review_required_domains": list(review),
        "approved_domain_count": len(approved),
        "tls_required": True,
        "max_redirects": settings.intelligence_fetch_max_redirects,
        "max_response_bytes": settings.intelligence_fetch_max_bytes,
        "user_agent": settings.intelligence_external_fetch_user_agent,
        "checks": checks,
        "external_calls": False,
    }


def _guard(settings: Settings, *, operation: str) -> None:
    if settings.external_mutations_emergency_stop or settings.intelligence_external_kill_switch:
        raise HTTPException(409, "External research is disabled by the emergency stop.")
    if settings.intelligence_external_provider_mode == "DISABLED":
        raise HTTPException(403, "External research is disabled.")
    if settings.intelligence_external_provider_mode == "LIVE_READ_ONLY" and not (
        settings.intelligence_enabled
        and settings.intelligence_external_research_enabled
        and settings.intelligence_search_provider_enabled
    ):
        raise HTTPException(403, "Live read-only search is blocked by configuration.")
    if operation == "search" and settings.intelligence_search_provider_kill_switch:
        raise HTTPException(409, "Search provider is disabled.")
    if operation == "fetch" and not settings.intelligence_web_fetch_enabled:
        raise HTTPException(403, "Approved web fetch is disabled.")
    if (
        settings.intelligence_external_provider_mode == "LIVE_READ_ONLY"
        and not settings.intelligence_external_approved_domains
    ):
        raise HTTPException(403, "Approved external domains are required for live research.")


def _check_quota(
    db: Session, owner: User, provider: str, settings: Settings
) -> ExternalProviderState:
    state = db.scalar(
        select(ExternalProviderState)
        .where(
            ExternalProviderState.owner_id == owner.id, ExternalProviderState.provider == provider
        )
        .with_for_update()
    )
    if state is None:
        state = ExternalProviderState(owner_id=owner.id, provider=provider, status="READY")
        db.add(state)
        db.flush()
    if state.disabled:
        raise HTTPException(409, "Search provider is disabled.")
    if (
        state.requests_minute >= settings.intelligence_search_requests_per_minute
        or state.requests_hour >= settings.intelligence_search_requests_per_hour
        or state.requests_day >= settings.intelligence_search_daily_cap
    ):
        state.status = "RATE_LIMITED"
        state.last_failure = "search_rate_limited"
        db.commit()
        raise HTTPException(429, "Search quota exceeded.")
    state.requests_minute += 1
    state.requests_hour += 1
    state.requests_day += 1
    return state


def search(db: Session, owner: User, data: ExternalSearchRequestBody) -> dict[str, object]:
    settings = _settings()
    mission, _task = _mission_context(
        db, owner, mission_id=data.mission_id, task_id=data.task_id, operation="search"
    )
    _guard(settings, operation="search")
    if not data.query.strip() or any(
        marker in data.query.lower()
        for marker in ("api_key", "authorization", "password", "token:")
    ):
        raise HTTPException(422, "Search query is not safe.")
    allowed = _effective_allowed(
        tuple(data.allowed_domains), _domains(settings.intelligence_external_approved_domains)
    )
    if mission is not None:
        mission_allowed = mission.source_policy.get("allowed_domains", [])
        if isinstance(mission_allowed, list):
            allowed = _effective_allowed(
                allowed, tuple(str(item).lower() for item in mission_allowed)
            )
    blocked = tuple(data.excluded_domains) + _domains(
        settings.intelligence_external_blocked_domains
    )
    provider = _provider(settings)
    identity = _identity(
        f"{provider.name}|{data.query.strip().lower()}|{data.market}|{data.language}|{data.max_results}|{allowed}|{blocked}|{data.mission_id}|{data.task_id}"
    )
    existing = db.scalar(
        select(ExternalSearchRequest).where(
            ExternalSearchRequest.owner_id == owner.id,
            ExternalSearchRequest.identity_key == identity,
        )
    )
    if existing is not None:
        results = list(
            db.scalars(
                select(ExternalSearchResult)
                .where(ExternalSearchResult.search_id == existing.id)
                .order_by(ExternalSearchResult.rank)
            )
        )
        return {
            "id": existing.id,
            "status": existing.status,
            "provider": existing.provider,
            "mode": existing.mode,
            "result_count": existing.result_count,
            "failure_code": existing.failure_code,
            "results": results,
        }
    execution_key = execution_identity(
        "search",
        owner_id=owner.id,
        mission_id=data.mission_id,
        task_id=data.task_id,
        value=identity,
    )
    execution, claimed = claim_execution(
        db,
        owner=owner,
        kind="search",
        identity_key=execution_key,
        provider=provider.name,
        mission_id=data.mission_id,
        task_id=data.task_id,
        correlation_id=data.correlation_id or str(uuid.uuid4()),
    )
    if not claimed:
        if execution.status == "COMPLETED":
            existing = db.scalar(
                select(ExternalSearchRequest).where(
                    ExternalSearchRequest.owner_id == owner.id,
                    ExternalSearchRequest.identity_key == identity,
                )
            )
            if existing is not None:
                results = list(
                    db.scalars(
                        select(ExternalSearchResult)
                        .where(ExternalSearchResult.search_id == existing.id)
                        .order_by(ExternalSearchResult.rank)
                    )
                )
                return {
                    "id": existing.id,
                    "status": existing.status,
                    "provider": existing.provider,
                    "mode": existing.mode,
                    "result_count": existing.result_count,
                    "failure_code": existing.failure_code,
                    "results": results,
                }
        if execution.status in {"RUNNING", "QUEUED"}:
            raise HTTPException(409, "External search execution is already in progress.")
    if claimed:
        checkpoint(db, execution, "BEFORE_PROVIDER")
    budget = ensure_budget(db, owner.id, mission) if mission is not None else None
    if budget is not None:
        try:
            consume_budget(db, budget, dimension="searches")
            consume_budget(db, budget, dimension="provider_requests")
            if budget.results_used >= budget.max_results:
                raise BudgetExhausted("results", budget.results_used, budget.max_results)
        except BudgetExhausted as exc:
            execution.status = "FAILED"
            execution.failure_code = "budget_exhausted"
            execution.safe_error_message = "External research budget exhausted safely."
            checkpoint(db, execution, "TERMINAL", status="FAILED")
            record_event(
                db,
                actor_id=owner.id,
                action="external.search.budget_exhausted",
                entity_type="external_search_execution",
                entity_id=execution.id,
                metadata={"dimension": exc.dimension, "used": exc.used, "maximum": exc.maximum},
                idempotency_key=f"external-search:{execution.id}:budget",
            )
            db.commit()
            raise
    try:
        _check_quota(db, owner, provider.name, settings)
    except HTTPException as exc:
        failure_code = "search_rate_limited" if exc.status_code == 429 else "provider_disabled"
        execution.status = "FAILED"
        execution.failure_code = failure_code
        execution.safe_error_message = (
            "External search quota or provider policy rejected the request."
        )
        checkpoint(db, execution, "TERMINAL", status="FAILED")
        record_event(
            db,
            actor_id=owner.id,
            action=(
                "external.search.rate_limited"
                if exc.status_code == 429
                else "external.search.provider_disabled"
            ),
            entity_type="external_search_execution",
            entity_id=execution.id,
            metadata={"failure_code": failure_code},
            idempotency_key=f"external-search:{execution.id}:quota",
        )
        db.commit()
        raise
    correlation = data.correlation_id or str(uuid.uuid4())
    request = ExternalSearchRequest(
        owner_id=owner.id,
        mission_id=data.mission_id,
        task_id=data.task_id,
        query=data.query.strip(),
        market=data.market,
        language=data.language,
        max_results=data.max_results,
        safe_search=data.safe_search,
        source_categories=data.source_categories,
        allowed_domains=list(allowed),
        excluded_domains=list(blocked),
        provider=provider.name,
        mode=settings.intelligence_external_provider_mode,
        status="RUNNING",
        correlation_id=correlation,
        identity_key=identity,
    )
    db.add(request)
    try:
        db.flush()
        record_event(
            db,
            actor_id=owner.id,
            action="external.search.requested",
            entity_type="external_search",
            entity_id=request.id,
            metadata={"provider": provider.name, "mode": request.mode},
            idempotency_key=f"external-search:{request.id}:requested",
        )
    except IntegrityError:
        db.rollback()
        return search(db, owner, data)
    try:
        for attempt in range(settings.intelligence_external_max_retries + 1):
            if attempt > 0 and budget is not None:
                consume_budget(db, budget, dimension="retries")
                consume_budget(db, budget, dimension="provider_requests")
            try:
                _guard(_settings(), operation="search")
                execution.provider_calls += 1
                values = provider.search(
                    query=request.query,
                    market=request.market,
                    language=request.language,
                    max_results=request.max_results,
                    safe_search=request.safe_search,
                    source_categories=tuple(request.source_categories),
                    allowed_domains=allowed,
                    excluded_domains=blocked,
                    correlation_id=correlation,
                )
                break
            except RuntimeError as exc:
                retryable = str(exc) in {
                    "search_rate_limited",
                    "search_provider_unavailable",
                    "search_timeout",
                    "search_network_failed",
                }
                if not retryable or attempt >= settings.intelligence_external_max_retries:
                    raise
                retry_after = getattr(exc, "retry_after", None)
                delay = (
                    retry_after
                    if isinstance(retry_after, (int, float))
                    else settings.intelligence_external_retry_backoff_seconds * (2**attempt)
                )
                time.sleep(min(float(delay), 5))
        checkpoint(db, execution, "PROVIDER_COMPLETE")
        rows: list[ExternalSearchResult] = []
        seen: set[str] = set()
        result_limit = request.max_results
        if budget is not None:
            result_limit = min(result_limit, max(0, budget.max_results - budget.results_used))
        for item in values[:result_limit]:
            url = canonical_url(item.url)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                ExternalSearchResult(
                    owner_id=owner.id,
                    search_id=request.id,
                    title=item.title[:500],
                    url=url,
                    canonical_url=url,
                    domain=host_of(url),
                    snippet=item.snippet[:2000],
                    published_at=item.published_at,
                    provider=item.provider,
                    provider_result_id=item.provider_result_id,
                    rank=item.rank,
                    metadata_json={"safe_search": request.safe_search},
                    raw_payload_reference=None,
                    source_classification="SEARCH_DISCOVERY_RESULT",
                    content_hash=hashlib.sha256((item.title + item.snippet).encode()).hexdigest(),
                    identity_key=_identity(f"{provider.name}|{item.provider_result_id}|{url}"),
                )
            )
        if budget is not None and rows:
            bounded_rows: list[ExternalSearchResult] = []
            known_domains = set(budget.domains_seen or [])
            new_domains: set[str] = set()
            for row in rows:
                if row.domain not in known_domains and row.domain not in new_domains:
                    if budget.domains_used + len(new_domains) >= budget.max_domains:
                        continue
                    new_domains.add(row.domain)
                bounded_rows.append(row)
            rows = bounded_rows
            consume_budget(db, budget, dimension="results", amount=len(rows))
            for _domain in new_domains:
                consume_budget(db, budget, dimension="domains", domain_new=True, domain=_domain)
        db.add_all(rows)
        checkpoint(db, execution, "RESULTS_PERSISTED", result_ids=[str(row.id) for row in rows])
        checkpoint(db, execution, "DOWNSTREAM_COMPLETE", result_ids=[str(row.id) for row in rows])
        request.status = "COMPLETED"
        request.result_count = len(rows)
        request.completed_at = datetime.now(UTC)
        record_event(
            db,
            actor_id=owner.id,
            action="external.search.completed",
            entity_type="external_search",
            entity_id=request.id,
            metadata={"provider": provider.name, "result_count": len(rows), "mode": request.mode},
            idempotency_key=f"external-search:{request.id}:completed",
        )
        checkpoint(
            db, execution, "TERMINAL", status="COMPLETED", result_ids=[str(row.id) for row in rows]
        )
        execution.completed_at = datetime.now(UTC)
        db.commit()
        return {
            "id": request.id,
            "status": request.status,
            "provider": request.provider,
            "mode": request.mode,
            "result_count": request.result_count,
            "failure_code": None,
            "results": rows,
        }
    except (RuntimeError, ValueError, BudgetExhausted) as exc:
        request.status = "FAILED"
        request.failure_code = "budget_exhausted" if isinstance(exc, BudgetExhausted) else str(exc)
        execution.status = "FAILED"
        execution.failure_code = request.failure_code
        execution.safe_error_message = "External search failed safely."
        checkpoint(db, execution, "TERMINAL", status="FAILED")
        record_event(
            db,
            actor_id=owner.id,
            action="external.search.failed",
            entity_type="external_search",
            entity_id=request.id,
            metadata={"failure_code": request.failure_code},
            idempotency_key=f"external-search:{request.id}:failed",
        )
        event_suffix = {
            "search_auth_failed": "auth_failed",
            "search_rate_limited": "rate_limited",
            "search_provider_unavailable": "provider_unavailable",
            "search_quota_exceeded": "quota_exhausted",
            "search_blocked": "blocked",
        }.get(request.failure_code)
        if event_suffix:
            record_event(
                db,
                actor_id=owner.id,
                action=f"external.search.{event_suffix}",
                entity_type="external_search",
                entity_id=request.id,
                metadata={"failure_code": request.failure_code},
                idempotency_key=f"external-search:{request.id}:{event_suffix}",
            )
        db.commit()
        if isinstance(exc, BudgetExhausted):
            raise exc
        raise HTTPException(502, "External search failed safely.") from exc


def fetch(db: Session, owner: User, data: ExternalFetchRequestBody) -> dict[str, object]:
    settings = _settings()
    mission, _task = _mission_context(
        db, owner, mission_id=data.mission_id, task_id=data.task_id, operation="fetch"
    )
    _guard(settings, operation="fetch")
    allowed = _effective_allowed(
        tuple(data.allowed_domains), _domains(settings.intelligence_external_approved_domains)
    )
    blocked = tuple(data.blocked_domains) + _domains(settings.intelligence_external_blocked_domains)
    if mission is not None:
        mission_allowed = mission.source_policy.get("allowed_domains", [])
        if isinstance(mission_allowed, list):
            allowed = _effective_allowed(
                allowed, tuple(str(item).lower() for item in mission_allowed)
            )
        mission_blocked = mission.source_policy.get("blocked_domains", [])
        if isinstance(mission_blocked, list):
            blocked += tuple(str(item).lower() for item in mission_blocked)
    profile = db.scalar(
        select(ExternalSourceProfile).where(
            ExternalSourceProfile.owner_id == owner.id,
            ExternalSourceProfile.name == data.source_profile,
        )
    )
    if profile is not None:
        if not profile.enabled:
            raise HTTPException(403, "External source profile is disabled.")
        allowed = _effective_allowed(
            allowed, tuple(str(item).lower() for item in profile.approved_domains)
        )
        blocked += tuple(str(item).lower() for item in profile.blocked_domains)
    requested = canonical_url(data.url)
    robots_policy, terms_status = _source_policy_allowed(
        host_of(requested), profile=profile, settings=settings
    )
    identity = _identity(f"{requested}|{data.source_profile}|{data.mission_id}|{data.task_id}")
    existing = db.scalar(
        select(ExternalFetch).where(
            ExternalFetch.owner_id == owner.id, ExternalFetch.identity_key == identity
        )
    )
    if existing is not None and not data.refresh:
        return existing.__dict__
    provider_name = settings.intelligence_search_provider
    execution_key = execution_identity(
        "fetch", owner_id=owner.id, mission_id=data.mission_id, task_id=data.task_id, value=identity
    )
    execution, claimed = claim_execution(
        db,
        owner=owner,
        kind="fetch",
        identity_key=execution_key,
        provider=provider_name,
        mission_id=data.mission_id,
        task_id=data.task_id,
        correlation_id=data.correlation_id or str(uuid.uuid4()),
    )
    if not claimed:
        if execution.status == "COMPLETED":
            existing = db.scalar(
                select(ExternalFetch).where(
                    ExternalFetch.owner_id == owner.id,
                    ExternalFetch.identity_key == identity,
                )
            )
            if existing is not None:
                return existing.__dict__
        if execution.status in {"RUNNING", "QUEUED"}:
            raise HTTPException(409, "External fetch execution is already in progress.")
    if claimed:
        checkpoint(db, execution, "BEFORE_FETCH")
    budget = ensure_budget(db, owner.id, mission) if mission is not None else None
    if budget is not None:
        consume_budget(db, budget, dimension="fetches")
        consume_budget(db, budget, dimension="provider_requests")
    if settings.intelligence_external_provider_mode == "LOCAL_FIXTURE":
        execution.provider_calls += 1
        _guard(_settings(), operation="fetch")
        result = {
            "requested_url": requested,
            "final_url": requested,
            "domain": host_of(requested),
            "status": "COMPLETED",
            "http_status": 200,
            "content_type": "text/plain",
            "content_length": 71,
            "content_hash": _identity(requested + "fixture"),
            "redirect_count": 0,
            "extracted": {
                "title": "Local fixture",
                "meta_description": "Bounded fixture",
                "text": "UNTRUSTED_EXTERNAL_DATA: local approved fixture content.",
                "canonical_url": requested,
            },
            "classification": "UNTRUSTED_EXTERNAL_DATA",
        }
    else:
        for attempt in range(settings.intelligence_external_max_retries + 1):
            if attempt > 0 and budget is not None:
                consume_budget(db, budget, dimension="retries")
                consume_budget(db, budget, dimension="provider_requests")
            try:
                _guard(_settings(), operation="fetch")
                execution.provider_calls += 1
                result = ApprovedWebFetcher(settings).fetch(
                    requested, allowed_domains=allowed, blocked_domains=blocked
                )
                break
            except RuntimeError as exc:
                retryable = str(exc) in {
                    "fetch_timeout",
                    "fetch_network_failed",
                    "fetch_5xx",
                    "fetch_rate_limited",
                }
                if not retryable or attempt >= settings.intelligence_external_max_retries:
                    execution.status = "FAILED"
                    execution.failure_code = str(exc)
                    execution.safe_error_message = "Approved fetch failed safely."
                    checkpoint(db, execution, "TERMINAL", status="FAILED")
                    failure_code = str(exc)
                    suffix = {
                        "redirect_blocked": "redirect_blocked",
                        "mime_blocked": "mime_blocked",
                        "response_too_large": "response_too_large",
                        "fetch_rate_limited": "rate_limited",
                        "fetch_timeout": "timeout",
                        "fetch_network_failed": "network_failed",
                        "fetch_5xx": "5xx",
                    }.get(failure_code, "failed")
                    record_event(
                        db,
                        actor_id=owner.id,
                        action=f"external.fetch.{suffix}",
                        entity_type="external_fetch_execution",
                        entity_id=execution.id,
                        metadata={"failure_code": failure_code},
                        idempotency_key=f"external-fetch:{execution.id}:{suffix}",
                    )
                    db.commit()
                    raise HTTPException(502, "Approved fetch failed safely.") from exc
                time.sleep(
                    min(
                        settings.intelligence_external_retry_backoff_seconds * (2**attempt),
                        5,
                    )
                )
    checkpoint(db, execution, "FETCH_COMPLETE")
    content_length = int(str(result.get("content_length", 0)))
    if budget is not None:
        if content_length > budget.max_response_bytes:
            execution.status = "FAILED"
            execution.failure_code = "response_too_large"
            execution.safe_error_message = "External response exceeded the configured limit."
            checkpoint(db, execution, "TERMINAL", status="FAILED")
            record_event(
                db,
                actor_id=owner.id,
                action="external.fetch.response_too_large",
                entity_type="external_fetch_execution",
                entity_id=execution.id,
                metadata={"content_length": content_length, "maximum": budget.max_response_bytes},
                idempotency_key=f"external-fetch:{execution.id}:too-large",
            )
            db.commit()
            raise BudgetExhausted("response_bytes", content_length, budget.max_response_bytes)
        consume_budget(db, budget, dimension="total_bytes", amount=content_length)
    checkpoint(db, execution, "CONTENT_HASHED")
    if (
        data.refresh
        and existing is not None
        and str(result.get("content_hash")) == str(existing.content_hash)
    ):
        return existing.__dict__
    if data.refresh and existing is not None:
        identity = _identity(f"{identity}|{result.get('content_hash')}")
    row = ExternalFetch(
        owner_id=owner.id,
        mission_id=data.mission_id,
        task_id=data.task_id,
        search_result_id=data.search_result_id,
        requested_url=requested,
        final_url=str(result["final_url"]),
        domain=str(result["domain"]),
        status=str(result["status"]),
        http_status=int(str(result["http_status"])),
        content_type=str(result["content_type"]),
        content_length=int(str(result["content_length"])),
        content_hash=str(result["content_hash"]),
        source_profile=data.source_profile,
        provider_mode=settings.intelligence_external_provider_mode,
        redirect_count=int(str(result["redirect_count"])),
        correlation_id=data.correlation_id or str(uuid.uuid4()),
        identity_key=identity,
        freshness="fresh",
        extracted=dict(result["extracted"]) if isinstance(result["extracted"], dict) else {},
    )
    row.retrieved_at = row.retrieved_at or datetime.now(UTC)
    freshness = derive_freshness(row.retrieved_at)
    row.freshness = freshness.state
    row.extracted = {
        **(row.extracted if isinstance(row.extracted, dict) else {}),
        "robots_policy": robots_policy,
        "terms_status": terms_status,
        "latency_ms": result.get("latency_ms"),
        "user_agent": result.get("user_agent"),
        "freshness_state": freshness.state,
        "fresh_until": freshness.fresh_until.isoformat() if freshness.fresh_until else None,
        "stale_at": freshness.stale_at.isoformat() if freshness.stale_at else None,
        "expires_at": freshness.expires_at.isoformat() if freshness.expires_at else None,
        "refresh_due": freshness.refresh_due,
        "usable_for_verification": freshness.usable_for_verification,
        "usable_for_scoring": freshness.usable_for_scoring,
    }
    db.add(row)
    db.flush()
    checkpoint(db, execution, "FETCH_COMPLETE")
    record_event(
        db,
        actor_id=owner.id,
        action="external.fetch.requested",
        entity_type="external_fetch",
        entity_id=row.id,
        metadata={"domain": row.domain},
        idempotency_key=f"external-fetch:{identity}:requested",
    )
    evidence_id = None
    if mission is not None and _task is not None:
        retrieval_identity = f"external-fetch:{identity}"
        evidence = db.scalar(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner.id,
                AutonomousResearchEvidence.retrieval_identity == retrieval_identity,
            )
        )
        if evidence is None:
            extracted = row.extracted if isinstance(row.extracted, dict) else {}
            evidence = AutonomousResearchEvidence(
                owner_id=owner.id,
                mission_id=mission.id,
                task_id=_task.id,
                source_class="EXTERNAL_WEB_FETCH",
                source_reference=row.final_url or row.requested_url,
                retrieval_identity=retrieval_identity,
                content_type=row.content_type or "text/plain",
                normalized_value={
                    **dict(extracted),
                    "fetch_id": str(row.id),
                    "search_result_id": str(row.search_result_id) if row.search_result_id else None,
                    "requested_url": row.requested_url,
                    "correlation_id": row.correlation_id,
                },
                content_hash=row.content_hash or "",
                verification_status="UNVERIFIED",
                freshness_status=row.freshness.upper(),
                fresh_until=freshness.fresh_until,
                stale_at=freshness.stale_at,
                expires_at=freshness.expires_at,
                freshness_at_verification=freshness.state,
                source_profile=row.source_profile,
                provider=row.provider_mode,
                canonical_url=row.final_url or row.requested_url,
                domain=row.domain,
                lineage={
                    "fetch_id": str(row.id),
                    "search_result_id": str(row.search_result_id) if row.search_result_id else None,
                    "correlation_id": row.correlation_id,
                },
                confidence=0,
                evidence_class="EXTERNAL_FETCH",
                is_untrusted_external_data=True,
                observed_at=row.created_at,
                retrieved_at=row.retrieved_at or datetime.now(UTC),
                created_at=datetime.now(UTC),
            )
            db.add(evidence)
            db.flush()
        projection = verify_and_project(db, owner, mission, _task, evidence)
        evidence = cast(AutonomousResearchEvidence, projection["evidence"])
        evidence_id = evidence.id
        row.extracted = {
            **(row.extracted if isinstance(row.extracted, dict) else {}),
            "verification_status": evidence.verification_status,
            "verification_reason": evidence.verification_reason,
        }
        checkpoint(db, execution, "VERIFICATION_COMPLETE", result_ids=[str(evidence.id)])
    checkpoint(
        db, execution, "EVIDENCE_PERSISTED", result_ids=[str(evidence_id)] if evidence_id else []
    )
    record_event(
        db,
        actor_id=owner.id,
        action="external.fetch.completed",
        entity_type="external_fetch",
        entity_id=row.id,
        metadata={
            "domain": row.domain,
            "content_type": row.content_type,
            "content_length": row.content_length,
        },
        idempotency_key=f"external-fetch:{identity}",
    )
    checkpoint(
        db,
        execution,
        "TERMINAL",
        status="COMPLETED",
        result_ids=[str(evidence_id)] if evidence_id else [],
    )
    execution.completed_at = datetime.now(UTC)
    db.commit()
    payload = dict(row.__dict__)
    if evidence_id is not None:
        payload["evidence_id"] = evidence_id
    return payload
