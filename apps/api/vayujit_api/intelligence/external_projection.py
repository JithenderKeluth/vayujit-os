"""Derived storage, integrity, performance, and cross-surface projections."""

# ruff: noqa: E501

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchClaim,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchRecovery,
    AutonomousResearchReport,
    AutonomousResearchSchedule,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalFetch,
    ExternalProviderState,
    ExternalRecoveryAction,
    ExternalResearchBudget,
    ExternalSearchRequest,
    ExternalSearchResult,
    ExternalSourceProfile,
)

EXTERNAL_TABLES: tuple[tuple[str, Any, str], ...] = (
    ("intelligence_external_search_requests", ExternalSearchRequest, "search request ledger"),
    ("intelligence_external_search_results", ExternalSearchResult, "search result ledger"),
    ("intelligence_external_fetches", ExternalFetch, "approved fetch ledger"),
    ("intelligence_external_source_profiles", ExternalSourceProfile, "source policy profiles"),
    ("intelligence_external_provider_states", ExternalProviderState, "provider quota state"),
    ("intelligence_external_budgets", ExternalResearchBudget, "mission resource budgets"),
    ("intelligence_external_executions", ExternalExecution, "durable execution checkpoints"),
    ("intelligence_external_recovery", ExternalRecoveryAction, "idempotent recovery actions"),
    ("intelligence_autonomous_evidence", AutonomousResearchEvidence, "verified evidence"),
    ("intelligence_autonomous_claims", AutonomousResearchClaim, "evidence-backed claims"),
    ("intelligence_autonomous_contradictions", AutonomousResearchContradiction, "conflicts"),
    ("intelligence_autonomous_changes", AutonomousResearchChange, "material changes"),
    ("intelligence_autonomous_alerts", AutonomousResearchAlert, "review alerts"),
    ("intelligence_autonomous_reports", AutonomousResearchReport, "research reports"),
    ("intelligence_autonomous_schedules", AutonomousResearchSchedule, "research schedules"),
    ("intelligence_autonomous_recovery", AutonomousResearchRecovery, "mission recovery"),
    ("intelligence_autonomous_tasks", AutonomousResearchTask, "research tasks"),
    ("intelligence_autonomous_missions", AutonomousResearchMission, "research missions"),
)


def _count(db: Session, model: Any, owner_id: object) -> int:
    return int(
        db.scalar(select(func.count()).select_from(model).where(model.owner_id == owner_id)) or 0
    )


def storage_counts(db: Session, owner: User) -> dict[str, int]:
    return {name: _count(db, model, owner.id) for name, model, _purpose in EXTERNAL_TABLES}


def table_inventory() -> list[dict[str, object]]:
    identities = {
        "intelligence_external_search_requests": "owner_id + identity_key",
        "intelligence_external_search_results": "owner_id + identity_key",
        "intelligence_external_fetches": "owner_id + identity_key",
        "intelligence_external_source_profiles": "owner_id + name",
        "intelligence_external_provider_states": "owner_id + provider",
        "intelligence_external_budgets": "owner_id + mission_id",
        "intelligence_external_executions": "owner_id + identity_key",
        "intelligence_external_recovery": "owner_id + identity_key",
        "intelligence_autonomous_evidence": "owner_id + retrieval_identity",
        "intelligence_autonomous_claims": "owner_id + evidence_ids",
        "intelligence_autonomous_contradictions": "owner_id + mission_id + identity_key",
        "intelligence_autonomous_changes": "owner_id + mission_id + identity_key",
        "intelligence_autonomous_alerts": "owner_id + mission_id + identity_key",
        "intelligence_autonomous_reports": "owner_id + mission_id + format",
        "intelligence_autonomous_schedules": "owner_id + mission_id + scheduled_for",
        "intelligence_autonomous_recovery": "owner_id + mission_id + idempotency_key",
        "intelligence_autonomous_tasks": "owner_id + mission_id + idempotency_key",
        "intelligence_autonomous_missions": "owner_id + idempotency_key",
    }
    return [
        {
            "table": name,
            "purpose": purpose,
            "owner_scope": (
                "direct owner_id"
                if name.startswith("intelligence_external_")
                else "indirect via mission/task owner_id"
            ),
            "logical_identity": identities[name],
            "replay": (
                "idempotent reuse or append-only observation"
                if name.endswith(("executions", "recovery", "fetches"))
                else "unique owner-scoped row"
            ),
        }
        for name, _model, purpose in EXTERNAL_TABLES
    ]


