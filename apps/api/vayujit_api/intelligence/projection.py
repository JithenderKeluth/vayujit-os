# ruff: noqa: E501
"""Bounded Intelligence projection consumed by Operations, with ORM access isolated here."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import (
    IntelligenceEvidence,
    IntelligenceResearchRun,
    IntelligenceSource,
)


def get_operations_projection(db: Session, owner: User) -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.intelligence_enabled,
        "research_execution_enabled": settings.intelligence_research_execution_enabled,
        "external_research_enabled": settings.intelligence_external_research_enabled,
        "workers": {"registered": True, "status": "local_deterministic_worker"},
        "scheduler": {"registered": True, "status": "local_deterministic_scheduler"},
        "pending_research_runs": int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceResearchRun)
                .where(
                    IntelligenceResearchRun.owner_id == owner.id,
                    IntelligenceResearchRun.status.in_(["pending", "running", "waiting"]),
                )
            )
            or 0
        ),
        "failed_research_runs": int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceResearchRun)
                .where(
                    IntelligenceResearchRun.owner_id == owner.id,
                    IntelligenceResearchRun.status == "failed",
                )
            )
            or 0
        ),
        "enabled_sources": int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceSource)
                .where(
                    IntelligenceSource.owner_id == owner.id, IntelligenceSource.enabled.is_(True)
                )
            )
            or 0
        ),
        "freshness_backlog": int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceEvidence)
                .where(
                    IntelligenceEvidence.owner_id == owner.id,
                    IntelligenceEvidence.freshness_status.in_(["stale", "expired"]),
                )
            )
            or 0
        ),
        "recovery_counts": {
            "failed_runs": int(
                db.scalar(
                    select(func.count())
                    .select_from(IntelligenceResearchRun)
                    .where(
                        IntelligenceResearchRun.owner_id == owner.id,
                        IntelligenceResearchRun.status == "failed",
                    )
                )
                or 0
            )
        },
        "external_calls": "disabled_by_default",
    }
