# ruff: noqa
"""Owner-scoped durable entities for Business Agent orchestration (Slice 9G)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def agent_now() -> datetime:
    return datetime.now(UTC)


class BusinessAgentGoal(Base):
    __tablename__ = "intelligence_business_agent_goals"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_agent_goal_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    raw_goal: Mapped[str] = mapped_column(Text)
    structured_goal: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    assumptions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    unresolved_questions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    extraction_version: Mapped[str] = mapped_column(String(40), default="business-goal-v1")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agent_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentPlan(Base):
    __tablename__ = "intelligence_business_agent_plans"
    __table_args__ = (UniqueConstraint("goal_id", "version", name="uq_agent_plan_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    planner: Mapped[str] = mapped_column(String(64), default="deterministic-local")
    plan_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agent_now, index=True
    )


class BusinessAgentStep(Base):
    __tablename__ = "intelligence_business_agent_steps"
    __table_args__ = (UniqueConstraint("plan_id", "step_key", name="uq_agent_step_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_plans.id", ondelete="CASCADE"),
        index=True,
    )
    step_key: Mapped[str] = mapped_column(String(100))
    capability_id: Mapped[str] = mapped_column(String(120), index=True)
    dependency_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)
    input_contract: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    output_contract: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    execution_mode: Mapped[str] = mapped_column(String(32), default="LOCAL_READ_ONLY")
    side_effect_class: Mapped[str] = mapped_column(String(32), default="NONE")
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentRun(Base):
    __tablename__ = "intelligence_business_agent_runs"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_agent_run_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="CASCADE"),
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_plans.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    budget: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    usage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    checkpoint: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agent_now, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentAttempt(Base):
    __tablename__ = "intelligence_business_agent_attempts"
    __table_args__ = (
        UniqueConstraint("owner_id", "step_id", "attempt_number", name="uq_agent_attempt"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_steps.id", ondelete="CASCADE"),
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BusinessAgentApproval(Base):
    __tablename__ = "intelligence_business_agent_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    reason: Mapped[str] = mapped_column(String(500))
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentArtifact(Base):
    __tablename__ = "intelligence_business_agent_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentFinding(Base):
    __tablename__ = "intelligence_business_agent_findings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    finding_type: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentToolInvocation(Base):
    __tablename__ = "intelligence_business_agent_tool_invocations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_steps.id", ondelete="CASCADE"),
        index=True,
    )
    capability_id: Mapped[str] = mapped_column(String(120))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="SUCCEEDED")
    side_effect_class: Mapped[str] = mapped_column(String(32), default="NONE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)


class BusinessAgentCheckpoint(Base):
    __tablename__ = "intelligence_business_agent_checkpoints"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    step_key: Mapped[str] = mapped_column(String(100))
    state: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agent_now)
