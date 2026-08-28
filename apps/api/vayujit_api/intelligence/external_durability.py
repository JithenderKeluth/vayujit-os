# ruff: noqa: E501
"""Durable budgets, execution checkpoints, and recovery for external research."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchMission,
)
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalRecoveryAction,
    ExternalResearchBudget,
)

BUDGET_DIMENSIONS = (
    "searches",
    "fetches",
    "domains",
    "results",
    "response_bytes",
    "total_bytes",
    "elapsed_seconds",
    "retries",
    "provider_requests",
)
PLATFORM_MAXIMUMS: dict[str, int] = {
    "max_searches": 1000,
    "max_fetches": 1000,
    "max_domains": 500,
    "max_results": 10000,
    "max_response_bytes": 20_000_000,
    "max_total_bytes": 100_000_000,
    "max_elapsed_seconds": 86_400,
    "max_retries": 20,
    "max_provider_requests": 5000,
}
DEFAULTS: dict[str, int] = {
    "max_searches": 10,
    "max_fetches": 10,
    "max_domains": 10,
    "max_results": 100,
    "max_response_bytes": 1_000_000,
    "max_total_bytes": 10_000_000,
    "max_elapsed_seconds": 300,
    "max_retries": 3,
    "max_provider_requests": 20,
}


class BudgetExhausted(HTTPException):
    def __init__(self, dimension: str, used: int | float, maximum: int | float) -> None:
        self.dimension, self.used, self.maximum = dimension, used, maximum
        super().__init__(429, "External research budget exhausted safely.")


@dataclass(frozen=True)
class BudgetPolicy:
    max_searches: int = 10
    max_fetches: int = 10
    max_domains: int = 10
    max_results: int = 100
    max_response_bytes: int = 1_000_000
    max_total_bytes: int = 10_000_000
    max_elapsed_seconds: int = 300
    max_retries: int = 3
    max_provider_requests: int = 20


def normalize_budget_policy(
    requested: dict[str, object] | None,
    *,
    mission: AutonomousResearchMission | None = None,
    provider_limits: dict[str, object] | None = None,
    profile_limits: dict[str, object] | None = None,
) -> BudgetPolicy:
    raw = requested or {}
    values: dict[str, int] = {}
    for key, default in DEFAULTS.items():
        candidate = raw.get(key, default)
        if candidate is None:
            candidate = default
        if isinstance(candidate, bool) or not isinstance(candidate, int):
            raise HTTPException(422, "External research budget values must be integers.")
        if candidate <= 0:
            raise HTTPException(422, "External research budget values must be positive.")
        bounds = [PLATFORM_MAXIMUMS[key]]
        for limits in (provider_limits, profile_limits):
            if limits is None or key not in limits or limits[key] is None:
                continue
            bound = limits[key]
            if isinstance(bound, bool) or not isinstance(bound, int) or bound <= 0:
                raise HTTPException(
                    422, "External research budget policy values must be positive integers."
                )
            bounds.append(bound)
        values[key] = min(candidate, *bounds)
    if mission is not None:
        values["max_elapsed_seconds"] = min(
            values["max_elapsed_seconds"], mission.max_elapsed_seconds
        )
        values["max_retries"] = min(values["max_retries"], max(1, mission.max_retries))
        values["max_provider_requests"] = min(
            values["max_provider_requests"], mission.max_provider_calls
        )
    return BudgetPolicy(**values)


def ensure_budget(
    db: Session, owner_id: uuid.UUID, mission: AutonomousResearchMission
) -> ExternalResearchBudget:
    row = db.scalar(
        select(ExternalResearchBudget)
        .where(
            ExternalResearchBudget.owner_id == owner_id,
            ExternalResearchBudget.mission_id == mission.id,
        )
        .with_for_update()
    )
    if row is not None:
        return row
    policy = normalize_budget_policy(mission.budget_policy, mission=mission)
    row = ExternalResearchBudget(owner_id=owner_id, mission_id=mission.id, **policy.__dict__)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        row = db.scalar(
            select(ExternalResearchBudget)
            .where(
                ExternalResearchBudget.owner_id == owner_id,
                ExternalResearchBudget.mission_id == mission.id,
            )
            .with_for_update()
        )
        if row is None:
            raise
    return row


def budget_snapshot(row: ExternalResearchBudget) -> dict[str, object]:
    return {
        key: getattr(row, key)
        for key in (
            *PLATFORM_MAXIMUMS,
            "searches_used",
            "fetches_used",
            "domains_used",
            "results_used",
            "bytes_used",
            "retries_used",
            "provider_requests_used",
            "domains_seen",
            "started_at",
            "elapsed_seconds",
        )
    }


def consume_budget(
    db: Session,
    row: ExternalResearchBudget,
    *,
    dimension: str,
    amount: int | float = 1,
    domain_new: bool = False,
    domain: str | None = None,
) -> ExternalResearchBudget:
    if dimension not in BUDGET_DIMENSIONS or amount < 0:
        raise ValueError("invalid budget dimension")
    locked = db.scalar(
        select(ExternalResearchBudget).where(ExternalResearchBudget.id == row.id).with_for_update()
    )
    if locked is None:
        raise HTTPException(409, "External research budget ledger is unavailable.")
    now = datetime.now(UTC)
    locked.elapsed_seconds = max(
        float(locked.elapsed_seconds or 0), (now - locked.started_at).total_seconds()
    )
    if locked.elapsed_seconds >= locked.max_elapsed_seconds and dimension not in {
        "elapsed_seconds"
    }:
        raise BudgetExhausted("elapsed_seconds", locked.elapsed_seconds, locked.max_elapsed_seconds)
    used_name = {
        "response_bytes": "bytes_used",
        "total_bytes": "bytes_used",
        "elapsed_seconds": "elapsed_seconds",
        "provider_requests": "provider_requests_used",
        "retries": "retries_used",
        "searches": "searches_used",
        "fetches": "fetches_used",
        "domains": "domains_used",
        "results": "results_used",
    }[dimension]
    max_name = {
        "response_bytes": "max_response_bytes",
        "total_bytes": "max_total_bytes",
        "elapsed_seconds": "max_elapsed_seconds",
        "provider_requests": "max_provider_requests",
        "retries": "max_retries",
        "searches": "max_searches",
        "fetches": "max_fetches",
        "domains": "max_domains",
        "results": "max_results",
    }[dimension]
    if dimension == "domains" and not domain_new:
        return locked
    used = float(getattr(locked, used_name) or 0)
    maximum = float(getattr(locked, max_name))
    if used + amount > maximum:
        raise BudgetExhausted(dimension, used, maximum)
    setattr(
        locked, used_name, int(used + amount) if used_name != "elapsed_seconds" else used + amount
    )
    if dimension == "domains" and domain:
        seen_domains = list(locked.domains_seen or [])
        if domain not in seen_domains:
            seen_domains.append(domain)
            locked.domains_seen = seen_domains
    locked.updated_at = now
    db.flush()
    return locked


def execution_identity(
    kind: str,
    *,
    owner_id: uuid.UUID,
    mission_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    value: str,
) -> str:
    return hashlib.sha256(f"{kind}|{owner_id}|{mission_id}|{task_id}|{value}".encode()).hexdigest()


def claim_execution(
    db: Session,
    *,
    owner: User,
    kind: str,
    identity_key: str,
    provider: str,
    mission_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    correlation_id: str,
) -> tuple[ExternalExecution, bool]:
    row = db.scalar(
        select(ExternalExecution)
        .where(
            ExternalExecution.owner_id == owner.id, ExternalExecution.identity_key == identity_key
        )
        .with_for_update()
    )
    if row is not None:
        return row, False
    row = ExternalExecution(
        owner_id=owner.id,
        mission_id=mission_id,
        task_id=task_id,
        kind=kind,
        identity_key=identity_key,
        correlation_id=correlation_id,
        provider=provider,
        status="RUNNING",
        checkpoint="CLAIMED",
        attempt_count=1,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        row = db.scalar(
            select(ExternalExecution)
            .where(
                ExternalExecution.owner_id == owner.id,
                ExternalExecution.identity_key == identity_key,
            )
            .with_for_update()
        )
        if row is None:
            raise
        return row, False
    return row, True


def checkpoint(
    db: Session,
    execution: ExternalExecution,
    value: str,
    *,
    status: str | None = None,
    result_ids: list[str] | None = None,
) -> None:
    execution.checkpoint = value
    if status is not None:
        execution.status = status
    if result_ids is not None:
        execution.result_ids = result_ids
    execution.updated_at = datetime.now(UTC)
    db.flush()


def record_recovery(
    db: Session,
    *,
    owner: User,
    action: str,
    failure_code: str,
    idempotency_key: str,
    correlation_id: str,
    mission_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    execution_id: uuid.UUID | None = None,
    status: str = "COMPLETED",
) -> dict[str, object]:
    identity = hashlib.sha256(f"{owner.id}|{idempotency_key}".encode()).hexdigest()
    existing = db.scalar(
        select(ExternalRecoveryAction).where(
            ExternalRecoveryAction.owner_id == owner.id,
            ExternalRecoveryAction.identity_key == identity,
        )
    )
    if existing is not None:
        return {
            "id": existing.id,
            "action": existing.action,
            "status": existing.status,
            "failure_code": existing.failure_code,
            "idempotent_reuse": True,
            "safe_reason_code": existing.safe_reason_code,
            "correlation_id": existing.correlation_id,
        }
    safe = f"EXTERNAL_{failure_code.upper()}"
    row = ExternalRecoveryAction(
        owner_id=owner.id,
        mission_id=mission_id,
        task_id=task_id,
        execution_id=execution_id,
        action=action,
        failure_code=failure_code,
        status=status,
        safe_reason_code=safe,
        correlation_id=correlation_id,
        identity_key=identity,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ExternalRecoveryAction)
            .where(
                ExternalRecoveryAction.owner_id == owner.id,
                ExternalRecoveryAction.identity_key == identity,
            )
            .with_for_update()
        )
        if existing is not None:
            return {
                "id": existing.id,
                "action": existing.action,
                "status": existing.status,
                "failure_code": existing.failure_code,
                "idempotent_reuse": True,
                "safe_reason_code": existing.safe_reason_code,
                "correlation_id": existing.correlation_id,
            }
        raise
    record_event(
        db,
        actor_id=owner.id,
        action="external.recovery.executed",
        entity_type="external_recovery",
        entity_id=row.id,
        metadata={"action": action, "failure_code": failure_code},
        idempotency_key=f"external-recovery:{identity}",
    )
    db.commit()
    return {
        "id": row.id,
        "action": action,
        "status": status,
        "failure_code": failure_code,
        "idempotent_reuse": False,
        "safe_reason_code": safe,
        "correlation_id": correlation_id,
    }


def recovery_actions(failure_code: str) -> list[str]:
    if failure_code in {
        "unsafe_url",
        "redirect_blocked",
        "mime_blocked",
        "prompt_injection_detected",
        "source_not_allowed",
        "domain_disabled",
        "external_research_disabled",
        "provider_disabled",
    }:
        return ["review_source", "skip_optional_source", "cancel"]
    if failure_code in {"search_rate_limited", "fetch_rate_limited"}:
        return ["retry_after", "review_source", "cancel"]
    if failure_code in {"budget_exhausted", "response_too_large"}:
        return ["review_source", "skip_optional_source", "cancel"]
    return ["retry", "reconcile", "cancel"]
