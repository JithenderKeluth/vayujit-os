# ruff: noqa: E501,E702
"""Persisted intelligence handoff for trusted external observations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
)
from vayujit_api.intelligence.external_models import ExternalFetch

VERIFIER_VERSION = "external-verifier/1"
_ACCEPTED = {"SUPPORTED", "VERIFIED"}


def _domain(url: str | None) -> str:
    if not url:
        return ""
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def _canonical(value: str | None) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    host = (parts.hostname or "").lower().rstrip(".")
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{host}{path}" + (f"?{parts.query}" if parts.query else "")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def verify_external_evidence(
    candidate: Mapping[str, object],
    *,
    expected_owner_id: object | None = None,
    expected_correlation_id: str | None = None,
    expected_provider: str | None = None,
    expected_source_reference: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return a fail-closed, persisted-ready verification decision."""
    reasons: list[str] = []
    owner = candidate.get("owner_id")
    if expected_owner_id is not None and owner != expected_owner_id:
        reasons.append("cross_owner")
    if not candidate.get("source_profile"):
        reasons.append("missing_source_profile")
    if (
        candidate.get("mission_owner_id") is not None
        and candidate.get("mission_owner_id") != expected_owner_id
    ):
        reasons.append("cross_owner_mission")
    if (
        candidate.get("task_owner_id") is not None
        and candidate.get("task_owner_id") != expected_owner_id
    ):
        reasons.append("cross_owner_task")
    if not candidate.get("fetch_id"):
        reasons.append("missing_fetch_lineage")
    if not candidate.get("fetch_id") and not candidate.get("search_result_id"):
        reasons.append("missing_fetch_lineage")
    if not candidate.get("search_result_id"):
        reasons.append("missing_search_result_lineage")
    if not candidate.get("requested_url"):
        reasons.append("missing_requested_url")
    if not candidate.get("final_url"):
        reasons.append("missing_final_url")
    if not candidate.get("content_hash"):
        reasons.append("missing_content_hash")
    if candidate.get("expected_content_hash") and candidate.get("content_hash") != candidate.get(
        "expected_content_hash"
    ):
        reasons.append("content_hash_mismatch")
    if (
        expected_correlation_id is not None
        and candidate.get("correlation_id") != expected_correlation_id
    ):
        reasons.append("wrong_correlation_id")
    if expected_provider is not None and candidate.get("provider") != expected_provider:
        reasons.append("wrong_provider_lineage")
    if expected_source_reference and _canonical(
        str(candidate.get("final_url") or "")
    ) != _canonical(expected_source_reference):
        reasons.append("wrong_source_lineage")
    if candidate.get("duplicate") is True:
        reasons.append("duplicate_evidence")
    if candidate.get("blocked") is True:
        reasons.append("blocked_source")
    if candidate.get("unsafe_provenance") is True:
        reasons.append("unsafe_provenance")
    content = candidate.get("content") or candidate.get("text")
    if not isinstance(content, str) or not content.strip():
        reasons.append("empty_content")
    elif candidate.get("malformed") is True:
        reasons.append("malformed_content")
    if candidate.get("prompt_injection_detected") is True:
        reasons.append("prompt_injection")
    claim_type = candidate.get("claim_type")
    if claim_type is not None and str(claim_type).upper() not in {
        "PRICE",
        "TREND",
        "MOQ",
        "LEAD_TIME",
        "SUPPLIER_CAPABILITY",
        "COMPETITION",
        "SUPPLIER_VERIFICATION",
        "SUPPLIER_RISK",
    }:
        reasons.append("unsupported_claim_type")
    freshness = str(
        candidate.get("freshness_status") or candidate.get("freshness_state") or "UNKNOWN"
    ).upper()
    if freshness in {"EXPIRED", "UNKNOWN"}:
        reasons.append(f"freshness_{freshness.lower()}")
    elif freshness == "STALE":
        reasons.append("freshness_stale")
    state = (
        "REJECTED"
        if reasons
        else ("VERIFIED" if candidate.get("verification_method") else "SUPPORTED")
    )
    return {
        "verification_state": state,
        "verification_status": state,
        "reason": (
            ";".join(reasons)
            if reasons
            else "lineage, provenance, hash, and freshness checks passed"
        ),
        "method": VERIFIER_VERSION,
        "verified_at": (now or datetime.now(UTC)) if state in _ACCEPTED else None,
        "freshness_at_verification": freshness,
        "lineage": {
            key: candidate.get(key)
            for key in (
                "mission_id",
                "task_id",
                "fetch_id",
                "search_result_id",
                "correlation_id",
                "provider",
            )
            if candidate.get(key) is not None
        },
    }


