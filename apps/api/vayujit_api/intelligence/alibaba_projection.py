"""Small owner-scoped projections for the Alibaba discovery boundary."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.alibaba_models import (
    AlibabaDiscoveryRequest,
    AlibabaDiscoveryResult,
)
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchRecovery,
    AutonomousResearchReport,
)
from vayujit_api.intelligence.marketplace_runtime import (
    MarketplaceExecution,
    MarketplaceRateWindow,
    marketplace_integrity_counters,
)
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence


def integrity(db: Session, owner: User) -> dict[str, object]:
    request_duplicate_groups = db.execute(
        select(AlibabaDiscoveryRequest.idempotency_key, func.count())
        .where(AlibabaDiscoveryRequest.owner_id == owner.id)
        .group_by(AlibabaDiscoveryRequest.idempotency_key)
        .having(func.count() > 1)
    ).all()
    result_duplicate_groups = db.execute(
        select(AlibabaDiscoveryResult.provider_result_id, func.count())
        .where(AlibabaDiscoveryResult.owner_id == owner.id)
        .group_by(AlibabaDiscoveryResult.provider_result_id)
        .having(func.count() > 1)
    ).all()
    supplier_duplicate_groups = db.execute(
        select(Supplier.normalized_identity, func.count())
        .where(Supplier.owner_id == owner.id)
        .group_by(Supplier.normalized_identity)
        .having(func.count() > 1)
    ).all()
    evidence_duplicate_groups = db.execute(
        select(SupplierEvidence.idempotency_key, func.count())
        .where(SupplierEvidence.owner_id == owner.id)
        .group_by(SupplierEvidence.idempotency_key)
        .having(func.count() > 1)
    ).all()
    duplicate_requests = sum(int(row[1]) - 1 for row in request_duplicate_groups)
    duplicate_results = sum(int(row[1]) - 1 for row in result_duplicate_groups)
    duplicate_candidates = sum(int(row[1]) - 1 for row in supplier_duplicate_groups)
    duplicate_evidence = sum(int(row[1]) - 1 for row in evidence_duplicate_groups)

    requests = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryRequest)
            .where(AlibabaDiscoveryRequest.owner_id == owner.id)
        )
        or 0
    )
    results = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryResult)
            .where(AlibabaDiscoveryResult.owner_id == owner.id)
        )
        or 0
    )
    orphan_results = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryResult)
            .outerjoin(
                AlibabaDiscoveryRequest,
                AlibabaDiscoveryRequest.id == AlibabaDiscoveryResult.request_id,
            )
            .where(
                AlibabaDiscoveryResult.owner_id == owner.id,
                AlibabaDiscoveryRequest.id.is_(None),
            )
        )
        or 0
    )
    cross_owner = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryResult)
            .join(
                AlibabaDiscoveryRequest,
                AlibabaDiscoveryRequest.id == AlibabaDiscoveryResult.request_id,
            )
            .where(
                AlibabaDiscoveryResult.owner_id == owner.id,
                AlibabaDiscoveryRequest.owner_id != owner.id,
            )
        )
        or 0
    )
    mission_ids = select(AutonomousResearchMission.id).where(
        AutonomousResearchMission.owner_id == owner.id
    )
    autonomous_counts = {
        "evidence": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchEvidence)
                .where(AutonomousResearchEvidence.owner_id == owner.id)
            )
            or 0
        ),
        "changes": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchChange)
                .where(AutonomousResearchChange.owner_id == owner.id)
            )
            or 0
        ),
        "alerts": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchAlert)
                .where(AutonomousResearchAlert.owner_id == owner.id)
            )
            or 0
        ),
        "contradictions": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchContradiction)
                .where(AutonomousResearchContradiction.owner_id == owner.id)
            )
            or 0
        ),
        "recovery": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchRecovery)
                .where(AutonomousResearchRecovery.owner_id == owner.id)
            )
            or 0
        ),
        "reports": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchReport)
                .where(AutonomousResearchReport.owner_id == owner.id)
            )
            or 0
        ),
    }
    autonomous_orphans = {
        "evidence_without_mission": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchEvidence)
                .where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    ~AutonomousResearchEvidence.mission_id.in_(mission_ids),
                )
            )
            or 0
        ),
        "changes_without_mission": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchChange)
                .where(
                    AutonomousResearchChange.owner_id == owner.id,
                    ~AutonomousResearchChange.mission_id.in_(mission_ids),
                )
            )
            or 0
        ),
        "alerts_without_mission": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchAlert)
                .where(
                    AutonomousResearchAlert.owner_id == owner.id,
                    ~AutonomousResearchAlert.mission_id.in_(mission_ids),
                )
            )
            or 0
        ),
    }
    duplicate_total = sum(
        (duplicate_requests, duplicate_results, duplicate_candidates, duplicate_evidence)
    )
    orphan_total = orphan_results + sum(autonomous_orphans.values())
    return {
        "classification": (
            "PASS" if not (duplicate_total or orphan_total or cross_owner) else "REQUIRES_REVIEW"
        ),
        "storage": {
            "intelligence_alibaba_discovery_requests": requests,
            "intelligence_alibaba_discovery_results": results,
            **autonomous_counts,
        },
        "duplicates": {
            "request_idempotency": duplicate_requests,
            "provider_result_identity": duplicate_results,
            "supplier_candidates": duplicate_candidates,
            "evidence": duplicate_evidence,
            "total": duplicate_total,
        },
        "orphans": {
            "results_without_request": orphan_results,
            **autonomous_orphans,
            "total": orphan_total,
        },
        "broken_lineage": {
            "provider_request_result": orphan_results,
            "autonomous": sum(autonomous_orphans.values()),
        },
        "cross_owner": {"request_result_owner_mismatch": cross_owner},
        "performance": {"classification": "LOCAL_FIXTURE_BASELINE", "samples": 0},
    }


def product_channel(db: Session, owner: User, product_id: uuid.UUID) -> dict[str, object]:
    from vayujit_api.products.models import Product

    if (
        db.scalar(select(Product.id).where(Product.id == product_id, Product.owner_id == owner.id))
        is None
    ):
        raise HTTPException(404, "Product not found.")
    rows = list(
        db.scalars(
            select(AlibabaDiscoveryResult)
            .where(
                AlibabaDiscoveryResult.owner_id == owner.id,
                AlibabaDiscoveryResult.product_id == product_id,
            )
            .order_by(AlibabaDiscoveryResult.retrieved_at.desc())
        )
    )
    evidence_ids = {row.evidence_id for row in rows if row.evidence_id}
    evidence = []
    if evidence_ids:
        evidence = list(
            db.scalars(
                select(AutonomousResearchEvidence).where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    AutonomousResearchEvidence.id.in_(evidence_ids),
                )
            )
        )
    mission_ids = {row.mission_id for row in evidence}
    contradiction_count = 0
    material_change_count = 0
    alert_count = 0
    if mission_ids:
        contradiction_count = int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchContradiction)
                .where(
                    AutonomousResearchContradiction.owner_id == owner.id,
                    AutonomousResearchContradiction.mission_id.in_(mission_ids),
                )
            )
            or 0
        )
        material_change_count = int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchChange)
                .where(
                    AutonomousResearchChange.owner_id == owner.id,
                    AutonomousResearchChange.mission_id.in_(mission_ids),
                    AutonomousResearchChange.material.is_(True),
                )
            )
            or 0
        )
        alert_count = int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchAlert)
                .where(
                    AutonomousResearchAlert.owner_id == owner.id,
                    AutonomousResearchAlert.mission_id.in_(mission_ids),
                )
            )
            or 0
        )
    freshness = {
        value: sum(1 for row in rows if row.freshness_status == value)
        for value in ("fresh", "aging", "stale", "expired", "unknown")
    }
    return {
        "product_id": str(product_id),
        "provider": "ALIBABA",
        "research_status": "available" if rows else "not_started",
        "candidate_count": len({row.supplier_id for row in rows if row.supplier_id}),
        "matched_supplier_count": sum(1 for row in rows if row.identity_match == "MATCH"),
        "listing_count": len(rows),
        "accepted_evidence_count": sum(
            1 for item in evidence if item.verification_status in {"SUPPORTED", "VERIFIED"}
        ),
        "discovery_evidence_count": len(evidence_ids),
        "commercial_observation_count": sum(
            1
            for row in rows
            if any((row.price_claim, row.moq_claim, row.lead_time_claim, row.availability_claim))
        ),
        "contradiction_count": contradiction_count,
        "material_change_count": material_change_count,
        "alert_count": alert_count,
        "last_researched": rows[0].retrieved_at if rows else None,
        "freshness": freshness,
        "confidence": (
            "bounded_provider_claim_only"
            if len({item.provider for item in evidence}) <= 1
            else "multi_source_review_required"
        ),
        "risk_summary": (
            "Contradictions or material changes require human review."
            if contradiction_count or material_change_count or alert_count
            else "Verification and independent source review required."
        ),
        "recommended_follow_up": "Review discovery-only evidence before any commercial decision.",
    }


def calendar(db: Session, owner: User) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(AlibabaDiscoveryRequest)
            .where(AlibabaDiscoveryRequest.owner_id == owner.id)
            .order_by(AlibabaDiscoveryRequest.created_at.desc())
        )
    )
    return [
        {
            "id": str(row.id),
            "type": "alibaba.discovery",
            "status": row.status,
            "scheduled_at": row.created_at,
            "correlation_id": row.correlation_id,
            "marketplace_execution_id": (
                str(row.marketplace_execution_id) if row.marketplace_execution_id else None
            ),
        }
        for row in rows
    ]


def report(db: Session, owner: User) -> dict[str, object]:
    return {
        "format": "json",
        "provider": "ALIBABA",
        "classification": "DISCOVERY_ONLY",
        "history": [
            {
                "id": str(row.id),
                "status": row.status,
                "query": row.query,
                "result_count": row.result_count,
                "correlation_id": row.correlation_id,
                "marketplace_execution_id": (
                    str(row.marketplace_execution_id) if row.marketplace_execution_id else None
                ),
            }
            for row in db.scalars(
                select(AlibabaDiscoveryRequest)
                .where(AlibabaDiscoveryRequest.owner_id == owner.id)
                .order_by(AlibabaDiscoveryRequest.created_at.desc())
            )
        ],
        "safety": "No contact, RFQ, order, payment, or raw provider payloads are supported.",
    }


def storage_inventory() -> dict[str, object]:
    return {
        "tables": [
            "intelligence_alibaba_discovery_requests",
            "intelligence_alibaba_discovery_results",
            "intelligence_suppliers (reused)",
            "intelligence_supplier_sources (reused)",
            "intelligence_supplier_products (reused)",
            "intelligence_supplier_evidence (reused)",
            "marketplace_executions (shared runtime)",
            "marketplace_rate_windows (shared runtime)",
            "marketplace_ledger (shared runtime)",
        ],
        "provider_specific_reason": (
            "Request/result lineage and provider-result idempotency require durable records."
        ),
    }


def operational_summary(db: Session, owner: User, settings: Settings) -> dict[str, object]:
    request_count = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryRequest)
            .where(AlibabaDiscoveryRequest.owner_id == owner.id)
        )
        or 0
    )
    result_count = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryResult)
            .where(AlibabaDiscoveryResult.owner_id == owner.id)
        )
        or 0
    )
    failure_count = int(
        db.scalar(
            select(func.count())
            .select_from(AlibabaDiscoveryRequest)
            .where(
                AlibabaDiscoveryRequest.owner_id == owner.id,
                AlibabaDiscoveryRequest.status == "failed",
            )
        )
        or 0
    )
    executions = list(
        db.scalars(
            select(MarketplaceExecution).where(
                MarketplaceExecution.owner_id == owner.id,
                MarketplaceExecution.provider == "ALIBABA",
            )
        )
    )
    windows = list(
        db.scalars(
            select(MarketplaceRateWindow).where(
                MarketplaceRateWindow.owner_id == owner.id,
                MarketplaceRateWindow.provider == "ALIBABA",
            )
        )
    )
    return {
        "provider": "ALIBABA",
        "preflight": {
            "mode": settings.alibaba_mode,
            "enabled": settings.alibaba_enabled,
            "kill_switch": settings.alibaba_kill_switch,
            "global_external_kill_switch": settings.intelligence_external_kill_switch,
            "emergency_stop": settings.external_mutations_emergency_stop,
            "live_validation": "NOT_RUN",
        },
        "read_only": True,
        "request_count": request_count,
        "result_count": result_count,
        "failure_count": failure_count,
        "budget": {
            "requests_per_minute": settings.alibaba_requests_per_minute,
            "requests_per_hour": settings.alibaba_requests_per_hour,
            "daily_quota": settings.alibaba_daily_quota,
            "max_results": settings.alibaba_max_results,
            "retry_max_attempts": settings.alibaba_retry_max_attempts,
        },
        "queue": {
            "pending": sum(row.status == "QUEUED" for row in executions),
            "running": sum(row.status == "RUNNING" for row in executions),
        },
        "runtime": {
            "registered": True,
            "execution_count": len(executions),
            "failed": sum(row.status in {"FAILED", "RETRY_WAIT"} for row in executions),
            "retry_wait": sum(row.status == "RETRY_WAIT" for row in executions),
            "last_execution": max(
                (row.completed_at or row.started_at for row in executions), default=None
            ),
            "rate_windows": [
                {
                    "minute_used": row.minute_used,
                    "hour_used": row.hour_used,
                }
                for row in windows
            ],
            "integrity": marketplace_integrity_counters(db, owner),
            "live_validation": "NOT_RUN",
        },
        "recovery": {"registered": True, "separate_recovery_system": False},
        "prohibited_actions": ["contact", "rfq", "order", "payment", "supplier_modification"],
    }
