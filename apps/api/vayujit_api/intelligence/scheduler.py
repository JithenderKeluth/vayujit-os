# ruff: noqa: E501
"""Durable local mission scheduler helpers."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import (
    IntelligenceResearchMission,
    IntelligenceResearchRun,
    IntelligenceResearchSchedule,
)
from vayujit_api.intelligence.research_engine import run_mission
from vayujit_api.intelligence.service import now


def next_occurrence(value: datetime, frequency: str) -> datetime | None:
    normalized = frequency.strip().lower()
    if normalized in {"hourly", "every_hour"}:
        return value + timedelta(hours=1)
    if normalized in {"daily", "every_day"}:
        return value + timedelta(days=1)
    if normalized in {"weekly", "every_week"}:
        return value + timedelta(days=7)
    if normalized in {"monthly", "every_month"}:
        return value + timedelta(days=30)
    return None


def materialize_due_missions(
    db: Session, user: User, *, at: datetime | None = None, limit: int = 10
) -> list[IntelligenceResearchRun]:
    due = at or datetime.now(UTC)
    missions = list(
        db.scalars(
            select(IntelligenceResearchMission)
            .where(
                IntelligenceResearchMission.owner_id == user.id,
                IntelligenceResearchMission.enabled.is_(True),
                IntelligenceResearchMission.status == "active",
                IntelligenceResearchMission.next_run_at.is_not(None),
                IntelligenceResearchMission.next_run_at <= due,
            )
            .order_by(IntelligenceResearchMission.next_run_at)
            .limit(limit)
        )
    )
    runs = []
    for mission in missions:
        scheduled_for = mission.next_run_at
        if scheduled_for is None:
            continue
        existing = db.scalar(
            select(IntelligenceResearchSchedule).where(
                IntelligenceResearchSchedule.owner_id == user.id,
                IntelligenceResearchSchedule.mission_id == mission.id,
                IntelligenceResearchSchedule.scheduled_for == scheduled_for,
            )
        )
        if existing and existing.run_id:
            continue
        if not existing:
            existing = IntelligenceResearchSchedule(
                owner_id=user.id,
                mission_id=mission.id,
                scheduled_for=scheduled_for,
                timezone=mission.timezone,
                frequency=mission.frequency,
                status="materializing",
                created_at=now(),
            )
            db.add(existing)
            db.flush()
        run = run_mission(
            db, user, mission, idempotency_key=f"schedule:{mission.id}:{scheduled_for.isoformat()}"
        )
        existing.run_id = run.id
        existing.status = "materialized"
        mission.next_run_at = next_occurrence(scheduled_for, mission.frequency)
        db.commit()
        runs.append(run)
    return runs
