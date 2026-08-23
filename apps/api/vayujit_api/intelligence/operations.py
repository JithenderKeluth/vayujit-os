from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.models import (
    IntelligenceEvidence,
    IntelligenceResearchRun,
    IntelligenceSource,
)

router = APIRouter(prefix="/api/v1/operations/intelligence", tags=["operations-intelligence"])
diagnostics_router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/projection")
def projection(db: DB, owner: Owner) -> dict[str, object]:
    settings = get_settings()
    return {
        "enabled": settings.intelligence_enabled,
        "research_execution_enabled": settings.intelligence_research_execution_enabled,
        "external_research_enabled": settings.intelligence_external_research_enabled,
        "workers": {"registered": False, "status": "foundation_only"},
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
        "external_calls": "disabled_by_default",
    }


@diagnostics_router.get("/system-doctor")
def system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    settings = get_settings()
    value = projection(db, owner)
    return {
        "status": "healthy" if settings.intelligence_enabled else "disabled",
        "checks": {
            "database_readiness": "ready",
            "worker_registration": value["workers"],
            "source_registry": {
                "enabled": value["enabled_sources"],
                "external_calls": value["external_calls"],
            },
            "unsafe_configuration": {
                "external_research_disabled": not settings.intelligence_external_research_enabled,
            },
            "freshness_backlog": value["freshness_backlog"],
            "evidence_storage": "ready",
        },
    }
