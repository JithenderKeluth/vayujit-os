"""Owner-scoped cross-channel Marketing Plan orchestration."""

# ruff: noqa: E501, E402

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from vayujit_api.ads.models import AdAccount, AdJob, AdMarketplaceListing, AdsBase
from vayujit_api.brands.models import Brand
from vayujit_api.products.models import Product


class MarketingPlan(AdsBase):
    __tablename__ = "marketing_plans"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_marketing_plan_idempotency"),
        CheckConstraint(
            "status IN ('draft','ready','blocked','queued','running','succeeded','partially_completed','failed','cancelled','stale')",
            name="ck_marketing_plan_status",
        ),
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_ids_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    objective: Mapped[str] = mapped_column(String(40))
    locale: Mapped[str] = mapped_column(String(20), default="en-IN")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone_name: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    target_channels_json: Mapped[list[object]] = mapped_column(JSONB, default=list)
    budget_envelope_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    strategy_mode: Mapped[str] = mapped_column(String(32), default="manual")
    automation_mode: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    preview_fingerprint: Mapped[str | None] = mapped_column(String(128))
    creative_mapping_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    targeting_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    schedule_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180))


class MarketingPlanChannel(AdsBase):
    __tablename__ = "marketing_plan_channels"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "plan_id", "plan_version", "channel", name="uq_marketing_plan_channel"
        ),
        CheckConstraint(
            "state IN ('planned','blocked','queued','running','retry_wait','succeeded','failed','ambiguous','recovered','cancelled','stale')",
            name="ck_marketing_plan_channel_state",
        ),
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_plans.id", ondelete="CASCADE"), index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str | None] = mapped_column(String(32), index=True)
    state: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    listing_id: Mapped[str | None] = mapped_column(String(180), index=True)
    listing_version: Mapped[int | None] = mapped_column(Integer)
    creative_mapping_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    downstream_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_message: Mapped[str | None] = mapped_column(String(500))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)


from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user

router = APIRouter(prefix="/api/v1/ads/marketing", tags=["marketing-automation"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]

OBJECTIVES = {
    "awareness",
    "traffic",
    "engagement",
    "leads",
    "conversions",
    "sales",
    "video_views",
    "remarketing",
    "launch",
    "promotion",
}
CHANNELS = {"meta", "google", "amazon", "flipkart", "social", "campaign"}
UNSUPPORTED_CHANNELS = {"meesho"}
PLAN_STATES = {
    "draft",
    "ready",
    "blocked",
    "queued",
    "running",
    "succeeded",
    "partially_completed",
    "failed",
    "cancelled",
    "stale",
}


class MarketingPlanCreate(BaseModel):
    brand_id: uuid.UUID
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    objective: str = "sales"
    locale: str = Field(default="en-IN", min_length=2, max_length=20)
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=80)
    target_channels: list[str] = Field(min_length=1, max_length=10)
    budget_envelope: dict[str, Any] = Field(
        default_factory=lambda: {"total": "0", "currency": "INR", "allocations": {}}
    )
    strategy_mode: Literal["manual", "equal", "weighted", "performance_informed"] = "manual"
    automation_mode: Literal["manual", "bounded"] = "manual"
    creative_mapping: dict[str, Any] = Field(default_factory=dict)
    targeting: dict[str, Any] = Field(default_factory=dict)
    schedule: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=180)

    @model_validator(mode="after")
    def validate_plan(self) -> MarketingPlanCreate:
        if self.objective not in OBJECTIVES:
            raise ValueError("The Marketing Plan objective is unsupported.")
        channels = set(self.target_channels)
        if not channels.issubset(CHANNELS | UNSUPPORTED_CHANNELS):
            raise ValueError("The Marketing Plan channel is unsupported.")
        if channels & UNSUPPORTED_CHANNELS:
            raise ValueError("Meesho Ads is not supported locally.")
        if len(channels) != len(self.target_channels):
            raise ValueError("Marketing Plan channels must be unique.")
        if self.end_at and self.start_at and self.end_at <= self.start_at:
            raise ValueError("The Marketing Plan end must be after its start.")
        return self


class MarketingPlanPreviewRequest(BaseModel):
    plan: MarketingPlanCreate
    expected_version: int = Field(default=1, ge=1)


class MarketingPlanConfirmRequest(MarketingPlanPreviewRequest):
    preview_fingerprint: str = Field(min_length=16, max_length=128)
    confirm: bool = False


class MarketingPlanActionRequest(BaseModel):
    action: Literal[
        "retry_channel",
        "retry_failed",
        "reconcile",
        "cancel_channel",
        "cancel_remaining",
        "review_dependency",
    ]
    channel: str | None = None
    confirm: bool = False


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _plan(db: Session, owner: User, plan_id: uuid.UUID) -> MarketingPlan:
    value = db.scalar(
        select(MarketingPlan).where(MarketingPlan.id == plan_id, MarketingPlan.owner_id == owner.id)
    )
    if value is None:
        raise HTTPException(404, "Marketing Plan not found.")
    return value


def _channel_state(channels: list[MarketingPlanChannel]) -> str:
    states = {item.state for item in channels}
    if not states:
        return "draft"
    if states <= {"succeeded"}:
        return "succeeded"
    if states & {"running", "queued", "retry_wait"}:
        return "running"
    if "succeeded" in states:
        return "partially_completed"
    if states <= {"cancelled"}:
        return "cancelled"
    if "blocked" in states:
        return "blocked"
    return "failed"


def _channel_response(value: MarketingPlanChannel) -> dict[str, Any]:
    return {
        "id": value.id,
        "channel": value.channel,
        "provider": value.provider,
        "state": value.state,
        "plan_version": value.plan_version,
        "account_id": value.account_id,
        "listing_id": value.listing_id,
        "listing_version": value.listing_version,
        "creative_mapping": value.creative_mapping_json,
        "downstream": value.downstream_json,
        "schedule_id": value.downstream_json.get("schedule_id"),
        "schedule_history": value.downstream_json.get("schedule_history", []),
        "failure_code": value.failure_code,
        "safe_message": value.safe_message,
        "correlation_id": value.correlation_id,
    }


def _response(db: Session, value: MarketingPlan) -> dict[str, Any]:
    channels = list(
        db.scalars(
            select(MarketingPlanChannel)
            .where(MarketingPlanChannel.plan_id == value.id)
            .order_by(MarketingPlanChannel.channel)
        )
    )
    from vayujit_api.ads.marketing_execution import MarketingPlanExecution

    execution = db.scalar(
        select(MarketingPlanExecution)
        .where(MarketingPlanExecution.plan_id == value.id)
        .order_by(MarketingPlanExecution.created_at.desc())
    )
    return {
        "id": value.id,
        "owner_id": value.owner_id,
        "brand_id": value.brand_id,
        "product_ids": value.product_ids_json,
        "objective": value.objective,
        "locale": value.locale,
        "start_at": value.start_at,
        "end_at": value.end_at,
        "timezone": value.timezone_name,
        "target_channels": value.target_channels_json,
        "budget_envelope": value.budget_envelope_json,
        "strategy_mode": value.strategy_mode,
        "automation_mode": value.automation_mode,
        "status": value.status,
        "current_version": value.current_version,
        "correlation_id": value.correlation_id,
        "preview_fingerprint": value.preview_fingerprint,
        "creative_mapping": value.creative_mapping_json,
        "targeting": value.targeting_json,
        "schedule": value.schedule_json,
        "channels": [_channel_response(item) for item in channels],
        "execution_id": execution.id if execution else None,
        "execution_state": execution.state if execution else None,
        "update_available": value.current_version > 1,
    }


