"""PR-6B deterministic explainable synthesis over PR-6A readiness snapshots."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.decision_evidence_models import DecisionEvidenceSnapshot
from vayujit_api.intelligence.decision_readiness_service import (
    create_decision_snapshot,
    serialize_snapshot,
)
from vayujit_api.intelligence.decision_synthesis_models import (
    SYNTHESIS_POLICY_VERSION,
    DecisionSynthesisSnapshot,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _as_list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _reason(
    item: dict[str, Any], *, category: str, blocking: bool, source_authority: str = "PR-6A"
) -> dict[str, Any]:
    return {
        "code": str(item.get("code", "UNKNOWN_REASON")),
        "category": category,
        "severity": str(item.get("severity", "INFO")),
        "source_authority": str(item.get("source_authority", source_authority)),
        "source_reference": item.get("source_reference") or item.get("source"),
        "trust": item.get("trust") or item.get("provenance"),
        "explanation": str(item.get("message", "Evidence requires human review.")),
        "blocking": blocking,
    }


def _reason_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("code")), str(row.get("explanation")), str(row.get("category")))


def _reason_rows(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _as_list(readiness.get("blockers")):
        category = "hard_constraint" if item.get("code") == "CAPITAL_DOES_NOT_FIT" else "blocker"
        rows.append(_reason(item, category=category, blocking=True))
    for item in _as_list(readiness.get("contradictions")):
        rows.append(_reason(item, category="contradiction", blocking=True))
    for item in _as_list(readiness.get("warnings")):
        rows.append(_reason(item, category="warning", blocking=False))
    for item in _as_list(readiness.get("unknowns")):
        category = (
            "required_evidence"
            if item.get("severity") in {"HIGH", "MEDIUM"}
            else "optional_unknown"
        )
        rows.append(_reason(item, category=category, blocking=False))
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(_reason_key(row), row)

    priority = {
        "hard_constraint": 0,
        "blocker": 1,
        "contradiction": 2,
        "required_evidence": 3,
        "warning": 4,
        "optional_unknown": 5,
    }
    return sorted(
        unique.values(),
        key=lambda row: (
            priority.get(str(row.get("category")), 9),
            str(row.get("code")),
            str(row.get("explanation")),
        ),
    )


def _capital_state(readiness: dict[str, Any]) -> str:
    economics = readiness.get("evidence_summary", {}).get("economics", {})
    value = economics.get("capital_fit")
    return str(value) if value else "UNKNOWN"


def map_readiness_to_posture(readiness: dict[str, Any]) -> str:
    """Map canonical PR-6A state; this never recalculates readiness."""

    blockers = _as_list(readiness.get("blockers"))
    capital_state = _capital_state(readiness)
    if (
        any(row.get("code") == "CAPITAL_DOES_NOT_FIT" for row in blockers)
        and capital_state == "DOES_NOT_FIT"
    ):
        return "CONSTRAINT_FAILED"
    state = str(readiness.get("readiness_state", "BLOCKED"))
    if state == "READY":
        return "HOLD" if blockers else "READY_FOR_HUMAN_DECISION"
    if state == "NEEDS_EVIDENCE":
        return "HOLD" if blockers else "CONTINUE_RESEARCH"
    return "HOLD"


def _safe_actions(posture: str, reasons: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    action_by_code = {
        "PRODUCT_SELECTION_REQUIRED": ("SELECT_PRODUCT_HUMAN", "Select a product explicitly", []),
        "DEMAND_EVIDENCE_MISSING": ("COLLECT_DEMAND_EVIDENCE", "Collect demand evidence", []),
        "DEMAND_EVIDENCE_REQUIRED": ("COLLECT_DEMAND_EVIDENCE", "Collect demand evidence", []),
        "LIVE_SUPPLIER_EVIDENCE_MISSING": (
            "OBTAIN_LIVE_SUPPLIER_EVIDENCE",
            "Obtain live supplier evidence",
            [],
        ),
        "SUPPLIER_NOT_VERIFIED": (
            "VERIFY_SUPPLIER_EVIDENCE",
            "Review supplier verification evidence",
            ["OBTAIN_LIVE_SUPPLIER_EVIDENCE"],
        ),
        "HUMAN_SUPPLIER_SHORTLIST_MISSING": (
            "SHORTLIST_SUPPLIER_HUMAN",
            "Record a human supplier shortlist decision",
            [],
        ),
        "ECONOMICS_CALCULATION_REQUIRED": (
            "COMPLETE_ECONOMICS_SCENARIO",
            "Complete the bounded economics scenario",
            [],
        ),
        "UNIT_ECONOMICS_REQUIRED": (
            "COMPLETE_UNIT_ECONOMICS",
            "Complete the bounded unit-economics scenario",
            ["COMPLETE_ECONOMICS_SCENARIO"],
        ),
        "CAPITAL_DOES_NOT_FIT": (
            "REVIEW_CAPITAL_CONSTRAINT",
            "Review the explicit capital constraint",
            [],
        ),
        "MATERIAL_CONTRADICTION": (
            "RESOLVE_CONTRADICTION",
            "Resolve the material contradiction",
            [],
        ),
    }
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in reasons:
        code = str(row.get("code"))
        spec = action_by_code.get(code)
        if spec is None or spec[0] in seen:
            continue
        seen.add(spec[0])
        actions.append(
            {
                "code": spec[0],
                "label": spec[1],
                "reason": row["explanation"],
                "target": target,
                "depends_on": spec[2],
                "external_action": False,
                "human_controlled": True,
            }
        )
    if posture == "READY_FOR_HUMAN_DECISION":
        actions.append(
            {
                "code": "HUMAN_DECISION_REVIEW",
                "label": "Review the evidence and record a human decision",
                "reason": (
                    "Readiness is bounded; no approval or recommendation is created automatically."
                ),
                "target": target,
                "depends_on": [],
                "external_action": False,
                "human_controlled": True,
            }
        )
    if not actions:
        actions.append(
            {
                "code": "REVIEW_EVIDENCE",
                "label": "Review the evidence record",
                "reason": "Review the bounded evidence before taking any consequential action.",
                "target": target,
                "depends_on": [],
                "external_action": False,
                "human_controlled": True,
            }
        )
    return actions


def _explanation(posture: str, primary: dict[str, Any]) -> str:
    text = str(primary.get("explanation", "The evidence remains bounded."))
    return {
        "CONTINUE_RESEARCH": f"Continue research. {text}",
        "HOLD": f"Hold for human review. {text}",
        "READY_FOR_HUMAN_DECISION": (
            "Evidence is ready for a human decision review; "
            "this is not an approval or recommendation."
        ),
        "CONSTRAINT_FAILED": f"The explicit constraint is not satisfied in this scenario. {text}",
    }[posture]


def synthesize_from_readiness(
    readiness: dict[str, Any],
    *,
    snapshot_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> dict[str, Any]:
    """Build a deterministic projection from a serialized PR-6A snapshot."""

    posture = map_readiness_to_posture(readiness)
    reasons = _reason_rows(readiness)
    if reasons:
        primary = dict(reasons[0])
    else:
        code = {
            "CONTINUE_RESEARCH": "RESEARCH_EVIDENCE_REQUIRED",
            "HOLD": "HUMAN_REVIEW_REQUIRED",
            "READY_FOR_HUMAN_DECISION": "READINESS_READY_HUMAN_REVIEW",
            "CONSTRAINT_FAILED": "EXPLICIT_CONSTRAINT_FAILED",
        }[posture]
        primary = {
            "code": code,
            "category": "required_evidence" if posture == "CONTINUE_RESEARCH" else "readiness",
            "severity": "INFO",
            "source_authority": "PR-6A",
            "source_reference": readiness.get("input_references"),
            "trust": "CANONICAL",
            "explanation": "The canonical readiness state requires bounded human review.",
            "blocking": posture in {"HOLD", "CONSTRAINT_FAILED"},
        }
    evidence_value = readiness.get("evidence_summary")
    evidence: dict[str, Any] = evidence_value if isinstance(evidence_value, dict) else {}
    trust_value = readiness.get("trust_environment")
    trust: dict[str, Any] = trust_value if isinstance(trust_value, dict) else {}
    economics_value = evidence.get("economics")
    economics: dict[str, Any] = economics_value if isinstance(economics_value, dict) else {}
    product_selection_value = trust.get("product_selection")
    product_selection: dict[str, Any] = (
        product_selection_value if isinstance(product_selection_value, dict) else {}
    )
    supporting: list[dict[str, Any]] = [
        {
            "code": "PR6A_EVIDENCE_SNAPSHOT",
            "source": "PR-6A",
            "reference": str(snapshot_id),
            "state": readiness.get("readiness_state"),
        },
        {"code": "PRODUCT_EVIDENCE", "source": "PR-6A", "value": evidence.get("product", {})},
        {
            "code": "PRODUCT_SELECTION",
            "source": "PR-6A",
            "value": evidence.get("product_selected", False),
            "trust": product_selection.get("trust", "UNKNOWN"),
        },
        {"code": "ECONOMICS_CONTEXT", "source": "PR-5A/PR-5B/PR-5C", "value": economics},
    ]
    limitations = _as_list(readiness.get("limitations"))
    payload = {
        "owner_id": str(owner_id),
        "opportunity_id": str(opportunity_id),
        "decision_evidence_snapshot_id": str(snapshot_id),
        "decision_target": str(readiness.get("decision_target")),
        "readiness_state": str(readiness.get("readiness_state")),
        "readiness_policy_version": str(readiness.get("policy_version")),
        "synthesis_policy_version": SYNTHESIS_POLICY_VERSION,
        "posture": posture,
        "primary_reason": primary,
        "reasons": reasons,
        "supporting_evidence": supporting,
        "blockers": _as_list(readiness.get("blockers")),
        "warnings": _as_list(readiness.get("warnings")),
        "unknowns": _as_list(readiness.get("unknowns")),
        "contradictions": _as_list(readiness.get("contradictions")),
        "limitations": limitations,
        "trust_summary": trust,
        "economics_summary": economics,
        "capital_fit_state": _capital_state(readiness),
        "safe_next_actions": _safe_actions(posture, reasons, str(readiness.get("decision_target"))),
        "human_review_required": True,
    }
    payload["input_fingerprint"] = _fingerprint(payload)
    payload["explanation"] = _explanation(posture, primary)
    return payload


def _owner_snapshot(
    db: Session, owner: User, opportunity_id: uuid.UUID, snapshot_id: uuid.UUID
) -> DecisionEvidenceSnapshot:
    row = db.scalar(
        select(DecisionEvidenceSnapshot).where(
            DecisionEvidenceSnapshot.id == snapshot_id,
            DecisionEvidenceSnapshot.owner_id == owner.id,
            DecisionEvidenceSnapshot.opportunity_id == opportunity_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Decision evidence snapshot not found in the owner scope.")
    return row


def _opportunity(db: Session, owner: User, opportunity_id: uuid.UUID) -> ProductOpportunity:
    row = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Product opportunity not found.")
    return row


def serialize_synthesis(row: DecisionSynthesisSnapshot) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "goal_id": str(row.goal_id) if row.goal_id is not None else None,
        "supplier_id": str(row.supplier_id) if row.supplier_id is not None else None,
        "decision_evidence_snapshot_id": str(row.decision_evidence_snapshot_id),
        "decision_target": row.decision_target,
        "readiness_state": row.readiness_state,
        "readiness_policy_version": row.readiness_policy_version,
        "synthesis_policy_version": row.synthesis_policy_version,
        "posture": row.posture,
        "primary_reason": row.primary_reason,
        "reasons": row.reasons,
        "supporting_evidence": row.supporting_evidence,
        "blockers": row.blockers,
        "warnings": row.warnings,
        "unknowns": row.unknowns,
        "contradictions": row.contradictions,
        "limitations": row.limitations,
        "trust_summary": row.trust_summary,
        "economics_summary": row.economics_summary,
        "capital_fit_state": row.capital_fit_state,
        "safe_next_actions": row.safe_next_actions,
        "human_review_required": row.human_review_required,
        "input_fingerprint": row.input_fingerprint,
        "idempotency_key": row.idempotency_key,
        "explanation": row.explanation,
        "created_at": row.created_at.isoformat(),
        "external_writes": [],
        "recommendation": None,
    }


def create_synthesis(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str = "COMMERCIAL_ASSESSMENT",
    snapshot_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> DecisionSynthesisSnapshot:
    target = target.upper()
    _opportunity(db, owner, opportunity_id)
    snapshot = (
        _owner_snapshot(db, owner, opportunity_id, snapshot_id)
        if snapshot_id is not None
        else create_decision_snapshot(
            db,
            owner,
            opportunity_id,
            target=target,
            assessment_id=assessment_id,
            goal_id=goal_id,
            supplier_id=supplier_id,
        )
    )
    if snapshot.decision_target != target:
        raise HTTPException(
            422, "Decision evidence snapshot target does not match synthesis target."
        )
    readiness = serialize_snapshot(snapshot)
    payload = synthesize_from_readiness(
        readiness, snapshot_id=snapshot.id, opportunity_id=opportunity_id, owner_id=owner.id
    )
    existing = db.scalar(
        select(DecisionSynthesisSnapshot).where(
            DecisionSynthesisSnapshot.owner_id == owner.id,
            DecisionSynthesisSnapshot.input_fingerprint == payload["input_fingerprint"],
        )
    )
    if existing is not None:
        return existing
    row = DecisionSynthesisSnapshot(
        owner_id=owner.id,
        goal_id=snapshot.goal_id,
        opportunity_id=opportunity_id,
        supplier_id=snapshot.supplier_id,
        decision_evidence_snapshot_id=snapshot.id,
        decision_target=snapshot.decision_target,
        readiness_state=snapshot.readiness_state,
        readiness_policy_version=snapshot.policy_version,
        synthesis_policy_version=SYNTHESIS_POLICY_VERSION,
        posture=payload["posture"],
        primary_reason=payload["primary_reason"],
        reasons=payload["reasons"],
        supporting_evidence=payload["supporting_evidence"],
        blockers=payload["blockers"],
        warnings=payload["warnings"],
        unknowns=payload["unknowns"],
        contradictions=payload["contradictions"],
        limitations=payload["limitations"],
        trust_summary=payload["trust_summary"],
        economics_summary=payload["economics_summary"],
        capital_fit_state=payload["capital_fit_state"],
        safe_next_actions=payload["safe_next_actions"],
        human_review_required=True,
        input_fingerprint=payload["input_fingerprint"],
        idempotency_key=idempotency_key or f"decision-synthesis:{payload['input_fingerprint']}",
        created_at=_now(),
        explanation=payload["explanation"],
        notes="PR-6B immutable synthesis; no recommendation or external action.",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(DecisionSynthesisSnapshot).where(
                DecisionSynthesisSnapshot.owner_id == owner.id,
                DecisionSynthesisSnapshot.input_fingerprint == payload["input_fingerprint"],
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(row)
    return row


def latest_synthesis(
    db: Session, owner: User, opportunity_id: uuid.UUID, target: str = "COMMERCIAL_ASSESSMENT"
) -> DecisionSynthesisSnapshot | None:
    return db.scalars(
        select(DecisionSynthesisSnapshot)
        .where(
            DecisionSynthesisSnapshot.owner_id == owner.id,
            DecisionSynthesisSnapshot.opportunity_id == opportunity_id,
            DecisionSynthesisSnapshot.decision_target == target.upper(),
        )
        .order_by(DecisionSynthesisSnapshot.created_at.desc())
    ).first()


def synthesis_history(
    db: Session, owner: User, opportunity_id: uuid.UUID, target: str = "COMMERCIAL_ASSESSMENT"
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(DecisionSynthesisSnapshot)
            .where(
                DecisionSynthesisSnapshot.owner_id == owner.id,
                DecisionSynthesisSnapshot.opportunity_id == opportunity_id,
                DecisionSynthesisSnapshot.decision_target == target.upper(),
            )
            .order_by(DecisionSynthesisSnapshot.created_at.desc())
        )
    )
    return [serialize_synthesis(row) for row in rows]


def project_latest_synthesis(
    db: Session, owner: User, opportunity_id: uuid.UUID, target: str = "COMMERCIAL_ASSESSMENT"
) -> dict[str, Any] | None:
    row = latest_synthesis(db, owner, opportunity_id, target)
    return serialize_synthesis(row) if row is not None else None
