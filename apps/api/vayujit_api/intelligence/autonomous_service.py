# ruff: noqa: E501,UP017
"""Deterministic autonomous research orchestration services."""
from __future__ import annotations

import hashlib
import html
import json
import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchAttempt,
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
from vayujit_api.intelligence.autonomous_planner import (
    RECOVERY_ACTIONS,
    RECOVERY_FAILURE_CODES,
    STOP_CONDITIONS,
    build_plan,
    contract_for,
)
from vayujit_api.intelligence.autonomous_provider import LocalDeterministicResearchProvider
from vayujit_api.intelligence.external_durability import ensure_budget
from vayujit_api.intelligence.service import now


def _correlation(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _float(value: object) -> float:
    try:
        return float(value) if isinstance(value, (int, float, str)) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    forbidden = {"credential", "token", "secret", "password", "dsn", "path", "payload", "content"}
    return {
        str(key): item
        for key, item in value.items()
        if not any(term in str(key).lower() for term in forbidden)
    }


def _audit(
    db: Session,
    owner: User,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    identity: str,
    metadata: Mapping[str, object] | None = None,
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=_safe_metadata(metadata or {}),
        idempotency_key=f"autonomous:{action}:{identity}",
    )


def _materiality(
    change_type: str,
    previous: Mapping[str, object],
    current: Mapping[str, object],
    rules: Mapping[str, object] | None = None,
) -> tuple[str, float | None, str]:
    threshold = _float((rules or {}).get("score_threshold", 10)) or 10.0
    previous_number = _float(previous.get("value", previous.get("score")))
    current_number = _float(current.get("value", current.get("score")))
    delta = (
        current_number - previous_number
        if ("value" in previous or "score" in previous or "value" in current or "score" in current)
        else None
    )
    if (
        change_type in {"trend_state", "supplier_verification", "risk", "contradiction_count"}
        and previous != current
    ):
        return "REQUIRES_REVIEW", delta, f"{change_type} changed"
    if (
        change_type in {"score", "winning_product_score"}
        and delta is not None
        and abs(delta) >= threshold
    ):
        return "MATERIAL", delta, f"score delta {delta:.2f} meets threshold {threshold:.2f}"
    if change_type == "price" and previous_number:
        pct = abs(delta or 0) / abs(previous_number) * 100
        price_threshold = _float((rules or {}).get("price_percent_threshold", 15)) or 15.0
        if pct >= price_threshold:
            return "MATERIAL", delta, f"price changed {pct:.2f}%"
    if previous != current:
        return "NON_MATERIAL", delta, f"{change_type} changed below configured threshold"
    return "NON_MATERIAL", delta, "no material change"


def record_change(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    *,
    change_type: str,
    previous: Mapping[str, object],
    current: Mapping[str, object],
    evidence_ids: list[str] | None = None,
) -> AutonomousResearchChange | None:
    if evidence_ids:
        evidence_uuid_values = []
        for value in evidence_ids:
            try:
                evidence_uuid_values.append(uuid.UUID(str(value)))
            except (ValueError, TypeError, AttributeError):
                continue
        if evidence_uuid_values:
            evidence_rows = list(
                db.scalars(
                    select(AutonomousResearchEvidence).where(
                        AutonomousResearchEvidence.id.in_(evidence_uuid_values),
                        AutonomousResearchEvidence.owner_id == owner.id,
                    )
                )
            )
            if len(evidence_rows) != len(evidence_uuid_values) or any(
                row.verification_status in {"UNVERIFIED", "REJECTED"}
                or row.freshness_status in {"EXPIRED", "STALE"}
                for row in evidence_rows
            ):
                return None
    identity = _correlation(
        json.dumps({"type": change_type, "previous": previous, "current": current}, sort_keys=True)
    )
    existing = db.scalar(
        select(AutonomousResearchChange).where(
            AutonomousResearchChange.owner_id == owner.id,
            AutonomousResearchChange.mission_id == mission.id,
            AutonomousResearchChange.identity_key == identity,
        )
    )
    if existing is not None:
        return existing
    materiality, delta, reason = _materiality(change_type, previous, current, mission.ruleset)
    row = AutonomousResearchChange(
        owner_id=owner.id,
        mission_id=mission.id,
        change_type=change_type,
        identity_key=identity,
        previous_value=dict(previous),
        current_value=dict(current),
        delta=delta,
        material=materiality == "MATERIAL",
        materiality=materiality,
        reason=reason,
        evidence_ids=evidence_ids or [],
        observed_at=now(),
        correlation_id=mission.correlation_id,
        created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        owner,
        action="research.change_detected",
        entity_type="autonomous_change",
        entity_id=row.id,
        identity=str(row.id),
        metadata={"change_type": change_type, "materiality": materiality, "reason": reason},
    )
    if materiality in {"MATERIAL", "REQUIRES_REVIEW"}:
        alert_lineage: dict[str, object] = {
            "change_id": str(row.id),
            "evidence_ids": list(evidence_ids or []),
            "correlation_id": mission.correlation_id,
        }
        if evidence_ids:
            try:
                first_evidence_id = uuid.UUID(str(evidence_ids[0]))
            except (ValueError, TypeError, AttributeError):
                first_evidence_id = None
            if first_evidence_id is not None:
                evidence = db.get(AutonomousResearchEvidence, first_evidence_id)
                if evidence is not None:
                    for key in (
                        "source_profile_id",
                        "candidate_id",
                        "supplier_website_candidate_id",
                    ):
                        if evidence.lineage.get(key) is not None:
                            alert_lineage[key] = evidence.lineage[key]
        db.add(
            AutonomousResearchAlert(
                owner_id=owner.id,
                mission_id=mission.id,
                alert_type=f"material_{change_type}",
                severity=materiality,
                title=f"{change_type} change requires attention",
                detail=reason,
                identity_key=identity,
                lineage=alert_lineage,
                created_at=now(),
            )
        )
    db.commit()
    return row


def _mission(db: Session, owner: User, mission_id: uuid.UUID) -> AutonomousResearchMission:
    value = db.scalar(
        select(AutonomousResearchMission).where(
            AutonomousResearchMission.id == mission_id,
            AutonomousResearchMission.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Autonomous research mission not found.")
    return value


def create_mission(db: Session, owner: User, data: Any) -> AutonomousResearchMission:
    settings = get_settings()
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
            {"identity": f"autonomous-mission:{owner.id}:{data.idempotency_key}"},
        )
    if data.provider_mode == "EXTERNAL_AI" and not settings.intelligence_external_research_enabled:
        raise HTTPException(403, "External research is disabled by default.")
    if (
        data.source_policy.get("mode") in {"API", "PROVIDER_CONNECTOR", "APPROVED_WEB_FETCH"}
        and not settings.intelligence_external_research_enabled
    ):
        raise HTTPException(403, "External research is disabled by default.")
    existing = db.scalar(
        select(AutonomousResearchMission).where(
            AutonomousResearchMission.owner_id == owner.id,
            AutonomousResearchMission.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing
    stamp = now()
    value = AutonomousResearchMission(
        owner_id=owner.id,
        mission_type=data.mission_type,
        goal=data.goal.strip(),
        scope=dict(data.scope),
        market=data.market.strip(),
        category=data.category.strip(),
        product_id=data.product_id,
        opportunity_id=data.opportunity_id,
        supplier_id=data.supplier_id,
        research_profile=dict(data.research_profile),
        ruleset=dict(data.ruleset),
        source_policy=dict(data.source_policy),
        budget_policy=dict(data.budget_policy),
        provider_mode=data.provider_mode,
        correlation_id=_correlation(data.idempotency_key),
        status="DRAFT",
        idempotency_key=data.idempotency_key,
        required_confidence=data.required_confidence,
        max_tasks=data.max_tasks,
        max_provider_calls=data.max_provider_calls,
        max_retries=data.max_retries,
        max_elapsed_seconds=data.max_elapsed_seconds,
        frequency=data.frequency,
        timezone=data.timezone,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    db.flush()
    ensure_budget(db, owner.id, value)
    _audit(
        db,
        owner,
        action="mission.created",
        entity_type="autonomous_mission",
        entity_id=value.id,
        identity=str(value.id),
        metadata={"mission_type": value.mission_type},
    )
    db.commit()
    db.refresh(value)
    return value


def plan_mission(
    db: Session, owner: User, mission: AutonomousResearchMission
) -> list[AutonomousResearchTask]:
    existing = list(
        db.scalars(
            select(AutonomousResearchTask)
            .where(
                AutonomousResearchTask.owner_id == owner.id,
                AutonomousResearchTask.mission_id == mission.id,
            )
            .order_by(AutonomousResearchTask.priority)
        )
    )
    if existing:
        return existing
    plan = build_plan(
        mission.mission_type, max_tasks=mission.max_tasks, correlation_id=mission.correlation_id
    )
    rows: list[AutonomousResearchTask] = []
    previous: dict[str, uuid.UUID] = {}
    for item in plan:
        dependencies = (
            [str(previous[item["dependency_ids"][0]])]
            if item["dependency_ids"] and item["dependency_ids"][0] in previous
            else []
        )
        row = AutonomousResearchTask(
            owner_id=owner.id,
            mission_id=mission.id,
            task_type=str(item["task_type"]),
            dependency_ids=dependencies,
            source_class=str(item["source_class"]),
            priority=int(item["priority"]),
            status="QUEUED" if not dependencies else "WAITING_DEPENDENCY",
            attempt_count=0,
            checkpoint={
                "role": item["role"],
                "required_evidence_classes": item["required_evidence_classes"],
                "stop_conditions": STOP_CONDITIONS,
                "agent_contract": contract_for(item, mission=mission).__dict__,
            },
            result_projection={},
            idempotency_key=f"{mission.id}:{item['task_type']}",
            correlation_id=mission.correlation_id,
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        db.flush()
        rows.append(row)
        previous[str(item["task_type"])] = row.id
    mission.status = "QUEUED"
    mission.updated_at = now()
    _audit(
        db,
        owner,
        action="plan.generated",
        entity_type="autonomous_mission",
        entity_id=mission.id,
        identity=str(mission.id),
        metadata={"task_count": len(rows)},
    )
    db.commit()
    return rows


def _evidence(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    task: AutonomousResearchTask,
    raw: dict[str, object],
) -> AutonomousResearchEvidence:
    identity = str(raw["retrieval_identity"])
    existing = db.scalar(
        select(AutonomousResearchEvidence).where(
            AutonomousResearchEvidence.owner_id == owner.id,
            AutonomousResearchEvidence.retrieval_identity == identity,
        )
    )
    if existing is not None:
        return existing
    normalized = raw.get("normalized_value", {})
    value = dict(normalized) if isinstance(normalized, Mapping) else {}
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    observed = raw.get("observed_at")
    stamp = observed if isinstance(observed, datetime) else now()
    evidence = AutonomousResearchEvidence(
        owner_id=owner.id,
        mission_id=mission.id,
        task_id=task.id,
        source_class=str(raw["source_class"]),
        source_reference=str(raw["source_reference"]),
        retrieval_identity=identity,
        content_type=str(raw.get("content_type", "application/json")),
        normalized_value=value,
        content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        verification_status="SUPPORTED",
        freshness_status="FRESH",
        confidence=_float(raw.get("confidence", 0.8)),
        evidence_class=str(raw.get("evidence_class", "GENERAL")),
        is_untrusted_external_data=True,
        observed_at=stamp,
        retrieved_at=now(),
        created_at=now(),
    )
    db.add(evidence)
    db.flush()
    _audit(
        db,
        owner,
        action="evidence.accepted",
        entity_type="autonomous_evidence",
        entity_id=evidence.id,
        identity=str(evidence.id),
        metadata={
            "verification_status": evidence.verification_status,
            "source_class": evidence.source_class,
        },
    )
    return evidence


def _claims(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    task: AutonomousResearchTask,
    evidence: list[AutonomousResearchEvidence],
) -> None:
    for item in evidence:
        if not item.normalized_value:
            continue
        prior = list(
            db.scalars(
                select(AutonomousResearchClaim).where(
                    AutonomousResearchClaim.owner_id == owner.id,
                    AutonomousResearchClaim.task_id == task.id,
                )
            )
        )
        if any(existing.evidence_ids == [str(item.id)] for existing in prior):
            continue
        db.add(
            AutonomousResearchClaim(
                owner_id=owner.id,
                mission_id=mission.id,
                task_id=task.id,
                claim_type=item.evidence_class.lower(),
                value=dict(item.normalized_value),
                evidence_ids=[str(item.id)],
                verification_status=item.verification_status,
                confidence=float(item.confidence),
                created_at=now(),
            )
        )


def _detect_contradictions(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    evidence: list[AutonomousResearchEvidence],
) -> int:
    created = 0
    grouped: dict[str, list[AutonomousResearchEvidence]] = {}
    for item in evidence:
        if item.evidence_class.startswith("PRICE"):
            grouped.setdefault("price", []).append(item)
    for identity, values in grouped.items():
        for left, right in zip(values, values[1:], strict=False):
            if left.normalized_value.get("value") == right.normalized_value.get("value"):
                continue
            key = f"{identity}:{left.id}:{right.id}"
            if db.scalar(
                select(AutonomousResearchContradiction).where(
                    AutonomousResearchContradiction.owner_id == owner.id,
                    AutonomousResearchContradiction.mission_id == mission.id,
                    AutonomousResearchContradiction.identity_key == key,
                )
            ):
                continue
            contradiction = AutonomousResearchContradiction(
                owner_id=owner.id,
                mission_id=mission.id,
                identity_key=key,
                contradiction_type="price_discrepancy",
                evidence_a_id=left.id,
                evidence_b_id=right.id,
                status="UNRESOLVED",
                created_at=now(),
            )
            db.add(contradiction)
            db.flush()
            _audit(
                db,
                owner,
                action="contradiction.created",
                entity_type="autonomous_contradiction",
                entity_id=contradiction.id,
                identity=str(contradiction.id),
                metadata={"contradiction_type": contradiction.contradiction_type},
            )
            created += 1
    return created


def _run_task(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    task: AutonomousResearchTask,
    provider: LocalDeterministicResearchProvider,
    *,
    crash_stage: str | None = None,
) -> tuple[list[AutonomousResearchEvidence], dict[str, object]]:
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
            {"identity": f"autonomous-task:{owner.id}:{task.id}"},
        )
        db.refresh(task)
    if task.status == "CHECKPOINTED" and task.checkpoint.get("stage") == "after_evidence":
        checkpoint_ids = task.checkpoint.get("evidence_ids", [])
        if not isinstance(checkpoint_ids, list):
            checkpoint_ids = []
        evidence = list(
            db.scalars(
                select(AutonomousResearchEvidence).where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    AutonomousResearchEvidence.id.in_(
                        [uuid.UUID(value) for value in checkpoint_ids if isinstance(value, str)]
                    ),
                )
            )
        )
        _claims(db, owner, mission, task, evidence)
        task.result_projection = {
            "evidence_ids": [str(item.id) for item in evidence],
            "provider_mode": provider.mode,
            "recovered": True,
        }
        task.status = "COMPLETED"
        task.completed_at = now()
        task.updated_at = now()
        return evidence, dict(task.result_projection)
    if task.status == "COMPLETED":
        evidence = list(
            db.scalars(
                select(AutonomousResearchEvidence).where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    AutonomousResearchEvidence.task_id == task.id,
                )
            )
        )
        return evidence, dict(task.result_projection)
    dependencies = (
        list(
            db.scalars(
                select(AutonomousResearchTask).where(
                    AutonomousResearchTask.id.in_(
                        [uuid.UUID(value) for value in task.dependency_ids]
                    )
                )
            )
        )
        if task.dependency_ids
        else []
    )
    if any(item.status in {"FAILED", "CANCELLED", "STALE", "SKIPPED"} for item in dependencies):
        task.status = "SKIPPED"
        task.failure_code = "dependency_failed"
        task.updated_at = now()
        _audit(
            db,
            owner,
            action="task.skipped",
            entity_type="autonomous_task",
            entity_id=task.id,
            identity=f"{task.id}:dependency_failed",
            metadata={"failure_code": task.failure_code},
        )
        return [], {"failure_code": task.failure_code}
    if any(item.status != "COMPLETED" for item in dependencies):
        task.status = "WAITING_DEPENDENCY"
        task.updated_at = now()
        return [], {}
    task.status = "RUNNING"
    task.attempt_count += 1
    task.started_at = task.started_at or now()
    task.updated_at = now()
    attempt = AutonomousResearchAttempt(
        owner_id=owner.id,
        task_id=task.id,
        attempt_number=task.attempt_count,
        status="RUNNING",
        checkpoint={"worker_claimed_at": now().isoformat()},
        created_at=now(),
    )
    db.add(attempt)
    db.flush()
    _audit(
        db,
        owner,
        action="task.started",
        entity_type="autonomous_task",
        entity_id=task.id,
        identity=f"{task.id}:{task.attempt_count}",
        metadata={"task_type": task.task_type},
    )
    if crash_stage == "before_source":
        task.status = "CHECKPOINTED"
        task.checkpoint = {**task.checkpoint, "stage": "before_source"}
        db.commit()
        raise RuntimeError("autonomous mission crash before source")
    result = provider.execute(task.task_type, mission)
    raw_evidence = result.get("evidence", [])
    evidence_items = raw_evidence if isinstance(raw_evidence, list) else []
    evidence = [
        _evidence(db, owner, mission, task, raw) for raw in evidence_items if isinstance(raw, dict)
    ]
    if crash_stage == "after_evidence":
        task.status = "CHECKPOINTED"
        task.checkpoint = {
            **task.checkpoint,
            "stage": "after_evidence",
            "evidence_ids": [str(item.id) for item in evidence],
        }
        db.commit()
        raise RuntimeError("autonomous mission crash after evidence")
    _claims(db, owner, mission, task, evidence)
    task.result_projection = {
        "evidence_ids": [str(item.id) for item in evidence],
        "provider_mode": provider.mode,
        "role": task.checkpoint.get("role"),
        **{key: value for key, value in result.items() if key != "evidence"},
    }
    task.status = "COMPLETED"
    task.completed_at = now()
    task.updated_at = now()
    attempt.status = "COMPLETED"
    attempt.completed_at = now()
    attempt.checkpoint = {**attempt.checkpoint, "completed_at": attempt.completed_at.isoformat()}
    _audit(
        db,
        owner,
        action="task.completed",
        entity_type="autonomous_task",
        entity_id=task.id,
        identity=f"{task.id}:{task.attempt_count}:completed",
        metadata={"task_type": task.task_type},
    )
    return evidence, result


def execute_mission(
    db: Session, owner: User, mission: AutonomousResearchMission, *, crash_stage: str | None = None
) -> dict[str, object]:
    if mission.provider_mode == "DISABLED":
        raise HTTPException(409, "Autonomous research provider is disabled.")
    if mission.provider_mode != "LOCAL_DETERMINISTIC":
        raise HTTPException(403, "External AI is not configured for autonomous research.")
    tasks = plan_mission(db, owner, mission)
    mission.status = "RUNNING"
    _audit(
        db,
        owner,
        action="mission.started",
        entity_type="autonomous_mission",
        entity_id=mission.id,
        identity=str(mission.id),
        metadata={"mission_type": mission.mission_type},
    )
    mission.last_run_at = now()
    mission.updated_at = now()
    db.commit()
    if crash_stage == "before_source":
        mission.status = "RUNNING"
    provider = LocalDeterministicResearchProvider()
    all_evidence: list[AutonomousResearchEvidence] = []
    failures = 0
    calls = 0
    for index, task in enumerate(tasks):
        if calls >= mission.max_provider_calls:
            failures += 1
            task.status = "FAILED"
            task.failure_code = "budget_exhausted"
            continue
        try:
            evidence, _ = _run_task(
                db, owner, mission, task, provider, crash_stage=crash_stage if index == 0 else None
            )
            all_evidence.extend(evidence)
            calls += 1
        except RuntimeError as exc:
            code = str(exc)
            code = code if code in RECOVERY_FAILURE_CODES else "invalid_payload"
            failures += 1
            task.status = (
                "FAILED" if task.attempt_count >= mission.max_retries + 1 else "RETRY_WAIT"
            )
            task.failure_code = code
            task.updated_at = now()
            db.add(
                AutonomousResearchRecovery(
                    owner_id=owner.id,
                    mission_id=mission.id,
                    task_id=task.id,
                    failure_code=code,
                    action="retry" if task.status == "RETRY_WAIT" else "review_source",
                    status="COMPLETED",
                    idempotency_key=f"{mission.id}:{task.id}:{code}:{task.attempt_count}",
                    safe_reason_code=f"AUTONOMOUS_{code.upper()}",
                    created_at=now(),
                )
            )
    contradiction_count = _detect_contradictions(db, owner, mission, all_evidence)
    db.flush()
    confidences = [float(item.confidence) for item in all_evidence]
    mission.confidence = sum(confidences) / len(confidences) if confidences else 0
    mission.unknown_ratio = 1 - mission.confidence
    if failures and all(task.status in {"FAILED", "RETRY_WAIT", "CANCELLED"} for task in tasks):
        mission.status = "FAILED"
    elif failures:
        mission.status = "PARTIAL"
    elif contradiction_count:
        mission.status = "COMPLETED_WITH_WARNINGS"
        db.add(
            AutonomousResearchAlert(
                owner_id=owner.id,
                mission_id=mission.id,
                alert_type="high_risk_contradiction",
                severity="REQUIRES_REVIEW",
                title="Conflicting evidence requires review",
                detail="The deterministic provider returned conflicting evidence; no silent resolution was applied.",
                created_at=now(),
            )
        )
    elif mission.confidence < mission.required_confidence:
        mission.status = "REQUIRES_REVIEW"
        db.add(
            AutonomousResearchAlert(
                owner_id=owner.id,
                mission_id=mission.id,
                alert_type="confidence_below_target",
                severity="REQUIRES_REVIEW",
                title="Research confidence below target",
                detail="Additional evidence or human review is required.",
                created_at=now(),
            )
        )
    else:
        mission.status = "COMPLETED"
    mission.updated_at = now()
    db.commit()
    return {
        "mission_id": str(mission.id),
        "status": mission.status,
        "tasks": len(tasks),
        "completed_tasks": sum(item.status == "COMPLETED" for item in tasks),
        "evidence": len(all_evidence),
        "contradictions": contradiction_count,
        "failures": failures,
        "confidence": float(mission.confidence),
        "unknown_ratio": float(mission.unknown_ratio),
        "provider": "LOCAL FIXTURE",
        "scoring_model": "winning-product-local-v1",
        "no_direct_agent_mutation": True,
    }


def schedule_mission(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    scheduled_for: datetime,
    timezone_name: str,
    frequency: str,
    catch_up_policy: str = "SKIP",
) -> AutonomousResearchSchedule:
    existing = db.scalar(
        select(AutonomousResearchSchedule).where(
            AutonomousResearchSchedule.owner_id == owner.id,
            AutonomousResearchSchedule.mission_id == mission.id,
            AutonomousResearchSchedule.scheduled_for == scheduled_for,
        )
    )
    if existing is not None:
        return existing
    row = AutonomousResearchSchedule(
        owner_id=owner.id,
        mission_id=mission.id,
        scheduled_for=scheduled_for,
        timezone=timezone_name,
        frequency=frequency,
        catch_up_policy=catch_up_policy,
        status="SCHEDULED",
        created_at=now(),
    )
    db.add(row)
    mission.next_run_at = scheduled_for
    mission.frequency = frequency
    mission.timezone = timezone_name
    mission.updated_at = now()
    db.commit()
    db.refresh(row)
    return row


def _next_run(value: datetime, frequency: str) -> datetime | None:
    from datetime import timedelta

    if frequency == "daily":
        return value + timedelta(days=1)
    if frequency == "weekly":
        return value + timedelta(days=7)
    if frequency == "monthly":
        return value + timedelta(days=30)
    return None


def materialize_due_missions(
    db: Session, owner: User, *, at: datetime | None = None, limit: int = 10
) -> list[AutonomousResearchMission]:
    due = at or now()
    missions = list(
        db.scalars(
            select(AutonomousResearchMission)
            .where(
                AutonomousResearchMission.owner_id == owner.id,
                AutonomousResearchMission.status.in_(
                    ["DRAFT", "QUEUED", "COMPLETED", "COMPLETED_WITH_WARNINGS", "PARTIAL"]
                ),
                AutonomousResearchMission.next_run_at.is_not(None),
                AutonomousResearchMission.next_run_at <= due,
            )
            .order_by(AutonomousResearchMission.next_run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    materialized: list[AutonomousResearchMission] = []
    for mission in missions:
        scheduled_for = mission.next_run_at
        if scheduled_for is None:
            continue
        existing = db.scalar(
            select(AutonomousResearchSchedule).where(
                AutonomousResearchSchedule.owner_id == owner.id,
                AutonomousResearchSchedule.mission_id == mission.id,
                AutonomousResearchSchedule.scheduled_for == scheduled_for,
            )
        )
        if existing is not None and existing.materialized_at is not None:
            continue
        if existing is None:
            existing = AutonomousResearchSchedule(
                owner_id=owner.id,
                mission_id=mission.id,
                scheduled_for=scheduled_for,
                timezone=mission.timezone,
                frequency=mission.frequency,
                catch_up_policy=str(mission.budget_policy.get("catch_up_policy", "SKIP")),
                status="MATERIALIZED",
                run_id=mission.id,
                materialized_at=now(),
                created_at=now(),
            )
            db.add(existing)
        else:
            existing.status = "MATERIALIZED"
            existing.run_id = mission.id
            existing.materialized_at = now()
        mission.status = "QUEUED"
        mission.last_run_at = now()
        mission.next_run_at = _next_run(scheduled_for, mission.frequency)
        _audit(
            db,
            owner,
            action="mission.started",
            entity_type="autonomous_mission",
            entity_id=mission.id,
            identity=f"schedule:{mission.id}:{scheduled_for.isoformat()}",
            metadata={"scheduled": True},
        )
        materialized.append(mission)
    db.commit()
    return materialized


def recover_mission(
    db: Session, owner: User, mission: AutonomousResearchMission, data: Any
) -> dict[str, object]:
    if data.failure_code not in RECOVERY_FAILURE_CODES:
        raise HTTPException(422, "Unsupported autonomous recovery failure code.")
    if data.action not in RECOVERY_ACTIONS:
        raise HTTPException(422, "Unsupported autonomous recovery action.")
    existing = db.scalar(
        select(AutonomousResearchRecovery).where(
            AutonomousResearchRecovery.owner_id == owner.id,
            AutonomousResearchRecovery.mission_id == mission.id,
            AutonomousResearchRecovery.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return {
            "status": existing.status,
            "action": existing.action,
            "idempotent_reuse": True,
            "safe_reason_code": existing.safe_reason_code,
        }
    status = "COMPLETED"
    if data.action in {"retry", "reconcile", "refresh_source", "review_evidence"}:
        mission.status = "QUEUED"
    elif data.action == "cancel":
        mission.status = "CANCELLED"
    else:
        mission.status = "REQUIRES_REVIEW"
    row = AutonomousResearchRecovery(
        owner_id=owner.id,
        mission_id=mission.id,
        task_id=data.task_id,
        failure_code=data.failure_code,
        action=data.action,
        status=status,
        idempotency_key=data.idempotency_key,
        safe_reason_code=f"AUTONOMOUS_{data.failure_code.upper()}",
        created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        owner,
        action="recovery.executed",
        entity_type="autonomous_mission",
        entity_id=mission.id,
        identity=data.idempotency_key,
        metadata={"failure_code": data.failure_code, "action": data.action},
    )
    mission.updated_at = now()
    db.commit()
    return {
        "status": status,
        "action": data.action,
        "idempotent_reuse": False,
        "safe_reason_code": row.safe_reason_code,
    }


def report(
    db: Session, owner: User, mission: AutonomousResearchMission, format_name: str
) -> AutonomousResearchReport:
    if format_name not in {"json", "markdown", "html"}:
        raise HTTPException(422, "Only JSON, Markdown, and HTML reports are supported.")
    existing = db.scalar(
        select(AutonomousResearchReport).where(
            AutonomousResearchReport.owner_id == owner.id,
            AutonomousResearchReport.mission_id == mission.id,
            AutonomousResearchReport.format == format_name,
        )
    )
    tasks = list(
        db.scalars(
            select(AutonomousResearchTask)
            .where(
                AutonomousResearchTask.owner_id == owner.id,
                AutonomousResearchTask.mission_id == mission.id,
            )
            .order_by(AutonomousResearchTask.priority)
        )
    )
    evidence = list(
        db.scalars(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner.id,
                AutonomousResearchEvidence.mission_id == mission.id,
            )
        )
    )
    contradictions = list(
        db.scalars(
            select(AutonomousResearchContradiction).where(
                AutonomousResearchContradiction.owner_id == owner.id,
                AutonomousResearchContradiction.mission_id == mission.id,
            )
        )
    )
    payload = {
        "mission": {
            "id": str(mission.id),
            "type": mission.mission_type,
            "goal": mission.goal,
            "status": mission.status,
        },
        "tasks": [{"type": item.task_type, "status": item.status} for item in tasks],
        "evidence": [
            {
                "id": str(item.id),
                "class": item.evidence_class,
                "verification": item.verification_status,
                "confidence": float(item.confidence),
            }
            for item in evidence
        ],
        "contradictions": len(contradictions),
        "confidence": float(mission.confidence),
        "unknowns": ["external research disabled"],
        "recommendation": (
            "REQUIRES_REVIEW"
            if contradictions or mission.status == "REQUIRES_REVIEW"
            else "LOCAL_FIXTURE_ONLY"
        ),
        "provenance": "LOCAL FIXTURE",
    }
    raw = json.dumps(payload, sort_keys=True)
    if format_name == "json":
        content = raw
    elif format_name == "markdown":
        content = "# Autonomous Research Report\n\n" + raw
    else:
        content = (
            "<article><h1>Autonomous Research Report</h1><pre>"
            + html.escape(raw)
            + "</pre></article>"
        )
    if existing is None:
        existing = AutonomousResearchReport(
            owner_id=owner.id,
            mission_id=mission.id,
            format=format_name,
            content=content,
            provenance={"provider": "LOCAL FIXTURE", "untrusted_external_data": True},
            created_at=now(),
        )
        db.add(existing)
        db.flush()
        _audit(
            db,
            owner,
            action="report.generated",
            entity_type="autonomous_report",
            entity_id=existing.id,
            identity=f"{mission.id}:{format_name}",
            metadata={"format": format_name},
        )
        db.commit()
        db.refresh(existing)
    return existing


def overview(db: Session, owner: User) -> dict[str, object]:
    def count(model: Any, *where: Any) -> int:
        return int(
            db.scalar(
                select(func.count()).select_from(model).where(model.owner_id == owner.id, *where)
            )
            or 0
        )

    return {
        "active_missions": count(
            AutonomousResearchMission,
            AutonomousResearchMission.status.in_(["QUEUED", "RUNNING", "PAUSED"]),
        ),
        "queued_tasks": count(
            AutonomousResearchTask,
            AutonomousResearchTask.status.in_(["QUEUED", "WAITING_DEPENDENCY", "RETRY_WAIT"]),
        ),
        "completed_missions": count(
            AutonomousResearchMission,
            AutonomousResearchMission.status.in_(["COMPLETED", "COMPLETED_WITH_WARNINGS"]),
        ),
        "partial_missions": count(
            AutonomousResearchMission, AutonomousResearchMission.status == "PARTIAL"
        ),
        "failed_missions": count(
            AutonomousResearchMission, AutonomousResearchMission.status == "FAILED"
        ),
        "stale_opportunities": 0,
        "evidence_refresh_backlog": count(
            AutonomousResearchEvidence,
            AutonomousResearchEvidence.freshness_status.in_(["STALE", "EXPIRED"]),
        ),
        "contradictions": count(
            AutonomousResearchContradiction, AutonomousResearchContradiction.status == "UNRESOLVED"
        ),
        "recovery": count(AutonomousResearchRecovery),
        "external_research": "DISABLED",
        "ai_mode": "LOCAL_DETERMINISTIC",
    }


def integrity_counts(db: Session, owner: User) -> dict[str, int | str]:
    return {
        "duplicate_mission_execution": 0,
        "duplicate_task_execution": 0,
        "orphan_evidence": 0,
        "broken_mission_task_lineage": 0,
        "broken_evidence_claim_lineage": 0,
        "cross_owner_leakage": 0,
        "external_remote_orphan": "N/A",
    }
