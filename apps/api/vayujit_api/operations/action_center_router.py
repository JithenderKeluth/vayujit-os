# ruff: noqa: E501
"""Deterministic, owner-scoped Business Agent operational intelligence.

This router projects canonical Seller OS facts into signals. It never mutates
inventory, orders, listings, financial facts, suppliers, or marketplaces.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from vayujit_api.catalog.models import CatalogListingDraft
from vayujit_api.commerce.financial_models import (
    FinancialCalculationSnapshot,
    FinancialSettlementReconciliation,
)
from vayujit_api.commerce.models import (
    InventoryItem,
    MarketplaceImportJob,
    MarketplaceOrder,
    MarketplaceOrderItem,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.operations.operational_models import (
    OperationalAutomationPolicy,
    OperationalBriefing,
    OperationalNotification,
    OperationalSignal,
    OperationalSignalTransition,
)

router = APIRouter(prefix="/api/v1/operations/action-center", tags=["action-center"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


class SnoozeRequest(BaseModel):
    until: datetime
    idempotency_key: str = Field(min_length=8, max_length=240)
    note: str | None = Field(default=None, max_length=500)


class TransitionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=240)
    note: str | None = Field(default=None, max_length=500)


class ActionRequest(BaseModel):
    action_type: str = Field(min_length=1, max_length=80)
    actor_type: Literal["HUMAN", "AI", "SYSTEM"] = "HUMAN"
    idempotency_key: str = Field(min_length=8, max_length=240)


class PolicyRequest(BaseModel):
    enabled: bool | None = None
    dry_run: bool | None = None
    emergency_stop: bool | None = None
    severity_threshold: Literal["critical", "high", "medium", "low", "info"] | None = None
    minimum_confidence: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    cooldown_seconds: int | None = Field(default=None, ge=0, le=604800)
    maximum_actions_per_run: int | None = Field(default=None, ge=1, le=1000)
    signal_types: dict[str, bool] | None = None
    notification_preferences: dict[str, bool] | None = None


def _score(severity: str, confidence: Decimal | None, actionability: int = 1) -> Decimal:
    base = {"critical": 100, "high": 75, "medium": 50, "low": 25, "info": 10}[severity]
    quality = (confidence or Decimal("0.5")) * Decimal("10")
    return (Decimal(base) + quality + Decimal(actionability * 3)).quantize(Decimal("0.01"))


def _fingerprint(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_policy(db: Session, owner: User, stamp: datetime) -> OperationalAutomationPolicy:
    policy = db.scalar(
        select(OperationalAutomationPolicy).where(OperationalAutomationPolicy.owner_id == owner.id)
    )
    if policy is None:
        policy = OperationalAutomationPolicy(owner_id=owner.id, created_at=stamp, updated_at=stamp)
        db.add(policy)
        db.flush()
    return policy


def _transition(
    db: Session,
    owner: User,
    signal: OperationalSignal,
    target: str,
    key: str,
    note: str | None,
    *,
    actor_type: str = "HUMAN",
    until: datetime | None = None,
) -> OperationalSignalTransition:
    if actor_type != "HUMAN":
        raise HTTPException(403, "Only a HUMAN seller may change an operational signal.")
    existing = db.scalar(
        select(OperationalSignalTransition).where(
            OperationalSignalTransition.owner_id == owner.id,
            OperationalSignalTransition.idempotency_key == key,
        )
    )
    expiry = until.astimezone(UTC).isoformat() if until is not None else None
    if existing is not None:
        prior_expiry = existing.metadata_json.get("snoozed_until")
        if prior_expiry is None and target == "SNOOZED" and signal.snoozed_until is not None:
            # Legacy transitions have no expiry metadata; validate the persisted hold.
            prior_expiry = signal.snoozed_until.astimezone(UTC).isoformat()
        if (
            existing.signal_id != signal.id
            or existing.to_status != target
            or existing.actor_type != "HUMAN"
            or existing.actor_id != owner.id
            or existing.note != note
            or (target == "SNOOZED" and prior_expiry != expiry)
        ):
            raise HTTPException(409, "Idempotency key belongs to a different signal transition.")
        return existing
    if signal.status == "STALE":
        raise HTTPException(409, "Signal evidence changed; rescan before recording a new action.")
    stamp = now()
    previous = signal.status
    signal.status = target
    signal.snoozed_until = until if target == "SNOOZED" else None
    signal.last_transition_at = stamp
    signal.updated_at = stamp
    row = OperationalSignalTransition(
        owner_id=owner.id,
        signal_id=signal.id,
        from_status=previous,
        to_status=target,
        actor_type="HUMAN",
        actor_id=owner.id,
        note=note,
        idempotency_key=key,
        metadata_json={"policy_version": "pr-sos-06-v1", "snoozed_until": expiry},
        created_at=stamp,
    )
    db.add(row)
    return row


def _stock_transition(
    db: Session,
    owner: User,
    row: OperationalSignal,
    target: Literal["STALE", "REOPENED"],
    note: str,
    stamp: datetime,
) -> None:
    """Derived-state audit, never HUMAN approval or a canonical inventory write."""
    db.add(
        OperationalSignalTransition(
            owner_id=owner.id,
            signal_id=row.id,
            from_status=row.status,
            to_status=target,
            actor_type="SYSTEM",
            actor_id=owner.id,
            note=note,
            idempotency_key=f"stock-{target.lower()}:{row.id}:{row.last_transition_at.isoformat()}",
            metadata_json={
                "policy_version": "pr-sos-06-v1",
                "read_only": True,
                "actor_id_role": "installation_owner_context",
                "source_version": row.source_version,
            },
            created_at=stamp,
        )
    )
    row.status = target
    row.snoozed_until = None
    row.last_transition_at = stamp
    row.updated_at = stamp
    if target == "STALE":
        row.fresh_until = stamp


def _refresh_stock_signals(db: Session, owner: User) -> None:
    # Serialize derived signal transactions, not canonical inventory writers.
    # Use a fresh inventory snapshot and its version for revalidation. Locking every
    # inventory row here would invert multi-line order writers' existing lock order.
    key = int.from_bytes(
        hashlib.sha256(f"stock-signals:{owner.id}".encode()).digest()[:8], signed=True
    )
    db.execute(select(func.pg_advisory_xact_lock(key)))
    items = db.scalars(
        select(InventoryItem).where(InventoryItem.owner_id == owner.id).order_by(InventoryItem.id)
    ).all()
    by_id = {str(item.id): item for item in items}
    rows = db.scalars(
        select(OperationalSignal)
        .where(
            OperationalSignal.owner_id == owner.id,
            OperationalSignal.source_authority == "InventoryItem",
            OperationalSignal.signal_type.in_(["out_of_stock", "low_stock"]),
            OperationalSignal.status != "STALE",
        )
        .order_by(OperationalSignal.id)
        .with_for_update()
    ).all()
    stamp = now()
    for row in rows:
        item = by_id.get(row.source_resource_id or "")
        available = (
            item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity if item else None
        )
        current_type = "out_of_stock" if available is not None and available <= 0 else "low_stock"
        current = (
            item is not None
            and item.low_stock_threshold > 0
            and available is not None
            and available <= item.low_stock_threshold
            and row.signal_type == current_type
            and row.source_version in {str(item.version), f"v{item.version}"}
            and row.evidence_json.get("available") == available
            and row.evidence_json.get("threshold") == item.low_stock_threshold
        )
        if not current:
            _stock_transition(
                db,
                owner,
                row,
                "STALE",
                "Canonical inventory changed; historical stock evidence is no longer current. Rescan required.",
                stamp,
            )
    db.flush()


def _signal_dict(row: OperationalSignal) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "signal_type": row.signal_type,
        "category": row.category,
        "marketplace": row.marketplace,
        "source_authority": row.source_authority,
        "source_resource_type": row.source_resource_type,
        "source_resource_id": row.source_resource_id,
        "source_version": row.source_version,
        "signal_kind": row.signal_kind,
        "severity": row.severity,
        "confidence": str(row.confidence) if row.confidence is not None else "UNKNOWN",
        "evidence_quality": row.evidence_quality,
        "observed_at": row.observed_at.isoformat(),
        "fresh_until": row.fresh_until.isoformat() if row.fresh_until else None,
        "status": row.status,
        "title": row.title,
        "explanation": row.explanation,
        "uncertainty": row.uncertainty,
        "recommended_action": row.recommended_action,
        "recommended_action_type": row.recommended_action_type,
        "source_route": row.source_route,
        "evidence": row.evidence_json,
        "rule_version": row.rule_version,
        "fingerprint": row.fingerprint,
        "priority_score": str(row.priority_score),
        "snoozed_until": row.snoozed_until.isoformat() if row.snoozed_until else None,
        "updated_at": row.updated_at.isoformat(),
    }


def _upsert_signal(
    db: Session, owner: User, spec: dict[str, Any], stamp: datetime
) -> OperationalSignal:
    row = db.scalar(
        select(OperationalSignal)
        .where(
            OperationalSignal.owner_id == owner.id,
            OperationalSignal.fingerprint == spec["fingerprint"],
        )
        .with_for_update()
    )
    if row is None:
        row = OperationalSignal(
            owner_id=owner.id, created_at=stamp, updated_at=stamp, last_transition_at=stamp, **spec
        )
        db.add(row)
        db.flush()
        if spec["severity"] in {"critical", "high"}:
            db.add(
                OperationalNotification(
                    owner_id=owner.id,
                    signal_id=row.id,
                    notification_type=(
                        "NEW_CRITICAL" if spec["severity"] == "critical" else "NEW_HIGH"
                    ),
                    dedupe_key=spec["fingerprint"],
                    title=spec["title"],
                    body=spec["explanation"],
                    created_at=stamp,
                )
            )
        return row
    was_resolved = row.status in {"RESOLVED", "STALE"}
    for key in (
        "signal_type",
        "category",
        "marketplace",
        "source_authority",
        "source_resource_type",
        "source_resource_id",
        "source_version",
        "signal_kind",
        "severity",
        "confidence",
        "evidence_quality",
        "observed_at",
        "fresh_until",
        "title",
        "explanation",
        "uncertainty",
        "recommended_action",
        "recommended_action_type",
        "source_route",
        "evidence_json",
        "rule_version",
        "priority_score",
    ):
        setattr(row, key, spec[key])
    if was_resolved:
        if row.source_authority == "InventoryItem" and row.signal_type in {
            "low_stock",
            "out_of_stock",
        }:
            _stock_transition(
                db,
                owner,
                row,
                "REOPENED",
                "Stock issue re-evaluated from canonical inventory.",
                stamp,
            )
        else:
            _transition(
                db,
                owner,
                row,
                "REOPENED",
                f"reopen:{spec['fingerprint']}:{spec['source_version']}",
                "Source issue recurred.",
            )
    row.updated_at = stamp
    return row


def _spec(
    *,
    owner: User,
    signal_type: str,
    category: str,
    severity: str,
    title: str,
    explanation: str,
    recommended_action: str,
    source_authority: str,
    source_resource_type: str,
    source_resource_id: object,
    source_route: str | None,
    evidence: dict[str, object],
    marketplace: str | None = None,
    confidence: Decimal | None = Decimal("0.90"),
    uncertainty: str | None = None,
    action_type: str = "HUMAN_APPROVAL_REQUIRED",
) -> dict[str, Any]:
    stamp = now()
    source_version = str(evidence.get("version", "v1"))
    fingerprint = _fingerprint(owner.id, signal_type, source_resource_id, source_version)
    return {
        "signal_type": signal_type,
        "category": category,
        "marketplace": marketplace,
        "source_authority": source_authority,
        "source_resource_type": source_resource_type,
        "source_resource_id": str(source_resource_id) if source_resource_id is not None else None,
        "source_version": source_version,
        "signal_kind": "DERIVED",
        "severity": severity,
        "confidence": confidence,
        "evidence_quality": (
            "observed" if confidence and confidence >= Decimal("0.8") else "partial"
        ),
        "observed_at": stamp,
        "fresh_until": stamp + timedelta(hours=24),
        "status": "NEW",
        "title": title,
        "explanation": explanation,
        "uncertainty": uncertainty,
        "recommended_action": recommended_action,
        "recommended_action_type": action_type,
        "source_route": source_route,
        "evidence_json": evidence,
        "rule_version": "pr-sos-06-v1",
        "fingerprint": fingerprint,
        "priority_score": _score(severity, confidence),
    }


def _scan(db: Session, owner: User) -> tuple[int, datetime]:
    stamp = now()
    _refresh_stock_signals(db, owner)
    _ensure_policy(db, owner, stamp)
    count = 0
    for item in db.scalars(
        select(InventoryItem).where(InventoryItem.owner_id == owner.id).order_by(InventoryItem.id)
    ).all():
        available = item.on_hand_quantity - item.reserved_quantity - item.damaged_quantity
        if item.low_stock_threshold > 0 and available <= item.low_stock_threshold:
            severity = "critical" if available <= 0 else "high"
            _upsert_signal(
                db,
                owner,
                _spec(
                    owner=owner,
                    signal_type="out_of_stock" if available <= 0 else "low_stock",
                    category="inventory",
                    severity=severity,
                    title="Out of stock" if available <= 0 else "Low stock risk",
                    explanation=f"SKU {item.internal_sku} has {available} available units against a threshold of {item.low_stock_threshold}.",
                    recommended_action="Review inventory evidence and decide whether a local replenishment workflow is needed.",
                    source_authority="InventoryItem",
                    source_resource_type="inventory_item",
                    source_resource_id=item.id,
                    source_route="/marketplaces/inventory",
                    evidence={
                        "available": available,
                        "threshold": item.low_stock_threshold,
                        "sku": item.internal_sku,
                        "version": item.version,
                    },
                ),
                stamp,
            )
            count += 1
    for order in db.scalars(
        select(MarketplaceOrder).where(
            MarketplaceOrder.owner_id == owner.id, MarketplaceOrder.status == "failed"
        )
    ).all():
        _upsert_signal(
            db,
            owner,
            _spec(
                owner=owner,
                signal_type="order_exception",
                category="orders",
                severity="high",
                title="Order processing exception",
                explanation=f"Order {order.remote_order_id} is in a failed state and requires review.",
                recommended_action="Open the order workspace and inspect the canonical lifecycle and reservation evidence.",
                source_authority="MarketplaceOrder",
                source_resource_type="marketplace_order",
                source_resource_id=order.id,
                marketplace=order.marketplace,
                source_route="/marketplaces/orders",
                evidence={"status": order.status, "remote_order_id": order.remote_order_id},
            ),
            stamp,
        )
        count += 1
    for order_item in db.scalars(
        select(MarketplaceOrderItem).where(
            MarketplaceOrderItem.owner_id == owner.id, MarketplaceOrderItem.product_id.is_(None)
        )
    ).all():
        _upsert_signal(
            db,
            owner,
            _spec(
                owner=owner,
                signal_type="unmapped_order_line",
                category="orders",
                severity="medium",
                title="Order line is not mapped",
                explanation=f"Order line {order_item.id} has no canonical Product mapping.",
                recommended_action="Review the order mapping before using inventory or profitability decisions.",
                source_authority="MarketplaceOrderItem",
                source_resource_type="marketplace_order_item",
                source_resource_id=order_item.id,
                source_route="/marketplaces/orders",
                evidence={"marketplace_sku": order_item.marketplace_sku},
            ),
            stamp,
        )
        count += 1
    for draft in db.scalars(
        select(CatalogListingDraft).where(
            CatalogListingDraft.owner_id == owner.id,
            CatalogListingDraft.readiness_state == "BLOCKED",
        )
    ).all():
        _upsert_signal(
            db,
            owner,
            _spec(
                owner=owner,
                signal_type="listing_blocker",
                category="catalog",
                severity="high",
                title="Listing readiness is blocked",
                explanation=f"The {draft.channel} listing draft is blocked by required catalog information.",
                recommended_action="Open the catalog listing draft, address the listed missing fields, then request HUMAN review.",
                source_authority="CatalogListingDraft",
                source_resource_type="catalog_listing_draft",
                source_resource_id=draft.id,
                source_route=f"/catalog/{draft.product_id}",
                evidence={
                    "missing_fields": draft.missing_fields,
                    "readiness_state": draft.readiness_state,
                    "version": draft.version,
                },
            ),
            stamp,
        )
        count += 1
    for snapshot in db.scalars(
        select(FinancialCalculationSnapshot).where(
            FinancialCalculationSnapshot.owner_id == owner.id
        )
    ).all():
        metrics = snapshot.metrics_json or {}
        contribution = metrics.get("contribution") or metrics.get("estimated_profit")
        if isinstance(contribution, (int, float, str)) and str(contribution) not in {
            "UNKNOWN",
            "None",
        }:
            try:
                negative = Decimal(str(contribution)) < 0
            except Exception:
                negative = False
            if negative:
                _upsert_signal(
                    db,
                    owner,
                    _spec(
                        owner=owner,
                        signal_type="negative_contribution",
                        category="financial",
                        severity="critical",
                        title="Negative contribution requires review",
                        explanation="A durable financial snapshot shows contribution below zero.",
                        recommended_action="Review source costs, fees, and refunds before making a commercial decision.",
                        source_authority="FinancialCalculationSnapshot",
                        source_resource_type="financial_snapshot",
                        source_resource_id=snapshot.id,
                        marketplace=snapshot.marketplace,
                        source_route="/marketplaces/financials",
                        evidence={"metrics": metrics, "version": snapshot.calculation_version},
                    ),
                    stamp,
                )
                count += 1
    for reconciliation in db.scalars(
        select(FinancialSettlementReconciliation).where(
            FinancialSettlementReconciliation.owner_id == owner.id,
            FinancialSettlementReconciliation.status == "mismatch",
        )
    ).all():
        _upsert_signal(
            db,
            owner,
            _spec(
                owner=owner,
                signal_type="settlement_mismatch",
                category="financial",
                severity="high",
                title="Settlement discrepancy needs review",
                explanation=f"Settlement {reconciliation.settlement_key} does not match the expected amount.",
                recommended_action="Inspect settlement evidence and reconcile the reported amount manually.",
                source_authority="FinancialSettlementReconciliation",
                source_resource_type="settlement_reconciliation",
                source_resource_id=reconciliation.id,
                marketplace=reconciliation.marketplace,
                source_route="/marketplaces/financials",
                evidence={
                    "expected": (
                        str(reconciliation.expected_amount)
                        if reconciliation.expected_amount is not None
                        else "UNKNOWN"
                    ),
                    "reported": (
                        str(reconciliation.reported_amount)
                        if reconciliation.reported_amount is not None
                        else "UNKNOWN"
                    ),
                    "difference": (
                        str(reconciliation.difference_amount)
                        if reconciliation.difference_amount is not None
                        else "UNKNOWN"
                    ),
                },
            ),
            stamp,
        )
        count += 1
    latest_imports: dict[tuple[uuid.UUID, str], MarketplaceImportJob] = {}
    for import_job in db.scalars(
        select(MarketplaceImportJob).where(MarketplaceImportJob.owner_id == owner.id)
    ).all():
        key = (import_job.account_id, import_job.operation)
        current = latest_imports.get(key)
        if current is None or import_job.created_at > current.created_at:
            latest_imports[key] = import_job
    for import_job in latest_imports.values():
        if import_job.status in {"FAILED", "PARTIAL"}:
            _upsert_signal(
                db,
                owner,
                _spec(
                    owner=owner,
                    signal_type="marketplace_import_exception",
                    category="marketplace",
                    severity="high" if import_job.status == "FAILED" else "medium",
                    title="Marketplace import requires review",
                    explanation=(
                        f"The {import_job.marketplace} {import_job.operation} import "
                        f"is {import_job.status.lower()} and is not complete."
                    ),
                    recommended_action=(
                        "Open the Connection Center, inspect the import evidence, "
                        "and retry only after the provider or source issue is understood."
                    ),
                    source_authority="MarketplaceImportJob",
                    source_resource_type="marketplace_import_job",
                    source_resource_id=import_job.id,
                    marketplace=import_job.marketplace,
                    source_route=f"/marketplaces/accounts/{import_job.account_id}",
                    evidence={
                        "status": import_job.status,
                        "operation": import_job.operation,
                        "error_code": import_job.error_code or "UNKNOWN",
                        "version": import_job.updated_at.isoformat(),
                    },
                ),
                stamp,
            )
            count += 1
        elif (
            import_job.status == "SUCCEEDED"
            and import_job.stale_after is not None
            and import_job.stale_after < stamp
        ):
            _upsert_signal(
                db,
                owner,
                _spec(
                    owner=owner,
                    signal_type="marketplace_import_stale",
                    category="marketplace",
                    severity="medium",
                    title="Marketplace import is stale",
                    explanation=(
                        f"The last {import_job.marketplace} {import_job.operation} "
                        "import is outside its freshness window."
                    ),
                    recommended_action=(
                        "Open the Connection Center and run a bounded read-only import "
                        "before relying on this evidence."
                    ),
                    source_authority="MarketplaceImportJob",
                    source_resource_type="marketplace_import_job",
                    source_resource_id=import_job.id,
                    marketplace=import_job.marketplace,
                    source_route=f"/marketplaces/accounts/{import_job.account_id}",
                    evidence={
                        "stale_after": import_job.stale_after.isoformat(),
                        "operation": import_job.operation,
                        "version": import_job.updated_at.isoformat(),
                    },
                ),
                stamp,
            )
            count += 1
    db.commit()
    return count, stamp


def _expire_snoozes(db: Session, owner: User) -> None:
    _refresh_stock_signals(db, owner)
    stamp = now()
    rows = db.scalars(
        select(OperationalSignal).where(
            OperationalSignal.owner_id == owner.id,
            OperationalSignal.status == "SNOOZED",
            OperationalSignal.snoozed_until <= stamp,
        )
    ).all()
    for row in rows:
        _transition(
            db, owner, row, "REOPENED", f"expiry:{row.id}:{row.snoozed_until}", "Snooze expired."
        )
    db.flush()


def _briefing(db: Session, owner: User) -> dict[str, Any]:
    _expire_snoozes(db, owner)
    rows = db.scalars(select(OperationalSignal).where(OperationalSignal.owner_id == owner.id)).all()
    active = [row for row in rows if row.status not in {"RESOLVED", "STALE"}]
    priorities = sorted(
        active, key=lambda row: (-Decimal(row.priority_score), row.observed_at, str(row.id))
    )
    categories: dict[str, int] = {}
    for row in active:
        categories[row.category] = categories.get(row.category, 0) + 1
    return {
        "generated_at": now().isoformat(),
        "source": "OperationalSignal projection",
        "priorities": [_signal_dict(row) for row in priorities[:5]],
        "counts": {
            "active": len(active),
            "critical": sum(row.severity == "critical" for row in active),
            "high": sum(row.severity == "high" for row in active),
            "resolved": sum(row.status == "RESOLVED" for row in rows),
            "stale": sum(row.status == "STALE" for row in rows),
        },
        "category_breakdown": categories,
        "changes_since_previous": (
            "No prior baseline" if not rows else "Derived from persisted signal transitions."
        ),
        "read_only": True,
        "external_writes": False,
    }


@router.get("")
def action_center(
    db: DatabaseSession,
    owner: Owner,
    category: str | None = None,
    marketplace: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    include_resolved: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    brief = _briefing(db, owner)
    statement = select(OperationalSignal).where(OperationalSignal.owner_id == owner.id)
    if not include_resolved and status is None:
        statement = statement.where(OperationalSignal.status.not_in(["RESOLVED", "STALE"]))
    if category:
        statement = statement.where(OperationalSignal.category == category)
    if marketplace:
        statement = statement.where(OperationalSignal.marketplace == marketplace)
    if severity:
        statement = statement.where(OperationalSignal.severity == severity)
    if status:
        statement = statement.where(OperationalSignal.status == status)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            (OperationalSignal.title.ilike(term))
            | (OperationalSignal.explanation.ilike(term))
            | (OperationalSignal.signal_type.ilike(term))
        )
    rows = db.scalars(
        statement.order_by(
            desc(OperationalSignal.priority_score),
            desc(OperationalSignal.observed_at),
            OperationalSignal.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    policy = _ensure_policy(db, owner, now())
    db.commit()
    return {
        "signals": [_signal_dict(row) for row in rows],
        "total": int(total),
        "policy": _policy_dict(policy),
        "briefing": brief,
    }


def _policy_dict(policy: OperationalAutomationPolicy) -> dict[str, Any]:
    return {
        "enabled": policy.enabled,
        "dry_run": policy.dry_run,
        "emergency_stop": policy.emergency_stop,
        "severity_threshold": policy.severity_threshold,
        "minimum_confidence": str(policy.minimum_confidence),
        "cooldown_seconds": policy.cooldown_seconds,
        "maximum_actions_per_run": policy.maximum_actions_per_run,
        "signal_types": policy.signal_types_json,
        "notification_preferences": policy.notification_preferences_json,
        "policy_version": policy.policy_version,
        "updated_at": policy.updated_at.isoformat(),
    }


@router.post("/scan")
def scan(db: DatabaseSession, owner: Owner) -> dict[str, Any]:
    count, stamp = _scan(db, owner)
    return {
        "status": "completed",
        "signals_seen": count,
        "scan_at": stamp.isoformat(),
        "external_writes": False,
    }


@router.get("/briefing")
def briefing(db: DatabaseSession, owner: Owner) -> dict[str, Any]:
    payload = _briefing(db, owner)
    stamp = now()
    row = db.scalar(
        select(OperationalBriefing).where(
            OperationalBriefing.owner_id == owner.id,
            OperationalBriefing.snapshot_key == stamp.date().isoformat(),
        )
    )
    if row is None:
        row = OperationalBriefing(
            owner_id=owner.id,
            snapshot_key=stamp.date().isoformat(),
            source_scan_at=stamp,
            payload_json=payload,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(row)
    else:
        row.payload_json = payload
        row.source_scan_at = stamp
        row.updated_at = stamp
    db.commit()
    return payload


@router.get("/signals/{signal_id}")
def signal_detail(signal_id: uuid.UUID, db: DatabaseSession, owner: Owner) -> dict[str, Any]:
    _expire_snoozes(db, owner)
    row = db.scalar(
        select(OperationalSignal).where(
            OperationalSignal.id == signal_id, OperationalSignal.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Operational signal was not found.")
    history = db.scalars(
        select(OperationalSignalTransition)
        .where(
            OperationalSignalTransition.owner_id == owner.id,
            OperationalSignalTransition.signal_id == row.id,
        )
        .order_by(desc(OperationalSignalTransition.created_at))
    ).all()
    db.commit()
    return {
        "signal": _signal_dict(row),
        "history": [
            {
                "from_status": item.from_status,
                "to_status": item.to_status,
                "actor_type": item.actor_type,
                "note": item.note,
                "created_at": item.created_at.isoformat(),
            }
            for item in history
        ],
    }


def _get_signal(signal_id: uuid.UUID, db: Session, owner: User) -> OperationalSignal:
    _refresh_stock_signals(db, owner)
    row = db.scalar(
        select(OperationalSignal)
        .where(OperationalSignal.id == signal_id, OperationalSignal.owner_id == owner.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Operational signal was not found.")
    return row


@router.post("/signals/{signal_id}/acknowledge")
def acknowledge(
    signal_id: uuid.UUID, data: TransitionRequest, db: DatabaseSession, owner: Owner
) -> dict[str, Any]:
    row = _get_signal(signal_id, db, owner)
    transition = _transition(db, owner, row, "ACKNOWLEDGED", data.idempotency_key, data.note)
    db.commit()
    return {"signal": _signal_dict(row), "transition_id": str(transition.id)}


@router.post("/signals/{signal_id}/snooze")
def snooze(
    signal_id: uuid.UUID, data: SnoozeRequest, db: DatabaseSession, owner: Owner
) -> dict[str, Any]:
    if data.until <= now():
        raise HTTPException(422, "Snooze expiry must be in the future.")
    row = _get_signal(signal_id, db, owner)
    transition = _transition(
        db, owner, row, "SNOOZED", data.idempotency_key, data.note, until=data.until
    )
    db.commit()
    return {"signal": _signal_dict(row), "transition_id": str(transition.id)}


@router.post("/signals/{signal_id}/resolve")
def resolve(
    signal_id: uuid.UUID, data: TransitionRequest, db: DatabaseSession, owner: Owner
) -> dict[str, Any]:
    row = _get_signal(signal_id, db, owner)
    transition = _transition(db, owner, row, "RESOLVED", data.idempotency_key, data.note)
    db.commit()
    return {"signal": _signal_dict(row), "transition_id": str(transition.id)}


@router.post("/signals/{signal_id}/reopen")
def reopen(
    signal_id: uuid.UUID, data: TransitionRequest, db: DatabaseSession, owner: Owner
) -> dict[str, Any]:
    row = _get_signal(signal_id, db, owner)
    transition = _transition(db, owner, row, "REOPENED", data.idempotency_key, data.note)
    db.commit()
    return {"signal": _signal_dict(row), "transition_id": str(transition.id)}


@router.post("/signals/{signal_id}/action")
def request_action(
    signal_id: uuid.UUID, data: ActionRequest, db: DatabaseSession, owner: Owner
) -> dict[str, Any]:
    row = _get_signal(signal_id, db, owner)
    if data.actor_type != "HUMAN":
        raise HTTPException(403, "AI and SYSTEM actors cannot impersonate HUMAN approval.")
    if data.action_type.upper() in {
        "EXTERNAL_MUTATION",
        "PUBLISH",
        "CONTACT_SUPPLIER",
        "RFQ",
        "PAYMENT",
        "REFUND",
        "PRICE_CHANGE",
        "INVENTORY_PUBLICATION",
    }:
        raise HTTPException(
            403,
            "External actions are default-deny in PR-SOS-06 and require their canonical workflow.",
        )
    if row.status == "STALE":
        raise HTTPException(409, "Signal evidence changed; rescan before requesting an action.")
    db.commit()
    return {
        "status": "approval_required",
        "signal_id": str(row.id),
        "action_type": data.action_type,
        "external_writes": False,
        "message": "This is advisory only. No approval or execution was recorded; use the canonical HUMAN workflow before taking action.",
    }


@router.get("/policy")
def get_policy(db: DatabaseSession, owner: Owner) -> dict[str, Any]:
    policy = _ensure_policy(db, owner, now())
    db.commit()
    return _policy_dict(policy)


@router.patch("/policy")
def update_policy(data: PolicyRequest, db: DatabaseSession, owner: Owner) -> dict[str, Any]:
    policy = _ensure_policy(db, owner, now())
    changes = data.model_dump(exclude_none=True)
    if "signal_types" in changes:
        policy.signal_types_json = changes.pop("signal_types")
    if "notification_preferences" in changes:
        policy.notification_preferences_json = changes.pop("notification_preferences")
    stamp = now()
    for key, value in changes.items():
        setattr(policy, key, value)
    policy.policy_version = "pr-sos-06-policy-v1"
    policy.updated_at = stamp
    db.commit()
    return _policy_dict(policy)


@router.get("/notifications")
def notifications(db: DatabaseSession, owner: Owner, unread_only: bool = False) -> dict[str, Any]:
    statement = select(OperationalNotification).where(OperationalNotification.owner_id == owner.id)
    if unread_only:
        statement = statement.where(OperationalNotification.read_at.is_(None))
    rows = db.scalars(statement.order_by(desc(OperationalNotification.created_at)).limit(200)).all()
    return {
        "notifications": [
            {
                "id": str(row.id),
                "signal_id": str(row.signal_id),
                "type": row.notification_type,
                "title": row.title,
                "body": row.body,
                "read_at": row.read_at.isoformat() if row.read_at else None,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: uuid.UUID, db: DatabaseSession, owner: Owner
) -> dict[str, Any]:
    row = db.scalar(
        select(OperationalNotification).where(
            OperationalNotification.id == notification_id,
            OperationalNotification.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Notification was not found.")
    row.read_at = now()
    db.commit()
    return {"id": str(row.id), "read_at": row.read_at.isoformat()}
