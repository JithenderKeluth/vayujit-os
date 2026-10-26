"""Server-authoritative sales, fee, profitability and settlement projections."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.commerce.financial_models import (
    FinancialCalculationSnapshot,
    FinancialCostEvidence,
    FinancialEvent,
    FinancialFeeRule,
    FinancialSettlementReconciliation,
)
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceFee,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplaceRefund,
    MarketplaceSettlement,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/financial", tags=["financial intelligence"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]
MONEY = Decimal("0.01")
EVIDENCE_STATES = {"modeled", "observed", "reported", "verified", "unknown"}
LOCAL_SOURCE_TYPES = {
    "synthetic_fixture",
    "seller_entered",
    "marketplace_reported",
    "verified",
    "canonical_order",
    "canonical_fee",
    "canonical_refund",
    "canonical_settlement",
}


def _money(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result.quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise HTTPException(422, "Amount must be a valid decimal monetary value.") from error


class FinancialEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    source_event_id: str = Field(min_length=1, max_length=240)
    marketplace: str = Field(min_length=2, max_length=30)
    event_type: str
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    order_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    settlement_id: uuid.UUID | None = None
    effective_at: datetime | None = None
    evidence_status: str = "modeled"
    source_type: str = "synthetic_fixture"
    source_reference: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("Currency must be an ISO alphabetic code.")
        return value

    @field_validator("evidence_status")
    @classmethod
    def evidence_code(cls, value: str) -> str:
        if value not in EVIDENCE_STATES:
            raise ValueError("Unsupported evidence status.")
        return value


class CostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID | None = None
    marketplace: str | None = None
    sku: str | None = None
    cost_key: str = Field(min_length=1, max_length=220)
    cost_type: str = Field(min_length=1, max_length=40)
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str = "INR"
    evidence_status: str = "observed"
    source_type: str = "seller_entered"
    source_reference: str | None = None
    effective_from: datetime | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("Currency must be an ISO alphabetic code.")
        return value

    @field_validator("evidence_status")
    @classmethod
    def evidence_code(cls, value: str) -> str:
        if value not in EVIDENCE_STATES:
            raise ValueError("Unsupported evidence status.")
        return value


class FeeRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace: str
    category: str | None = None
    rule_key: str
    fee_type: str
    rate_percent: Decimal = Field(default=Decimal("0"), ge=0)
    fixed_amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = "INR"
    effective_from: datetime | None = None
    source_type: str = "synthetic_fixture"
    assumptions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("Currency must be an ISO alphabetic code.")
        return value


class ReconciliationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    settlement_key: str = Field(min_length=1, max_length=240)
    marketplace: str
    expected_amount: Decimal | None = Field(default=None, ge=0)
    reported_amount: Decimal | None = Field(default=None, ge=0)
    verified_amount: Decimal | None = Field(default=None, ge=0)
    currency: str = "INR"
    settlement_id: uuid.UUID | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("Currency must be an ISO alphabetic code.")
        return value


def _account(db: Session, user: User, account_id: uuid.UUID) -> MarketplaceAccount:
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id, MarketplaceAccount.owner_id == user.id
        )
    )
    if account is None:
        raise HTTPException(404, "Marketplace account was not found.")
    return account


def _json_amount(payload: dict[str, object], *keys: str) -> Decimal | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (Decimal, int, float, str)):
            try:
                return _money(value)
            except HTTPException:
                continue
    return None


def _event_query(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[FinancialEvent]:
    query = select(FinancialEvent).where(FinancialEvent.owner_id == user.id)
    if marketplace:
        query = query.where(FinancialEvent.marketplace == marketplace.lower())
    if date_from:
        query = query.where(FinancialEvent.effective_at >= date_from)
    if date_to:
        query = query.where(FinancialEvent.effective_at <= date_to)
    return list(
        db.scalars(query.order_by(FinancialEvent.effective_at, FinancialEvent.source_event_id))
    )


def _decimal_map(events: list[FinancialEvent]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    seen: set[tuple[uuid.UUID, str]] = set()
    for event in events:
        key = (event.account_id, event.source_event_id)
        if key in seen:
            continue
        seen.add(key)
        totals[event.event_type] += event.amount
    return totals


def _canonical_orders(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[MarketplaceOrder]:
    query = select(MarketplaceOrder).where(MarketplaceOrder.owner_id == user.id)
    if marketplace:
        query = query.where(MarketplaceOrder.marketplace == marketplace.lower())
    if date_from:
        query = query.where(MarketplaceOrder.ordered_at >= date_from)
    if date_to:
        query = query.where(MarketplaceOrder.ordered_at <= date_to)
    return list(db.scalars(query.order_by(MarketplaceOrder.ordered_at, MarketplaceOrder.id)))


def _canonical_fees(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[MarketplaceFee]:
    query = (
        select(MarketplaceFee)
        .join(MarketplaceAccount, MarketplaceAccount.id == MarketplaceFee.account_id)
        .where(MarketplaceFee.owner_id == user.id)
    )
    if marketplace:
        query = query.where(MarketplaceAccount.marketplace == marketplace.lower())
    if date_from:
        query = query.where(MarketplaceFee.occurred_at >= date_from)
    if date_to:
        query = query.where(MarketplaceFee.occurred_at <= date_to)
    return list(db.scalars(query.order_by(MarketplaceFee.occurred_at, MarketplaceFee.id)))


def _canonical_refunds(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[MarketplaceRefund]:
    query = (
        select(MarketplaceRefund)
        .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceRefund.order_id)
        .where(MarketplaceRefund.owner_id == user.id)
    )
    if marketplace:
        query = query.where(MarketplaceOrder.marketplace == marketplace.lower())
    if date_from:
        query = query.where(MarketplaceRefund.created_at >= date_from)
    if date_to:
        query = query.where(MarketplaceRefund.created_at <= date_to)
    return list(db.scalars(query.order_by(MarketplaceRefund.created_at, MarketplaceRefund.id)))


def _canonical_settlements(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[MarketplaceSettlement]:
    query = select(MarketplaceSettlement).where(MarketplaceSettlement.owner_id == user.id)
    if marketplace:
        query = query.where(MarketplaceSettlement.marketplace == marketplace.lower())
    if date_from:
        query = query.where(MarketplaceSettlement.period_end >= date_from)
    if date_to:
        query = query.where(MarketplaceSettlement.period_end <= date_to)
    return list(
        db.scalars(query.order_by(MarketplaceSettlement.period_end, MarketplaceSettlement.id))
    )


def _canonical_totals(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    orders = _canonical_orders(db, user, marketplace, date_from, date_to)
    fees = _canonical_fees(db, user, marketplace, date_from, date_to)
    refunds = _canonical_refunds(db, user, marketplace, date_from, date_to)
    sales = Decimal("0")
    discounts = Decimal("0")
    currency_mismatches: list[str] = []
    for order in orders:
        totals = order.totals_json or {}
        order_currency = str(totals.get("currency", "INR")).upper()
        if order_currency != "INR":
            currency_mismatches.append(f"order:{order.remote_order_id}:{order_currency}")
            continue
        amount = _json_amount(totals, "item_subtotal", "total")
        if amount is not None:
            sales += amount
        discount = order.discount_amount or _json_amount(totals, "discount", "discount_amount")
        if discount is not None:
            discounts += discount
    refund_total = Decimal("0")
    for refund_row in refunds:
        if refund_row.currency.upper() != "INR":
            currency_mismatches.append(f"refund:{refund_row.id}:{refund_row.currency.upper()}")
            continue
        refund_total += refund_row.amount
    fee_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for fee_row in fees:
        if fee_row.currency.upper() != "INR":
            currency_mismatches.append(f"fee:{fee_row.id}:{fee_row.currency.upper()}")
            continue
        fee_type = fee_row.fee_type.lower()
        if fee_type in {"shipping", "fulfilment", "tax"}:
            fee_totals[fee_type] += fee_row.amount
        else:
            fee_totals["fee"] += fee_row.amount
    return {
        "orders": orders,
        "fees": fees,
        "refunds": refunds,
        "sales": sales,
        "discounts": discounts,
        "refund_total": refund_total,
        "fee_totals": fee_totals,
        "currency_mismatches": currency_mismatches,
    }


def _validate_references(
    db: Session,
    user: User,
    account: MarketplaceAccount,
    order_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
    settlement_id: uuid.UUID | None,
) -> None:
    if order_id is not None:
        order = db.scalar(
            select(MarketplaceOrder).where(
                MarketplaceOrder.id == order_id, MarketplaceOrder.owner_id == user.id
            )
        )
        if order is None or order.account_id != account.id:
            raise HTTPException(404, "Order reference was not found in this seller account.")
    if product_id is not None:
        product = db.scalar(
            select(Product).where(Product.id == product_id, Product.owner_id == user.id)
        )
        if product is None:
            raise HTTPException(404, "Product reference was not found in this seller account.")
    if settlement_id is not None:
        settlement = db.scalar(
            select(MarketplaceSettlement).where(
                MarketplaceSettlement.id == settlement_id,
                MarketplaceSettlement.owner_id == user.id,
                MarketplaceSettlement.account_id == account.id,
            )
        )
        if settlement is None:
            raise HTTPException(404, "Settlement reference was not found in this seller account.")


def _validate_currency(currency: str, account: MarketplaceAccount) -> None:
    configured = str(account.configuration_json.get("currency", "INR")).upper()
    if currency != "INR" and currency != configured:
        raise HTTPException(
            422, "Currency conversion evidence is required before mixing currencies."
        )


def _validate_source(source_type: str) -> None:
    if source_type not in LOCAL_SOURCE_TYPES:
        raise HTTPException(
            422, "External providers are not callable from this local financial path."
        )


def _cost_evidence_rows(
    db: Session,
    user: User,
    marketplace: str | None = None,
    as_of: datetime | None = None,
) -> list[FinancialCostEvidence]:
    query = select(FinancialCostEvidence).where(
        FinancialCostEvidence.owner_id == user.id,
        FinancialCostEvidence.effective_from <= (as_of or now()),
    )
    if marketplace:
        query = query.where(
            (FinancialCostEvidence.marketplace.is_(None))
            | (FinancialCostEvidence.marketplace == marketplace.lower())
        )
    rows = list(
        db.scalars(
            query.order_by(
                FinancialCostEvidence.cost_key,
                FinancialCostEvidence.effective_from.desc(),
                FinancialCostEvidence.created_at.desc(),
                FinancialCostEvidence.id.desc(),
            )
        )
    )
    latest: dict[str, FinancialCostEvidence] = {}
    for row in rows:
        latest.setdefault(row.cost_key, row)
    return list(latest.values())


def _cost_state(rows: list[FinancialCostEvidence]) -> tuple[Decimal, bool, bool]:
    """Latest UNKNOWN is a blocker, not a request to search an older revision."""
    known = [row for row in rows if row.evidence_status != "unknown" and row.amount is not None]
    amount = sum((row.amount for row in known if row.amount is not None), Decimal("0"))
    unknown = any(row.evidence_status == "unknown" or row.amount is None for row in rows)
    return amount, bool(known), unknown


def _provenance(db: Session, user: User, rows: list[Any]) -> dict[str, Any]:
    """Classify persisted sources, never infer real/verified from absence of fake flags.

    Account configuration and explicit source types are declarations, not proof of
    a live provider acquisition. Canonical rows lacking provenance remain UNKNOWN.
    Positive synthetic ancestry always dominates a contradictory source claim.
    """
    accounts = {
        row.id: row
        for row in db.scalars(
            select(MarketplaceAccount).where(MarketplaceAccount.owner_id == user.id)
        )
    }
    parent_ids = {row.order_id for row in rows if getattr(row, "order_id", None)}
    parents = {
        row.id: row
        for row in db.scalars(
            select(MarketplaceOrder).where(
                MarketplaceOrder.owner_id == user.id, MarketplaceOrder.id.in_(parent_ids)
            )
        )
    }
    sources: list[dict[str, str]] = []
    for row in rows:
        parent_id = getattr(row, "order_id", None)
        parent = parents.get(parent_id) if parent_id is not None else None
        account_id = getattr(row, "account_id", None) or getattr(parent, "account_id", None)
        account = accounts.get(account_id) if account_id is not None else None
        metadata = [
            getattr(row, field, None) or {}
            for field in ("provenance_json", "payload_json", "totals_json")
        ]
        if parent is not None:
            metadata.append(parent.totals_json or {})
        source_type = getattr(row, "source_type", None)
        if not source_type:
            source_type = metadata[0].get("source_type")
        synthetic = (
            source_type == "synthetic_fixture"
            or any(data.get("fake_provider") is True for data in metadata)
            or (
                account is not None
                and (
                    account.environment == "sandbox"
                    or account.capabilities_json.get("fake_provider") is True
                )
            )
        )
        classification = (
            "SYNTHETIC"
            if synthetic
            else (
                "REPORTED"
                if source_type in {"seller_entered", "marketplace_reported", "verified"}
                else "UNKNOWN"
            )
        )
        sources.append(
            {"authority": type(row).__name__, "id": str(row.id), "classification": classification}
        )
    sources.sort(key=lambda source: (source["authority"], source["id"]))
    states = {source["classification"] for source in sources}
    status = next(iter(states)) if len(states) == 1 else "MIXED" if states else "UNKNOWN"
    return {
        "provenance_status": status,
        "synthetic_provider": "SYNTHETIC" in states,
        "provenance_unknown": not states or "UNKNOWN" in states,
        "provenance_sources": sources,
    }


def _event_response(row: FinancialEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "account_id": str(row.account_id),
        "order_id": str(row.order_id) if row.order_id else None,
        "product_id": str(row.product_id) if row.product_id else None,
        "settlement_id": str(row.settlement_id) if row.settlement_id else None,
        "marketplace": row.marketplace,
        "source_event_id": row.source_event_id,
        "event_type": row.event_type,
        "amount": str(row.amount),
        "currency": row.currency,
        "evidence_status": row.evidence_status,
        "source_type": row.source_type,
        "source_reference": row.source_reference,
        "effective_at": row.effective_at.isoformat(),
        "observed_at": row.observed_at.isoformat(),
        "calculation_version": row.calculation_version,
        "provenance": row.provenance_json,
        "payload": row.payload_json,
    }


def _summary(
    db: Session,
    user: User,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    events = _event_query(db, user, marketplace, date_from, date_to)
    totals = _decimal_map(events)
    canonical = _canonical_totals(db, user, marketplace, date_from, date_to)
    event_types = {event.event_type for event in events}
    using_canonical_orders = "sale" not in event_types
    sales = totals["sale"] if "sale" in event_types else canonical["sales"]
    discounts = totals["discount"] if "discount" in event_types else canonical["discounts"]
    refunds = totals["refund"] if "refund" in event_types else canonical["refund_total"]
    deduction_types = ("fee", "shipping", "fulfilment", "tax", "adjustment")
    deduction_values: dict[str, Decimal] = {}
    for event_type in deduction_types:
        if event_type in event_types:
            deduction_values[event_type] = totals[event_type]
        else:
            deduction_values[event_type] = canonical["fee_totals"].get(event_type, Decimal("0"))
    fees = sum(deduction_values.values(), Decimal("0"))
    cost_rows = _cost_evidence_rows(db, user, marketplace, date_to)
    costs, has_known_cost, unknown_cost = _cost_state(cost_rows)
    source_rows: list[Any] = [*events, *cost_rows]
    if using_canonical_orders or "discount" not in event_types:
        source_rows.extend(canonical["orders"])
    if "refund" not in event_types:
        source_rows.extend(canonical["refunds"])
    source_rows.extend(
        row
        for row in canonical["fees"]
        if (row.fee_type if row.fee_type in {"shipping", "fulfilment", "tax"} else "fee")
        not in event_types
    )
    missing: list[str] = []
    recognized_sales = bool(sales) and ("sale" in event_types or bool(canonical["orders"]))
    if not recognized_sales:
        missing.append("sales_evidence")
    has_fee_evidence = any(
        event_type in event_types for event_type in ("fee", "shipping", "fulfilment", "tax")
    ) or bool(canonical["fees"])
    if (
        not any(
            event_type in event_types for event_type in ("fee", "shipping", "fulfilment", "tax")
        )
        and not canonical["fees"]
    ):
        missing.append("marketplace_fee_evidence")
    if recognized_sales and (not has_known_cost or unknown_cost):
        missing.append("product_cost_evidence")
    if canonical["currency_mismatches"]:
        missing.append("currency_conversion_evidence")
    sales = sales or Decimal("0")
    discounts = discounts or Decimal("0")
    refunds = refunds or Decimal("0")
    net_sales = sales - discounts - refunds
    contribution = net_sales - fees - costs
    complete = not missing
    if complete:
        status = "observed" if canonical["orders"] or canonical["fees"] else "reported"
    elif events or canonical["orders"] or canonical["fees"]:
        status = "partial"
    else:
        status = "unknown"
    return {
        "currency": "INR",
        "evidence_status": status,
        "calculation_version": "pr-sos-05-v1",
        "basis": (
            "financial event effective_at"
            if not using_canonical_orders
            else "canonical marketplace order ordered_at; event effective_at when present"
        ),
        "gross_merchandise_value": str(sales),
        "gross_sales": str(sales),
        "discounts": str(discounts),
        "refunds": str(refunds),
        "net_sales": str(net_sales),
        "fees": str(fees) if has_fee_evidence else "UNKNOWN",
        "known_direct_costs": str(costs) if has_known_cost else "UNKNOWN",
        "cost_evidence_ids": [str(row.id) for row in cost_rows],
        "unknown_cost_evidence_ids": [
            str(row.id)
            for row in cost_rows
            if row.evidence_status == "unknown" or row.amount is None
        ],
        "contribution": str(contribution) if complete else "UNKNOWN",
        "estimated_profit": str(contribution) if complete else None,
        "margin_percent": (
            str(
                (contribution / net_sales * 100).quantize(Decimal("0.01"))
                if complete and net_sales
                else Decimal("0")
            )
            if complete
            else None
        ),
        "order_count": (
            len({event.order_id for event in events if event.order_id})
            if not using_canonical_orders
            else len(canonical["orders"])
        ),
        "event_count": len(events),
        "missing_inputs": missing,
        **_provenance(db, user, source_rows),
        "canonical_order_fallback": using_canonical_orders and bool(canonical["orders"]),
        "external_writes": False,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "currency_mismatches": canonical["currency_mismatches"],
    }


@router.post("/events", status_code=201)
@router.post("/fixtures/events", status_code=201, include_in_schema=False)
def ingest_event(data: FinancialEventInput, db: DatabaseSession, user: Owner) -> dict[str, Any]:
    account = _account(db, user, data.account_id)
    allowed_types = {
        "sale",
        "discount",
        "fee",
        "shipping",
        "fulfilment",
        "refund",
        "tax",
        "settlement",
        "adjustment",
    }
    if data.event_type not in allowed_types:
        raise HTTPException(422, "Unsupported financial event type.")
    _validate_currency(data.currency, account)
    _validate_source(data.source_type)
    _validate_references(db, user, account, data.order_id, data.product_id, data.settlement_id)
    existing = db.scalar(
        select(FinancialEvent).where(
            FinancialEvent.owner_id == user.id,
            FinancialEvent.account_id == account.id,
            FinancialEvent.source_event_id == data.source_event_id,
        )
    )
    if existing is not None:
        return _event_replay(existing, data)
    stamp = now()
    event = FinancialEvent(
        owner_id=user.id,
        account_id=account.id,
        order_id=data.order_id,
        product_id=data.product_id,
        settlement_id=data.settlement_id,
        marketplace=data.marketplace.lower(),
        source_event_id=data.source_event_id,
        event_type=data.event_type,
        amount=_money(data.amount),
        currency=data.currency,
        evidence_status=data.evidence_status,
        source_type=data.source_type,
        source_reference=data.source_reference,
        effective_at=data.effective_at or stamp,
        observed_at=stamp,
        calculation_version="pr-sos-05-v1",
        provenance_json={
            "source_type": data.source_type,
            "source_event_id": data.source_event_id,
            "account_environment": account.environment,
            "fake_provider": data.source_type == "synthetic_fixture"
            or account.environment == "sandbox"
            or account.capabilities_json.get("fake_provider") is True,
        },
        payload_json=data.payload,
        created_at=stamp,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        existing = db.scalar(
            select(FinancialEvent).where(
                FinancialEvent.owner_id == user.id,
                FinancialEvent.account_id == account.id,
                FinancialEvent.source_event_id == data.source_event_id,
            )
        )
        if existing is None:
            raise HTTPException(409, "Financial event could not be recorded safely.") from error
        return _event_replay(existing, data)
    return {"idempotent": False, "event": _event_response(event)}


def _event_replay(row: FinancialEvent, data: FinancialEventInput) -> dict[str, Any]:
    # Omitted effective_at means the server's original timestamp, not "now" on retry.
    if (
        row.account_id != data.account_id
        or row.source_event_id != data.source_event_id
        or row.marketplace != data.marketplace.lower()
        or row.event_type != data.event_type
        or row.amount != _money(data.amount)
        or row.currency != data.currency
        or row.product_id != data.product_id
        or row.order_id != data.order_id
        or row.settlement_id != data.settlement_id
        or row.evidence_status != data.evidence_status
        or row.source_type != data.source_type
        or row.source_reference != data.source_reference
        or row.payload_json != data.payload
        or (data.effective_at is not None and row.effective_at != data.effective_at)
    ):
        raise HTTPException(
            409, "Source event identity conflicts with persisted financial evidence."
        )
    return {"idempotent": True, "event": _event_response(row)}


@router.get("/events")
def list_events(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return [
        _event_response(row)
        for row in _event_query(db, user, marketplace, date_from, date_to)[:limit]
    ]


@router.post("/costs", status_code=201)
def add_cost(data: CostInput, db: DatabaseSession, user: Owner) -> dict[str, Any]:
    _validate_source(data.source_type)
    if data.currency.upper() != "INR":
        raise HTTPException(
            422, "Cost evidence must include verified currency conversion before use."
        )
    if data.amount is None and data.evidence_status != "unknown":
        raise HTTPException(422, "A non-unknown cost evidence record requires an amount.")
    if data.product_id is not None:
        product = db.scalar(
            select(Product).where(Product.id == data.product_id, Product.owner_id == user.id)
        )
        if product is None:
            raise HTTPException(404, "Product reference was not found in this seller account.")
    stamp = data.effective_from or now()
    row = FinancialCostEvidence(
        owner_id=user.id,
        product_id=data.product_id,
        marketplace=data.marketplace,
        sku=data.sku,
        cost_key=data.cost_key,
        cost_type=data.cost_type,
        amount=_money(data.amount) if data.amount is not None else None,
        currency=data.currency.upper(),
        evidence_status=data.evidence_status,
        source_type=data.source_type,
        source_reference=data.source_reference,
        effective_from=stamp,
        provenance_json=data.provenance,
        created_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        existing = db.scalar(
            select(FinancialCostEvidence).where(
                FinancialCostEvidence.owner_id == user.id,
                FinancialCostEvidence.cost_key == data.cost_key,
                FinancialCostEvidence.effective_from == stamp,
            )
        )
        if existing is not None:
            return {
                "idempotent": True,
                "id": str(existing.id),
                "amount": str(existing.amount) if existing.amount is not None else None,
            }
        raise HTTPException(409, "Cost evidence version already exists.") from error
    return {
        "idempotent": False,
        "id": str(row.id),
        "amount": str(row.amount) if row.amount is not None else None,
        "evidence_status": row.evidence_status,
    }


@router.post("/fee-rules", status_code=201)
def add_fee_rule(data: FeeRuleInput, db: DatabaseSession, user: Owner) -> dict[str, Any]:
    row = FinancialFeeRule(
        owner_id=user.id,
        marketplace=data.marketplace.lower(),
        category=data.category,
        rule_key=data.rule_key,
        fee_type=data.fee_type,
        rate_percent=data.rate_percent,
        fixed_amount=_money(data.fixed_amount),
        currency=data.currency.upper(),
        source_type=data.source_type,
        effective_from=data.effective_from or now(),
        version="pr-sos-05-v1",
        assumptions_json=data.assumptions,
        created_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Fee rule version already exists.") from error
    return {
        "id": str(row.id),
        "marketplace": row.marketplace,
        "fee_type": row.fee_type,
        "source_type": row.source_type,
        "version": row.version,
    }


@router.get("/fee-rules")
def fee_rules(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    category: str | None = None,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return the seller's immutable fee-rule versions for audit and review.

    Rule storage is deliberately separate from observed marketplace fees: this
    read-only projection never applies a modelled rule to reported financial
    facts and makes the effective-date boundary explicit to the UI and tests.
    """
    query = select(FinancialFeeRule).where(FinancialFeeRule.owner_id == user.id)
    if marketplace:
        query = query.where(FinancialFeeRule.marketplace == marketplace.lower())
    if category:
        query = query.where(
            (FinancialFeeRule.category == category) | (FinancialFeeRule.category.is_(None))
        )
    if as_of:
        query = query.where(FinancialFeeRule.effective_from <= as_of)
    rows = list(
        db.scalars(
            query.order_by(
                FinancialFeeRule.marketplace,
                FinancialFeeRule.category,
                FinancialFeeRule.rule_key,
                FinancialFeeRule.effective_from.desc(),
            )
        )
    )
    return [
        {
            "id": str(row.id),
            "marketplace": row.marketplace,
            "category": row.category,
            "rule_key": row.rule_key,
            "fee_type": row.fee_type,
            "rate_percent": str(row.rate_percent),
            "fixed_amount": str(row.fixed_amount),
            "currency": row.currency,
            "effective_from": row.effective_from.isoformat(),
            "source_type": row.source_type,
            "version": row.version,
            "assumptions": row.assumptions_json,
        }
        for row in rows
    ]


