# ruff: noqa: E501,F401
from __future__ import annotations

import uuid
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchChange,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
)
from vayujit_api.intelligence.external_durability import (
    budget_snapshot,
    record_recovery,
    recovery_actions,
)
from vayujit_api.intelligence.external_intelligence import current_observation, observation_history
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalFetch,
    ExternalProviderState,
    ExternalRecoveryAction,
    ExternalResearchBudget,
    ExternalSearchRequest,
    ExternalSearchResult,
)
from vayujit_api.intelligence.external_projection import (
    alerts_projection,
    calendar_projection,
    integrity_projection,
    performance_projection,
    product_channel_projection,
    table_inventory,
)
from vayujit_api.intelligence.external_provider import classify_prompt_injection
from vayujit_api.intelligence.external_schemas import (
    ExternalFetchRequestBody,
    ExternalSearchRequestBody,
)
from vayujit_api.intelligence.external_service import (
    ALLOWED_MODES,
    fetch,
    provider_preflight,
    search,
)

router = APIRouter(prefix="/api/v1/intelligence/external", tags=["external-research"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _credential_status(settings: object) -> str:
    value = getattr(settings, "intelligence_search_provider_api_key", None)
    return "CONFIGURED" if isinstance(value, str) and value else "NOT_CONFIGURED"


def _policy_status(settings: object) -> str:
    mode = getattr(settings, "intelligence_external_provider_mode", "DISABLED")
    if mode == "DISABLED":
        return "DISABLED"
    if mode == "LIVE_READ_ONLY" and not getattr(
        settings, "intelligence_search_provider_api_key", None
    ):
        return "BLOCKED_BY_EXTERNAL_CREDENTIALS"
    if mode == "LIVE_READ_ONLY" and not all(
        getattr(settings, key, False)
        for key in (
            "intelligence_enabled",
            "intelligence_external_research_enabled",
            "intelligence_search_provider_enabled",
        )
    ):
        return "BLOCKED_BY_CONFIGURATION"
    return "READY"


@router.get("/policy")
def policy() -> dict[str, object]:
    settings = get_settings()
    return {
        "provider": settings.intelligence_search_provider,
        "mode": settings.intelligence_external_provider_mode,
        "allowed_modes": list(ALLOWED_MODES),
        "status": _policy_status(settings),
        "search_enabled": settings.intelligence_search_provider_enabled,
        "fetch_enabled": settings.intelligence_web_fetch_enabled,
        "kill_switch": settings.intelligence_external_kill_switch,
        "provider_kill_switch": settings.intelligence_search_provider_kill_switch,
        "approved_domains_configured": bool(settings.intelligence_external_approved_domains),
        "credentials_configured": bool(settings.intelligence_search_provider_api_key),
        "credential_status": _credential_status(settings),
        "robots_policy": "UNKNOWN",
        "terms_status": "UNKNOWN",
    }


@router.get("/status")
def status(db: DB, owner: Owner) -> dict[str, object]:
    settings = get_settings()
    states = list(
        db.scalars(select(ExternalProviderState).where(ExternalProviderState.owner_id == owner.id))
    )
    return {
        "provider": settings.intelligence_search_provider,
        "mode": settings.intelligence_external_provider_mode,
        "status": _policy_status(settings),
        "credentials_configured": bool(settings.intelligence_search_provider_api_key),
        "credential_status": _credential_status(settings),
        "quota": [
            {
                "provider": row.provider,
                "requests_minute": row.requests_minute,
                "requests_hour": row.requests_hour,
                "requests_day": row.requests_day,
                "status": row.status,
            }
            for row in states
        ],
        "recent_failures": [row.last_failure for row in states if row.last_failure],
    }


@router.get("/preflight")
def preflight() -> dict[str, object]:
    """Return safe provider readiness; performs no request without credentials."""
    return provider_preflight(get_settings())


@router.post("/search")
def search_endpoint(data: ExternalSearchRequestBody, db: DB, owner: Owner) -> dict[str, object]:
    try:
        result = search(db, owner, data)
    except HTTPException:
        raise
    return {
        "id": result["id"],
        "status": result["status"],
        "provider": result["provider"],
        "mode": result["mode"],
        "result_count": result["result_count"],
        "failure_code": result["failure_code"],
        "results": [
            {
                "id": row.id,
                "title": row.title,
                "url": row.url,
                "canonical_url": row.canonical_url,
                "domain": row.domain,
                "snippet": row.snippet,
                "published_at": row.published_at,
                "retrieved_at": row.retrieved_at,
                "provider": row.provider,
                "provider_result_id": row.provider_result_id,
                "rank": row.rank,
                "source_classification": row.source_classification,
                "fetch_eligible": True,
            }
            for row in cast(list[Any], result["results"])
        ],
    }


@router.post("/fetch")
def fetch_endpoint(data: ExternalFetchRequestBody, db: DB, owner: Owner) -> dict[str, object]:
    try:
        result = fetch(db, owner, data)
    except HTTPException:
        raise
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, "Approved fetch failed safely.") from exc
    return {
        key: result[key]
        for key in (
            "id",
            "requested_url",
            "final_url",
            "domain",
            "status",
            "http_status",
            "content_type",
            "content_length",
            "content_hash",
            "source_profile",
            "provider_mode",
            "redirect_count",
            "correlation_id",
            "freshness",
            "extracted",
        )
        if key in result
    } | {"classification": "UNTRUSTED_EXTERNAL_DATA"}


@router.get("/searches")
def searches(
    db: DB, owner: Owner, limit: int = Query(default=100, ge=1, le=500)
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(ExternalSearchRequest)
            .where(ExternalSearchRequest.owner_id == owner.id)
            .order_by(ExternalSearchRequest.created_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "query": row.query,
            "provider": row.provider,
            "mode": row.mode,
            "status": row.status,
            "failure_code": row.failure_code,
            "result_count": row.result_count,
            "correlation_id": row.correlation_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/results")
def results(db: DB, owner: Owner, search_id: uuid.UUID | None = None) -> list[dict[str, object]]:
    statement = select(ExternalSearchResult).where(ExternalSearchResult.owner_id == owner.id)
    if search_id:
        statement = statement.where(ExternalSearchResult.search_id == search_id)
    return [
        {
            "id": row.id,
            "search_id": row.search_id,
            "title": row.title,
            "url": row.url,
            "domain": row.domain,
            "snippet": row.snippet,
            "provider": row.provider,
            "rank": row.rank,
            "source_classification": row.source_classification,
            "retrieved_at": row.retrieved_at,
            "fetch_eligible": True,
        }
        for row in db.scalars(statement.order_by(ExternalSearchResult.rank))
    ]


@router.get("/fetches")
def fetches(
    db: DB, owner: Owner, limit: int = Query(default=100, ge=1, le=500)
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(ExternalFetch)
            .where(ExternalFetch.owner_id == owner.id)
            .order_by(ExternalFetch.created_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "requested_url": row.requested_url,
            "final_url": row.final_url,
            "domain": row.domain,
            "status": row.status,
            "http_status": row.http_status,
            "content_type": row.content_type,
            "content_length": row.content_length,
            "freshness": row.freshness,
            "retrieved_at": row.retrieved_at,
            "source_profile": row.source_profile,
        }
        for row in rows
    ]


@router.get("/history")
@router.get("/evidence")
def evidence_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(AutonomousResearchEvidence)
            .where(AutonomousResearchEvidence.owner_id == owner.id)
            .order_by(AutonomousResearchEvidence.retrieved_at.desc())
        )
    )
    return [
        {
            "id": row.id,
            "mission_id": row.mission_id,
            "task_id": row.task_id,
            "source_class": row.source_class,
            "source_reference": row.source_reference,
            "verification_status": row.verification_status,
            "freshness_status": row.freshness_status,
            "evidence_class": row.evidence_class,
            "is_untrusted_external_data": row.is_untrusted_external_data,
            "retrieved_at": row.retrieved_at,
        }
        for row in rows
    ]


def history(db: DB, owner: Owner) -> dict[str, object]:
    recoveries = list(
        db.scalars(
            select(ExternalRecoveryAction)
            .where(ExternalRecoveryAction.owner_id == owner.id)
            .order_by(ExternalRecoveryAction.created_at.desc())
            .limit(100)
        )
    )
    audit_ids = list(
        db.scalars(
            select(AuditEvent.id)
            .where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.entity_type.in_(
                    [
                        "external_search",
                        "external_fetch",
                        "external_recovery",
                        "external_search_execution",
                        "external_fetch_execution",
                    ]
                ),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(100)
        )
    )
    return {
        "searches": searches(db, owner),
        "results": results(db, owner),
        "fetches": fetches(db, owner),
        "verification": evidence_list(db, owner),
        "contradictions": [
            {
                "id": row.id,
                "mission_id": row.mission_id,
                "identity_key": row.identity_key,
                "contradiction_type": row.contradiction_type,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in db.scalars(
                select(AutonomousResearchContradiction)
                .where(AutonomousResearchContradiction.owner_id == owner.id)
                .order_by(AutonomousResearchContradiction.created_at.desc())
                .limit(100)
            )
        ],
        "changes": [
            {
                "id": row.id,
                "mission_id": row.mission_id,
                "change_type": row.change_type,
                "field_key": row.field_key,
                "material": row.material,
                "created_at": row.created_at,
            }
            for row in db.scalars(
                select(AutonomousResearchChange)
                .where(AutonomousResearchChange.owner_id == owner.id)
                .order_by(AutonomousResearchChange.created_at.desc())
                .limit(100)
            )
        ],
        "alerts": alerts_projection(db, owner),
        "recovery": [
            {
                "id": row.id,
                "execution_id": row.execution_id,
                "action": row.action,
                "failure_code": row.failure_code,
                "status": row.status,
                "safe_reason_code": row.safe_reason_code,
                "correlation_id": row.correlation_id,
            }
            for row in recoveries
        ],
        "audit_ids": audit_ids,
    }


@router.get("/observations/current")
def observation_current(url: str, db: DB, owner: Owner) -> dict[str, object] | None:
    row = current_observation(db, owner.id, url)
    if row is None:
        return None
    return {
        "id": row.id,
        "requested_url": row.requested_url,
        "final_url": row.final_url,
        "content_hash": row.content_hash,
        "freshness": row.freshness,
        "retrieved_at": row.retrieved_at,
        "extracted": row.extracted,
    }


@router.get("/observations/history")
def observation_history_endpoint(url: str, db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "id": row.id,
            "requested_url": row.requested_url,
            "final_url": row.final_url,
            "content_hash": row.content_hash,
            "freshness": row.freshness,
            "retrieved_at": row.retrieved_at,
        }
        for row in observation_history(db, owner.id, url)
    ]


@router.get("/integrity")
def integrity(db: DB, owner: Owner) -> dict[str, object]:
    return integrity_projection(db, owner)


@router.get("/performance")
def performance(db: DB, owner: Owner) -> dict[str, object]:
    return performance_projection(db, owner)


@router.get("/tables")
def tables() -> list[dict[str, object]]:
    return table_inventory()


@router.get("/products/{product_id}/channel")
def product_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.products.models import Product

    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    return product_channel_projection(db, owner, product.id)


@router.get("/calendar")
def calendar(db: DB, owner: Owner) -> list[dict[str, object]]:
    return calendar_projection(db, owner)


@router.get("/alerts")
def alerts(db: DB, owner: Owner) -> list[dict[str, object]]:
    return alerts_projection(db, owner)


@router.get("/recovery/catalog")
def recovery_catalog() -> dict[str, object]:
    return {
        "failure_codes": [
            "search_provider_unavailable",
            "search_rate_limited",
            "search_auth_failed",
            "search_invalid_response",
            "search_blocked",
            "search_quota_exceeded",
            "budget_exhausted",
            "checkpoint_invalid",
            "fetch_timeout",
            "fetch_network_failed",
            "fetch_5xx",
            "unsafe_url",
            "redirect_blocked",
            "mime_blocked",
            "response_too_large",
            "source_not_allowed",
            "external_research_disabled",
            "provider_disabled",
            "domain_disabled",
            "prompt_injection_detected",
            "content_validation_failed",
        ],
        "actions": [
            "retry",
            "retry_after",
            "review_source",
            "disable_source",
            "refresh_search",
            "skip_optional_source",
            "cancel",
            "reconcile",
        ],
    }


@router.post("/prompt-injection/check")
def prompt_injection_check(payload: dict[str, object]) -> dict[str, object]:
    return classify_prompt_injection(str(payload.get("content", "")))


@router.get("/budgets/{mission_id}")
def budget_get(mission_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(ExternalResearchBudget).where(
            ExternalResearchBudget.owner_id == owner.id,
            ExternalResearchBudget.mission_id == mission_id,
        )
    )
    if row is None:
        raise HTTPException(404, "External research budget not found.")
    return budget_snapshot(row)


@router.get("/executions")
def execution_history(
    db: DB, owner: Owner, limit: int = Query(default=100, ge=1, le=500)
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(ExternalExecution)
            .where(ExternalExecution.owner_id == owner.id)
            .order_by(ExternalExecution.started_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "identity_key": row.identity_key,
            "mission_id": row.mission_id,
            "task_id": row.task_id,
            "provider": row.provider,
            "status": row.status,
            "checkpoint": row.checkpoint,
            "provider_calls": row.provider_calls,
            "attempt_count": row.attempt_count,
            "failure_code": row.failure_code,
            "safe_error_message": row.safe_error_message,
            "result_ids": row.result_ids,
            "correlation_id": row.correlation_id,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
        }
        for row in rows
    ]


@router.post("/recovery")
def recovery_endpoint(payload: dict[str, object], db: DB, owner: Owner) -> dict[str, object]:
    action = str(payload.get("action", ""))
    allowed = {
        "retry",
        "retry_after",
        "refresh_search",
        "review_source",
        "disable_source",
        "skip_optional_source",
        "cancel",
        "reconcile",
    }
    if action not in allowed:
        raise HTTPException(422, "Unsupported external recovery action.")
    failure_code = str(payload.get("failure_code", "external_failure"))
    advertised = recovery_actions(failure_code)
    if action not in advertised:
        raise HTTPException(422, "Recovery action is not allowed for this failure code.")
    correlation_id = str(payload.get("correlation_id") or uuid.uuid4())
    mission_id = uuid.UUID(str(payload["mission_id"])) if payload.get("mission_id") else None
    task_id = uuid.UUID(str(payload["task_id"])) if payload.get("task_id") else None
    execution_id = uuid.UUID(str(payload["execution_id"])) if payload.get("execution_id") else None
    if execution_id is not None:
        scoped_execution = db.scalar(
            select(ExternalExecution).where(
                ExternalExecution.owner_id == owner.id,
                ExternalExecution.id == execution_id,
            )
        )
        if scoped_execution is None:
            raise HTTPException(404, "External execution not found.")
    idempotency_key = str(
        payload.get("idempotency_key") or f"{action}:{execution_id or mission_id}:{failure_code}"
    )
    result = record_recovery(
        db,
        owner=owner,
        action=action,
        failure_code=failure_code,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        mission_id=mission_id,
        task_id=task_id,
        execution_id=execution_id,
    )
    if not result["idempotent_reuse"] and execution_id is not None:
        execution = db.scalar(
            select(ExternalExecution)
            .where(ExternalExecution.owner_id == owner.id, ExternalExecution.id == execution_id)
            .with_for_update()
        )
        if execution is not None:
            if action in {"retry", "retry_after", "refresh_search", "reconcile"}:
                execution.status = "QUEUED"
                execution.checkpoint = "CLAIMED"
            elif action in {"cancel", "skip_optional_source", "disable_source"}:
                execution.status = "CANCELLED" if action == "cancel" else "SKIPPED"
                execution.checkpoint = "TERMINAL"
            db.commit()
    request_payload = payload.get("request")
    if (
        not result["idempotent_reuse"]
        and isinstance(request_payload, dict)
        and action in {"retry", "retry_after", "refresh_search"}
    ):
        try:
            if str(payload.get("operation", "search")) == "search":
                replayed = search(
                    db, owner, ExternalSearchRequestBody.model_validate(request_payload)
                )
                result["replayed"] = {
                    "status": replayed.get("status"),
                    "result_count": replayed.get("result_count"),
                    "id": replayed.get("id"),
                }
            elif str(payload.get("operation")) == "fetch":
                replayed = fetch(
                    db, owner, ExternalFetchRequestBody.model_validate(request_payload)
                )
                result["replayed"] = {
                    "status": replayed.get("status"),
                    "id": replayed.get("id"),
                    "content_hash": replayed.get("content_hash"),
                }
        except HTTPException as exc:
            result["replayed"] = {
                "status": "failed",
                "failure_code": "recovery_replay_failed",
                "safe_message": str(exc.detail),
            }
    result["available_actions"] = advertised
    return result
