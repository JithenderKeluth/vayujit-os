# ruff: noqa: E501,E702
"""Deterministic external evidence verification and downstream handoff."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchClaim,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_evidence import derive_freshness
from vayujit_api.intelligence.external_intelligence import (
    confidence_handoff,
    record_external_alert,
    record_external_change,
    record_external_contradiction,
    source_diversity_evaluation,
    verify_external_evidence,
)


def verify_and_project(
    db: Session,
    owner: User,
    mission: AutonomousResearchMission,
    task: AutonomousResearchTask,
    evidence: AutonomousResearchEvidence,
) -> dict[str, object]:
    freshness = derive_freshness(evidence.retrieved_at)
    evidence.freshness_status = freshness.state
    evidence.fresh_until = freshness.fresh_until
    evidence.stale_at = freshness.stale_at
    evidence.expires_at = freshness.expires_at
    evidence.freshness_at_verification = freshness.state
    extracted = evidence.normalized_value if isinstance(evidence.normalized_value, dict) else {}
    decision = verify_external_evidence(
        {
            "owner_id": evidence.owner_id,
            "source_profile": evidence.source_profile or extracted.get("source_profile", "default"),
            "fetch_id": extracted.get("fetch_id") or extracted.get("external_fetch_id"),
            "search_result_id": extracted.get("search_result_id")
            or evidence.lineage.get("search_result_id"),
            "requested_url": extracted.get("requested_url") or evidence.source_reference,
            "final_url": evidence.source_reference,
            "content_hash": evidence.content_hash,
            "content": extracted.get("text") or extracted.get("content") or "external observation",
            "prompt_injection_detected": extracted.get("prompt_injection_detected") is True,
            "freshness_status": freshness.state,
            "correlation_id": extracted.get("correlation_id")
            or evidence.lineage.get("correlation_id"),
            "provider": evidence.provider or evidence.source_class,
            "mission_id": mission.id,
            "task_id": task.id,
        },
        expected_owner_id=owner.id,
    )
    evidence.verification_status = str(decision["verification_status"])
    evidence.verification_reason = str(decision["reason"])
    evidence.verification_method = str(decision["method"])
    evidence.verified_at = cast(datetime | None, decision["verified_at"])
    evidence.lineage = {
        key: str(value) if isinstance(value, uuid.UUID) else value
        for key, value in (
            decision["lineage"].items() if isinstance(decision["lineage"], dict) else ()
        )
    }
    claims: list[AutonomousResearchClaim] = []
    raw_claims = extracted.get("claims", [])
    if evidence.verification_status in {"SUPPORTED", "VERIFIED"} and isinstance(raw_claims, list):
        for raw in raw_claims:
            if not isinstance(raw, dict) or not raw.get("key"):
                continue
            key = str(raw["key"])
            value = raw.get("value")
            existing = db.scalar(
                select(AutonomousResearchClaim).where(
                    AutonomousResearchClaim.owner_id == owner.id,
                    AutonomousResearchClaim.mission_id == mission.id,
                    AutonomousResearchClaim.claim_type == key,
                    AutonomousResearchClaim.evidence_ids.contains([str(evidence.id)]),
                )
            )
            if existing is None:
                existing = AutonomousResearchClaim(
                    owner_id=owner.id,
                    mission_id=mission.id,
                    task_id=task.id,
                    claim_type=key,
                    value={"value": value},
                    evidence_ids=[str(evidence.id)],
                    verification_status=evidence.verification_status,
                    confidence=0.7 if evidence.verification_status == "SUPPORTED" else 0.85,
                )
                db.add(existing)
            claims.append(existing)
    for claim in claims:
        prior_claims = list(
            db.scalars(
                select(AutonomousResearchClaim).where(
                    AutonomousResearchClaim.owner_id == owner.id,
                    AutonomousResearchClaim.mission_id == mission.id,
                    AutonomousResearchClaim.claim_type == claim.claim_type,
                    AutonomousResearchClaim.id != claim.id,
                )
            )
        )
        for prior in prior_claims:
            if prior.value == claim.value or not prior.evidence_ids:
                continue
            try:
                prior_evidence = db.get(
                    AutonomousResearchEvidence, uuid.UUID(str(prior.evidence_ids[0]))
                )
            except (ValueError, IndexError):
                prior_evidence = None
            if prior_evidence is None:
                continue
            contradiction = record_external_contradiction(
                db, mission, prior_evidence, evidence, claim_key=claim.claim_type
            )
            record_external_change(
                db,
                mission,
                change_type=claim.claim_type,
                entity_id=str(mission.id),
                field_key=claim.claim_type,
                previous=prior.value,
                current=claim.value,
                evidence_ids=[str(prior_evidence.id), str(evidence.id)],
            )
            record_external_alert(
                db,
                mission,
                alert_type="high_risk_contradiction",
                title="External evidence requires review",
                detail="Conflicting accepted claims require human review.",
                identity=str(contradiction.identity_key),
            )
    db.flush()
    return {
        "evidence": evidence,
        "claims": claims,
        "verification_status": evidence.verification_status,
        "reason": evidence.verification_reason,
        "freshness_at_verification": freshness.state,
    }


def confidence_breakdown(
    evidence: list[AutonomousResearchEvidence], contradiction_count: int = 0
) -> dict[str, object]:
    return confidence_handoff(evidence, contradiction_count=contradiction_count)


def source_diversity(evidence: list[AutonomousResearchEvidence]) -> dict[str, object]:
    result = source_diversity_evaluation(evidence)
    result["source_diversity_score"] = result["diversity_score"]
    return result
