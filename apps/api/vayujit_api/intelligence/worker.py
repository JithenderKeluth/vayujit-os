from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from sqlalchemy import select

from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceResearchRun
from vayujit_api.intelligence.research_engine import execute_research_run

logger = logging.getLogger(__name__)


def run_pending_once(limit: int = 10) -> int:
    """Execute a bounded batch of owner-scoped local research runs."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    completed = 0
    with SessionFactory() as db:
        runs = list(
            db.scalars(
                select(IntelligenceResearchRun)
                .where(IntelligenceResearchRun.status.in_(["pending", "running"]))
                .order_by(IntelligenceResearchRun.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for run in runs:
            owner = db.get(User, run.owner_id)
            if owner is None:
                run.status = "failed"
                run.failure_classification = "owner_missing"
                db.commit()
                continue
            try:
                execute_research_run(db, owner, run)
                completed += 1
            except Exception:
                db.rollback()
                failed = db.get(IntelligenceResearchRun, run.id)
                if failed is not None:
                    failed.status = "failed"
                    failed.failure_classification = "local_worker_failure"
                    db.commit()
                logger.exception("Intelligence research run failed", extra={"run_id": str(run.id)})
    return completed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded local Intelligence research work.")
    parser.add_argument("command", choices=["once"], nargs="?", default="once")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if args.command == "once":
        print(run_pending_once(args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
