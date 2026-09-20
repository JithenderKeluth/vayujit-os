# ruff: noqa: E501
"""Bounded Intelligence projection consumed by Operations, with ORM access isolated here."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.alibaba_projection import (
    operational_summary as alibaba_operational_summary,
)
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchContradiction,
)
from vayujit_api.intelligence.cross_marketplace_service import (
    operations as cross_marketplace_operations,
)
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalProviderState,
    ExternalRecoveryAction,
    ExternalResearchBudget,
)
from vayujit_api.intelligence.external_projection import integrity_projection
from vayujit_api.intelligence.external_service import approved_fetch_preflight
from vayujit_api.intelligence.global_sources_projection import (
    operational_summary as global_sources_operational_summary,
)
from vayujit_api.intelligence.indiamart_projection import operational_summary
from vayujit_api.intelligence.marketplace_runtime import (
    MarketplaceExecution,
    MarketplaceLedger,
    MarketplaceRateWindow,
    marketplace_integrity_counters,
)
from vayujit_api.intelligence.models import (
    IntelligenceEvidence,
    IntelligenceResearchRun,
    IntelligenceSource,
)
from vayujit_api.intelligence.portfolio_integration import operations as portfolio_operations
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewAnalysisAnnotation,
    ReviewAnalysisItem,
    ReviewChangeComparison,
    ReviewChangeEvent,
    ReviewContext,
    ReviewIngestionBatch,
    ReviewOpportunitySignal,
    ReviewProductGap,
    ReviewProductGapAnalysis,
    ReviewRecord,
    ReviewSnapshot,
)
from vayujit_api.intelligence.shortlisting_service import operations as shortlisting_operations
from vayujit_api.intelligence.tradeindia_projection import (
    operational_summary as tradeindia_operational_summary,
)
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    WebsiteObservation,
    WebsiteRefreshJob,
    WebsiteSourceProfile,
)


def _unknown_sentiment_count(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    unknown = value.get("UNKNOWN")
    if not isinstance(unknown, dict):
        return 0
    count = unknown.get("count")
    return count if isinstance(count, int) else 0


def get_operations_projection(db: Session, owner: User) -> dict[str, Any]:
    settings = get_settings()
    external_integrity = integrity_projection(db, owner)
    fetch_preflight = approved_fetch_preflight(settings)
    storage_counts = external_integrity.get("storage", {})
    if not isinstance(storage_counts, dict):
        storage_counts = {}
    refresh_jobs = list(
        db.scalars(select(WebsiteRefreshJob).where(WebsiteRefreshJob.owner_id == owner.id))
    )
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    refresh_due = int(
        db.scalar(
            select(func.count())
            .select_from(WebsiteSourceProfile)
            .where(
                WebsiteSourceProfile.owner_id == owner.id,
                WebsiteSourceProfile.enabled.is_(True),
                WebsiteSourceProfile.next_refresh_at.is_not(None),
                WebsiteSourceProfile.next_refresh_at <= now,
            )
        )
        or 0
    )
    refresh_failed = sum(1 for job in refresh_jobs if job.status == "FAILED")
    refresh_queued = sum(1 for job in refresh_jobs if job.status == "QUEUED")
    refresh_running = sum(1 for job in refresh_jobs if job.status == "RUNNING")
    analysis_rows = list(
        db.scalars(select(ReviewAnalysis).where(ReviewAnalysis.owner_id == owner.id))
    )
    analysis_annotations = list(
        db.scalars(
            select(ReviewAnalysisAnnotation).where(ReviewAnalysisAnnotation.owner_id == owner.id)
        )
    )
    analysis_items = list(
        db.scalars(select(ReviewAnalysisItem).where(ReviewAnalysisItem.owner_id == owner.id))
    )
    gap_analyses = list(
        db.scalars(
            select(ReviewProductGapAnalysis).where(ReviewProductGapAnalysis.owner_id == owner.id)
        )
    )
    product_gaps = list(
        db.scalars(select(ReviewProductGap).where(ReviewProductGap.owner_id == owner.id))
    )
    opportunity_signals = list(
        db.scalars(
            select(ReviewOpportunitySignal).where(ReviewOpportunitySignal.owner_id == owner.id)
        )
    )
    change_comparisons = list(
        db.scalars(
            select(ReviewChangeComparison).where(ReviewChangeComparison.owner_id == owner.id)
        )
    )
    change_events = list(
        db.scalars(select(ReviewChangeEvent).where(ReviewChangeEvent.owner_id == owner.id))
    )
    latest_analysis = max(analysis_rows, key=lambda row: row.created_at, default=None)
    refresh_successes = [
        job.completed_at for job in refresh_jobs if job.status == "SUCCEEDED" and job.completed_at
    ]
    next_due = min(
        (
            profile.next_refresh_at
            for profile in db.scalars(
                select(WebsiteSourceProfile).where(WebsiteSourceProfile.owner_id == owner.id)
            )
            if profile.next_refresh_at
        ),
        default=None,
    )
    marketplace_rows = list(
        db.scalars(select(MarketplaceExecution).where(MarketplaceExecution.owner_id == owner.id))
    )
    marketplace_windows = list(
        db.scalars(select(MarketplaceRateWindow).where(MarketplaceRateWindow.owner_id == owner.id))
    )
    marketplace_ledger = list(
        db.scalars(select(MarketplaceLedger).where(MarketplaceLedger.owner_id == owner.id))
    )
    marketplace_counts = {
        entity_type: sum(row.entity_type == entity_type for row in marketplace_ledger)
        for entity_type in (
            "request",
            "result",
            "candidate",
            "supplier",
            "product",
            "offering",
            "evidence",
            "observation",
            "change",
            "alert",
            "report",
            "recovery",
        )
    }
    marketplace_projection = {
        "registered_providers": sorted({row.provider for row in marketplace_rows}) or ["INDIAMART"],
        "provider_mode": {
            provider: ("LOCAL_FIXTURE" if provider == "INDIAMART" else "UNKNOWN")
            for provider in sorted({row.provider for row in marketplace_rows}) or ["INDIAMART"]
        },
        "queued": sum(row.status == "QUEUED" for row in marketplace_rows),
        "running": sum(row.status == "RUNNING" for row in marketplace_rows),
        "failed": sum(row.status in {"FAILED", "RETRY_WAIT"} for row in marketplace_rows),
        "last_execution": max(
            (row.completed_at or row.started_at for row in marketplace_rows), default=None
        ),
        "rate_windows": [
            {"provider": row.provider, "minute_used": row.minute_used, "hour_used": row.hour_used}
            for row in marketplace_windows
        ],
        "retry_budget": {
            "executions": len(marketplace_rows),
            "retry_wait": sum(row.status == "RETRY_WAIT" for row in marketplace_rows),
        },
        "ledger": marketplace_counts,
        "recovery": {
            "registered": True,
            "executions": marketplace_counts["recovery"],
        },
        "integrity": marketplace_integrity_counters(db, owner),
        "performance": {"classification": "LOCAL_FIXTURE_BASELINE"},
        "live_validation": "NOT_RUN",
    }
    return {
        "enabled": settings.intelligence_enabled,
        "website_intelligence": {
            "enabled": True,
            "source_profiles": int(
                db.scalar(
                    select(func.count())
                    .select_from(WebsiteSourceProfile)
                    .where(WebsiteSourceProfile.owner_id == owner.id)
                )
                or 0
            ),
            "manufacturer_candidates": int(
                db.scalar(
                    select(func.count())
                    .select_from(ManufacturerCandidate)
                    .where(ManufacturerCandidate.owner_id == owner.id)
                )
                or 0
            ),
            "observation_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(WebsiteObservation)
                    .where(WebsiteObservation.owner_id == owner.id)
                )
                or 0
            ),
            "approved_fetch_dependency": "single_page_allowlisted",
            "supplier_contact": "DISABLED",
            "purchasing": "NOT_IMPLEMENTED",
            "refresh_policy": "profile-scoped DAILY/WEEKLY/MONTHLY or MANUAL",
            "refresh_due": refresh_due,
            "refresh_queued": refresh_queued,
            "refresh_running": refresh_running,
            "refresh_failed": refresh_failed,
            "refresh_job_count": len(refresh_jobs),
            "last_successful_refresh": max(refresh_successes, default=None),
            "next_due_refresh": next_due,
            "scheduler_state": "healthy" if refresh_failed == 0 else "requires_review",
            "worker_registered": True,
            "scheduler_registered": True,
            "integrity": external_integrity.get("refresh", {}),
            "recovery": {"registered": True, "retryable_failure_code": "refresh_failed"},
        },
        "indiamart": operational_summary(db, owner, settings),
        "alibaba": alibaba_operational_summary(db, owner, settings),
        "tradeindia": tradeindia_operational_summary(db, owner, settings),
        "global_sources": global_sources_operational_summary(db, owner, settings),
        "cross_marketplace_supplier_intelligence": cross_marketplace_operations(db, owner),
        "supplier_shortlisting": shortlisting_operations(db, owner),
        "supplier_portfolios": portfolio_operations(db, owner),
        "reviews": {
            "enabled": True,
            "contexts": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewContext)
                    .where(ReviewContext.owner_id == owner.id)
                )
                or 0
            ),
            "active_contexts": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewContext)
                    .where(ReviewContext.owner_id == owner.id, ReviewContext.status == "ACTIVE")
                )
                or 0
            ),
            "review_records": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewRecord)
                    .where(ReviewRecord.owner_id == owner.id)
                )
                or 0
            ),
            "snapshots": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewSnapshot)
                    .where(ReviewSnapshot.owner_id == owner.id)
                )
                or 0
            ),
            "stale_evidence": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewRecord)
                    .where(
                        ReviewRecord.owner_id == owner.id, ReviewRecord.freshness_status == "STALE"
                    )
                )
                or 0
            ),
            "missing_evidence": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewRecord)
                    .where(
                        ReviewRecord.owner_id == owner.id, ReviewRecord.evidence_state == "MISSING"
                    )
                )
                or 0
            ),
            "source_counts": {
                str(provider): int(count)
                for provider, count in db.execute(
                    select(ReviewRecord.provider, func.count())
                    .where(ReviewRecord.owner_id == owner.id)
                    .group_by(ReviewRecord.provider)
                ).tuples()
            },
            "ingestion_batches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewIngestionBatch)
                    .where(ReviewIngestionBatch.owner_id == owner.id)
                )
                or 0
            ),
            "successful_ingestion_batches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewIngestionBatch)
                    .where(
                        ReviewIngestionBatch.owner_id == owner.id,
                        ReviewIngestionBatch.status == "COMPLETED",
                    )
                )
                or 0
            ),
            "partial_ingestion_batches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewIngestionBatch)
                    .where(
                        ReviewIngestionBatch.owner_id == owner.id,
                        ReviewIngestionBatch.status == "PARTIAL",
                    )
                )
                or 0
            ),
            "failed_ingestion_batches": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewIngestionBatch)
                    .where(
                        ReviewIngestionBatch.owner_id == owner.id,
                        ReviewIngestionBatch.status == "FAILED",
                    )
                )
                or 0
            ),
            "accepted_ingestion_candidates": int(
                db.scalar(
                    select(func.sum(ReviewIngestionBatch.accepted_count)).where(
                        ReviewIngestionBatch.owner_id == owner.id
                    )
                )
                or 0
            ),
            "rejected_ingestion_candidates": int(
                db.scalar(
                    select(func.sum(ReviewIngestionBatch.rejected_count)).where(
                        ReviewIngestionBatch.owner_id == owner.id
                    )
                )
                or 0
            ),
            "duplicate_ingestion_candidates": int(
                db.scalar(
                    select(func.sum(ReviewIngestionBatch.duplicate_count)).where(
                        ReviewIngestionBatch.owner_id == owner.id
                    )
                )
                or 0
            ),
            "external_writes": "DISABLED",
            "analyses": len(analysis_rows),
            "current_analyses": sum(row.status == "COMPLETED" for row in analysis_rows),
            "failed_analyses": sum(row.status == "FAILED" for row in analysis_rows),
            "reviews_analyzed": sum(row.included_records for row in analysis_rows),
            "reviews_excluded": sum(row.excluded_records for row in analysis_rows),
            "unsupported_language_reviews": sum(
                1
                for row in analysis_rows
                if any(
                    isinstance(item, dict) and item.get("code") == "UNSUPPORTED_LANGUAGE"
                    for item in (row.evidence_gaps if isinstance(row.evidence_gaps, list) else [])
                )
            ),
            "unknown_sentiment": sum(
                _unknown_sentiment_count(row.sentiment_distribution) for row in analysis_rows
            ),
            "research_gaps": sum(len(row.evidence_gaps) for row in analysis_rows),
            "analysis_annotations": len(analysis_annotations),
            "analysis_items": len(analysis_items),
            "latest_analysis_id": str(latest_analysis.id) if latest_analysis else None,
            "gap_analyses": len(gap_analyses),
            "product_gaps": len(product_gaps),
            "opportunity_signals": len(opportunity_signals),
            "change_comparisons": len(change_comparisons),
            "change_events": len(change_events),
            "moderate_high_changes": sum(
                row.materiality in {"MODERATE", "HIGH"} for row in change_events
            ),
            "unresolved_changes": sum(row.status == "UNRESOLVED" for row in change_events),
            "possibly_disappeared_signals": sum(
                row.status == "POSSIBLY_DISAPPEARED" for row in change_events
            ),
            "alert_eligible_changes": sum(
                row.alert_eligibility in {"REVIEW", "ALERT"} for row in change_events
            ),
            "source_mix_changes": sum(
                row.change_type == "SOURCE_COVERAGE_CHANGE" for row in change_events
            ),
            "latest_change_comparison_id": (
                str(max(change_comparisons, key=lambda row: row.created_at).id)
                if change_comparisons
                else None
            ),
            "research_required_signals": sum(
                item.status == "RESEARCH_REQUIRED" for item in opportunity_signals
            ),
            "contradictory_signals": sum(
                item.status == "CONTRADICTORY" for item in opportunity_signals
            ),
            "preserve_signals": sum(
                item.signal_type == "PRESERVE_STRENGTH" for item in opportunity_signals
            ),
            "latest_gap_analysis_id": (
                str(max(gap_analyses, key=lambda row: row.created_at).id) if gap_analyses else None
            ),
        },
        "marketplace": marketplace_projection,
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
            "approved_fetch_status": fetch_preflight["status"],
            "approved_domain_count": fetch_preflight["approved_domain_count"],
            "tls_required": fetch_preflight["tls_required"],
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