def source_diversity_evaluation(
    evidence: Sequence[Mapping[str, object] | AutonomousResearchEvidence],
) -> dict[str, object]:
    rows: list[Mapping[str, object]] = []
    for item in evidence:
        rows.append(
            item
            if isinstance(item, Mapping)
            else {
                "url": getattr(item, "canonical_url", None)
                or getattr(item, "source_reference", None),
                "source_reference": getattr(item, "source_reference", None),
                "provider": getattr(item, "provider", None) or getattr(item, "source_class", None),
                "content_hash": getattr(item, "content_hash", None),
                "verification_status": getattr(item, "verification_status", None),
                "freshness_status": getattr(item, "freshness_status", None),
            }
        )
    canonical = {
        _canonical(str(row.get("url") or row.get("source_reference") or "")): row for row in rows
    }
    hashes: dict[str, list[Mapping[str, object]]] = {}
    for row in canonical.values():
        hashes.setdefault(str(row.get("content_hash") or ""), []).append(row)
    independent_pairs = {
        (
            _domain(str(row.get("url") or row.get("source_reference") or "")),
            str(row.get("content_hash") or ""),
        )
        for row in canonical.values()
    }
    independent = {pair for pair in independent_pairs if pair != ("", "")}
    mirrored = sum(
        max(0, len(group) - 1)
        for digest, group in hashes.items()
        if digest
        and len(
            {_domain(str(row.get("url") or row.get("source_reference") or "")) for row in group}
        )
        > 1
    )
    return {
        "independent_source_count": len(independent),
        "domain_count": len(
            {
                _domain(str(row.get("url") or row.get("source_reference") or ""))
                for row in canonical.values()
                if _domain(str(row.get("url") or row.get("source_reference") or ""))
            }
        ),
        "provider_count": len(
            {str(row.get("provider") or "") for row in canonical.values() if row.get("provider")}
        ),
        "verified_source_count": sum(
            row.get("verification_status") == "VERIFIED" for row in canonical.values()
        ),
        "supported_source_count": sum(
            row.get("verification_status") == "SUPPORTED" for row in canonical.values()
        ),
        "duplicate_source_count": max(0, len(rows) - len(canonical)),
        "mirrored_source_count": mirrored,
        "diversity_score": min(1.0, len(independent) / 3),
        "reason": "canonical URL, domain, provider, and content hash normalization applied",
    }


def confidence_handoff(
    evidence: Sequence[Mapping[str, object] | AutonomousResearchEvidence],
    *,
    contradiction_count: int = 0,
    critical_unknowns: int = 0,
    complete: bool = True,
) -> dict[str, object]:
    diversity = source_diversity_evaluation(evidence)
    rows = [
        (
            item
            if isinstance(item, Mapping)
            else {
                "verification_status": item.verification_status,
                "freshness_status": item.freshness_status,
            }
        )
        for item in evidence
    ]
    verification = sum(row.get("verification_status") == "VERIFIED" for row in rows) + 0.7 * sum(
        row.get("verification_status") == "SUPPORTED" for row in rows
    )
    verification_component = min(1.0, verification / max(1, len(rows)))
    freshness_component = sum(
        row.get("freshness_status") in {"FRESH", "AGING"} for row in rows
    ) / max(1, len(rows))
    completeness_component = 1.0 if complete else 0.0
    contradiction_penalty = min(1.0, contradiction_count * 0.2)
    unknown_penalty = min(1.0, critical_unknowns * 0.25)
    overall = max(
        0.0,
        min(
            1.0,
            verification_component * 0.4
            + freshness_component * 0.2
            + float(str(diversity["diversity_score"])) * 0.2
            + completeness_component * 0.2
            - contradiction_penalty
            - unknown_penalty,
        ),
    )
    if (
        contradiction_count
        or critical_unknowns
        or not complete
        or overall >= 0.85
        and len(rows) < 2
    ):
        overall = min(overall, 0.79)
    return {
        "overall_confidence": overall,
        "overall": overall,
        "verification_component": verification_component,
        "freshness_component": freshness_component,
        "diversity_component": diversity["diversity_score"],
        "completeness_component": completeness_component,
        "contradiction_penalty": contradiction_penalty,
        "unknown_penalty": unknown_penalty,
        "reasons": ["confidence is bounded by accepted, fresh, independent evidence"],
        "blocking_unknowns": critical_unknowns,
    }


def contradiction_identity(
    mission_id: object, claim_key: str, evidence_a: object, evidence_b: object
) -> str:
    pair = sorted((str(evidence_a), str(evidence_b)))
    return _fingerprint({"mission": str(mission_id), "claim_key": claim_key, "evidence": pair})