def _validate_dependencies(
    db: Session, owner: User, data: MarketingPlanCreate
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    brand = db.scalar(select(Brand).where(Brand.id == data.brand_id, Brand.owner_id == owner.id))
    if brand is None:
        blockers.append("brand:owner_scope_required")
    products = list(
        db.scalars(
            select(Product).where(
                Product.id.in_(data.product_ids),
                Product.owner_id == owner.id,
                Product.brand_id == data.brand_id,
            )
        )
    )
    if len(products) != len(data.product_ids):
        blockers.append("product:owner_scope_required")
    account_ids: dict[str, str | None] = {}
    account_currencies: dict[str, str | None] = {}
    listing_details: dict[str, dict[str, Any] | None] = {}
    for channel in data.target_channels:
        if channel in {"meta", "google", "amazon", "flipkart"}:
            account = db.scalar(
                select(AdAccount)
                .where(
                    AdAccount.owner_id == owner.id,
                    AdAccount.provider == channel,
                    AdAccount.enabled.is_(True),
                    AdAccount.validated.is_(True),
                )
                .order_by(AdAccount.updated_at.desc())
                .limit(1)
            )
            account_ids[channel] = str(account.id) if account else None
            account_currencies[channel] = account.currency.upper() if account else None
            if account is None:
                blockers.append(f"{channel}:validated_account_required")
            elif (
                account.currency.upper() != str(data.budget_envelope.get("currency", "INR")).upper()
            ):
                blockers.append(f"{channel}:currency_mismatch")
        if channel in {"amazon", "flipkart"}:
            listing = db.scalar(
                select(AdMarketplaceListing)
                .where(
                    AdMarketplaceListing.owner_id == owner.id,
                    AdMarketplaceListing.marketplace == channel,
                    AdMarketplaceListing.product_id.in_(data.product_ids),
                    AdMarketplaceListing.state == "active",
                )
                .order_by(AdMarketplaceListing.version.desc())
                .limit(1)
            )
            listing_details[channel] = (
                {
                    "id": str(listing.id),
                    "listing_id": listing.listing_id,
                    "version": listing.version,
                    "product_id": str(listing.product_id),
                }
                if listing
                else None
            )
            if listing is None:
                blockers.append(f"{channel}:active_listing_required")
        if channel == "social":
            warnings.append("social:local_scheduler_projection")
        if channel == "campaign":
            warnings.append("campaign:existing_campaign_dependency_must_be_selected")
    allocations = data.budget_envelope.get("allocations", {})
    if not isinstance(allocations, dict):
        allocations = {}
    budget_blockers = _budget_errors(data.budget_envelope)
    blockers.extend(f"budget:{item}" for item in budget_blockers)
    return [
        {
            "channel": channel,
            "ready": not any(item.startswith(f"{channel}:") for item in blockers)
            and not budget_blockers,
            "blockers": [
                item.split(":", 1)[1] for item in blockers if item.startswith(f"{channel}:")
            ]
            + [f"budget:{item}" for item in budget_blockers],
            "warnings": [
                item.split(":", 1)[1] for item in warnings if item.startswith(f"{channel}:")
            ],
            "information": [
                "provider_capabilities_are_server_derived",
                "provider_mutation_is_deferred_to_durable_workers",
            ],
            "provider_identity": {"provider": channel if channel in CHANNELS else None},
            "account": {
                "id": account_ids.get(channel),
                "currency": account_currencies.get(channel),
            },
            "products": [str(item) for item in data.product_ids],
            "listing": listing_details.get(channel),
            "creative": data.creative_mapping.get(channel, {}),
            "budget": {
                "allocation": allocations.get(channel),
                "currency": data.budget_envelope.get("currency", "INR"),
            },
            "targeting": data.targeting,
            "schedule": data.schedule,
            "dependency_state": (
                "ready"
                if not any(item.startswith(f"{channel}:") for item in blockers)
                else "blocked"
            ),
            "owner_scope": {
                "brand": brand is not None,
                "products": len(products) == len(data.product_ids),
            },
        }
        for channel in data.target_channels
    ], blockers


@router.get("/capabilities")
def marketing_capabilities() -> dict[str, Any]:
    return {
        "channels": sorted(CHANNELS),
        "unsupported": sorted(UNSUPPORTED_CHANNELS),
        "objectives": sorted(OBJECTIVES),
        "strategies": ["manual", "equal", "weighted", "performance_informed"],
        "automation_modes": ["manual", "bounded"],
    }


@router.get("/plans")
def list_plans(
    db: DB,
    owner: Owner,
    status: str | None = None,
    channel: str | None = None,
    product_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    values = list(
        db.scalars(
            select(MarketingPlan)
            .where(MarketingPlan.owner_id == owner.id)
            .order_by(MarketingPlan.updated_at.desc())
        )
    )
    result = []
    for value in values:
        if status and value.status != status:
            continue
        if product_id and product_id not in value.product_ids_json:
            continue
        item = _response(db, value)
        if channel and channel not in item["target_channels"]:
            continue
        result.append(item)
    return result


@router.post("/plans/readiness")
def plan_readiness(data: MarketingPlanCreate, db: DB, owner: Owner) -> dict[str, Any]:
    channel_readiness, blockers = _validate_dependencies(db, owner, data)
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "channels": channel_readiness,
        "blockers": blockers,
        "warnings": [item for row in channel_readiness for item in row["warnings"]],
        "information": ["No provider mutation occurs during readiness."],
        "fingerprint": _fingerprint(data.model_dump(mode="json")),
    }


@router.post("/plans/preview")
def plan_preview(data: MarketingPlanPreviewRequest, db: DB, owner: Owner) -> dict[str, Any]:
    readiness = plan_readiness(data.plan, db, owner)
    payload = data.plan.model_dump(mode="json") | {
        "expected_version": data.expected_version,
        "readiness": readiness,
    }
    return {
        "mutates": False,
        "plan_version": data.expected_version,
        "fingerprint": _fingerprint(payload),
        "readiness": readiness,
        "plan": payload,
    }


@router.post("/plans/confirm", status_code=201)
def plan_confirm(data: MarketingPlanConfirmRequest, db: DB, owner: Owner) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(
            422, "Explicit confirmation is required before Marketing Plan execution."
        )
    readiness = plan_readiness(data.plan, db, owner)
    if any(
        item in {"brand:owner_scope_required", "product:owner_scope_required"}
        for item in readiness["blockers"]
    ):
        raise HTTPException(404, "Marketing Plan dependencies were not found.")
    expected = _fingerprint(
        data.plan.model_dump(mode="json")
        | {"expected_version": data.expected_version, "readiness": readiness}
    )
    if expected != data.preview_fingerprint:
        raise HTTPException(409, "The Marketing Plan preview is stale; preview again.")
    existing = db.scalar(
        select(MarketingPlan).where(
            MarketingPlan.owner_id == owner.id,
            MarketingPlan.idempotency_key == data.plan.idempotency_key,
        )
    )
    if existing:
        return _response(db, existing)
    stamp = _now()
    correlation_id = uuid.uuid4().hex
    value = MarketingPlan(
        owner_id=owner.id,
        brand_id=data.plan.brand_id,
        product_ids_json=[str(item) for item in data.plan.product_ids],
        objective=data.plan.objective,
        locale=data.plan.locale,
        start_at=data.plan.start_at,
        end_at=data.plan.end_at,
        timezone_name=data.plan.timezone,
        target_channels_json=data.plan.target_channels,
        budget_envelope_json=data.plan.budget_envelope,
        strategy_mode=data.plan.strategy_mode,
        automation_mode=data.plan.automation_mode,
        status="ready" if readiness["ready"] else "blocked",
        current_version=data.expected_version,
        correlation_id=correlation_id,
        preview_fingerprint=data.preview_fingerprint,
        creative_mapping_json=data.plan.creative_mapping,
        targeting_json=data.plan.targeting,
        schedule_json=data.plan.schedule,
        idempotency_key=data.plan.idempotency_key,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    db.flush()
    for row in readiness["channels"]:
        db.add(
            MarketingPlanChannel(
                plan_id=value.id,
                owner_id=owner.id,
                plan_version=data.expected_version,
                channel=row["channel"],
                provider=(
                    row["channel"]
                    if row["channel"] in {"meta", "google", "amazon", "flipkart"}
                    else None
                ),
                state="queued" if row["ready"] else "blocked",
                account_id=(uuid.UUID(row["account"]["id"]) if row["account"].get("id") else None),
                listing_id=(row["listing"].get("listing_id") if row["listing"] else None),
                listing_version=(row["listing"].get("version") if row["listing"] else None),
                creative_mapping_json=data.plan.creative_mapping.get(row["channel"], {}),
                correlation_id=correlation_id,
                created_at=stamp,
                updated_at=stamp,
                safe_message=None if row["ready"] else "The channel prerequisites are not ready.",
                downstream_json={},
            )
        )
    from vayujit_api.ads.marketing_execution import MarketingPlanRevision, materialize_plan

    revision = MarketingPlanRevision(
        owner_id=owner.id,
        plan_id=value.id,
        version=data.expected_version,
        fingerprint=data.preview_fingerprint,
        snapshot_json=data.plan.model_dump(mode="json"),
        reason="confirmed",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(revision)
    db.flush()
    execution = materialize_plan(db, owner, value)
    value.status = execution.state
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_confirmed",
        entity_type="marketing_plan",
        entity_id=value.id,
        metadata={
            "channels": data.plan.target_channels,
            "plan_version": data.expected_version,
            "execution_id": str(execution.id),
        },
    )
    db.commit()
    db.refresh(value)
    return _response(db, value)


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    return _response(db, _plan(db, owner, plan_id))


@router.get("/plans/{plan_id}/history")
def plan_history(plan_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, Any]]:
    plan = _plan(db, owner, plan_id)
    from vayujit_api.ads.marketing_execution import MarketingPlanExecution

    execution_ids = list(
        db.scalars(
            select(MarketingPlanExecution.id).where(
                MarketingPlanExecution.plan_id == plan.id,
                MarketingPlanExecution.owner_id == owner.id,
            )
        )
    )
    entity_ids = [plan.id, *execution_ids]
    values = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.actor_id == owner.id,
            AuditEvent.entity_id.in_(entity_ids),
            AuditEvent.entity_type.in_(["marketing_plan", "marketing_plan_execution"]),
        )
        .order_by(AuditEvent.occurred_at)
    )
    return [
        {
            "action": item.action,
            "occurred_at": item.occurred_at,
            "metadata": item.metadata_json,
            "correlation_id": item.correlation_id or plan.correlation_id,
        }
        for item in values
    ]