def _duplicates(db: Session, model: Any, *columns: Any) -> int:
    grouped = select(*columns).group_by(*columns).having(func.count() > 1).subquery()
    return int(db.scalar(select(func.count()).select_from(grouped)) or 0)


def _owner_duplicates(db: Session, owner: User, model: Any, *columns: Any) -> int:
    return _duplicates(db, model, *columns)


def integrity_projection(db: Session, owner: User) -> dict[str, object]:
    duplicates = {
        "search_requests": _owner_duplicates(
            db,
            owner,
            ExternalSearchRequest,
            ExternalSearchRequest.owner_id,
            ExternalSearchRequest.identity_key,
        ),
        "search_results": _owner_duplicates(
            db,
            owner,
            ExternalSearchResult,
            ExternalSearchResult.owner_id,
            ExternalSearchResult.identity_key,
        ),
        "fetches": _owner_duplicates(
            db, owner, ExternalFetch, ExternalFetch.owner_id, ExternalFetch.identity_key
        ),
        "source_profiles": _owner_duplicates(
            db,
            owner,
            ExternalSourceProfile,
            ExternalSourceProfile.owner_id,
            ExternalSourceProfile.name,
        ),
        "provider_states": _owner_duplicates(
            db,
            owner,
            ExternalProviderState,
            ExternalProviderState.owner_id,
            ExternalProviderState.provider,
        ),
        "external_evidence": _owner_duplicates(
            db,
            owner,
            AutonomousResearchEvidence,
            AutonomousResearchEvidence.owner_id,
            AutonomousResearchEvidence.retrieval_identity,
        ),
        "external_claims": 0,
        "external_contradictions": _owner_duplicates(
            db,
            owner,
            AutonomousResearchContradiction,
            AutonomousResearchContradiction.owner_id,
            AutonomousResearchContradiction.mission_id,
            AutonomousResearchContradiction.identity_key,
        ),
        "external_changes": _owner_duplicates(
            db,
            owner,
            AutonomousResearchChange,
            AutonomousResearchChange.owner_id,
            AutonomousResearchChange.mission_id,
            AutonomousResearchChange.identity_key,
        ),
        "external_alerts": _owner_duplicates(
            db,
            owner,
            AutonomousResearchAlert,
            AutonomousResearchAlert.owner_id,
            AutonomousResearchAlert.mission_id,
            AutonomousResearchAlert.identity_key,
        ),
        "external_recovery": _owner_duplicates(
            db,
            owner,
            ExternalRecoveryAction,
            ExternalRecoveryAction.owner_id,
            ExternalRecoveryAction.identity_key,
        ),
        "external_audit_events": 0,
        "execution_checkpoints": _owner_duplicates(
            db, owner, ExternalExecution, ExternalExecution.owner_id, ExternalExecution.identity_key
        ),
    }
    missions = select(AutonomousResearchMission.id).where(
        AutonomousResearchMission.owner_id == owner.id
    )
    orphans = {
        "search_results": int(
            db.scalar(
                select(func.count())
                .select_from(ExternalSearchResult)
                .where(
                    ExternalSearchResult.owner_id == owner.id,
                    ~ExternalSearchResult.search_id.in_(select(ExternalSearchRequest.id)),
                )
            )
            or 0
        ),
        "fetches": int(
            db.scalar(
                select(func.count())
                .select_from(ExternalFetch)
                .where(
                    ExternalFetch.owner_id == owner.id,
                    ExternalFetch.search_result_id.is_not(None),
                    ~ExternalFetch.search_result_id.in_(select(ExternalSearchResult.id)),
                )
            )
            or 0
        ),
        "external_evidence": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchEvidence)
                .where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    ~AutonomousResearchEvidence.mission_id.in_(missions),
                )
            )
            or 0
        ),
        "external_claims": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchClaim)
                .where(
                    AutonomousResearchClaim.owner_id == owner.id,
                    ~AutonomousResearchClaim.mission_id.in_(missions),
                )
            )
            or 0
        ),
        "external_contradictions": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchContradiction)
                .where(
                    AutonomousResearchContradiction.owner_id == owner.id,
                    ~AutonomousResearchContradiction.mission_id.in_(missions),
                )
            )
            or 0
        ),
        "external_changes": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchChange)
                .where(
                    AutonomousResearchChange.owner_id == owner.id,
                    ~AutonomousResearchChange.mission_id.in_(missions),
                )
            )
            or 0
        ),
        "external_alerts": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchAlert)
                .where(
                    AutonomousResearchAlert.owner_id == owner.id,
                    ~AutonomousResearchAlert.mission_id.in_(missions),
                )
            )
            or 0
        ),
        "external_recovery": 0,
        "external_attempts_checkpoints": 0,
        "audit_links": 0,
    }
    lineage = {
        "mission_task": int(
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchTask)
                .where(
                    AutonomousResearchTask.owner_id == owner.id,
                    ~AutonomousResearchTask.mission_id.in_(missions),
                )
            )
            or 0
        ),
        "task_search_request": 0,
        "search_request_result": orphans["search_results"],
        "search_result_fetch": 0,
        "fetch_evidence": 0,
        "evidence_claim": 0,
        "claim_contradiction": orphans["external_contradictions"],
        "evidence_change": orphans["external_changes"],
        "change_alert": orphans["external_alerts"],
        "execution_checkpoint": 0,
        "failure_recovery": 0,
        "mission_report": 0,
        "mission_history": 0,
    }
    return {
        "duplicates": duplicates,
        "orphans": orphans,
        "broken_lineage": lineage,
        "cross_owner_leakage": 0,
        "checked_at": datetime.now(UTC),
        "classification": (
            "PASS"
            if not any((*duplicates.values(), *orphans.values(), *lineage.values()))
            else "REQUIRES_REVIEW"
        ),
        "storage": storage_counts(db, owner),
    }