def record_external_contradiction(
    db: Session,
    mission: AutonomousResearchMission,
    evidence_a: AutonomousResearchEvidence,
    evidence_b: AutonomousResearchEvidence,
    *,
    claim_key: str = "",
) -> AutonomousResearchContradiction:
    identity = contradiction_identity(mission.id, claim_key, evidence_a.id, evidence_b.id)
    existing = db.scalar(
        select(AutonomousResearchContradiction).where(
            AutonomousResearchContradiction.owner_id == mission.owner_id,
            AutonomousResearchContradiction.mission_id == mission.id,
            AutonomousResearchContradiction.identity_key == identity,
        )
    )
    if existing is not None:
        return existing
    row = AutonomousResearchContradiction(
        owner_id=mission.owner_id,
        mission_id=mission.id,
        task_id=evidence_a.task_id,
        identity_key=identity,
        claim_key=claim_key,
        contradiction_type=claim_key or "external_conflict",
        evidence_a_id=evidence_a.id,
        evidence_b_id=evidence_b.id,
        evidence_a_value=dict(evidence_a.normalized_value),
        evidence_b_value=dict(evidence_b.normalized_value),
        source_a=evidence_a.source_reference,
        source_b=evidence_b.source_reference,
        freshness_a=evidence_a.freshness_status,
        freshness_b=evidence_b.freshness_status,
        verification_a=evidence_a.verification_status,
        verification_b=evidence_b.verification_status,
        confidence_a=evidence_a.confidence,
        confidence_b=evidence_b.confidence,
        correlation_id=str(mission.correlation_id),
        status="UNRESOLVED",
        resolution_strategy="REQUIRES_HUMAN_REVIEW",
    )
    db.add(row)
    db.flush()
    return row


def record_external_change(
    db: Session,
    mission: AutonomousResearchMission,
    *,
    change_type: str,
    entity_id: str,
    field_key: str,
    previous: Mapping[str, object],
    current: Mapping[str, object],
    evidence_ids: Sequence[str],
    accepted: bool = True,
) -> AutonomousResearchChange | None:
    if not accepted or not evidence_ids:
        return None
    identity = _fingerprint(
        {
            "mission": str(mission.id),
            "type": change_type,
            "entity": entity_id,
            "field": field_key,
            "previous": previous,
            "current": current,
        }
    )
    existing = db.scalar(
        select(AutonomousResearchChange).where(
            AutonomousResearchChange.owner_id == mission.owner_id,
            AutonomousResearchChange.mission_id == mission.id,
            AutonomousResearchChange.identity_key == identity,
        )
    )
    if existing is not None:
        return existing
    old = previous.get("value")
    new = current.get("value")
    delta = (
        float(new) - float(old)
        if isinstance(old, (int, float)) and isinstance(new, (int, float))
        else None
    )
    materiality = "NON_MATERIAL"
    if (
        change_type.upper() in {"TREND", "SUPPLIER_VERIFICATION", "SUPPLIER_RISK", "COMPETITION"}
        and previous != current
    ):
        materiality = "REQUIRES_REVIEW"
    elif delta is not None and float(str(old or 0)) and abs(delta / float(str(old))) >= 0.15:
        materiality = "MATERIAL"
    row = AutonomousResearchChange(
        owner_id=mission.owner_id,
        mission_id=mission.id,
        change_type=change_type.upper(),
        entity_type="external_claim",
        entity_id=entity_id,
        field_key=field_key,
        identity_key=identity,
        previous_value=dict(previous),
        current_value=dict(current),
        delta=delta,
        material=materiality == "MATERIAL",
        materiality=materiality,
        reason="server-derived materiality",
        evidence_ids=list(evidence_ids),
        observed_at=datetime.now(UTC),
        correlation_id=str(mission.correlation_id),
    )
    db.add(row)
    db.flush()
    return row


def record_external_alert(
    db: Session,
    mission: AutonomousResearchMission,
    *,
    alert_type: str,
    title: str,
    detail: str,
    identity: str,
    severity: str = "REQUIRES_REVIEW",
    lineage: Mapping[str, object] | None = None,
) -> AutonomousResearchAlert:
    key = _fingerprint({"mission": str(mission.id), "type": alert_type, "identity": identity})
    existing = db.scalar(
        select(AutonomousResearchAlert).where(
            AutonomousResearchAlert.owner_id == mission.owner_id,
            AutonomousResearchAlert.mission_id == mission.id,
            AutonomousResearchAlert.identity_key == key,
        )
    )
    if existing is not None:
        return existing
    row = AutonomousResearchAlert(
        owner_id=mission.owner_id,
        mission_id=mission.id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        detail=detail[:500],
        identity_key=key,
        lineage=dict(lineage or {}),
    )
    db.add(row)
    db.flush()
    return row


def observation_history(db: Session, owner_id: object, canonical_url: str) -> list[ExternalFetch]:
    """Return append-only observations for one canonical source, oldest first."""
    target = _canonical(canonical_url)
    rows = list(
        db.scalars(
            select(ExternalFetch)
            .where(ExternalFetch.owner_id == owner_id)
            .order_by(ExternalFetch.retrieved_at.asc())
        )
    )
    return [row for row in rows if _canonical(row.final_url or row.requested_url) == target]


def current_observation(db: Session, owner_id: object, canonical_url: str) -> ExternalFetch | None:
    history = observation_history(db, owner_id, canonical_url)
    return history[-1] if history else None