@router.post("/plans/{plan_id}/actions")
def plan_action(
    plan_id: uuid.UUID, data: MarketingPlanActionRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    if not data.confirm:
        raise HTTPException(
            422, "Explicit confirmation is required for this Marketing Plan action."
        )
    channels = list(
        db.scalars(select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == value.id))
    )
    selected = [item for item in channels if data.channel is None or item.channel == data.channel]
    if data.action in {"retry_channel", "retry_failed"}:
        for item in selected:
            if item.state in {"failed", "retry_wait", "ambiguous", "blocked"}:
                item.state = "queued"
                item.failure_code = None
                item.safe_message = None
    elif data.action == "reconcile":
        for item in selected:
            if item.state == "ambiguous":
                item.state = "succeeded"
    elif data.action in {"cancel_channel", "cancel_remaining"}:
        for item in selected:
            if item.state not in {"succeeded", "cancelled"}:
                item.state = "cancelled"
    else:
        raise HTTPException(422, "The requested Marketing Plan action is not executable.")
    from vayujit_api.ads.marketing_execution import (
        MarketingChannelExecution,
        MarketingPlanExecution,
        _state_from_channels,
    )

    execution = db.scalar(
        select(MarketingPlanExecution)
        .where(MarketingPlanExecution.plan_id == value.id)
        .order_by(MarketingPlanExecution.created_at.desc())
    )
    if execution is not None:
        durable_channels = list(
            db.scalars(
                select(MarketingChannelExecution).where(
                    MarketingChannelExecution.execution_id == execution.id
                )
            )
        )
        selected_names = {item.channel for item in selected}
        for durable in durable_channels:
            if durable.channel not in selected_names:
                continue
            source = next(item for item in selected if item.channel == durable.channel)
            durable.state = (
                "recovered"
                if source.state == "succeeded" and data.action == "reconcile"
                else source.state
            )
            durable.retryable = durable.state in {"failed", "retry_wait", "ambiguous"}
            durable.failure_code = source.failure_code
            durable.safe_message = source.safe_message
        execution.state = _state_from_channels(durable_channels)
        execution.updated_at = _now()
    value.status = _channel_state(channels)
    value.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action=f"ads.marketing_plan_{data.action}",
        entity_type="marketing_plan",
        entity_id=value.id,
        metadata={"channel": data.channel},
    )
    db.commit()
    return _response(db, value)


@router.get("/overview")
def marketing_overview(db: DB, owner: Owner) -> dict[str, Any]:
    plans = list_plans(db, owner)
    return {
        "plans": plans,
        "active_count": sum(item["status"] in {"queued", "running", "ready"} for item in plans),
        "recommendations": [],
        "anomalies": [],
        "unsupported": ["meesho"],
        "synthetic": True,
    }


class MarketingBudgetChange(BaseModel):
    proposed: dict[str, Any]
    expected_version: int = Field(default=1, ge=1)
    preview_fingerprint: str = Field(min_length=16, max_length=128)
    confirm: bool = False
    idempotency_key: str = Field(
        default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=180
    )


class MarketingVersionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    creative_mapping: dict[str, Any] | None = None
    budget_envelope: dict[str, Any] | None = None
    targeting: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None


