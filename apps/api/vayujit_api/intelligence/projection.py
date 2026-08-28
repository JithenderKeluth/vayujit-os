# ruff: noqa: E501
"""Bounded Intelligence projection consumed by Operations, with ORM access isolated here."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchContradiction,
)
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalProviderState,
    ExternalRecoveryAction,
    ExternalResearchBudget,
)
from vayujit_api.intelligence.external_projection import integrity_projection
from vayujit_api.intelligence.models import (
    IntelligenceEvidence,
    IntelligenceResearchRun,
    IntelligenceSource,
)


def get_operations_projection(db: Session, owner: User) -> dict[str, Any]:
    settings = get_settings()
    external_integrity = integrity_projection(db, owner)
    storage_counts = external_integrity.get("storage", {})
    if not isinstance(storage_counts, dict):
        storage_counts = {}
    return {
        "enabled": settings.intelligence_enabled,
        "research_execution_enabled": settings.intelligence_research_execution_enabled,
        "external_research_enabled": settings.intelligence_external_research_enabled,
        "external_provider_mode": settings.intelligence_external_provider_mode,
        "autonomous_research_enabled": settings.intelligence_autonomous_research_enabled,
        "ai_mode": "LOCAL_DETERMINISTIC",
        "web_fetch": "DISABLED" if not settings.intelligence_web_fetch_enabled else "CONFIGURED",
        "search_provider": (
            "NOT_CONFIGURED" if not settings.intelligence_search_provider_enabled else "CONFIGURED"
        ),
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
        "external_integrity": external_integrity,
        "external_performance": {"classification": "LOCAL_FIXTURE_BASELINE"},
        "external_execution": {
            "queued_searches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.kind == "search",
                        ExternalExecution.status == "QUEUED",
                    )
                )
                or 0
            ),
            "running_searches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.kind == "search",
                        ExternalExecution.status == "RUNNING",
                    )
                )
                or 0
            ),
            "failed_searches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.kind == "search",
                        ExternalExecution.status == "FAILED",
                    )
                )
                or 0
            ),
            "queued_fetches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.kind == "fetch",
                        ExternalExecution.status == "QUEUED",
                    )
                )
                or 0
            ),
            "running_fetches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.kind == "fetch",
                        ExternalExecution.status == "RUNNING",
                    )
                )
                or 0
            ),
            "failed_fetches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.kind == "fetch",
                        ExternalExecution.status == "FAILED",
                    )
                )
                or 0
            ),
            "recovery_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalRecoveryAction)
                    .where(ExternalRecoveryAction.owner_id == owner.id)
                )
                or 0
            ),
            "provider_kill_switch": settings.intelligence_search_provider_kill_switch,
            "global_kill_switch": settings.intelligence_external_kill_switch,
            "emergency_stop": settings.external_mutations_emergency_stop,
            "provider_mode": settings.intelligence_external_provider_mode,
            "budget_configured": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalResearchBudget)
                    .where(ExternalResearchBudget.owner_id == owner.id)
                )
                or 0
            ),
            "rate_limit_configured": settings.intelligence_search_provider_enabled,
            "recovery_registered": True,
            "provider_health": (
                "READY"
                if settings.intelligence_external_provider_mode != "DISABLED"
                else "DISABLED"
            ),
            "search_enabled": settings.intelligence_search_provider_enabled,
            "fetch_enabled": settings.intelligence_web_fetch_enabled,
            "approved_domain_state": bool(settings.intelligence_external_approved_domains),
            "rate_limit_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalProviderState)
                    .where(
                        ExternalProviderState.owner_id == owner.id,
                        ExternalProviderState.last_failure == "rate_limited",
                    )
                )
                or 0
            ),
            "budget_exhaustion_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(ExternalExecution)
                    .where(
                        ExternalExecution.owner_id == owner.id,
                        ExternalExecution.failure_code == "budget_exhausted",
                    )
                )
                or 0
            ),
            "evidence_freshness_backlog": int(
                storage_counts.get("intelligence_autonomous_evidence", 0)
            ),
            "contradiction_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(AutonomousResearchContradiction)
                    .where(AutonomousResearchContradiction.owner_id == owner.id)
                )
                or 0
            ),
            "alert_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(AutonomousResearchAlert)
                    .where(AutonomousResearchAlert.owner_id == owner.id)
                )
                or 0
            ),
            "integrity_classification": external_integrity["classification"],
            "performance_classification": "LOCAL_FIXTURE_BASELINE",
        },
    }