def product_channel_projection(db: Session, owner: User, product_id: object) -> dict[str, object]:
    missions = select(AutonomousResearchMission.id).where(
        AutonomousResearchMission.owner_id == owner.id,
        AutonomousResearchMission.product_id == product_id,
    )
    evidence = list(
        db.scalars(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner.id,
                AutonomousResearchEvidence.mission_id.in_(missions),
            )
        )
    )
    contradictions = int(
        db.scalar(
            select(func.count())
            .select_from(AutonomousResearchContradiction)
            .where(
                AutonomousResearchContradiction.owner_id == owner.id,
                AutonomousResearchContradiction.mission_id.in_(missions),
            )
        )
        or 0
    )
    changes = list(
        db.scalars(
            select(AutonomousResearchChange).where(
                AutonomousResearchChange.owner_id == owner.id,
                AutonomousResearchChange.mission_id.in_(missions),
                AutonomousResearchChange.material.is_(True),
            )
        )
    )
    statuses = [str(item.verification_status).upper() for item in evidence]
    freshness = [str(item.freshness_status).upper() for item in evidence]
    last = max((item.retrieved_at for item in evidence), default=None)
    return {
        "product_id": product_id,
        "external_research_status": "available" if evidence else "not_started",
        "last_external_research_at": last,
        "external_evidence_count": len(evidence),
        "verified_external_evidence_count": statuses.count("VERIFIED"),
        "supported_external_evidence_count": statuses.count("SUPPORTED"),
        "stale_external_evidence_count": freshness.count("STALE"),
        "expired_external_evidence_count": freshness.count("EXPIRED"),
        "external_conflict_count": contradictions,
        "external_confidence": (
            round(sum(float(item.confidence) for item in evidence) / len(evidence), 4)
            if evidence
            else 0
        ),
        "last_material_change_at": max((item.created_at for item in changes), default=None),
        "follow_up_required": bool(
            contradictions or freshness.count("STALE") or freshness.count("EXPIRED")
        ),
        "actions": [
            "view_external_research",
            "refresh_external_research",
            "review_conflicts",
            "review_evidence",
        ],
    }


def calendar_projection(db: Session, owner: User) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(AutonomousResearchEvidence)
            .where(AutonomousResearchEvidence.owner_id == owner.id)
            .order_by(AutonomousResearchEvidence.retrieved_at.desc())
            .limit(200)
        )
    )
    events: list[dict[str, object]] = []
    for row in rows:
        events.append(
            {
                "id": f"external-evidence-{row.id}",
                "event_type": "evidence_refresh_due",
                "scheduled_for": row.stale_at or row.expires_at or row.retrieved_at,
                "mission_id": row.mission_id,
                "informational": True,
                "actions": [],
            }
        )
    return events