@router.get("/summary")
def summary(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    return _summary(db, user, marketplace, date_from, date_to)


def _snapshot_scope(
    marketplace: str | None, date_from: datetime | None, date_to: datetime | None
) -> str:
    return "|".join(
        (
            marketplace.lower() if marketplace else "all",
            date_from.isoformat() if date_from else "open",
            date_to.isoformat() if date_to else "open",
        )
    )


@router.post("/calculations/recalculate", status_code=201)
def recalculate(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    value = _summary(db, user, marketplace, date_from, date_to)
    scope_key = _snapshot_scope(marketplace, date_from, date_to)
    lineage = {
        "event_ids": [
            str(row.id) for row in _event_query(db, user, marketplace, date_from, date_to)
        ],
        "canonical_order_fallback": value["canonical_order_fallback"],
        "basis": value["basis"],
        "cost_evidence_ids": value["cost_evidence_ids"],
        "unknown_cost_evidence_ids": value["unknown_cost_evidence_ids"],
        "provenance_status": value["provenance_status"],
        "provenance_sources": value["provenance_sources"],
    }
    row = db.scalar(
        select(FinancialCalculationSnapshot).where(
            FinancialCalculationSnapshot.owner_id == user.id,
            FinancialCalculationSnapshot.scope_key == scope_key,
            FinancialCalculationSnapshot.calculation_version == "pr-sos-05-v1",
        )
    )
    stamp = now()
    if row is None:
        row = FinancialCalculationSnapshot(
            owner_id=user.id,
            scope_key=scope_key,
            scope_type="financial_summary",
            marketplace=marketplace.lower() if marketplace else None,
            calculation_version="pr-sos-05-v1",
            evidence_status=value["evidence_status"],
            metrics_json=value,
            missing_inputs_json=value["missing_inputs"],
            lineage_json=lineage,
            created_at=stamp,
        )
        db.add(row)
    else:
        row.evidence_status = value["evidence_status"]
        row.metrics_json = value
        row.missing_inputs_json = value["missing_inputs"]
        row.lineage_json = lineage
    db.commit()
    return {
        "id": str(row.id),
        "scope_key": row.scope_key,
        "calculation_version": row.calculation_version,
        "evidence_status": row.evidence_status,
        "metrics": row.metrics_json,
        "missing_inputs": row.missing_inputs_json,
        "lineage": row.lineage_json,
    }


@router.get("/calculations")
def calculations(
    db: DatabaseSession, user: Owner, limit: int = Query(100, ge=1, le=500)
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(FinancialCalculationSnapshot)
        .where(FinancialCalculationSnapshot.owner_id == user.id)
        .order_by(FinancialCalculationSnapshot.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(row.id),
            "scope_key": row.scope_key,
            "scope_type": row.scope_type,
            "marketplace": row.marketplace,
            "calculation_version": row.calculation_version,
            "evidence_status": row.evidence_status,
            "metrics": row.metrics_json,
            "missing_inputs": row.missing_inputs_json,
            "lineage": row.lineage_json,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/sales")
def sales(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    events = _event_query(db, user, marketplace, date_from, date_to)
    canonical = _canonical_totals(db, user, marketplace, date_from, date_to)
    provenance_by_id = {
        row["id"]: row["classification"]
        for row in _provenance(db, user, canonical["orders"])["provenance_sources"]
    }
    return {
        "basis": "event effective_at; canonical order ordered_at fallback",
        "currency": "INR",
        "evidence_status": "observed" if events or canonical["orders"] else "unknown",
        "events": [
            _event_response(row)
            for row in events
            if row.event_type in {"sale", "discount", "refund"}
        ],
        "canonical_orders": [
            {
                "id": str(order.id),
                "remote_order_id": order.remote_order_id,
                "marketplace": order.marketplace,
                "status": order.status,
                "ordered_at": order.ordered_at.isoformat(),
                "totals": order.totals_json,
                "source_type": "canonical_order",
                "provenance_status": provenance_by_id[str(order.id)],
                "evidence_status": (
                    "modeled" if provenance_by_id[str(order.id)] == "SYNTHETIC" else "unknown"
                ),
            }
            for order in canonical["orders"]
        ],
        "summary": _summary(db, user, marketplace, date_from, date_to),
    }


def _canonical_profitability_rows(
    db: Session,
    user: User,
    marketplace: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    group_mode: str = "product",
) -> list[dict[str, Any]]:
    canonical = _canonical_totals(db, user, marketplace, date_from, date_to)
    products: dict[str, dict[str, Any]] = {}
    for order in canonical["orders"]:
        items = list(
            db.scalars(
                select(MarketplaceOrderItem)
                .where(MarketplaceOrderItem.order_id == order.id)
                .order_by(MarketplaceOrderItem.id)
            )
        )
        order_total = _json_amount(order.totals_json or {}, "item_subtotal", "total")
        order_fees = sum(
            (fee.amount for fee in canonical["fees"] if fee.order_id == order.id),
            Decimal("0"),
        )
        order_refunds = sum(
            (refund.amount for refund in canonical["refunds"] if refund.order_id == order.id),
            Decimal("0"),
        )
        order_deductions = order_fees + order_refunds + (order.discount_amount or Decimal("0"))
        item_total = sum((item.total_price for item in items), Decimal("0")) if items else None
        if not items:
            key = order.remote_order_id if group_mode == "order" else "unknown"
            is_new = key not in products
            entry = products.setdefault(
                key,
                {
                    "product_id": None,
                    "sales": None,
                    "deductions": Decimal("0"),
                    "group_key": key,
                },
            )
            if order_total is None:
                entry["sales"] = None
            elif is_new:
                entry["sales"] = order_total
            elif entry["sales"] is not None:
                entry["sales"] += order_total
            entry["deductions"] += order_deductions
            continue
        if group_mode == "order":
            key = order.remote_order_id
            entry = products.setdefault(
                key,
                {
                    "product_id": None,
                    "sales": None,
                    "deductions": Decimal("0"),
                    "group_key": key,
                },
            )
            if order_total is None:
                entry["sales"] = None
            elif entry["sales"] is None:
                entry["sales"] = order_total
            entry["deductions"] += order_deductions
            continue
        for item in items:
            key = (
                str(item.marketplace_sku or item.product_id or "unknown")
                if group_mode == "sku"
                else str(item.product_id or "unknown")
            )
            entry = products.setdefault(
                key,
                {
                    "product_id": item.product_id,
                    "sales": Decimal("0"),
                    "deductions": Decimal("0"),
                    "group_key": key,
                },
            )
            if item_total:
                entry["deductions"] += (order_deductions * item.total_price / item_total).quantize(
                    MONEY
                )
            else:
                entry["deductions"] += order_deductions
            entry["sales"] += item.total_price

    rows: list[dict[str, Any]] = []
    for _key, entry in sorted(products.items()):
        product_id = entry["product_id"]
        costs = Decimal("0")
        has_known_cost = False
        unknown_cost = False
        if product_id:
            evidence = [
                cost
                for cost in _cost_evidence_rows(db, user, marketplace, date_to)
                if cost.product_id == product_id
            ]
            costs, has_known_cost, unknown_cost = _cost_state(evidence)
            # A legacy product value cannot override explicit UNKNOWN cost evidence.
            if not evidence:
                product = db.scalar(
                    select(Product).where(Product.id == product_id, Product.owner_id == user.id)
                )
                if product is not None and product.cost_amount is not None:
                    costs = _money(product.cost_amount)
                    has_known_cost = True
        sales_value = entry["sales"]
        missing: list[str] = []
        if sales_value is None:
            missing.append("sales_evidence")
            contribution = None
            deductions = None
        else:
            deductions = entry["deductions"]
            contribution = sales_value - deductions - costs
        if not has_known_cost or unknown_cost:
            missing.append("product_cost_evidence")
        rows.append(
            {
                "product_id": str(product_id) if product_id else None,
                "group_key": entry["group_key"],
                "scope": group_mode,
                "gross_sales": str(sales_value) if sales_value is not None else "UNKNOWN",
                "deductions": str(deductions) if deductions is not None else "UNKNOWN",
                "known_direct_costs": str(costs) if has_known_cost else "UNKNOWN",
                "contribution": (
                    str(contribution) if contribution is not None and not missing else "UNKNOWN"
                ),
                "estimated_profit": (
                    str(contribution) if contribution is not None and not missing else None
                ),
                "evidence_status": "observed" if not missing else "partial",
                "missing_inputs": missing,
                "calculation_version": "pr-sos-05-v1",
                "cost_source": "canonical_product_cost" if has_known_cost else None,
                "basis": "canonical marketplace order ordered_at and order-line totals",
            }
        )
    return rows


@router.get("/profitability")
def profitability(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    events = _event_query(db, user, marketplace, date_from, date_to)
    by_product: dict[str, list[FinancialEvent]] = defaultdict(list)
    for event in events:
        by_product[str(event.product_id or "unknown")].append(event)
    rows: list[dict[str, Any]] = []
    for product_key, product_events in sorted(by_product.items()):
        totals = _decimal_map(product_events)
        product_id = product_events[0].product_id
        cost_rows = [
            cost
            for cost in _cost_evidence_rows(db, user, marketplace, date_to)
            if product_id and cost.product_id == product_id
        ]
        costs, has_known_cost, unknown_cost = _cost_state(cost_rows)
        sales_value = totals["sale"]
        deductions = (
            totals["discount"]
            + totals["refund"]
            + totals["fee"]
            + totals["shipping"]
            + totals["fulfilment"]
            + totals["tax"]
        )
        missing = [] if has_known_cost and not unknown_cost else ["product_cost_evidence"]
        contribution = sales_value - deductions - costs
        rows.append(
            {
                "product_id": None if product_key == "unknown" else product_key,
                "gross_sales": str(sales_value),
                "deductions": str(deductions),
                "known_direct_costs": str(costs) if has_known_cost else "UNKNOWN",
                "contribution": str(contribution) if not missing else "UNKNOWN",
                "estimated_profit": str(contribution) if not missing else None,
                "evidence_status": "observed" if not missing else "partial",
                "missing_inputs": missing,
                "calculation_version": "pr-sos-05-v1",
            }
        )
    if "sale" not in {event.event_type for event in events}:
        rows.extend(_canonical_profitability_rows(db, user, marketplace, date_from, date_to))
    return {
        "currency": "INR",
        "rows": rows,
        "summary": _summary(db, user, marketplace, date_from, date_to),
    }


@router.get("/profitability/{scope}")
def scoped_profitability(
    scope: str,
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    if scope not in {"sku", "order"}:
        raise HTTPException(404, "Unsupported profitability scope.")
    events = _event_query(db, user, marketplace, date_from, date_to)
    if events and any(event.event_type == "sale" for event in events):
        rows = profitability(db, user, marketplace, date_from, date_to)["rows"]
    else:
        rows = _canonical_profitability_rows(
            db, user, marketplace, date_from, date_to, group_mode=scope
        )
    return {
        "scope": scope,
        "currency": "INR",
        "rows": rows,
        "summary": _summary(db, user, marketplace, date_from, date_to),
    }


@router.get("/missing-costs")
def missing_costs(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    value = profitability(db, user, marketplace, date_from, date_to)
    rows = [
        row for row in value["rows"] if "product_cost_evidence" in (row.get("missing_inputs") or [])
    ]
    return {
        "rows": rows,
        "count": len(rows),
        "evidence_status": "unknown" if rows else value["summary"]["evidence_status"],
        "next_action": "Record effective-dated product cost evidence before using profitability.",
    }


@router.get("/refund-impact")
def refund_impact(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    events = _event_query(db, user, marketplace, date_from, date_to)
    refund_events = [row for row in events if row.event_type == "refund"]
    canonical = _canonical_totals(db, user, marketplace, date_from, date_to)
    if refund_events:
        rows = [_event_response(row) for row in refund_events]
        total = sum((row.amount for row in refund_events), Decimal("0"))
        evidence_status = (
            "reported"
            if any(row.evidence_status == "reported" for row in refund_events)
            else "observed"
        )
    else:
        rows = [
            {
                "id": str(row.id),
                "order_id": str(row.order_id),
                "amount": str(row.amount),
                "currency": row.currency,
                "source_type": "canonical_refund",
                "evidence_status": "reported",
            }
            for row in canonical["refunds"]
        ]
        total = canonical["refund_total"]
        evidence_status = "reported" if rows else "unknown"
    return {
        "currency": "INR",
        "total_refunds": str(total) if rows else "UNKNOWN",
        "refunds": rows,
        "evidence_status": evidence_status,
        "basis": "explicit refund evidence; no return or cancellation inference",
        **_provenance(db, user, refund_events or canonical["refunds"]),
    }


@router.get("/revenue-trends")
def revenue_trends(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    events = _event_query(db, user, marketplace, date_from, date_to)
    points: dict[str, dict[str, Decimal]] = {}
    for event in events:
        key = event.effective_at.date().isoformat()
        point = points.setdefault(
            key,
            {
                "gross_sales": Decimal("0"),
                "discounts": Decimal("0"),
                "refunds": Decimal("0"),
                "fees": Decimal("0"),
            },
        )
        if event.event_type == "sale":
            point["gross_sales"] += event.amount
        elif event.event_type == "discount":
            point["discounts"] += event.amount
        elif event.event_type == "refund":
            point["refunds"] += event.amount
        elif event.event_type in {"fee", "shipping", "fulfilment", "tax", "adjustment"}:
            point["fees"] += event.amount
    if not events:
        for order in _canonical_orders(db, user, marketplace, date_from, date_to):
            amount = _json_amount(order.totals_json or {}, "item_subtotal", "total")
            key = order.ordered_at.date().isoformat()
            point = points.setdefault(
                key,
                {
                    "gross_sales": Decimal("0"),
                    "discounts": Decimal("0"),
                    "refunds": Decimal("0"),
                    "fees": Decimal("0"),
                },
            )
            if amount is not None:
                point["gross_sales"] += amount
    rows = []
    for key in sorted(points):
        point = points[key]
        rows.append(
            {
                "date": key,
                "gross_sales": str(point["gross_sales"]),
                "discounts": str(point["discounts"]),
                "refunds": str(point["refunds"]),
                "fees": str(point["fees"]),
                "net_sales": str(point["gross_sales"] - point["discounts"] - point["refunds"]),
                "evidence_status": "observed" if events else "reported",
            }
        )
    return {
        "currency": "INR",
        "basis": "event effective_at; canonical order ordered_at fallback",
        "rows": rows,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
    }


@router.get("/marketplace-comparison")
def marketplace_comparison(
    db: DatabaseSession,
    user: Owner,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    names: set[str] = set()
    names.update(
        row
        for row in db.scalars(
            select(FinancialEvent.marketplace).where(FinancialEvent.owner_id == user.id)
        )
        if row
    )
    names.update(
        row
        for row in db.scalars(
            select(MarketplaceOrder.marketplace).where(MarketplaceOrder.owner_id == user.id)
        )
        if row
    )
    rows = [
        {"marketplace": name, **_summary(db, user, name, date_from, date_to)}
        for name in sorted(names)
    ]
    return {"currency": "INR", "rows": rows, "count": len(rows)}


@router.get("/fees")
def fees(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    events = _event_query(db, user, marketplace, date_from, date_to)
    canonical = _canonical_totals(db, user, marketplace, date_from, date_to)
    by_type: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for event in events:
        if event.event_type in {"fee", "shipping", "fulfilment", "tax", "adjustment"}:
            by_type[event.event_type] += event.amount
    if not by_type:
        by_type.update(canonical["fee_totals"])
    return {
        "currency": "INR",
        "evidence_status": "reported" if events else ("observed" if by_type else "unknown"),
        "fees": {key: str(value) for key, value in sorted(by_type.items())},
        "missing_inputs": ["marketplace_fee_evidence"] if not by_type else [],
        "calculation_version": "pr-sos-05-v1",
    }


def _reconciliation(row: FinancialSettlementReconciliation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "settlement_key": row.settlement_key,
        "marketplace": row.marketplace,
        "expected_amount": str(row.expected_amount) if row.expected_amount is not None else None,
        "reported_amount": str(row.reported_amount) if row.reported_amount is not None else None,
        "verified_amount": str(row.verified_amount) if row.verified_amount is not None else None,
        "difference_amount": (
            str(row.difference_amount) if row.difference_amount is not None else None
        ),
        "currency": row.currency,
        "status": row.status,
        "evidence_status": row.evidence_status,
        "provenance": row.provenance_json,
        "calculation_version": row.calculation_version,
    }


@router.post("/settlements/reconcile", status_code=201)
def reconcile(data: ReconciliationInput, db: DatabaseSession, user: Owner) -> dict[str, Any]:
    account = _account(db, user, data.account_id)
    _validate_currency(data.currency.upper(), account)
    if data.settlement_id is not None:
        _validate_references(db, user, account, None, None, data.settlement_id)
    expected = _money(data.expected_amount) if data.expected_amount is not None else None
    reported = _money(data.reported_amount) if data.reported_amount is not None else None
    verified = _money(data.verified_amount) if data.verified_amount is not None else None
    difference = (reported - expected) if expected is not None and reported is not None else None
    status = (
        "unknown"
        if expected is None or reported is None
        else ("matched" if difference == 0 else "mismatch")
    )
    evidence = (
        "verified" if verified is not None else ("reported" if reported is not None else "unknown")
    )
    existing = db.scalar(
        select(FinancialSettlementReconciliation).where(
            FinancialSettlementReconciliation.owner_id == user.id,
            FinancialSettlementReconciliation.settlement_key == data.settlement_key,
        )
    )
    stamp = now()
    if existing is None:
        existing = FinancialSettlementReconciliation(
            owner_id=user.id,
            account_id=data.account_id,
            settlement_id=data.settlement_id,
            marketplace=data.marketplace.lower(),
            settlement_key=data.settlement_key,
            expected_amount=expected,
            reported_amount=reported,
            verified_amount=verified,
            difference_amount=difference,
            currency=data.currency.upper(),
            status=status,
            evidence_status=evidence,
            provenance_json=data.provenance,
            calculation_version="pr-sos-05-v1",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(existing)
    else:
        if existing.account_id != data.account_id:
            raise HTTPException(409, "Settlement reconciliation belongs to another account.")
        history = existing.provenance_json.get("revision_history", [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "updated_at": existing.updated_at.isoformat(),
                "expected_amount": (
                    str(existing.expected_amount) if existing.expected_amount is not None else None
                ),
                "reported_amount": (
                    str(existing.reported_amount) if existing.reported_amount is not None else None
                ),
                "verified_amount": (
                    str(existing.verified_amount) if existing.verified_amount is not None else None
                ),
                "status": existing.status,
            }
        )
        existing.provenance_json = {
            **existing.provenance_json,
            "revision_history": history,
            "last_revision_source": data.provenance,
        }
        (
            existing.expected_amount,
            existing.reported_amount,
            existing.verified_amount,
            existing.difference_amount,
        ) = (expected, reported, verified, difference)
        existing.status, existing.evidence_status, existing.updated_at = status, evidence, stamp
    db.commit()
    return _reconciliation(existing)


@router.get("/settlements")
def settlements(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    query = select(FinancialSettlementReconciliation).where(
        FinancialSettlementReconciliation.owner_id == user.id
    )
    if marketplace:
        query = query.where(FinancialSettlementReconciliation.marketplace == marketplace.lower())
    if date_from:
        query = query.where(FinancialSettlementReconciliation.created_at >= date_from)
    if date_to:
        query = query.where(FinancialSettlementReconciliation.created_at <= date_to)
    rows = list(db.scalars(query.order_by(FinancialSettlementReconciliation.created_at.desc())))
    canonical = _canonical_settlements(db, user, marketplace, date_from, date_to)
    known_keys = {row.settlement_key for row in rows}
    canonical_rows = [
        {
            "id": str(row.id),
            "settlement_key": row.remote_settlement_id,
            "marketplace": row.marketplace,
            "expected_amount": None,
            "reported_amount": str(row.net_amount),
            "verified_amount": None,
            "difference_amount": None,
            "currency": row.currency,
            "status": "unknown",
            "evidence_status": "reported",
            "provenance": {"source_type": "canonical_settlement"},
            "calculation_version": "pr-sos-05-v1",
        }
        for row in canonical
        if row.remote_settlement_id not in known_keys
    ]
    return {
        "rows": [_reconciliation(row) for row in rows] + canonical_rows,
        "count": len(rows) + len(canonical_rows),
        **_provenance(
            db,
            user,
            [*rows, *[row for row in canonical if row.remote_settlement_id not in known_keys]],
        ),
    }


@router.get("/reconciliation")
def reconciliation(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    return settlements(db, user, marketplace, date_from, date_to)


@router.get("/alerts")
def alerts(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    value = _summary(db, user, marketplace, date_from, date_to)
    alerts: list[dict[str, str]] = []
    for item in value["missing_inputs"]:
        alerts.append(
            {
                "severity": "warning",
                "code": item,
                "message": f"{item.replace('_', ' ').capitalize()} is not available.",
            }
        )
    contribution_value = value["contribution"]
    if contribution_value != "UNKNOWN" and Decimal(contribution_value) < 0:
        alerts.append(
            {
                "severity": "high",
                "code": "negative_contribution",
                "message": "Known direct costs and deductions exceed net sales.",
            }
        )
    return {"alerts": alerts, "evidence_status": value["evidence_status"]}


@router.get("/business-agent")
def business_agent_guidance(db: DatabaseSession, user: Owner) -> dict[str, Any]:
    value = _summary(db, user)
    actions = [
        {
            "type": "review_financial_evidence",
            "label": "Review financial evidence",
            "reason": "The financial workspace is read-only and retains source lineage.",
        }
    ]
    if "product_cost_evidence" in value["missing_inputs"]:
        actions.insert(
            0,
            {
                "type": "add_cost_evidence",
                "label": "Add product cost evidence",
                "reason": "Profitability is partial until direct product costs are known.",
            },
        )
    if "marketplace_fee_evidence" in value["missing_inputs"]:
        actions.insert(
            0,
            {
                "type": "review_fee_evidence",
                "label": "Review marketplace fee evidence",
                "reason": "Marketplace deductions are not fully evidenced.",
            },
        )
    return {
        "summary": value,
        "actions": actions,
        "authority": "read_only",
        "external_writes": False,
        "human_approval_required_for": ["cost_correction", "marketplace_change", "payout_action"],
    }
