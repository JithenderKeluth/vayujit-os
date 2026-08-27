"""Bounded durable worker for autonomous research missions."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from sqlalchemy import select

from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission
from vayujit_api.intelligence.autonomous_service import execute_mission
from vayujit_api.intelligence.service import now

logger = logging.getLogger(__name__)


def run_pending_once(limit: int = 10) -> int:
    """Execute a bounded batch of queued autonomous missions."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    completed = 0
    with SessionFactory() as db:
        missions = list(
            db.scalars(
                select(AutonomousResearchMission)
                .where(AutonomousResearchMission.status.in_(["QUEUED", "RUNNING", "RETRY_WAIT"]))
                .order_by(AutonomousResearchMission.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for mission in missions:
            owner = db.get(User, mission.owner_id)
            if owner is None:
                mission.status = "FAILED"
                db.commit()
                continue
            try:
                execute_mission(db, owner, mission)
                completed += 1
            except Exception:
                db.rollback()
                failed = db.get(AutonomousResearchMission, mission.id)
                if failed is not None:
                    failed.status = "FAILED"
                    failed.updated_at = now()
                    db.commit()
                logger.exception("Autonomous mission failed", extra={"mission_id": str(mission.id)})
    return completed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded autonomous research missions.")
    parser.add_argument("command", choices=["once"], nargs="?", default="once")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if args.command == "once":
        print(run_pending_once(args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
