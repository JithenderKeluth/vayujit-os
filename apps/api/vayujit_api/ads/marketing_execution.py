# ruff: noqa: E501, E402, I001

"""Durable local execution records for cross-channel Marketing Plans.

This module deliberately materializes work only.  Provider calls remain in the
existing channel workers and connectors; the HTTP API never invokes them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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

from vayujit_api.ads.models import AdJob, AdsBase
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user


CHANNEL_STATES = {
    "planned",
    "blocked",
    "queued",
    "running",
    "retry_wait",
    "succeeded",
    "failed",
    "ambiguous",
    "recovered",
    "cancelled",
    "stale",
}
PLAN_STATES = {
    "planned",
    "blocked",
    "queued",
    "running",
    "succeeded",
    "partially_completed",
    "failed",
    "cancelled",
    "stale",
}


class MarketingPlanRevision(AdsBase):
    __tablename__ = "marketing_plan_revisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "plan_id", "version", name="uq_marketing_plan_revision"),
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_plans.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(80), default="confirmed")


class MarketingPlanExecution(AdsBase):
    __tablename__ = "marketing_plan_executions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_marketing_plan_execution_idempotency"
        ),
        CheckConstraint(
            "state IN ('planned','blocked','queued','running','succeeded','partially_completed','failed','cancelled','stale')",
            name="ck_marketing_plan_execution_state",
        ),
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_plans.id", ondelete="CASCADE"), index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketingChannelExecution(AdsBase):
    __tablename__ = "marketing_channel_executions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "execution_id", "channel", name="uq_marketing_channel_execution"
        ),
        CheckConstraint(
            "state IN ('planned','blocked','queued','running','retry_wait','succeeded','failed','ambiguous','recovered','cancelled','stale')",
            name="ck_marketing_channel_execution_state",
        ),
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_plan_executions.id", ondelete="CASCADE"),
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_plans.id", ondelete="CASCADE"), index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str | None] = mapped_column(String(32), index=True)
    state: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    dependency_state: Mapped[str] = mapped_column(String(32), default="ready")
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    downstream_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    creative_mapping_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_message: Mapped[str | None] = mapped_column(String(500))
    retryable: Mapped[bool] = mapped_column(default=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]
router = APIRouter(prefix="/api/v1/ads/marketing", tags=["marketing-automation-execution"])


class ExecutionRunRequest(BaseModel):
    confirm: bool = False
    outcomes: dict[
        str,
        Literal[
            "planned",
            "blocked",
            "queued",
            "running",
            "retry_wait",
            "succeeded",
            "failed",
            "ambiguous",
            "recovered",
            "cancelled",
            "stale",
        ],
    ] = Field(default_factory=dict)
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex)


class ExecutionActionRequest(BaseModel):
    action: Literal[
        "retry_channel", "retry_failed", "reconcile", "cancel_channel", "cancel_remaining"
    ]
    channel: str | None = None
    confirm: bool = False
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex)


def _now() -> datetime:
    return datetime.now(UTC)


def _state_from_channels(channels: list[MarketingChannelExecution]) -> str:
    """Derive plan state using deterministic precedence for mixed channels."""
    states = {item.state for item in channels}
    if not states:
        return "planned"
    if states <= {"succeeded", "recovered"}:
        return "succeeded"
    if states <= {"cancelled"}:
        return "cancelled"
    if states <= {"failed"}:
        return "failed"
    if states <= {"stale"}:
        return "stale"
    if states & {"queued", "running", "retry_wait"}:
        return "running"
    if states & {"succeeded", "recovered"}:
        return "partially_completed"
    if states <= {"blocked"}:
        return "blocked"
    if "blocked" in states:
        return "partially_completed"
    if "ambiguous" in states:
        return "failed"
    return "failed"


def _execution_response(
    db: Session, execution: MarketingPlanExecution, *, idempotent_reuse: bool = False
) -> dict[str, Any]:
    channels = list(
        db.scalars(
            select(MarketingChannelExecution)
            .where(MarketingChannelExecution.execution_id == execution.id)
            .order_by(MarketingChannelExecution.channel)
        )
    )
    return {
        "id": execution.id,
        "plan_id": execution.plan_id,
        "plan_version": execution.plan_version,
        "state": execution.state,
        "idempotency_key": execution.idempotency_key,
        "correlation_id": execution.correlation_id,
        "summary": execution.summary_json,
        "idempotent_reuse": idempotent_reuse,
        "channels": [
            {
                "id": item.id,
                "channel": item.channel,
                "provider": item.provider,
                "state": item.state,
                "dependency_state": item.dependency_state,
                "job_id": item.job_id,
                "schedule_id": item.schedule_id,
                "downstream": item.downstream_json,
                "downstream_type": item.downstream_json.get("type"),
                "downstream_entity_id": item.downstream_json.get("entity_id"),
                "downstream_job_id": item.downstream_json.get("job_id", item.job_id),
                "provider_remote_id": item.downstream_json.get("provider_remote_id"),
                "plan_version": item.plan_version,
                "product_ids": item.downstream_json.get("product_ids", []),
                "account_id": item.downstream_json.get("account_id"),
                "listing_id": item.downstream_json.get("listing_id"),
                "budget_version": item.downstream_json.get("budget_version"),
                "correlation_id": execution.correlation_id,
                "creative_mapping": item.creative_mapping_json,
                "failure_code": item.failure_code,
                "safe_message": item.safe_message,
                "retryable": item.retryable,
                "attempt_count": item.attempt_count,
            }
            for item in channels
        ],
    }


def materialize_plan(db: Session, owner: User, plan: Any) -> MarketingPlanExecution:
    """Create one immutable plan execution and one durable child per channel."""
    # Serialize concurrent confirmations for the same owner-scoped plan.
    db.refresh(plan, with_for_update=True)
    existing = db.scalar(
        select(MarketingPlanExecution).where(
            MarketingPlanExecution.owner_id == owner.id,
            MarketingPlanExecution.plan_id == plan.id,
            MarketingPlanExecution.plan_version == plan.current_version,
        )
    )
    if existing is not None:
        return existing
    stamp = _now()
    correlation_id = plan.correlation_id
    execution = MarketingPlanExecution(
        owner_id=owner.id,
        plan_id=plan.id,
        plan_version=plan.current_version,
        state="queued" if plan.status != "blocked" else "blocked",
        idempotency_key=f"marketing-plan-execution:{plan.id}:v{plan.current_version}",
        correlation_id=correlation_id,
        summary_json={"materialized": True, "provider_mutation": False},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(execution)
    db.flush()
    from vayujit_api.ads.marketing import MarketingPlanChannel

    target_channels = list(plan.target_channels_json or [])
    channel_rows = {
        row.channel: row
        for row in db.scalars(
            select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == plan.id)
        )
    }
    for channel in target_channels:
        name = str(channel)
        ready = plan.status != "blocked"
        row = channel_rows.get(name)
        job_id = uuid.uuid4()
        schedule_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"marketing-schedule:{plan.id}:{name}:v{plan.current_version}"
        )
        downstream_type = {
            "meta": "ads_job",
            "google": "ads_job",
            "amazon": "ads_job",
            "flipkart": "ads_job",
            "social": "publishing_job",
            "campaign": "campaign_activity",
        }.get(name, "marketing_channel_job")
        downstream_entity_id = f"{name}:{plan.id}:v{plan.current_version}"
        downstream = {
            "type": downstream_type,
            "entity_id": downstream_entity_id,
            "job_id": str(job_id),
            "schedule_id": str(schedule_id),
            "provider_mutated": False,
            "provider_remote_id": None,
            "product_ids": [str(item) for item in (plan.product_ids_json or [])],
            "creative_versions": (plan.creative_mapping_json or {}).get(name, {}),
            "account_id": str(row.account_id) if row and row.account_id else None,
            "listing_id": row.listing_id if row else None,
            "budget_version": plan.current_version,
            "correlation_id": correlation_id,
        }
        db.add(
            MarketingChannelExecution(
                owner_id=owner.id,
                execution_id=execution.id,
                plan_id=plan.id,
                plan_version=plan.current_version,
                channel=name,
                provider=name if name in {"meta", "google", "amazon", "flipkart"} else None,
                state="queued" if ready else "blocked",
                dependency_state="ready" if ready else "blocked",
                job_id=job_id,
                schedule_id=schedule_id,
                downstream_json=downstream,
                creative_mapping_json=(plan.creative_mapping_json or {}).get(name, {}),
                safe_message=None if ready else "The channel prerequisites are not ready.",
                retryable=False,
                attempt_count=0,
                idempotency_key=f"marketing-channel:{plan.id}:v{plan.current_version}:{name}",
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            AdJob(
                id=job_id,
                owner_id=owner.id,
                operation="marketing_plan_channel",
                entity_type=downstream_type,
                entity_id=plan.id,
                provider=name,
                status="queued" if ready else "blocked",
                attempt_count=0,
                max_attempts=3,
                idempotency_key=f"marketing-ad-job:{plan.id}:v{plan.current_version}:{name}",
                request_json={
                    "plan_id": str(plan.id),
                    "plan_version": plan.current_version,
                    "channel": name,
                    "channel_execution_id": None,
                    "schedule_id": str(schedule_id),
                    "correlation_id": correlation_id,
                },
                result_json=None,
                correlation_id=correlation_id,
                created_at=stamp,
                updated_at=stamp,
            )
        )
    db.flush()
    durable_rows = list(
        db.scalars(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.execution_id == execution.id
            )
        )
    )
    for durable in durable_rows:
        legacy = channel_rows.get(durable.channel)
        if legacy is not None:
            legacy.state = durable.state
            legacy.downstream_json = durable.downstream_json
            legacy.updated_at = stamp
        job = db.get(AdJob, durable.job_id)
        if job is not None:
            job.request_json = {**job.request_json, "channel_execution_id": str(durable.id)}
    return execution


def _owned_execution(db: Session, owner: User, execution_id: uuid.UUID) -> MarketingPlanExecution:
    execution = db.scalar(
        select(MarketingPlanExecution).where(
            MarketingPlanExecution.id == execution_id,
            MarketingPlanExecution.owner_id == owner.id,
        )
    )
    if execution is None:
        raise HTTPException(404, "Marketing Plan execution not found.")
    return execution


def _sync_plan_projection(
    db: Session, execution: MarketingPlanExecution, channels: list[MarketingChannelExecution]
) -> None:
    from vayujit_api.ads.marketing import MarketingPlan, MarketingPlanChannel

    plan = db.get(MarketingPlan, execution.plan_id)
    if plan is None:
        return
    canonical = {
        item.channel: item
        for item in db.scalars(
            select(MarketingPlanChannel).where(MarketingPlanChannel.plan_id == plan.id)
        )
    }
    for durable in channels:
        legacy = canonical.get(durable.channel)
        if legacy is None:
            continue
        legacy.state = durable.state
        legacy.failure_code = durable.failure_code
        legacy.safe_message = durable.safe_message
        legacy.downstream_json = durable.downstream_json
        legacy.updated_at = _now()
    plan.status = execution.state
    plan.updated_at = _now()


def _record_state_once(
    db: Session,
    execution: MarketingPlanExecution,
    owner: User,
    state: str,
    *,
    channel: str | None = None,
) -> None:
    from vayujit_api.audit.models import AuditEvent

    action = f"ads.marketing_plan_execution_{state}"
    existing = db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.actor_id == owner.id,
            AuditEvent.action == action,
            AuditEvent.entity_type == "marketing_plan_execution",
            AuditEvent.entity_id == execution.id,
        )
    )
    if existing is None:
        record_event(
            db,
            actor_id=owner.id,
            action=action,
            entity_type="marketing_plan_execution",
            entity_id=execution.id,
            metadata={"state": state, "channel": channel},
        )


def _record_completion_once(db: Session, execution: MarketingPlanExecution, owner: User) -> None:
    """Record one completion event for a durable execution.

    Workers can be retried after a lease loss.  The event is therefore
    guarded by the execution identity instead of the worker attempt.
    """
    existing = db.scalar(
        select(__import__("vayujit_api.audit.models", fromlist=["AuditEvent"]).AuditEvent.id).where(
            __import__("vayujit_api.audit.models", fromlist=["AuditEvent"]).AuditEvent.actor_id
            == owner.id,
            __import__("vayujit_api.audit.models", fromlist=["AuditEvent"]).AuditEvent.action
            == "ads.marketing_plan_execution_completed",
            __import__("vayujit_api.audit.models", fromlist=["AuditEvent"]).AuditEvent.entity_type
            == "marketing_plan_execution",
            __import__("vayujit_api.audit.models", fromlist=["AuditEvent"]).AuditEvent.entity_id
            == execution.id,
        )
    )
    if existing is None:
        record_event(
            db,
            actor_id=owner.id,
            action="ads.marketing_plan_execution_completed",
            entity_type="marketing_plan_execution",
            entity_id=execution.id,
            metadata={
                "state": execution.state,
                "channel_states": {
                    row.channel: row.state
                    for row in db.scalars(
                        select(MarketingChannelExecution).where(
                            MarketingChannelExecution.execution_id == execution.id
                        )
                    )
                },
            },
        )


def run_marketing_channel_job(
    db: Session, job: AdJob, *, worker_id: str = "marketing-worker"
) -> AdJob:
    """Execute one Marketing Plan channel through a deterministic local adapter.

    The worker owns all provider mutation.  HTTP endpoints only materialize
    jobs.  Provider checkpoints are persisted before the plan projection is
    updated, making retries and crash-after-provider-success safe.
    """
    channel = db.scalar(
        select(MarketingChannelExecution).where(MarketingChannelExecution.job_id == job.id)
    )
    if channel is None and job.operation in {
        "marketing_plan_budget",
        "marketing_plan_rollback",
        "marketing_plan_channel",
    }:
        raw_channel_id = job.request_json.get("channel_execution_id")
        if raw_channel_id:
            try:
                channel = db.get(MarketingChannelExecution, uuid.UUID(str(raw_channel_id)))
            except ValueError:
                channel = None
    if channel is None:
        job.status = "failed"
        job.failure_code = "marketing.channel_not_found"
        job.safe_failure_message = "The Marketing Plan channel could not be found safely."
        job.completed_at = _now()
        db.commit()
        return job
    execution = db.get(MarketingPlanExecution, channel.execution_id)
    if execution is None or execution.owner_id != job.owner_id:
        job.status = "failed"
        job.failure_code = "marketing.execution_not_found"
        job.safe_failure_message = "The Marketing Plan execution could not be found safely."
        job.completed_at = _now()
        db.commit()
        return job
    owner = db.get(User, job.owner_id)
    if owner is None:
        job.status = "failed"
        job.failure_code = "marketing.owner_not_found"
        job.safe_failure_message = "The Marketing Plan owner could not be found safely."
        job.completed_at = _now()
        db.commit()
        return job
    if (
        job.operation not in {"marketing_plan_rollback", "marketing_plan_budget"}
        and channel.state in {"succeeded", "recovered"}
        and channel.downstream_json.get("provider_remote_id")
    ):
        job.status = "succeeded"
        job.result_json = channel.downstream_json
        job.completed_at = job.completed_at or _now()
        db.commit()
        return job

    now = _now()
    expected_schedule = job.request_json.get("schedule_id")
    current_schedule = (channel.downstream_json or {}).get("schedule_id")
    if expected_schedule and current_schedule and str(expected_schedule) != str(current_schedule):
        channel.state = "stale"
        channel.failure_code = "marketing.stale_schedule"
        channel.safe_message = "The schedule is stale; refresh the current plan before execution."
        channel.retryable = False
        job.status = "failed"
        job.failure_code = channel.failure_code
        job.safe_failure_message = channel.safe_message
        job.completed_at = now
        db.commit()
        return job
    channel.state = "running"
    channel.attempt_count += 1
    channel.lease_owner = worker_id
    channel.lease_expires_at = now
    execution.state = "running"
    job.status = "running"
    job.attempt_count += 1
    job.lease_expires_at = now
    job.updated_at = now
    _record_state_once(db, execution, owner, "started", channel=channel.channel)
    db.commit()

    downstream = dict(channel.downstream_json or {})
    checkpoint = downstream.get("checkpoint")
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    try:
        remote: dict[str, object]
        remote_id = checkpoint.get("remote_id") or downstream.get("provider_remote_id")
        if job.operation in {
            "marketing_plan_budget",
            "marketing_plan_rollback",
        } and channel.channel in {"meta", "google", "amazon", "flipkart"}:
            from vayujit_api.ads.connectors import (
                AdsConnectorError,
                connector_for as ads_connector_for,
            )

            if not remote_id:
                raise AdsConnectorError(
                    "ads.remote_not_found",
                    "The remote Ads campaign could not be found safely.",
                )
            payload: dict[str, object] = {
                "budget": job.request_json.get("target_budget", job.request_json.get("budget")),
                "budget_version": job.request_json.get(
                    "target_version", job.request_json.get("plan_version")
                ),
            }
            if job.operation == "marketing_plan_rollback":
                payload.update(
                    {
                        "creative_mapping": job.request_json.get("target_creative_mapping", {}),
                        "schedule": job.request_json.get("target_schedule", {}),
                        "rollback": True,
                    }
                )
            remote = ads_connector_for(channel.channel).update_campaign(str(remote_id), payload)
        elif remote_id:
            remote = {"remote_id": str(remote_id), "reused_checkpoint": True}
        elif job.operation == "marketing_plan_budget":
            remote = {
                "remote_id": f"budget:{channel.plan_id}:v{channel.plan_version}:{channel.channel}",
                "budget_version": job.request_json.get("plan_version"),
            }
        elif channel.channel in {"meta", "google", "amazon", "flipkart"}:
            from vayujit_api.ads.connectors import connector_for as ads_connector_for

            payload = {
                "plan_id": str(channel.plan_id),
                "plan_version": channel.plan_version,
                "channel": channel.channel,
                "product_ids": downstream.get("product_ids", []),
                "creative_versions": downstream.get("creative_versions", {}),
                "budget_version": downstream.get("budget_version"),
                "correlation_id": execution.correlation_id,
                "listing_id": downstream.get("listing_id"),
            }
            remote = ads_connector_for(channel.channel).create_campaign(
                str(downstream.get("entity_id") or channel.id), payload
            )
        elif channel.channel == "social":
            from vayujit_api.social.connectors import connector_for as social_connector_for

            remote = social_connector_for("social", {"scenario": "success"}).publish_post(
                {"remote_account_id": str(downstream.get("account_id") or "local-social")},
                {
                    "plan_id": str(channel.plan_id),
                    "plan_version": channel.plan_version,
                    "product_ids": downstream.get("product_ids", []),
                    "creative_versions": downstream.get("creative_versions", {}),
                },
                channel.idempotency_key,
            )
            remote = {"remote_id": str(remote["remote_publication_id"]), **remote}
        else:
            # Campaign Activity is an existing local durable dependency.  The
            # local identity is deterministic and does not expose campaign data.
            remote = {
                "remote_id": f"campaign-activity:{channel.plan_id}:v{channel.plan_version}",
                "status": "succeeded",
            }
        provider_remote_id = str(remote.get("remote_id") or remote.get("remote_publication_id"))
        checkpoint = {
            "remote_id": provider_remote_id,
            "state": "succeeded",
            "provider": channel.channel,
            "worker_id": worker_id,
        }
        downstream.update(
            {
                "provider_mutated": True,
                "provider_remote_id": provider_remote_id,
                "rollback_provider_mutated": job.operation == "marketing_plan_rollback",
                "budget_version": job.request_json.get(
                    "target_version", downstream.get("budget_version")
                ),
                "checkpoint": checkpoint,
                "execution_id": str(channel.id),
                "job_id": str(job.id),
                "correlation_id": execution.correlation_id,
            }
        )
        channel.downstream_json = downstream
        # Persist the provider checkpoint before finalizing local state. If the
        # process crashes after the provider call, the next lease reuses it.
        db.flush()
        db.commit()
        budget_only = job.operation == "marketing_plan_budget"
        rollback_only = job.operation == "marketing_plan_rollback"
        if not budget_only or rollback_only:
            channel.state = "succeeded"
        channel.dependency_state = "ready"
        channel.failure_code = None
        channel.safe_message = None
        channel.retryable = False
        channel.lease_expires_at = None
        job.status = "succeeded"
        job.result_json = downstream
        job.failure_code = None
        job.safe_failure_message = None
        job.lease_expires_at = None
        job.completed_at = now
        _sync_plan_projection(
            db,
            execution,
            list(
                db.scalars(
                    select(MarketingChannelExecution).where(
                        MarketingChannelExecution.execution_id == execution.id
                    )
                )
            ),
        )
        execution.state = _state_from_channels(
            list(
                db.scalars(
                    select(MarketingChannelExecution).where(
                        MarketingChannelExecution.execution_id == execution.id
                    )
                )
            )
        )
        if execution.state in {"succeeded", "partially_completed", "failed", "cancelled"}:
            execution.completed_at = now
        if not budget_only or rollback_only:
            _record_state_once(db, execution, owner, "completed", channel=channel.channel)
            _record_completion_once(db, execution, owner)
        db.commit()
        return job
    except Exception as error:
        from vayujit_api.ads.connectors import AdsConnectorError

        if isinstance(error, AdsConnectorError):
            if error.ambiguous:
                channel.state = "ambiguous"
                channel.failure_code = error.code
                channel.safe_message = error.safe_message
                channel.retryable = False
            elif error.retryable:
                channel.state = "retry_wait"
                channel.failure_code = error.code
                channel.safe_message = error.safe_message
                channel.retryable = True
            else:
                channel.state = "failed"
                channel.failure_code = error.code
                channel.safe_message = error.safe_message
                channel.retryable = False
            job.failure_code = error.code
            job.safe_failure_message = error.safe_message
            job.retry_after_seconds = error.retry_after_seconds
        else:
            channel.state = "failed"
            channel.failure_code = "marketing.worker_error"
            channel.safe_message = "The local Marketing Plan worker failed safely."
            channel.retryable = False
            job.failure_code = "marketing.worker_error"
            job.safe_failure_message = channel.safe_message
        channel.lease_expires_at = None
        job.lease_expires_at = None
        job.status = "retry_wait" if channel.state == "retry_wait" else "failed"
        _sync_plan_projection(
            db,
            execution,
            list(
                db.scalars(
                    select(MarketingChannelExecution).where(
                        MarketingChannelExecution.execution_id == execution.id
                    )
                )
            ),
        )
        execution.state = _state_from_channels(
            list(
                db.scalars(
                    select(MarketingChannelExecution).where(
                        MarketingChannelExecution.execution_id == execution.id
                    )
                )
            )
        )
        execution.updated_at = _now()
        _record_state_once(db, execution, owner, channel.state, channel=channel.channel)
        if execution.state in {"succeeded", "partially_completed", "failed", "cancelled"}:
            _record_completion_once(db, execution, owner)
        db.commit()
        return job


@router.post("/plans/{plan_id}/materialize")
def materialize_endpoint(plan_id: uuid.UUID, confirm: bool, db: DB, owner: Owner) -> dict[str, Any]:
    from vayujit_api.ads.marketing import _plan

    if not confirm:
        raise HTTPException(422, "Explicit confirmation is required before materialization.")
    plan = _plan(db, owner, plan_id)
    execution = materialize_plan(db, owner, plan)
    plan.status = execution.state
    plan.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketing_plan_materialized",
        entity_type="marketing_plan",
        entity_id=plan.id,
        metadata={"execution_id": str(execution.id), "plan_version": execution.plan_version},
    )
    db.commit()
    return _execution_response(db, execution)


@router.get("/plans/{plan_id}/execution")
def latest_execution(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    from vayujit_api.ads.marketing import _plan

    plan = _plan(db, owner, plan_id)
    execution = db.scalar(
        select(MarketingPlanExecution)
        .where(MarketingPlanExecution.plan_id == plan.id)
        .order_by(MarketingPlanExecution.created_at.desc())
    )
    if execution is None:
        raise HTTPException(404, "Marketing Plan execution not found.")
    return _execution_response(db, execution)


@router.get("/plans/{plan_id}/revisions")
def plan_revisions(plan_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, Any]]:
    from vayujit_api.ads.marketing import _plan

    plan = _plan(db, owner, plan_id)
    values = list(
        db.scalars(
            select(MarketingPlanRevision)
            .where(
                MarketingPlanRevision.plan_id == plan.id,
                MarketingPlanRevision.owner_id == owner.id,
            )
            .order_by(MarketingPlanRevision.version)
        )
    )
    return [
        {
            "version": item.version,
            "fingerprint": item.fingerprint,
            "reason": item.reason,
            "snapshot": item.snapshot_json,
            "created_at": item.created_at,
        }
        for item in values
    ]


@router.post("/executions/{execution_id}/run")
def run_execution(
    execution_id: uuid.UUID, data: ExecutionRunRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before running execution work.")
    execution = _owned_execution(db, owner, execution_id)
    db.refresh(execution, with_for_update=True)
    channels = list(
        db.scalars(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.execution_id == execution.id
            )
        )
    )
    seen_runs = cast(
        dict[str, dict[str, object]], execution.summary_json.get("run_idempotency", {})
    )
    if data.idempotency_key in seen_runs:
        return _execution_response(db, execution, idempotent_reuse=True)
    execution.state = "running"
    execution.started_at = execution.started_at or _now()
    for channel in channels:
        target = data.outcomes.get(channel.channel, "succeeded")
        if channel.state == "blocked" and channel.channel not in data.outcomes:
            target = "blocked"
        if channel.state == "cancelled":
            continue
        channel.state = target
        channel.attempt_count += 1
        job = db.get(AdJob, channel.job_id)
        if job is not None:
            job.status = {
                "queued": "queued",
                "running": "running",
                "retry_wait": "retry_wait",
                "succeeded": "succeeded",
                "failed": "failed",
                "ambiguous": "failed",
                "cancelled": "cancelled",
                "blocked": "blocked",
                "stale": "failed",
                "recovered": "succeeded",
            }.get(target, "queued")
        channel.retryable = target in {"retry_wait", "failed", "ambiguous"}
        channel.downstream_json = {
            **channel.downstream_json,
            "provider_mutated": False,
            "checkpoint": "local_only",
            "provider_remote_id": (
                f"local:{channel.channel}:{channel.job_id}"
                if target in {"succeeded", "recovered"}
                else channel.downstream_json.get("provider_remote_id")
            ),
        }
        if target == "blocked":
            channel.dependency_state = "blocked"
            channel.safe_message = "A prerequisite is not ready; no provider mutation occurred."
        elif target == "ambiguous":
            channel.failure_code = "remote_result_ambiguous"
            channel.safe_message = "The remote result is ambiguous; reconciliation is required."
        elif target == "failed":
            channel.failure_code = "channel_execution_failed"
            channel.safe_message = "The channel execution failed safely."
        else:
            channel.failure_code = None
            channel.safe_message = None
    execution.state = _state_from_channels(channels)
    _sync_plan_projection(db, execution, channels)
    seen_runs[data.idempotency_key] = {"state": execution.state}
    execution.summary_json = {
        "channel_count": len(channels),
        "states": {item.channel: item.state for item in channels},
        "provider_mutation": False,
        "run_idempotency": dict(list(seen_runs.items())[-100:]),
        "action_idempotency": execution.summary_json.get("action_idempotency", {}),
    }
    if execution.state in {"succeeded", "partially_completed", "failed", "cancelled"}:
        execution.completed_at = _now()
    execution.updated_at = _now()
    _record_completion_once(db, execution, owner)
    db.commit()
    return _execution_response(db, execution)


@router.post("/executions/{execution_id}/actions")
def execution_action(
    execution_id: uuid.UUID, data: ExecutionActionRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required for this execution action.")
    execution = _owned_execution(db, owner, execution_id)
    db.refresh(execution, with_for_update=True)
    channels = list(
        db.scalars(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.execution_id == execution.id
            )
        )
    )
    seen_actions = cast(dict[str, object], execution.summary_json.get("action_idempotency", {}))
    if data.idempotency_key in seen_actions:
        return _execution_response(db, execution, idempotent_reuse=True)
    selected = [item for item in channels if data.channel is None or item.channel == data.channel]
    for channel in selected:
        if data.action in {"retry_channel", "retry_failed"} and channel.state in {
            "failed",
            "retry_wait",
            "ambiguous",
            "blocked",
        }:
            channel.state = "queued"
            channel.retryable = False
            channel.failure_code = None
            channel.safe_message = None
            job = db.get(AdJob, channel.job_id)
            if job is not None:
                job.status = "queued"
        elif data.action == "reconcile" and channel.state == "ambiguous":
            channel.state = "recovered"
            channel.retryable = False
            job = db.get(AdJob, channel.job_id)
            if job is not None:
                job.status = "succeeded"
        elif data.action in {"cancel_channel", "cancel_remaining"} and channel.state not in {
            "succeeded",
            "recovered",
            "cancelled",
        }:
            channel.state = "cancelled"
            job = db.get(AdJob, channel.job_id)
            if job is not None:
                job.status = "cancelled"
        elif data.action not in {
            "review_creative",
            "review_budget",
            "review_account",
            "review_listing",
            "review_dependency",
        }:
            if data.action not in {
                "retry_channel",
                "retry_failed",
                "reconcile",
                "cancel_channel",
                "cancel_remaining",
            }:
                raise HTTPException(422, "The requested execution action is not executable.")
    execution.state = _state_from_channels(channels)
    _sync_plan_projection(db, execution, channels)
    seen_actions[data.idempotency_key] = {"action": data.action, "channel": data.channel}
    execution.summary_json = {
        **execution.summary_json,
        "action_idempotency": dict(list(seen_actions.items())[-100:]),
    }
    execution.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action=f"ads.marketing_plan_execution_{data.action}",
        entity_type="marketing_plan_execution",
        entity_id=execution.id,
        metadata={"channel": data.channel, "idempotency_key": data.idempotency_key},
    )
    db.commit()
    return _execution_response(db, execution)


@router.get("/plans/{plan_id}/recovery")
def execution_recovery(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    from vayujit_api.ads.marketing import _plan

    plan = _plan(db, owner, plan_id)
    execution = db.scalar(
        select(MarketingPlanExecution)
        .where(MarketingPlanExecution.plan_id == plan.id)
        .order_by(MarketingPlanExecution.created_at.desc())
    )
    if execution is None:
        return {"plan_id": plan.id, "channels": [], "actions": []}
    channels = list(
        db.scalars(
            select(MarketingChannelExecution).where(
                MarketingChannelExecution.execution_id == execution.id
            )
        )
    )
    rows = []
    for item in channels:
        actions: list[str] = []
        if item.state in {"failed", "retry_wait", "blocked"}:
            actions.append("retry_channel")
        if item.state == "ambiguous":
            actions.append("reconcile")
        if item.state not in {"succeeded", "recovered", "cancelled"}:
            actions.append("cancel_channel")
        rows.append(
            {
                "channel": item.channel,
                "provider": item.provider,
                "state": item.state,
                "job_id": item.job_id,
                "failure_code": item.failure_code,
                "safe_message": item.safe_message,
                "retryable": item.retryable,
                "actions": actions,
                "correlation_id": execution.correlation_id,
            }
        )
    return {
        "plan_id": plan.id,
        "execution_id": execution.id,
        "state": execution.state,
        "channels": rows,
        "actions": sorted(
            {
                *(action for item in rows for action in cast(list[str], item["actions"])),
                "retry_failed",
                "cancel_remaining",
                "review_creative",
                "review_budget",
                "review_account",
                "review_listing",
                "review_dependency",
            }
        ),
    }