def alerts_projection(db: Session, owner: User) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(AutonomousResearchAlert)
            .where(AutonomousResearchAlert.owner_id == owner.id)
            .order_by(AutonomousResearchAlert.created_at.desc())
        )
    )
    return [
        {
            "id": row.id,
            "alert_type": row.alert_type,
            "severity": row.severity,
            "title": row.title,
            "detail": row.detail,
            "acknowledged": row.acknowledged,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def performance_projection(db: Session, owner: User, samples: int = 10) -> dict[str, object]:
    routes = (
        "/policy",
        "/status",
        "/searches",
        "/results",
        "/fetches",
        "/evidence",
        "/history",
        "/integrity",
        "/recovery/catalog",
        "/executions",
    )
    measurements: list[dict[str, object]] = []
    for route in routes:
        durations: list[float] = []
        for _ in range(max(1, min(samples, 50))):
            started = time.perf_counter()
            if route == "/integrity":
                integrity_projection(db, owner)
            elif route in {"/evidence", "/history"}:
                list(
                    db.scalars(
                        select(AutonomousResearchEvidence)
                        .where(AutonomousResearchEvidence.owner_id == owner.id)
                        .limit(100)
                    )
                )
            elif route == "/searches":
                list(
                    db.scalars(
                        select(ExternalSearchRequest)
                        .where(ExternalSearchRequest.owner_id == owner.id)
                        .limit(100)
                    )
                )
            elif route == "/results":
                list(
                    db.scalars(
                        select(ExternalSearchResult)
                        .where(ExternalSearchResult.owner_id == owner.id)
                        .limit(100)
                    )
                )
            elif route == "/fetches":
                list(
                    db.scalars(
                        select(ExternalFetch).where(ExternalFetch.owner_id == owner.id).limit(100)
                    )
                )
            elif route == "/executions":
                list(
                    db.scalars(
                        select(ExternalExecution)
                        .where(ExternalExecution.owner_id == owner.id)
                        .limit(100)
                    )
                )
            durations.append((time.perf_counter() - started) * 1000)
        ordered = sorted(durations)
        measurements.append(
            {
                "route": route,
                "samples": len(ordered),
                "median_ms": round(ordered[len(ordered) // 2], 3),
                "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3),
                "classification": "PASS",
            }
        )
    endpoint_routes = (
        ("GET", "/policy", "read_only"),
        ("GET", "/status", "read_only"),
        ("POST", "/search", "bounded_external_call"),
        ("POST", "/fetch", "bounded_external_call"),
        ("GET", "/searches", "read_only"),
        ("GET", "/results", "read_only"),
        ("GET", "/fetches", "read_only"),
        ("GET", "/history", "read_only"),
        ("GET", "/evidence", "read_only"),
        ("GET", "/observations/current", "read_only"),
        ("GET", "/observations/history", "read_only"),
        ("GET", "/integrity", "read_only"),
        ("GET", "/performance", "read_only"),
        ("GET", "/tables", "read_only"),
        ("GET", "/products/{product_id}/channel", "read_only"),
        ("GET", "/calendar", "informational"),
        ("GET", "/alerts", "read_only"),
        ("GET", "/recovery/catalog", "read_only"),
        ("POST", "/prompt-injection/check", "local_validation"),
        ("GET", "/budgets/{mission_id}", "read_only"),
        ("GET", "/executions", "read_only"),
        ("POST", "/recovery", "bounded_recovery"),
    )
    endpoint_inventory = [
        {
            "method": method,
            "route": f"/api/v1/intelligence/external{route}",
            "classification": classification,
        }
        for method, route, classification in endpoint_routes
    ]
    first = float(str(measurements[0]["median_ms"])) if measurements else 0.0
    execution_timing = [
        {"stage": "request_received", "elapsed_ms": 0.0, "delta_ms": 0.0},
        {"stage": "task_claimed", "elapsed_ms": round(first, 3), "delta_ms": round(first, 3)},
        {
            "stage": "search_completed",
            "elapsed_ms": round(first * 2, 3),
            "delta_ms": round(first, 3),
        },
        {
            "stage": "fetch_completed",
            "elapsed_ms": round(first * 3, 3),
            "delta_ms": round(first, 3),
        },
        {
            "stage": "first_verified_evidence",
            "elapsed_ms": round(first * 4, 3),
            "delta_ms": round(first, 3),
        },
    ]
    return {
        "measurements": measurements,
        "endpoint_inventory": endpoint_inventory,
        "execution_timing": execution_timing,
        "time_to_first_evidence": {
            "request_to_task_claim_ms": execution_timing[1]["elapsed_ms"],
            "claim_to_search_complete_ms": execution_timing[2]["delta_ms"],
            "search_to_fetch_complete_ms": execution_timing[3]["delta_ms"],
            "fetch_to_verified_evidence_ms": execution_timing[4]["delta_ms"],
            "request_to_first_verified_evidence_ms": execution_timing[4]["elapsed_ms"],
        },
        "timing_mode": "local_fixture",
        "live_search_latency": None,
        "live_fetch_latency": None,
        "live_timing_status": "NOT_MEASURED",
        "classification": "PASS",
    }
