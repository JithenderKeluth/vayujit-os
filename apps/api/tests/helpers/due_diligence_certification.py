"""Test-only infrastructure for Due Diligence certification.

This module deliberately contains no production behavior. It provides one
checkpoint controller and one two-session PostgreSQL barrier so certification
scenarios use the same synchronization and cleanup semantics.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Barrier
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.identity.models import User

CHECKPOINTS = (
    "DD_BEFORE_PLAN_DISPATCH",
    "DD_AFTER_PLAN_PERSIST",
    "DD_BEFORE_SOURCE",
    "DD_AFTER_EXECUTION",
    "DD_AFTER_EVIDENCE",
    "DD_AFTER_REASSESSMENT",
)

PRODUCTION_NATIVE_CRASH_HOOKS = ("DD_BEFORE_SOURCE", "DD_AFTER_EVIDENCE")

T = TypeVar("T")


class DueDiligenceCheckpointTriggered(RuntimeError):
    """Deterministic test-only interruption at a durable orchestration boundary."""

    def __init__(self, checkpoint: str) -> None:
        super().__init__(f"test checkpoint triggered: {checkpoint}")
        self.checkpoint = checkpoint


@dataclass
class DueDiligenceCheckpointController:
    """Arms one checkpoint and records each checkpoint hit exactly once."""

    armed: str | None = None
    hits: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.armed is not None and self.armed not in CHECKPOINTS:
            raise ValueError(f"Unknown Due Diligence checkpoint: {self.armed}")

    def hit(self, checkpoint: str) -> None:
        if checkpoint not in CHECKPOINTS:
            raise ValueError(f"Unknown Due Diligence checkpoint: {checkpoint}")
        self.hits.append(checkpoint)
        if checkpoint == self.armed:
            raise DueDiligenceCheckpointTriggered(checkpoint)


@dataclass(frozen=True)
class SessionResult[T]:
    worker: int
    value: T | None = None
    exception: str | None = None


def run_two_postgres_sessions[T](
    factory: sessionmaker[Session],
    operation: Callable[[Session, User, int], T],
    *,
    owner_email: str = "owner@example.com",
    timeout_seconds: float = 30.0,
) -> list[SessionResult[T]]:
    """Run one operation from two independent PostgreSQL sessions.

    Both sessions resolve the owner and wait at the same barrier before the
    operation begins. Each transaction is committed on success, rolled back on
    error, and closed in a finally block. This is the only shared concurrency
    harness used by Due Diligence certification.
    """

    barrier = Barrier(2)

    def worker(index: int) -> SessionResult[T]:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == owner_email))
            if owner is None:
                return SessionResult(worker=index, exception="owner_not_found")
            try:
                barrier.wait(timeout=timeout_seconds)
                value = operation(db, owner, index)
                if db.in_transaction():
                    db.commit()
                return SessionResult(worker=index, value=value)
            except Exception as exc:  # test harness captures race outcomes
                db.rollback()
                return SessionResult(
                    worker=index,
                    exception=f"{type(exc).__name__}: {exc}",
                )
            finally:
                db.close()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="dd-cert") as pool:
        results = list(pool.map(worker, (0, 1)))
    return sorted(results, key=lambda result: result.worker)


def run_checkpointed_workflow(
    callbacks: dict[str, Callable[[], Any]], controller: DueDiligenceCheckpointController
) -> list[str]:
    """Execute named orchestration callbacks through the test-only checkpoints."""

    for checkpoint in CHECKPOINTS:
        controller.hit(checkpoint)
        callback = callbacks.get(checkpoint)
        if callback is not None:
            callback()
    return list(controller.hits)


def snapshot_replay_ledger(db: Session, owner_id: object, context_id: object) -> dict[str, int]:
    """Read-only entity count snapshot for one due-diligence context."""
    from sqlalchemy import func

    from vayujit_api.audit.models import AuditEvent
    from vayujit_api.intelligence.autonomous_models import (
        AutonomousResearchAttempt,
        AutonomousResearchClaim,
        AutonomousResearchEvidence,
        AutonomousResearchMission,
        AutonomousResearchRecovery,
        AutonomousResearchTask,
    )
    from vayujit_api.intelligence.due_diligence_models import (
        SupplierDueDiligenceAssessment,
        SupplierDueDiligenceContext,
        SupplierEvidenceGap,
        SupplierResearchPlan,
        SupplierResearchTask,
    )
    from vayujit_api.intelligence.website_models import WebsiteObservation

    context = db.get(SupplierDueDiligenceContext, context_id)
    scoped_ids = (
        {context_id} if context is not None and context.owner_id == owner_id else {context_id}
    )
    assessments = list(
        db.scalars(
            select(SupplierDueDiligenceAssessment).where(
                SupplierDueDiligenceAssessment.owner_id == owner_id,
                SupplierDueDiligenceAssessment.context_id.in_(scoped_ids),
            )
        )
    )
    gaps = list(
        db.scalars(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.owner_id == owner_id,
                SupplierEvidenceGap.context_id.in_(scoped_ids),
            )
        )
    )
    plans = list(
        db.scalars(
            select(SupplierResearchPlan).where(
                SupplierResearchPlan.owner_id == owner_id,
                SupplierResearchPlan.context_id.in_(scoped_ids),
            )
        )
    )
    due_tasks = list(
        db.scalars(
            select(SupplierResearchTask)
            .join(SupplierResearchPlan, SupplierResearchPlan.id == SupplierResearchTask.plan_id)
            .where(
                SupplierResearchTask.owner_id == owner_id,
                SupplierResearchPlan.context_id.in_(scoped_ids),
            )
        )
    )
    missions = [
        mission
        for mission in db.scalars(
            select(AutonomousResearchMission).where(AutonomousResearchMission.owner_id == owner_id)
        )
        if mission.scope.get("due_diligence_context_id") == str(context_id)
    ]
    mission_ids = {mission.id for mission in missions}
    shared_tasks = list(
        db.scalars(
            select(AutonomousResearchTask).where(
                AutonomousResearchTask.owner_id == owner_id,
                AutonomousResearchTask.mission_id.in_(mission_ids or scoped_ids),
            )
        )
    )
    task_ids = {task.id for task in shared_tasks}
    evidence = list(
        db.scalars(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner_id,
                AutonomousResearchEvidence.mission_id.in_(mission_ids or scoped_ids),
            )
        )
    )
    attempts = list(
        db.scalars(
            select(AutonomousResearchAttempt).where(
                AutonomousResearchAttempt.owner_id == owner_id,
                AutonomousResearchAttempt.task_id.in_(task_ids or scoped_ids),
            )
        )
    )
    claims = list(
        db.scalars(
            select(AutonomousResearchClaim).where(
                AutonomousResearchClaim.owner_id == owner_id,
                AutonomousResearchClaim.mission_id.in_(mission_ids or scoped_ids),
            )
        )
    )
    observations = list(
        db.scalars(
            select(WebsiteObservation).where(
                WebsiteObservation.owner_id == owner_id,
                WebsiteObservation.correlation_id == f"due-diligence:{context_id}",
            )
        )
    )
    recoveries = list(
        db.scalars(
            select(AutonomousResearchRecovery).where(
                AutonomousResearchRecovery.owner_id == owner_id,
                AutonomousResearchRecovery.mission_id.in_(mission_ids or scoped_ids),
            )
        )
    )
    human_actions = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.actor_id == owner_id,
                AuditEvent.entity_type == "supplier_evidence_gap",
                AuditEvent.entity_id.in_([gap.id for gap in gaps] or list(scoped_ids)),
            )
        )
    )
    risk_history = sum(
        isinstance(item.summary, dict) and isinstance(item.summary.get("risk_recomputation"), dict)
        for item in assessments
    )
    return {
        "contexts": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierDueDiligenceContext)
                .where(
                    SupplierDueDiligenceContext.owner_id == owner_id,
                    SupplierDueDiligenceContext.id.in_(scoped_ids),
                )
            )
            or 0
        ),
        "assessments": len(assessments),
        "gaps": len(gaps),
        "gap_versions": len({gap.assessment_version for gap in gaps}),
        "research_plans": len(plans),
        "research_tasks": len(due_tasks),
        "autonomous_missions": len(missions),
        "executions": len(attempts),
        "evidence": len(evidence),
        "claims": len(claims),
        "verification_references": sum(bool(item.verification_status) for item in evidence),
        "observations": len(observations),
        "risk_references_history": risk_history,
        "human_actions": len(human_actions),
        "waivers": sum(gap.status == "WAIVED_BY_HUMAN" for gap in gaps),
        "product_channel_projection_records": 0,
        "calendar_events": 0,
        "recovery_records_references": len(recoveries),
    }


def assert_replay_ledger_unchanged(
    before: dict[str, int], after: dict[str, int], *, allowed_deltas: set[str] | None = None
) -> None:
    """Assert a replay did not duplicate current-state entities."""
    allowed = allowed_deltas or set()
    for key, value in before.items():
        if key in allowed:
            assert after[key] >= value, (key, before, after)
        else:
            assert after[key] == value, (key, before, after)
