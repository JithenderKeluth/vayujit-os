# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceResearchRun
from vayujit_api.intelligence.research_engine import execute_research_run


@dataclass(frozen=True)
class WorkerResult:
    run_id: str
    status: str
    attempts: int


def run_pending_once(db: Session, user: User, *, limit: int = 10) -> list[WorkerResult]:
    runs = list(
        db.query(IntelligenceResearchRun)
        .filter(
            IntelligenceResearchRun.owner_id == user.id,
            IntelligenceResearchRun.status.in_(["pending", "running", "waiting", "stale"]),
        )
        .order_by(IntelligenceResearchRun.created_at)
        .limit(limit)
    )
    output: list[WorkerResult] = []
    for run in runs:
        try:
            run.status = "claimed"
            db.flush()
            execute_research_run(db, user, run)
            output.append(WorkerResult(str(run.id), "completed", 1))
        except Exception:
            run.status = "retry_wait"
            db.commit()
            output.append(WorkerResult(str(run.id), "retry_wait", 1))
    return output