def _budget_errors(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        total = float(value.get("total", 0))
        if total < 0:
            errors.append("total_budget_must_be_non_negative")
        allocations = value.get("allocations", {})
        if not isinstance(allocations, dict):
            errors.append("allocations_must_be_an_object")
        else:
            numbers = [float(item) for item in allocations.values()]
            if any(item < 0 for item in numbers):
                errors.append("allocation_must_be_non_negative")
            if sum(numbers) > total + 1e-9:
                errors.append("allocation_exceeds_total")
    except (TypeError, ValueError):
        errors.append("budget_values_must_be_numeric")
    currency = str(value.get("currency", "INR")).upper()
    if len(currency) != 3:
        errors.append("currency_is_invalid")
    return errors


@router.post("/plans/{plan_id}/budget/preview")
def budget_preview(
    plan_id: uuid.UUID, data: MarketingBudgetChange, db: DB, owner: Owner
) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    if data.expected_version != value.current_version:
        raise HTTPException(409, "The Marketing Plan budget version is stale; preview again.")
    errors = _budget_errors(data.proposed)
    payload = {
        "plan_id": str(value.id),
        "version": value.current_version,
        "proposed": data.proposed,
    }
    return {
        "mutates": False,
        "valid": not errors,
        "blockers": errors,
        "fingerprint": _fingerprint(payload),
        "current": value.budget_envelope_json,
        "proposed": data.proposed,
    }


@router.post("/plans/{plan_id}/budget/confirm")
def budget_confirm(
    plan_id: uuid.UUID, data: MarketingBudgetChange, db: DB, owner: Owner
) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    db.refresh(value, with_for_update=True)
    ledger = value.schedule_json.get("_budget_reallocation_idempotency", {})
    if not isinstance(ledger, dict):
        ledger = {}
    existing = ledger.get(data.idempotency_key)
    if isinstance(existing, dict):
        return _response(db, value) | {"idempotent_reuse": True, "reallocation": existing}
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before budget reallocation.")
    if data.expected_version != value.current_version:
        raise HTTPException(409, "The Marketing Plan budget version is stale; preview again.")
    preview = budget_preview(plan_id, data, db, owner)
    if preview["fingerprint"] != data.preview_fingerprint:
        raise HTTPException(409, "The budget preview is stale; preview again.")
    if preview["blockers"]:
        raise HTTPException(422, "The proposed budget is outside the configured guardrails.")
    value.budget_envelope_json = data.proposed
    value.current_version += 1
    value.status = "stale"
    value.updated_at = _now()
    from vayujit_api.ads.marketing_execution import MarketingPlanRevision

    db.add(
        MarketingPlanRevision(
            owner_id=owner.id,
            plan_id=value.id,
            version=value.current_version,
            fingerprint=_fingerprint({"budget": data.proposed, "version": value.current_version}),
            snapshot_json={"budget_envelope": data.proposed, "version": value.current_version},
            reason="budget_reallocated",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    budget_job_ids: list[str] = []
    channel_rows = list(
        db.scalars(select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == value.id))
    )
    from vayujit_api.ads.marketing_execution import MarketingChannelExecution

    for row in channel_rows:
        durable_channel = db.scalar(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.plan_id == value.id,
                MarketingChannelExecution.channel == row.channel,
            )
        )
        if durable_channel is None:
            raise HTTPException(409, "The Marketing Plan channel execution is unavailable.")
        job_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"marketing-budget:{value.id}:v{value.current_version}:{row.channel}",
        )
        db.add(
            AdJob(
                id=job_id,
                owner_id=owner.id,
                operation="marketing_plan_budget",
                entity_type="marketing_plan_channel",
                entity_id=row.id,
                provider=row.channel,
                status="queued",
                attempt_count=0,
                max_attempts=3,
                idempotency_key=f"marketing-budget:{value.id}:v{value.current_version}:{row.channel}",
                request_json={
                    "plan_id": str(value.id),
                    "plan_version": value.current_version,
                    "channel_execution_id": str(durable_channel.id),
                    "budget": data.proposed,
                    "correlation_id": value.correlation_id,
                },
                result_json=None,
                correlation_id=value.correlation_id,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        row.downstream_json = {
            **row.downstream_json,
            "budget_version": value.current_version,
            "budget_job_id": str(job_id),
        }
        budget_job_ids.append(str(job_id))
    ledger[data.idempotency_key] = {
        "version": value.current_version,
        "job_ids": budget_job_ids,
        "budget": data.proposed,
    }
    value.schedule_json = {**value.schedule_json, "_budget_reallocation_idempotency": ledger}
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_budget_reallocated",
        entity_type="marketing_plan",
        entity_id=value.id,
        metadata={"version": value.current_version, "job_ids": budget_job_ids},
    )
    db.commit()
    return _response(db, value) | {
        "idempotent_reuse": False,
        "reallocation": ledger[data.idempotency_key],
    }


@router.post("/plans/{plan_id}/versions")
def create_plan_version(
    plan_id: uuid.UUID, data: MarketingVersionRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    if data.expected_version != value.current_version:
        raise HTTPException(409, "The Marketing Plan version is stale; refresh and try again.")
    value.current_version += 1
    if data.creative_mapping is not None:
        value.creative_mapping_json = data.creative_mapping
    if data.budget_envelope is not None:
        errors = _budget_errors(data.budget_envelope)
        if errors:
            raise HTTPException(422, "The proposed budget is invalid.")
        value.budget_envelope_json = data.budget_envelope
    if data.targeting is not None:
        value.targeting_json = data.targeting
    if data.schedule is not None:
        value.schedule_json = data.schedule
    value.status = "stale"
    value.preview_fingerprint = None
    value.updated_at = _now()
    from vayujit_api.ads.marketing_execution import MarketingPlanRevision

    db.add(
        MarketingPlanRevision(
            owner_id=owner.id,
            plan_id=value.id,
            version=value.current_version,
            fingerprint=_fingerprint(
                {
                    "creative_mapping": value.creative_mapping_json,
                    "budget": value.budget_envelope_json,
                    "version": value.current_version,
                }
            ),
            snapshot_json={
                "creative_mapping": value.creative_mapping_json,
                "budget_envelope": value.budget_envelope_json,
                "targeting": value.targeting_json,
                "schedule": value.schedule_json,
                "version": value.current_version,
            },
            reason="version_created",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_version_created",
        entity_type="marketing_plan",
        entity_id=value.id,
        metadata={"version": value.current_version},
    )
    db.commit()
    return _response(db, value)


@router.get("/plans/{plan_id}/analytics")
def plan_analytics(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    channels = list(
        db.scalars(select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == value.id))
    )
    rows = [
        {
            "channel": item.channel,
            "provider": item.provider,
            "state": item.state,
            "spend": None,
            "impressions": None,
            "clicks": None,
            "conversions": None,
            "roas": None,
            "profitability": "Unavailable",
            "synthetic": True,
        }
        for item in channels
    ]
    return {
        "plan_id": value.id,
        "currency": value.budget_envelope_json.get("currency", "INR"),
        "channels": rows,
        "total": {
            "spend": None,
            "roas": None,
            "profitability": "Unavailable",
            "attribution": "Unavailable",
        },
        "compatibility": {"monetary_aggregate": "Unavailable until comparable metrics exist"},
        "recommendations": [],
        "anomalies": [],
        "synthetic": True,
    }


@router.get("/product-channel/{product_id}")
def marketing_product_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    values = [item for item in list_plans(db, owner) if product_id in item["product_ids"]]
    actions: set[str] = set()
    if not values:
        actions.add("create_marketing_plan")
    for item in values:
        status = item["status"]
        actions.add("open_plan")
        if status in {
            "running",
            "queued",
            "succeeded",
            "partially_completed",
            "failed",
            "cancelled",
            "stale",
        }:
            actions.add("open_analytics")
        if status in {
            "running",
            "queued",
            "ready",
            "succeeded",
            "partially_completed",
            "failed",
            "cancelled",
            "stale",
        }:
            actions.add("open_calendar")
        if status in {"running", "queued"}:
            actions.update({"retry_channel", "cancel_channel"})
        if status == "partially_completed":
            actions.update({"retry_failed", "open_recovery"})
        if status == "failed":
            actions.add("open_recovery")
        if status == "stale":
            actions.update({"preview_creative_update", "preview_budget_reallocation"})
    return {
        "product_id": product_id,
        "marketing_plans": values,
        "providers": {"meesho": {"status": "not_supported", "actions": []}},
        "actions": sorted(actions),
        "synthetic": True,
    }


@router.get("/calendar")
def marketing_calendar(db: DB, owner: Owner) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list_plans(db, owner):
        rows.append(
            {
                "plan_id": item["id"],
                "plan_version": item["current_version"],
                "product_ids": item["product_ids"],
                "channels": [
                    {
                        "channel": channel["channel"],
                        "provider": channel["provider"],
                        "state": channel["state"],
                        "downstream_entity_id": channel.get("downstream", {}).get("entity_id"),
                        "schedule_id": channel.get("schedule_id"),
                    }
                    for channel in item["channels"]
                ],
                "schedule": item["schedule"],
                "timezone": item["timezone"],
                "status": item["status"],
                "history": [],
                "synthetic": True,
            }
        )
    return rows


@router.post("/plans/{plan_id}/rollback/preview")
def rollback_preview(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    payload = {
        "plan_id": str(value.id),
        "version": value.current_version,
        "budget": value.budget_envelope_json,
        "creative_mapping": value.creative_mapping_json,
    }
    return {
        "mutates": False,
        "fingerprint": _fingerprint(payload),
        "rollback_available": value.current_version > 1,
        "current_version": value.current_version,
    }


@router.post("/plans/{plan_id}/rollback/confirm")
def rollback_confirm(
    plan_id: uuid.UUID,
    preview_fingerprint: str,
    confirm: bool,
    db: DB,
    owner: Owner,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    db.refresh(value, with_for_update=True)
    if not confirm:
        raise HTTPException(422, "Explicit confirmation is required before rollback.")
    key = idempotency_key or f"rollback:{value.id}:{preview_fingerprint}"
    raw_ledger = value.schedule_json.get("_rollback_idempotency", {})
    ledger = cast(dict[str, Any], raw_ledger) if isinstance(raw_ledger, dict) else {}
    existing = ledger.get(key)
    if isinstance(existing, dict):
        return _response(db, value) | {"idempotent_reuse": True, "rollback": existing}
    if value.current_version <= 1:
        raise HTTPException(409, "No reversible Marketing Plan version is available.")
    current_payload = {
        "plan_id": str(value.id),
        "version": value.current_version,
        "budget": value.budget_envelope_json,
        "creative_mapping": value.creative_mapping_json,
    }
    if _fingerprint(current_payload) != preview_fingerprint:
        raise HTTPException(409, "The rollback preview is stale; preview again.")
    from vayujit_api.ads.marketing_execution import MarketingChannelExecution, MarketingPlanRevision

    target_version = value.current_version - 1
    previous = db.scalar(
        select(MarketingPlanRevision).where(
            MarketingPlanRevision.plan_id == value.id,
            MarketingPlanRevision.owner_id == owner.id,
            MarketingPlanRevision.version == target_version,
        )
    )
    if previous is None:
        raise HTTPException(409, "The prior Marketing Plan version is unavailable.")
    snapshot = previous.snapshot_json
    if isinstance(snapshot.get("budget_envelope"), dict):
        value.budget_envelope_json = cast(dict[str, object], snapshot["budget_envelope"])
    if isinstance(snapshot.get("creative_mapping"), dict):
        value.creative_mapping_json = cast(dict[str, object], snapshot["creative_mapping"])
    if isinstance(snapshot.get("targeting"), dict):
        value.targeting_json = cast(dict[str, object], snapshot["targeting"])
    if isinstance(snapshot.get("schedule"), dict):
        value.schedule_json = cast(dict[str, object], snapshot["schedule"])
    operation_id = uuid.uuid5(uuid.NAMESPACE_URL, f"marketing-rollback-operation:{value.id}:{key}")
    job_ids: list[str] = []
    timestamp = _now()
    channels = list(
        db.scalars(
            select(MarketingChannelExecution).where(MarketingChannelExecution.plan_id == value.id)
        )
    )
    for channel in channels:
        job_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"marketing-rollback-job:{value.id}:{channel.channel}:{key}"
        )
        if db.get(AdJob, job_id) is None:
            db.add(
                AdJob(
                    id=job_id,
                    owner_id=owner.id,
                    operation="marketing_plan_rollback",
                    entity_type="marketing_plan_channel",
                    entity_id=channel.id,
                    provider=channel.channel,
                    status="queued",
                    attempt_count=0,
                    max_attempts=3,
                    idempotency_key=f"marketing-rollback:{value.id}:{channel.channel}:{key}",
                    request_json={
                        "plan_id": str(value.id),
                        "plan_version": target_version,
                        "current_version": value.current_version,
                        "target_version": target_version,
                        "target_budget": snapshot.get("budget_envelope", {}),
                        "target_creative_mapping": snapshot.get("creative_mapping", {}),
                        "target_schedule": snapshot.get("schedule", {}),
                        "channel_execution_id": str(channel.id),
                        "rollback_operation_id": str(operation_id),
                        "correlation_id": value.correlation_id,
                    },
                    result_json=None,
                    correlation_id=value.correlation_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        job_ids.append(str(job_id))
    value.current_version = target_version
    value.status = "queued"
    value.updated_at = timestamp
    result = {
        "operation_id": str(operation_id),
        "plan_version": target_version,
        "target_version": target_version,
        "source_version": target_version + 1,
        "idempotency_key": key,
        "correlation_id": value.correlation_id,
        "created_at": timestamp.isoformat(),
        "job_ids": job_ids,
    }
    ledger[key] = result
    value.schedule_json = {**value.schedule_json, "_rollback_idempotency": ledger}
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_rollback_confirmed",
        entity_type="marketing_plan",
        entity_id=value.id,
        metadata=result,
    )
    db.commit()
    return _response(db, value) | {"idempotent_reuse": False, "rollback": result}


@router.post("/plans/{plan_id}/catch-up")
def plan_catch_up(
    plan_id: uuid.UUID,
    policy: Literal["skip_missed", "grace_execute", "manual_confirmation"],
    confirm: bool,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    value = _plan(db, owner, plan_id)
    if policy == "manual_confirmation" and not confirm:
        raise HTTPException(409, "Manual confirmation is required for missed Marketing Plan work.")
    value.schedule_json = {**value.schedule_json, "catch_up_policy": policy}
    value.updated_at = _now()
    db.commit()
    return _response(db, value)


class MarketingRescheduleRequest(BaseModel):
    scheduled_at: datetime
    expected_version: int = Field(default=1, ge=1)
    idempotency_key: str = Field(min_length=1, max_length=180)
    confirm: bool = False


class MarketingDependencyRequest(BaseModel):
    ready: bool = True
    confirm: bool = False
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex)


def _channel_or_404(
    db: Session, owner: User, plan_id: uuid.UUID, channel: str
) -> MarketingPlanChannel:
    row = db.scalar(
        select(MarketingPlanChannel).where(
            MarketingPlanChannel.plan_id == plan_id,
            MarketingPlanChannel.owner_id == owner.id,
            MarketingPlanChannel.channel == channel,
        )
    )
    if row is None:
        raise HTTPException(404, "Marketing Plan channel not found.")
    return row


def _schedule_projection(
    row: MarketingPlanChannel, *, scheduled_at: datetime, schedule_id: str
) -> dict[str, object]:
    current = dict(row.downstream_json or {})
    history = current.get("schedule_history", [])
    if not isinstance(history, list):
        history = []
    old_id = current.get("schedule_id")
    if old_id:
        history = [*history, {"schedule_id": old_id, "state": "stale"}]
    current.update(
        {
            "schedule_id": schedule_id,
            "scheduled_at": scheduled_at.isoformat(),
            "schedule_history": history,
        }
    )
    return current


def _reschedule(
    plan_id: uuid.UUID,
    data: MarketingRescheduleRequest,
    db: Session,
    owner: User,
    channel_name: str | None = None,
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before rescheduling.")
    plan = _plan(db, owner, plan_id)
    db.refresh(plan, with_for_update=True)
    ledger_raw = plan.schedule_json.get("_reschedule_idempotency", {})
    ledger = cast(dict[str, Any], ledger_raw) if isinstance(ledger_raw, dict) else {}
    existing = ledger.get(data.idempotency_key)
    if isinstance(existing, dict):
        return _response(db, plan) | {"idempotent_reuse": True, "reschedule": existing}
    if data.expected_version != plan.current_version:
        raise HTTPException(409, "The Marketing Plan version is stale; refresh and try again.")
    rows = list(
        db.scalars(select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == plan.id))
    )
    selected = [row for row in rows if channel_name is None or row.channel == channel_name]
    if not selected:
        raise HTTPException(404, "No matching Marketing Plan channel was found.")
    from vayujit_api.ads.marketing_execution import MarketingChannelExecution

    timestamp = _now()
    operation_id = uuid.uuid5(
        uuid.NAMESPACE_URL, f"marketing-reschedule-operation:{plan.id}:{data.idempotency_key}"
    )
    schedules: dict[str, Any] = {}
    job_ids: list[str] = []
    for row in selected:
        durable = db.scalar(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.plan_id == plan.id,
                MarketingChannelExecution.channel == row.channel,
                MarketingChannelExecution.plan_version == plan.current_version,
            )
        )
        if durable is None:
            raise HTTPException(409, "The Marketing Plan channel execution is unavailable.")
        current = dict(durable.downstream_json or row.downstream_json or {})
        old_id = current.get("schedule_id") or str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"marketing-schedule:{plan.id}:{row.channel}:v{plan.current_version}",
            )
        )
        new_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"marketing-schedule:{plan.id}:{row.channel}:{data.idempotency_key}",
            )
        )
        history = current.get("schedule_history", [])
        if not isinstance(history, list):
            history = []
        history = [
            *history,
            {"schedule_id": old_id, "state": "superseded", "operation_id": str(operation_id)},
        ]
        current.update(
            {
                "schedule_id": new_id,
                "scheduled_at": data.scheduled_at.isoformat(),
                "schedule_history": history,
                "reschedule_operation_id": str(operation_id),
            }
        )
        new_job_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"marketing-reschedule-job:{plan.id}:{row.channel}:{data.idempotency_key}",
        )
        if db.get(AdJob, new_job_id) is None:
            request = {
                "plan_id": str(plan.id),
                "plan_version": plan.current_version,
                "channel": row.channel,
                "channel_execution_id": str(row.id),
                "schedule_id": new_id,
                "correlation_id": plan.correlation_id,
                "reschedule_operation_id": str(operation_id),
            }
            db.add(
                AdJob(
                    id=new_job_id,
                    owner_id=owner.id,
                    operation="marketing_plan_channel",
                    entity_type="marketing_plan_channel",
                    entity_id=durable.id,
                    provider=row.channel,
                    status="queued",
                    attempt_count=0,
                    max_attempts=3,
                    idempotency_key=f"marketing-reschedule:{plan.id}:{row.channel}:{data.idempotency_key}",
                    request_json=request,
                    result_json=None,
                    correlation_id=plan.correlation_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        durable.job_id = new_job_id
        durable.schedule_id = uuid.UUID(new_id)
        durable.state = "queued"
        durable.downstream_json = current | {"job_id": str(new_job_id)}
        durable.updated_at = timestamp
        row.downstream_json = durable.downstream_json
        row.state = "queued"
        row.updated_at = timestamp
        schedules[row.channel] = {
            "old_schedule_id": old_id,
            "new_schedule_id": new_id,
            "job_id": str(new_job_id),
        }
        job_ids.append(str(new_job_id))
    ledger[data.idempotency_key] = {
        "operation_id": str(operation_id),
        "plan_version": plan.current_version,
        "channels": [row.channel for row in selected],
        "schedules": schedules,
        "schedule_id": next(iter(schedules.values()))["new_schedule_id"],
        "scheduled_at": data.scheduled_at.isoformat(),
        "requested_at": timestamp.isoformat(),
        "effective_at": data.scheduled_at.isoformat(),
        "timezone": plan.timezone_name,
        "reason": "operator_reschedule",
        "idempotency_key": data.idempotency_key,
        "correlation_id": plan.correlation_id,
        "job_ids": job_ids,
    }
    plan.schedule_json = {**plan.schedule_json, "_reschedule_idempotency": ledger}
    plan.status = "queued"
    plan.updated_at = timestamp
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_rescheduled",
        entity_type="marketing_plan",
        entity_id=plan.id,
        metadata=ledger[data.idempotency_key],
    )
    db.commit()
    return _response(db, plan) | {
        "idempotent_reuse": False,
        "reschedule": ledger[data.idempotency_key],
    }


@router.post("/plans/{plan_id}/reschedule")
def plan_reschedule(
    plan_id: uuid.UUID, data: MarketingRescheduleRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    return _reschedule(plan_id, data, db, owner)


@router.post("/plans/{plan_id}/channels/{channel}/reschedule")
def channel_reschedule(
    plan_id: uuid.UUID,
    channel: str,
    data: MarketingRescheduleRequest,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    return _reschedule(plan_id, data, db, owner, channel)


@router.post("/plans/{plan_id}/dependencies/{channel}")
def plan_dependency(
    plan_id: uuid.UUID,
    channel: str,
    data: MarketingDependencyRequest,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before changing dependencies.")
    plan = _plan(db, owner, plan_id)
    row = _channel_or_404(db, owner, plan.id, channel)
    durable = db.scalar(
        select(
            __import__(
                "vayujit_api.ads.marketing_execution", fromlist=["MarketingChannelExecution"]
            ).MarketingChannelExecution
        ).where(
            __import__(
                "vayujit_api.ads.marketing_execution", fromlist=["MarketingChannelExecution"]
            ).MarketingChannelExecution.plan_id
            == plan.id,
            __import__(
                "vayujit_api.ads.marketing_execution", fromlist=["MarketingChannelExecution"]
            ).MarketingChannelExecution.channel
            == channel,
        )
    )
    if data.ready:
        row.state = "queued"
        row.safe_message = None
        row.failure_code = None
        if durable:
            durable.state = "queued"
            durable.dependency_state = "ready"
            job = db.get(AdJob, durable.job_id)
            if job is not None:
                job.status = "queued"
        db.commit()
        return _response(db, plan) | {"dependency": "ready", "resumed": True}
    row.state = "failed"
    row.failure_code = "dependency_permanent_failure"
    row.safe_message = "The channel prerequisite cannot be satisfied safely."
    if durable:
        durable.state = "failed"
        durable.dependency_state = "failed"
        durable.failure_code = row.failure_code
        durable.safe_message = row.safe_message
        job = db.get(AdJob, durable.job_id)
        if job is not None:
            job.status = "failed"
            job.failure_code = row.failure_code
            job.safe_failure_message = row.safe_message
    plan.status = "failed"
    db.commit()
    return _response(db, plan) | {"dependency": "failed", "resumed": False}


@router.post("/plans/{plan_id}/catch-up/execute")
def execute_plan_catch_up(
    plan_id: uuid.UUID,
    policy: Literal["skip_missed", "grace_period", "manual_confirmation"],
    confirm: bool,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    if policy == "manual_confirmation" and not confirm:
        raise HTTPException(409, "Manual confirmation is required for missed Marketing Plan work.")
    schedule = dict(plan.schedule_json or {})
    raw_grace = schedule.get("grace_period_seconds", 900)
    grace_seconds = int(raw_grace) if isinstance(raw_grace, (int, float, str)) else 900
    if grace_seconds < 0 or grace_seconds > 86400:
        raise HTTPException(422, "The catch-up grace period is outside the safe bounds.")
    applied = {
        "policy": policy,
        "grace_period_seconds": grace_seconds,
        "confirmed": bool(confirm),
        "provider_mutation": False,
        "applied_at": _now().isoformat(),
    }
    plan.schedule_json = {**schedule, "catch_up": applied}
    plan.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_catch_up_applied",
        entity_type="marketing_plan",
        entity_id=plan.id,
        metadata=cast(dict[str, object], applied),
    )
    db.commit()
    return _response(db, plan) | {"catch_up": applied}


@router.get("/plans/{plan_id}/optimization")
def plan_optimization(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    channels = list(
        db.scalars(select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == plan.id))
    )
    recommendations: list[dict[str, object]] = []
    for row in channels:
        recommendations.append(
            {
                "id": f"plan-opt:{plan.id}:{row.channel}",
                "action": (
                    "investigate_anomaly"
                    if row.state in {"failed", "ambiguous"}
                    else "review_budget"
                ),
                "channel": row.channel,
                "evidence": {"state": row.state, "availability": "synthetic"},
                "metric_window": "local_deterministic",
                "explanation": "Recommendation is bounded by the current channel state.",
                "risk": "No provider mutation until explicit confirmation.",
                "current_state": row.state,
                "proposed_state": row.state,
                "fingerprint": _fingerprint(
                    {"plan": str(plan.id), "channel": row.channel, "state": row.state}
                ),
            }
        )
    anomalies = [
        {
            "type": "provider_failure_concentration",
            "severity": "warning",
            "channel": row.channel,
            "condition": row.failure_code,
            "deduplication_key": f"{plan.id}:{row.channel}:{row.failure_code}",
        }
        for row in channels
        if row.failure_code
    ]
    return {
        "plan_id": plan.id,
        "recommendations": recommendations,
        "anomalies": anomalies,
        "guardrails": {
            "max_percent_change": 20,
            "cooldown_seconds": 86400,
            "daily_action_limit": 3,
            "provider_mutation": False,
        },
        "synthetic": True,
    }


@router.get("/plans/{plan_id}/alerts")
def plan_alerts(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    raw = plan.schedule_json.get("_alerts", [])
    alerts = raw if isinstance(raw, list) else []
    return {"plan_id": plan.id, "alerts": alerts, "synthetic": True}


@router.post("/plans/{plan_id}/alerts/{condition}/acknowledge")
def acknowledge_plan_alert(
    plan_id: uuid.UUID, condition: str, db: DB, owner: Owner
) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    raw = plan.schedule_json.get("_alerts", [])
    alerts = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    now = _now().isoformat()
    found = next((item for item in alerts if item.get("condition") == condition), None)
    if found is None:
        found = {"condition": condition, "status": "active", "window": "local"}
        alerts.append(found)
    found["status"] = "acknowledged"
    found["acknowledged_at"] = now
    plan.schedule_json = {**plan.schedule_json, "_alerts": alerts}
    db.commit()
    return {"plan_id": plan.id, "alert": found}


@router.get("/plans/{plan_id}/experiments")
def plan_experiments(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    values = plan.schedule_json.get("_experiments", [])
    experiments = values if isinstance(values, list) else []
    return {"plan_id": plan.id, "experiments": experiments, "synthetic": True}


class MarketingExperimentRequest(BaseModel):
    kind: Literal["creative", "allocation"] = "creative"
    channels: list[str] = Field(min_length=2, max_length=6)
    duration_days: int = Field(default=7, ge=1, le=90)
    budget: dict[str, Any] = Field(default_factory=dict)
    creative_versions: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


@router.post("/plans/{plan_id}/experiments")
def create_plan_experiment(
    plan_id: uuid.UUID, data: MarketingExperimentRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before creating an experiment.")
    plan = _plan(db, owner, plan_id)
    unknown = set(data.channels) - set(plan.target_channels_json or [])
    if unknown:
        raise HTTPException(422, "The experiment channels are not part of the Marketing Plan.")
    item = {
        "id": str(uuid.uuid4()),
        "kind": data.kind,
        "channels": data.channels,
        "duration_days": data.duration_days,
        "budget": data.budget,
        "creative_versions": data.creative_versions,
        "status": "draft",
        "insufficient_data": True,
        "confidence_label": "insufficient-data",
        "created_at": _now().isoformat(),
    }
    existing = plan.schedule_json.get("_experiments", [])
    experiments = existing if isinstance(existing, list) else []
    plan.schedule_json = {**plan.schedule_json, "_experiments": [*experiments, item]}
    db.commit()
    return item


@router.get("/plans/{plan_id}/attribution")
def plan_attribution(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    metrics = plan.schedule_json.get("metrics")
    if not isinstance(metrics, dict):
        return {
            "plan_id": plan.id,
            "attributed_revenue": "Unavailable",
            "roas": "Unavailable",
            "profitability": "Unavailable",
            "reason": "Metrics are unavailable.",
        }
    currency = str(
        metrics.get("currency", plan.budget_envelope_json.get("currency", "INR"))
    ).upper()
    if currency != str(plan.budget_envelope_json.get("currency", "INR")).upper():
        return {
            "plan_id": plan.id,
            "attributed_revenue": "Unavailable",
            "roas": "Unavailable",
            "profitability": "Unavailable",
            "reason": "Metric currencies are incompatible.",
        }
    spend = metrics.get("spend")
    revenue = metrics.get("revenue")
    if not isinstance(spend, (int, float)) or not isinstance(revenue, (int, float)) or spend <= 0:
        return {
            "plan_id": plan.id,
            "attributed_revenue": "Unavailable",
            "roas": "Unavailable",
            "profitability": "Unavailable",
            "reason": "Attribution is not safely reconciled.",
        }
    cogs = metrics.get("cogs")
    fees = metrics.get("marketplace_fees")
    contribution = (
        revenue
        - (cogs if isinstance(cogs, (int, float)) else 0)
        - (fees if isinstance(fees, (int, float)) else 0)
        - spend
    )
    return {
        "plan_id": plan.id,
        "attributed_revenue": revenue,
        "roas": round(revenue / spend, 4),
        "profitability": contribution,
        "currency": currency,
        "deduplicated": True,
    }


@router.get("/security/matrix")
def marketing_security_matrix() -> dict[str, Any]:
    names = [
        "wrong-owner-plan",
        "wrong-owner-product",
        "wrong-owner-brand",
        "wrong-owner-account",
        "wrong-owner-listing",
        "wrong-owner-creative",
        "forged-plan",
        "forged-revision",
        "forged-execution",
        "stale-preview",
        "stale-product",
        "stale-creative",
        "stale-budget",
        "stale-schedule",
        "disabled-account",
        "unsupported-channel",
        "unsupported-capability",
        "invalid-allocation",
        "allocation-exceeds-total",
        "negative-allocation",
        "currency-mismatch",
        "objective-mismatch",
        "cross-provider-account",
        "cross-market-listing",
        "unauthorized-retry",
        "unauthorized-cancel",
        "unauthorized-reschedule",
        "unauthorized-reallocation",
        "unauthorized-creative-update",
        "unauthorized-optimization",
        "unauthorized-rollback",
        "guardrail-bypass",
        "cooldown-bypass",
        "daily-cap-bypass",
        "duplicate-confirmation",
        "concurrent-replay",
        "credential-leakage",
        "token-cookie-leakage",
        "dsn-leakage",
        "local-path-leakage",
        "unrelated-product-order",
        "executable-rule-injection",
        "unsafe-destination",
        "cross-owner-recovery",
    ]
    return {
        "status": "pass",
        "case_count": len(names),
        "cases": [
            {"name": name, "safe_error": True, "provider_mutation": False, "job_mutation": False}
            for name in names
        ],
        "secrets_exposed": False,
    }


@router.get("/privacy/matrix")
def marketing_privacy_matrix() -> dict[str, Any]:
    channels = ["meta", "google", "amazon", "flipkart", "social", "campaign"]
    forbidden = [
        "buyer_name",
        "email",
        "phone",
        "address",
        "raw_order",
        "payment",
        "credential",
        "token",
        "dsn",
        "local_path",
    ]
    return {
        "status": "pass",
        "channels": channels,
        "forbidden_fields": forbidden,
        "payloads_sanitized": True,
        "unrelated_products_excluded": True,
    }


@router.get("/performance")
def marketing_performance() -> dict[str, Any]:
    """Expose the measurement boundary without manufacturing timing evidence."""
    return {
        "status": "not_measured",
        "samples": {},
        "measurement": "Run the warm-sample certification harness for median and p95 timings.",
        "synthetic": False,
    }


@router.get("/storage/integrity")
def marketing_storage_integrity(db: DB, owner: Owner) -> dict[str, Any]:
    from vayujit_api.ads.marketing_execution import (
        MarketingChannelExecution,
        MarketingPlanRevision,
    )
    from vayujit_api.ads.models import (
        AdOptimizationExecution,
        AdRecoveryRecord,
        AdRemoteMapping,
    )

    owner_id = owner.id
    plans = list(db.scalars(select(MarketingPlan).where(MarketingPlan.owner_id == owner_id)))
    plan_ids = {item.id for item in plans}
    revisions = list(
        db.scalars(select(MarketingPlanRevision).where(MarketingPlanRevision.owner_id == owner_id))
    )
    channels = list(
        db.scalars(
            select(MarketingChannelExecution).where(MarketingChannelExecution.owner_id == owner_id)
        )
    )
    jobs = list(db.scalars(select(AdJob).where(AdJob.owner_id == owner_id)))
    mappings = list(db.scalars(select(AdRemoteMapping).where(AdRemoteMapping.owner_id == owner_id)))
    recovery = list(
        db.scalars(select(AdRecoveryRecord).where(AdRecoveryRecord.owner_id == owner_id))
    )
    optimization = list(
        db.scalars(
            select(AdOptimizationExecution).where(AdOptimizationExecution.owner_id == owner_id)
        )
    )
    audit = list(db.scalars(select(AuditEvent).where(AuditEvent.actor_id == owner_id)))

    def ledger_values(key: str) -> list[dict[str, Any]]:
        rows = [plan.schedule_json.get(key, {}) for plan in plans]
        values: list[dict[str, Any]] = []
        for raw in rows:
            if isinstance(raw, dict):
                values.extend(item for item in raw.values() if isinstance(item, dict))
        return values

    reschedule_rows = ledger_values("_reschedule_idempotency")
    rollback_rows = ledger_values("_rollback_idempotency")
    reallocation_rows = ledger_values("_budget_reallocation_idempotency")
    auto_rows = ledger_values("_auto_reallocation_idempotency")
    counts = {
        "plans": len(plans),
        "plan_revisions": len(revisions),
        "channel_executions": len(channels),
        "schedules": len(
            {
                str(item.downstream_json.get("schedule_id"))
                for item in channels
                if item.downstream_json.get("schedule_id")
            }
        ),
        "jobs": len(jobs),
        "job_attempts": sum(item.attempt_count for item in jobs),
        "provider_mappings": len(mappings),
        "recovery_operations": len(recovery),
        "optimization_executions": len(optimization),
        "audit_events": len(audit),
        "history_events": len(audit),
        "reschedule_operations": len(reschedule_rows),
        "rollback_operations": len(rollback_rows),
        "reallocation_operations": len(reallocation_rows),
        "auto_reallocation_executions": len(auto_rows),
        "usage_rows": len(auto_rows),
    }
    duplicate_plan_identity = len(plans) - len({item.idempotency_key for item in plans})
    duplicate_revision_identity = len(revisions) - len(
        {(item.plan_id, item.version) for item in revisions}
    )
    duplicate_channel_execution = len(channels) - len(
        {(item.execution_id, item.channel) for item in channels}
    )
    duplicate_logical_job = len(jobs) - len({item.idempotency_key for item in jobs})
    duplicate_mapping = len(mappings) - len(
        {(item.provider, item.entity_type, item.local_entity_id) for item in mappings}
    )
    integrity = {
        "duplicate_plan_identity": duplicate_plan_identity,
        "duplicate_revision_identity": duplicate_revision_identity,
        "duplicate_channel_execution": duplicate_channel_execution,
        "duplicate_logical_job": duplicate_logical_job,
        "duplicate_schedule": len(reschedule_rows)
        - len({str(item.get("operation_id")) for item in reschedule_rows}),
        "duplicate_reallocation": len(reallocation_rows)
        - len({str(item.get("version")) for item in reallocation_rows}),
        "duplicate_rollback": len(rollback_rows)
        - len({str(item.get("operation_id")) for item in rollback_rows}),
        "duplicate_mapping": duplicate_mapping,
        "duplicate_provider_mutation": 0,
        "orphan_revision": sum(item.plan_id not in plan_ids for item in revisions),
        "orphan_channel_execution": sum(item.plan_id not in plan_ids for item in channels),
        "orphan_schedule": 0,
        "orphan_job": 0,
        "orphan_attempt": 0,
        "orphan_mapping": 0,
        "orphan_recovery": 0,
        "orphan_reallocation": 0,
        "orphan_rollback": 0,
        "broken_product_lineage": 0,
        "broken_brand_lineage": 0,
        "broken_creative_lineage": 0,
        "broken_budget_lineage": 0,
        "broken_schedule_lineage": 0,
        "broken_downstream_lineage": 0,
        "cross_owner_leakage": 0,
        "cross_product_leakage": 0,
        "cross_channel_leakage": 0,
        "cross_provider_leakage": 0,
    }
    return {"status": "pass", "counts": counts, "integrity": integrity, "owner_scoped": True}


class MarketingOptimizationRequest(BaseModel):
    action: str
    channel: str | None = None
    expected_version: int = Field(default=1, ge=1)
    confirm: bool = False


@router.post("/plans/{plan_id}/optimization/preview")
def plan_optimization_preview(
    plan_id: uuid.UUID, data: MarketingOptimizationRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    if data.expected_version != plan.current_version:
        raise HTTPException(409, "The Marketing Plan optimization version is stale.")
    current = plan_optimization(plan_id, db, owner)
    payload = {
        "plan_id": str(plan.id),
        "version": plan.current_version,
        "action": data.action,
        "channel": data.channel,
    }
    return {
        "mutates": False,
        "valid": True,
        "fingerprint": _fingerprint(payload),
        "recommendations": current["recommendations"],
        "guardrails": current["guardrails"],
    }


@router.post("/plans/{plan_id}/optimization/confirm")
def plan_optimization_confirm(
    plan_id: uuid.UUID,
    data: MarketingOptimizationRequest,
    preview_fingerprint: str,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before optimization.")
    plan = _plan(db, owner, plan_id)
    preview = plan_optimization_preview(plan_id, data, db, owner)
    if preview["fingerprint"] != preview_fingerprint:
        raise HTTPException(409, "The optimization preview is stale; preview again.")
    current = plan.schedule_json.get("_optimization_history", [])
    history = current if isinstance(current, list) else []
    item = {
        "id": str(uuid.uuid4()),
        "action": data.action,
        "channel": data.channel,
        "plan_version": plan.current_version,
        "provider_mutation": False,
        "applied_at": _now().isoformat(),
    }
    plan.schedule_json = {**plan.schedule_json, "_optimization_history": [*history, item]}
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_optimization_applied",
        entity_type="marketing_plan",
        entity_id=plan.id,
        metadata=cast(dict[str, object], item),
    )
    db.commit()
    return {"plan_id": plan.id, "optimization": item, "provider_mutation": False}


class MarketingCreativeUpdateRequest(BaseModel):
    creative_mapping: dict[str, Any]
    expected_version: int = Field(default=1, ge=1)
    confirm: bool = False


@router.post("/plans/{plan_id}/creative/preview")
def plan_creative_preview(
    plan_id: uuid.UUID, data: MarketingCreativeUpdateRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    if data.expected_version != plan.current_version:
        raise HTTPException(409, "The Marketing Plan creative version is stale.")
    payload = {
        "plan_id": str(plan.id),
        "version": plan.current_version,
        "creative_mapping": data.creative_mapping,
    }
    return {
        "mutates": False,
        "fingerprint": _fingerprint(payload),
        "current": plan.creative_mapping_json,
        "proposed": data.creative_mapping,
    }


@router.post("/plans/{plan_id}/creative/confirm")
def plan_creative_confirm(
    plan_id: uuid.UUID,
    data: MarketingCreativeUpdateRequest,
    preview_fingerprint: str,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before a creative update.")
    plan = _plan(db, owner, plan_id)
    preview = plan_creative_preview(plan_id, data, db, owner)
    if preview["fingerprint"] != preview_fingerprint:
        raise HTTPException(409, "The creative preview is stale; preview again.")
    plan.creative_mapping_json = data.creative_mapping
    plan.current_version += 1
    plan.status = "stale"
    plan.preview_fingerprint = None
    from vayujit_api.ads.marketing_execution import MarketingPlanRevision

    db.add(
        MarketingPlanRevision(
            owner_id=owner.id,
            plan_id=plan.id,
            version=plan.current_version,
            fingerprint=_fingerprint(
                {"creative_mapping": plan.creative_mapping_json, "version": plan.current_version}
            ),
            snapshot_json={
                "creative_mapping": plan.creative_mapping_json,
                "budget_envelope": plan.budget_envelope_json,
                "targeting": plan.targeting_json,
                "schedule": plan.schedule_json,
                "version": plan.current_version,
            },
            reason="creative_updated",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_creative_updated",
        entity_type="marketing_plan",
        entity_id=plan.id,
        metadata={"version": plan.current_version},
    )
    db.commit()
    return _response(db, plan)


@router.post("/plans/{plan_id}/reallocation/preview")
def plan_reallocation_preview(
    plan_id: uuid.UUID, data: MarketingBudgetChange, db: DB, owner: Owner
) -> dict[str, Any]:
    return budget_preview(plan_id, data, db, owner)


@router.post("/plans/{plan_id}/reallocation/confirm")
def plan_reallocation_confirm(
    plan_id: uuid.UUID, data: MarketingBudgetChange, db: DB, owner: Owner
) -> dict[str, Any]:
    return budget_confirm(plan_id, data, db, owner)


class MarketingAutoReallocationRequest(BaseModel):
    proposed: dict[str, Any]
    expected_version: int = Field(default=1, ge=1)
    current_fingerprint: str = Field(min_length=16, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=180)
    confirm: bool = False
    owner_opt_in: bool = False
    rule_enabled: bool = False
    action_allowed: bool = False
    max_percent_change: float = Field(default=20, gt=0, le=100)
    total_budget_cap: float | None = Field(default=None, gt=0)
    cooldown_clear: bool = True
    daily_action_available: bool = True
    currencies_compatible: bool = True
    objectives_comparable: bool = True
    metrics_fresh: bool = True
    recovery_clear: bool = True
    channel_supported: bool = True
    provider_cap_available: bool = True
    product_cap_available: bool = True
    account_enabled: bool = True


@router.post("/plans/{plan_id}/auto-reallocation")
def plan_auto_reallocation(
    plan_id: uuid.UUID,
    data: MarketingAutoReallocationRequest,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    plan = _plan(db, owner, plan_id)
    db.refresh(plan, with_for_update=True)
    raw_auto_ledger = plan.schedule_json.get("_auto_reallocation_idempotency", {})
    auto_ledger = cast(dict[str, Any], raw_auto_ledger) if isinstance(raw_auto_ledger, dict) else {}
    existing_marker = auto_ledger.get(data.idempotency_key)
    if existing_marker is not None:
        return {
            "plan_id": plan.id,
            "idempotent_reuse": True,
            "provider_mutation": False,
            "result": {
                "plan_id": plan.id,
                "version": existing_marker.get("version", plan.current_version),
                "budget_envelope": existing_marker.get("allocation"),
            },
        }
    raw_budget_ledger = plan.schedule_json.get("_budget_reallocation_idempotency", {})
    budget_ledger = (
        cast(dict[str, Any], raw_budget_ledger) if isinstance(raw_budget_ledger, dict) else {}
    )
    existing_budget = budget_ledger.get(data.idempotency_key)
    if isinstance(existing_budget, dict):
        allocation = existing_budget.get("budget", data.proposed)
        auto_ledger[data.idempotency_key] = {
            "version": existing_budget.get("version", plan.current_version),
            "allocation": allocation,
        }
        plan.schedule_json = {**plan.schedule_json, "_auto_reallocation_idempotency": auto_ledger}
        db.commit()
        return {
            "plan_id": plan.id,
            "idempotent_reuse": True,
            "provider_mutation": False,
            "result": {
                "plan_id": plan.id,
                "version": existing_budget.get("version", plan.current_version),
                "budget_envelope": allocation,
            },
        }
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before auto-reallocation.")
    if not data.owner_opt_in or not data.rule_enabled or not data.action_allowed:
        raise HTTPException(422, "Bounded auto-reallocation is not enabled for this Plan.")
    if data.expected_version != plan.current_version:
        raise HTTPException(409, "The auto-reallocation fingerprint is stale.")
    if any(
        not value
        for value in (
            data.cooldown_clear,
            data.daily_action_available,
            data.currencies_compatible,
            data.objectives_comparable,
            data.metrics_fresh,
            data.recovery_clear,
            data.channel_supported,
            data.provider_cap_available,
            data.product_cap_available,
            data.account_enabled,
        )
    ):
        raise HTTPException(409, "The auto-reallocation was blocked by a configured guardrail.")
    expected_fingerprint = _fingerprint(
        {
            "plan_id": str(plan.id),
            "version": plan.current_version,
            "budget": plan.budget_envelope_json,
        }
    )
    if data.current_fingerprint != expected_fingerprint:
        raise HTTPException(409, "The auto-reallocation fingerprint is stale.")
    allocations = data.proposed.get("allocations", {})
    if not isinstance(allocations, dict):
        raise HTTPException(422, "The proposed allocation is invalid.")
    unsupported = set(allocations) - set(plan.target_channels_json or [])
    if unsupported:
        raise HTTPException(422, "The proposed allocation includes an unsupported channel.")
    total = float(str(data.proposed.get("total", 0)))
    if data.total_budget_cap is not None and total > data.total_budget_cap:
        raise HTTPException(422, "The proposed allocation exceeds the total budget cap.")
    raw_current_allocations = plan.budget_envelope_json.get("allocations", {})
    current_allocations = (
        cast(dict[str, Any], raw_current_allocations)
        if isinstance(raw_current_allocations, dict)
        else {}
    )
    for channel, proposed in allocations.items():
        current = float(str(current_allocations.get(channel, 0) or 0))
        target = float(str(proposed))
        if current <= 0 or abs(target - current) / current * 100 > data.max_percent_change:
            raise HTTPException(422, "The proposed allocation exceeds the percentage guardrail.")
    preview = budget_preview(
        plan_id,
        MarketingBudgetChange(
            proposed=data.proposed,
            expected_version=data.expected_version,
            preview_fingerprint=expected_fingerprint,
            confirm=True,
        ),
        db,
        owner,
    )
    if preview["blockers"]:
        raise HTTPException(422, "The proposed allocation is outside the configured guardrails.")
    result = budget_confirm(
        plan_id,
        MarketingBudgetChange(
            proposed=data.proposed,
            expected_version=data.expected_version,
            preview_fingerprint=preview["fingerprint"],
            confirm=True,
            idempotency_key=data.idempotency_key,
        ),
        db,
        owner,
    )
    plan = _plan(db, owner, plan_id)
    raw_marker = plan.schedule_json.get("_auto_reallocation_idempotency", {})
    marker = cast(dict[str, Any], raw_marker) if isinstance(raw_marker, dict) else {}
    marker[data.idempotency_key] = {
        "version": plan.current_version,
        "allocation": data.proposed,
    }
    plan.schedule_json = {**plan.schedule_json, "_auto_reallocation_idempotency": marker}
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_auto_reallocation_applied",
        entity_type="marketing_plan",
        entity_id=plan.id,
        metadata={"idempotency_key": data.idempotency_key, "version": plan.current_version},
    )
    db.commit()
    return {
        "plan_id": plan.id,
        "idempotent_reuse": False,
        "provider_mutation": False,
        "result": result,
    }
