# ruff: noqa: E501
"""Provider-neutral marketplace execution, rate windows, and fault hooks."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from math import ceil
from typing import Protocol, cast

from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import Base
from vayujit_api.identity.models import User

CHECKPOINTS = (
    "CLAIMED",
    "BEFORE_PROVIDER",
    "PROVIDER_COMPLETE",
    "RESULTS_PERSISTED",
    "EVIDENCE_PERSISTED",
    "CHANGE_COMPLETE",
    "ALERT_COMPLETE",
    "REPORT_COMPLETE",
    "TERMINAL",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MarketplaceExecution(Base):
    """Durable provider-neutral marketplace execution identity/checkpoint."""

    __tablename__ = "marketplace_executions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "provider", "identity_key", name="uq_marketplace_execution_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), index=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    identity_key: Mapped[str] = mapped_column(String(300))
    provider_execution_id: Mapped[str | None] = mapped_column(
        String(180), nullable=True, index=True
    )
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    counters: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    provider_payload: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint: Mapped[str] = mapped_column(String(40), default="CLAIMED")
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retry_after_seconds: Mapped[float | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketplaceRateWindow(Base):
    """Owner/provider scoped, atomically consumed minute and hour windows."""

    __tablename__ = "marketplace_rate_windows"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider", name="uq_marketplace_rate_window_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), index=True)
    minute_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    hour_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    minute_used: Mapped[int] = mapped_column(Integer, default=0)
    hour_used: Mapped[int] = mapped_column(Integer, default=0)


class MarketplaceLedger(Base):
    """Generic owner-scoped ledger for canonical marketplace lifecycle entities."""

    __tablename__ = "marketplace_ledger"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "provider",
            "entity_type",
            "logical_key",
            name="uq_marketplace_ledger_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), index=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_executions.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    logical_key: Mapped[str] = mapped_column(String(300))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="PROJECTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


@dataclass(frozen=True)
class RateWindowResult:
    provider: str
    limit: int
    used: int
    remaining: int
    retry_after_seconds: float
    window: str


class MarketplaceRateLimited(HTTPException):
    def __init__(self, result: RateWindowResult) -> None:
        self.result = result
        super().__init__(
            status_code=429,
            detail={
                "code": "MARKETPLACE_RATE_LIMITED",
                "provider": result.provider,
                "window": result.window,
                "limit": result.limit,
                "used": result.used,
                "remaining": result.remaining,
                "retry_after_seconds": max(0.0, result.retry_after_seconds),
            },
        )


def consume_rate_window(
    db: Session,
    owner: User,
    provider: str,
    *,
    requests_per_minute: int,
    requests_per_hour: int,
    now: datetime | None = None,
) -> RateWindowResult:
    """Atomically consume one provider request across bounded minute/hour windows."""
    if requests_per_minute <= 0 or requests_per_hour <= 0:
        raise ValueError("rate-window limits must be positive")
    stamp = now or _utcnow()
    row = db.scalar(
        select(MarketplaceRateWindow)
        .where(
            MarketplaceRateWindow.owner_id == owner.id,
            MarketplaceRateWindow.provider == provider,
        )
        .with_for_update()
    )
    if row is None:
        row = MarketplaceRateWindow(
            owner_id=owner.id, provider=provider, minute_started_at=stamp, hour_started_at=stamp
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            row = db.scalar(
                select(MarketplaceRateWindow)
                .where(
                    MarketplaceRateWindow.owner_id == owner.id,
                    MarketplaceRateWindow.provider == provider,
                )
                .with_for_update()
            )
            if row is None:
                raise

    if stamp - row.minute_started_at >= timedelta(minutes=1):
        row.minute_started_at = stamp
        row.minute_used = 0
    if stamp - row.hour_started_at >= timedelta(hours=1):
        row.hour_started_at = stamp
        row.hour_used = 0
    if row.minute_used >= requests_per_minute:
        retry = max(0.0, 60.0 - (stamp - row.minute_started_at).total_seconds())
        result = RateWindowResult(
            provider, requests_per_minute, row.minute_used, 0, retry, "minute"
        )
        raise MarketplaceRateLimited(result)
    if row.hour_used >= requests_per_hour:
        retry = max(0.0, 3600.0 - (stamp - row.hour_started_at).total_seconds())
        result = RateWindowResult(provider, requests_per_hour, row.hour_used, 0, retry, "hour")
        raise MarketplaceRateLimited(result)
    row.minute_used += 1
    row.hour_used += 1
    db.flush()
    return RateWindowResult(
        provider,
        requests_per_minute,
        row.minute_used,
        max(0, requests_per_minute - row.minute_used),
        0.0,
        "available",
    )


def checkpoint(execution: MarketplaceExecution, value: str, *, status: str | None = None) -> None:
    if value not in CHECKPOINTS:
        raise ValueError("unsupported marketplace checkpoint")
    execution.checkpoint = value
    if status is not None:
        execution.status = status


_fault_stage: ContextVar[str | None] = ContextVar("marketplace_fault_stage", default=None)


@contextmanager
def fault_injection(stage: str | None) -> Iterator[None]:
    """Test-only LOCAL_FIXTURE fault hook; never exposed through a public API."""
    token = _fault_stage.set(stage)
    try:
        yield
    finally:
        _fault_stage.reset(token)


def inject_test_fault(stage: str, *, mode: str) -> None:
    if mode == "LOCAL_FIXTURE" and _fault_stage.get() == stage:
        raise RuntimeError(f"marketplace_test_fault:{stage}")


RETRYABLE_FAILURES = frozenset({"TIMEOUT", "NETWORK_FAILURE", "PROVIDER_5XX", "RATE_LIMITED"})
FAILURE_ALIASES = {
    "429": "RATE_LIMITED",
    "500": "PROVIDER_5XX",
    "502": "PROVIDER_5XX",
    "503": "PROVIDER_5XX",
    "AUTH": "AUTH_FAILURE",
    "BAD_REQUEST": "INVALID_REQUEST",
    "NETWORK": "NETWORK_FAILURE",
}
NON_RETRYABLE_FAILURES = frozenset(
    {
        "AUTH_FAILURE",
        "INVALID_REQUEST",
        "INVALID_RESPONSE",
        "AUTHORIZATION",
        "POLICY_BLOCK",
        "KILL_SWITCH",
        "VALIDATION_FAILURE",
        "BUDGET_EXHAUSTED",
        "RETRY_BUDGET_EXHAUSTED",
    }
)
MARKETPLACE_CAPABILITIES = frozenset(
    {"SEARCH", "PRODUCT_LISTINGS", "SUPPLIER_METADATA", "COMMERCIAL_CLAIMS"}
)
FORBIDDEN_CAPABILITIES = frozenset({"CONTACT", "MESSAGE", "RFQ", "ORDER", "PURCHASE", "PAYMENT"})


@dataclass(frozen=True)
class RetryDecision:
    retryable: bool
    failure_code: str
    retry_after_seconds: int | None = None


def parse_retry_after(value: object, *, max_seconds: int = 3600) -> int | None:
    """Normalize seconds or an HTTP date and cap it to a safe maximum."""
    if max_seconds < 0:
        raise ValueError("max_seconds must be non-negative")
    seconds: float
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
    elif isinstance(value, str):
        text = value.strip()
        try:
            seconds = float(text)
        except ValueError:
            try:
                target = parsedate_to_datetime(text)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=UTC)
                seconds = (target - _utcnow()).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return None
    else:
        return None
    return min(max_seconds, ceil(max(0.0, seconds)))


def classify_failure(
    code: str, *, retry_after: object = None, max_retry_after: int = 3600
) -> RetryDecision:
    normalized = str(code).upper().strip()
    normalized = FAILURE_ALIASES.get(normalized, normalized)
    return RetryDecision(
        normalized in RETRYABLE_FAILURES,
        normalized,
        parse_retry_after(retry_after, max_seconds=max_retry_after),
    )


def consume_retry_budget(db: Session, execution_id: uuid.UUID, *, max_attempts: int) -> int:
    """Atomically claim the next retry attempt for an execution."""
    if max_attempts < 0:
        raise ValueError("max_attempts must be non-negative")
    execution = db.scalar(
        select(MarketplaceExecution)
        .where(MarketplaceExecution.id == execution_id)
        .with_for_update()
    )
    if execution is None:
        raise LookupError("marketplace execution not found")
    if execution.attempt >= max_attempts:
        raise RuntimeError("marketplace retry budget exhausted")
    execution.attempt += 1
    db.flush()
    return execution.attempt


class MarketplaceAdapter(Protocol):
    def preflight(self) -> dict[str, object]: ...
    def search(self, query: str) -> object: ...
    def normalize(self, payload: object) -> list[dict[str, object]]: ...
    def classify_failure(self, error: Exception) -> str: ...


@dataclass(frozen=True)
class MarketplaceLifecycleResult:
    """Safe projection of one canonical marketplace lifecycle."""

    execution_id: uuid.UUID
    provider: str
    correlation_id: str
    checkpoint: str
    status: str
    idempotent_reuse: bool
    lineage: dict[str, str | None]
    counters: dict[str, int]


def _safe_lineage(
    *, execution: MarketplaceExecution, mission_id: uuid.UUID | None, task_id: uuid.UUID | None
) -> dict[str, str | None]:
    return {
        "mission_id": str(mission_id) if mission_id else None,
        "request_id": str(execution.id),
        "provider_execution_id": execution.provider_execution_id,
        "result_id": str(execution.id),
        "candidate_id": str(execution.id),
        "evidence_id": str(execution.id),
        "observation_id": str(execution.id),
        "change_id": str(execution.id),
        "alert_id": str(execution.id),
        "report_id": str(execution.id),
        "task_id": str(task_id) if task_id else None,
        "correlation_id": execution.correlation_id,
    }


LEDGER_ENTITY_TYPES = (
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
    "recovery",
)


def _ensure_ledger(
    db: Session,
    execution: MarketplaceExecution,
    entity_type: str,
    *,
    payload: dict[str, object] | None = None,
    logical_key: str | None = None,
) -> MarketplaceLedger:
    """Create or reuse one bounded canonical ledger row."""
    logical_key = logical_key or f"{execution.identity_key}:{entity_type}"
    row = db.scalar(
        select(MarketplaceLedger).where(
            MarketplaceLedger.owner_id == execution.owner_id,
            MarketplaceLedger.provider == execution.provider,
            MarketplaceLedger.entity_type == entity_type,
            MarketplaceLedger.logical_key == logical_key,
        )
    )
    if row is not None:
        return row
    row = MarketplaceLedger(
        owner_id=execution.owner_id,
        provider=execution.provider,
        execution_id=execution.id,
        entity_type=entity_type,
        logical_key=logical_key,
        correlation_id=execution.correlation_id,
        lineage={"execution_id": str(execution.id), "correlation_id": execution.correlation_id},
        payload=payload or {},
        status="PROJECTED",
    )
    db.add(row)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        row = db.scalar(
            select(MarketplaceLedger).where(
                MarketplaceLedger.owner_id == execution.owner_id,
                MarketplaceLedger.provider == execution.provider,
                MarketplaceLedger.entity_type == entity_type,
                MarketplaceLedger.logical_key == logical_key,
            )
        )
        if row is None:
            raise
    return row


def marketplace_integrity_counters(db: Session, owner: User) -> dict[str, int]:
    """Compute duplicate, orphan, broken-lineage, and cross-owner counters."""
    executions = list(db.scalars(select(MarketplaceExecution)))
    execution_ids = {value.id for value in executions}
    execution_owners = {value.id: value.owner_id for value in executions}
    rows = list(db.scalars(select(MarketplaceLedger).where(MarketplaceLedger.owner_id == owner.id)))
    counts: dict[tuple[str, str, str], int] = {}
    for row in rows:
        key = (row.provider, row.entity_type, row.logical_key)
        counts[key] = counts.get(key, 0) + 1
    duplicate_by_type: dict[str, int] = {}
    for (_, entity_type, _), count in counts.items():
        duplicate_by_type[entity_type] = duplicate_by_type.get(entity_type, 0) + max(0, count - 1)
    orphan = sum(row.execution_id not in execution_ids for row in rows)
    broken = sum(
        str((row.lineage or {}).get("execution_id")) != str(row.execution_id) for row in rows
    )
    cross_owner = sum(
        execution_owners.get(row.execution_id) is not None
        and execution_owners[row.execution_id] != row.owner_id
        for row in rows
    )
    return {
        "duplicate_executions": 0,
        "duplicate_requests": duplicate_by_type.get("request", 0),
        "duplicate_results": duplicate_by_type.get("result", 0),
        "duplicate_candidates": duplicate_by_type.get("candidate", 0),
        "duplicate_evidence": duplicate_by_type.get("evidence", 0),
        "duplicate_observations": duplicate_by_type.get("observation", 0),
        "duplicate_changes": duplicate_by_type.get("change", 0),
        "duplicate_alerts": duplicate_by_type.get("alert", 0),
        "duplicate_recovery": duplicate_by_type.get("recovery", 0),
        "duplicate_reports": duplicate_by_type.get("report", 0),
        "orphan_rows": orphan,
        "broken_lineage": broken,
        "cross_owner_rows": cross_owner,
    }


@dataclass(frozen=True)
class MarketplaceRecoveryResult:
    execution_id: uuid.UUID
    action: str
    idempotent_reuse: bool
    status: str


def execute_marketplace_recovery(
    db: Session,
    owner: User,
    execution_id: uuid.UUID,
    *,
    action: str = "retry",
) -> MarketplaceRecoveryResult:
    """Authorize and idempotently execute a marketplace recovery action."""
    if action not in {"retry", "replay"}:
        raise ValueError("unsupported marketplace recovery action")
    execution = db.scalar(
        select(MarketplaceExecution)
        .where(MarketplaceExecution.id == execution_id, MarketplaceExecution.owner_id == owner.id)
        .with_for_update()
    )
    if execution is None:
        raise LookupError("marketplace execution not found")
    key = f"{execution.identity_key}:recovery:{action}"
    existing = db.scalar(
        select(MarketplaceLedger).where(
            MarketplaceLedger.owner_id == owner.id,
            MarketplaceLedger.provider == execution.provider,
            MarketplaceLedger.entity_type == "recovery",
            MarketplaceLedger.logical_key == key,
        )
    )
    if existing is not None:
        return MarketplaceRecoveryResult(execution.id, action, True, execution.status)
    _ensure_ledger(
        db,
        execution,
        "recovery",
        payload={"action": action},
        logical_key=key,
    )
    execution.status = "RETRY_WAIT"
    record_event(
        db,
        actor_id=owner.id,
        action="marketplace.recovery.executed",
        entity_type="marketplace_execution",
        entity_id=execution.id,
        metadata={"action": action},
        idempotency_key=f"marketplace:recovery:{execution.id}:{action}",
    )
    db.commit()
    return MarketplaceRecoveryResult(execution.id, action, False, execution.status)


def execute_marketplace_lifecycle(
    db: Session,
    owner: User,
    adapter: MarketplaceAdapter,
    *,
    provider: str,
    mission_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    correlation_id: str | None = None,
    identity_key: str,
    query: str,
    mode: str = "LOCAL_FIXTURE",
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    retry_after: object = None,
    max_retry_after: int = 3600,
) -> MarketplaceLifecycleResult:
    """Run one durable provider-neutral lifecycle; replay never duplicates work."""
    existing = db.scalar(
        select(MarketplaceExecution)
        .where(
            MarketplaceExecution.owner_id == owner.id,
            MarketplaceExecution.provider == provider,
            MarketplaceExecution.identity_key == identity_key,
        )
        .with_for_update()
    )
    if existing is None:
        execution = MarketplaceExecution(
            owner_id=owner.id,
            provider=provider,
            mission_id=mission_id,
            task_id=task_id,
            correlation_id=correlation_id or uuid.uuid4().hex,
            identity_key=identity_key,
            status="RUNNING",
            checkpoint="CLAIMED",
            attempt=0,
            counters={},
        )
        db.add(execution)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(MarketplaceExecution)
                .where(
                    MarketplaceExecution.owner_id == owner.id,
                    MarketplaceExecution.provider == provider,
                    MarketplaceExecution.identity_key == identity_key,
                )
                .with_for_update()
            )
            if existing is None:
                raise
    if existing is not None:
        execution = existing
        if execution.status == "SUCCEEDED" and execution.checkpoint == "TERMINAL":
            return MarketplaceLifecycleResult(
                execution.id,
                execution.provider,
                execution.correlation_id,
                execution.checkpoint,
                execution.status,
                True,
                {
                    str(key): (str(value) if value is not None else None)
                    for key, value in (execution.lineage or {}).items()
                },
                dict(execution.counters or {}),
            )
    checkpoint_index = {value: index for index, value in enumerate(CHECKPOINTS)}
    try:
        if checkpoint_index.get(execution.checkpoint, 0) < checkpoint_index["PROVIDER_COMPLETE"]:
            checkpoint(execution, "BEFORE_PROVIDER", status="RUNNING")
            preflight = adapter.preflight()
            if str(preflight.get("status", "READY")) not in {"READY", "LOCAL_FIXTURE"}:
                execution.failure_code = "PROVIDER_DISABLED"
                execution.status = "FAILED"
                db.commit()
                return MarketplaceLifecycleResult(
                    execution.id,
                    execution.provider,
                    execution.correlation_id,
                    execution.checkpoint,
                    execution.status,
                    False,
                    {},
                    {},
                )
            consume_rate_window(
                db,
                owner,
                provider,
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour,
            )
            db.commit()
            inject_test_fault("BEFORE_PROVIDER", mode=mode)
            execution.provider_payload = adapter.search(query)
            execution.provider_execution_id = f"{provider.lower()}:{execution.id}"
            checkpoint(execution, "PROVIDER_COMPLETE")
            db.flush()
            record_event(
                db,
                actor_id=owner.id,
                action="marketplace.discovery.requested",
                entity_type="marketplace_execution",
                entity_id=execution.id,
                idempotency_key=f"marketplace:requested:{execution.id}",
            )
            record_event(
                db,
                actor_id=owner.id,
                action="marketplace.discovery.completed",
                entity_type="marketplace_execution",
                entity_id=execution.id,
                idempotency_key=f"marketplace:completed:{execution.id}",
            )
            db.commit()
        inject_test_fault("AFTER_PROVIDER", mode=mode)
        if checkpoint_index.get(execution.checkpoint, 0) < checkpoint_index["RESULTS_PERSISTED"]:
            normalized = adapter.normalize(execution.provider_payload)
            execution.counters = {
                "provider_requests": 1,
                "provider_executions": 1,
                "results": 1,
                "candidates": len(normalized),
                "evidence": len(normalized),
                "observations": len(normalized),
                "changes": 0,
                "alerts": 0,
                "reports": 1,
            }
            checkpoint(execution, "RESULTS_PERSISTED")
            db.commit()
            inject_test_fault("AFTER_RESULT", mode=mode)
        if checkpoint_index.get(execution.checkpoint, 0) < checkpoint_index["EVIDENCE_PERSISTED"]:
            checkpoint(execution, "EVIDENCE_PERSISTED")
            record_event(
                db,
                actor_id=owner.id,
                action="marketplace.evidence.projected",
                entity_type="marketplace_execution",
                entity_id=execution.id,
                idempotency_key=f"marketplace:evidence:{execution.id}",
            )
            db.commit()
            inject_test_fault("AFTER_EVIDENCE", mode=mode)
        if checkpoint_index.get(execution.checkpoint, 0) < checkpoint_index["CHANGE_COMPLETE"]:
            checkpoint(execution, "CHANGE_COMPLETE")
            db.commit()
            inject_test_fault("AFTER_CHANGE", mode=mode)
        if checkpoint_index.get(execution.checkpoint, 0) < checkpoint_index["ALERT_COMPLETE"]:
            checkpoint(execution, "ALERT_COMPLETE")
            db.commit()
            inject_test_fault("AFTER_ALERT", mode=mode)
        if checkpoint_index.get(execution.checkpoint, 0) < checkpoint_index["REPORT_COMPLETE"]:
            checkpoint(execution, "REPORT_COMPLETE")
        ledger_rows = {
            entity_type: _ensure_ledger(
                db,
                execution,
                entity_type,
                payload={"count": (execution.counters or {}).get(entity_type + "s", 0)},
            )
            for entity_type in LEDGER_ENTITY_TYPES
            if entity_type != "recovery"
        }
        lineage = {
            **_safe_lineage(
                execution=execution, mission_id=execution.mission_id, task_id=execution.task_id
            ),
            **{f"{entity_type}_id": str(row.id) for entity_type, row in ledger_rows.items()},
        }
        execution.lineage = cast(dict[str, object], lineage)
        execution.counters = dict(execution.counters or {})
        checkpoint(execution, "TERMINAL", status="SUCCEEDED")
        execution.completed_at = _utcnow()
        record_event(
            db,
            actor_id=owner.id,
            action="marketplace.discovery.completed",
            entity_type="marketplace_execution",
            entity_id=execution.id,
            idempotency_key=f"marketplace:terminal:{execution.id}",
        )
        db.commit()
        return MarketplaceLifecycleResult(
            execution.id,
            execution.provider,
            execution.correlation_id,
            execution.checkpoint,
            execution.status,
            existing is not None,
            lineage,
            dict(execution.counters or {}),
        )
    except MarketplaceRateLimited as exc:
        execution.failure_code = "RATE_LIMITED"
        execution.retry_after_seconds = min(3600.0, max(0.0, exc.result.retry_after_seconds))
        execution.status = "FAILED"
        record_event(
            db,
            actor_id=owner.id,
            action="marketplace.discovery.rate_limited",
            entity_type="marketplace_execution",
            entity_id=execution.id,
            idempotency_key=f"marketplace:rate:{execution.id}",
        )
        db.commit()
        raise
    except Exception as exc:
        decision = classify_failure(
            adapter.classify_failure(exc), retry_after=retry_after, max_retry_after=max_retry_after
        )
        execution.failure_code = decision.failure_code
        execution.retry_after_seconds = decision.retry_after_seconds
        execution.status = "RETRY_WAIT" if decision.retryable else "FAILED"
        record_event(
            db,
            actor_id=owner.id,
            action="marketplace.discovery.failed",
            entity_type="marketplace_execution",
            entity_id=execution.id,
            metadata={"failure_code": decision.failure_code},
            idempotency_key=f"marketplace:failed:{execution.id}:{execution.checkpoint}",
        )
        if decision.failure_code in {"BUDGET_EXHAUSTED", "RETRY_BUDGET_EXHAUSTED"}:
            record_event(
                db,
                actor_id=owner.id,
                action="marketplace.discovery.budget_exhausted",
                entity_type="marketplace_execution",
                entity_id=execution.id,
                idempotency_key=f"marketplace:budget:{execution.id}:{execution.checkpoint}",
            )
        db.commit()
        raise


def validate_capabilities(
    capabilities: Iterator[str] | tuple[str, ...] | set[str],
) -> frozenset[str]:
    declared = frozenset(str(value).upper() for value in capabilities)
    forbidden = declared & FORBIDDEN_CAPABILITIES
    if forbidden:
        raise ValueError(f"read-only marketplace runtime forbids: {', '.join(sorted(forbidden))}")
    unknown = declared - MARKETPLACE_CAPABILITIES
    if unknown:
        raise ValueError(f"unsupported marketplace capabilities: {', '.join(sorted(unknown))}")
    return declared


def bounded_percentile(samples: list[float], percentile: float) -> float:
    if not samples:
        return 0.0
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, max(0, ceil(percentile / 100 * len(ordered)) - 1))]
