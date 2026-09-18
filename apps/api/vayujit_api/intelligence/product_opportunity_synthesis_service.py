"""Deterministic assessment-bound 9E synthesis over existing intelligence outputs."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_commercial_models import (
    ProductOpportunityCommercialOutput,
)
from vayujit_api.intelligence.product_opportunity_feasibility_models import (
    ProductOpportunitySourcingFeasibilityOutput,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    ProductOpportunityIntelligenceOutput,
)
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.product_opportunity_synthesis_models import (
    CALCULATION_VERSION,
    ProductOpportunityRiskEvidenceSynthesis,
)
from vayujit_api.intelligence.product_opportunity_synthesis_schemas import SynthesisCalculateRequest


def _assessment(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityAssessment:
    row = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if row is None:
        raise LookupError("Product opportunity assessment not found.")
    return row


def _readiness(output: Any, domain: str) -> str:
    if output is None:
        return "UNKNOWN"
    gaps = output.research_gaps if hasattr(output, "research_gaps") else []
    dimensions = output.dimensions if hasattr(output, "dimensions") else []
    states = {str(item.get("evidence_state")) for item in dimensions if isinstance(item, dict)}
    if any("BLOCK" in str(item).upper() for item in dimensions):
        return "BLOCKED"
    if not dimensions and not gaps:
        return "INSUFFICIENT_EVIDENCE"
    if any("STALE" in state.upper() for state in states):
        return "STALE"
    if gaps:
        return "PARTIAL"
    return "READY"


def _gap(origin: str, value: Any) -> dict[str, Any]:
    text = str(value)
    return {
        "origin": origin,
        "type": text,
        "priority": "HIGH" if "REQUIRED" in text else "MODERATE",
        "reason": f"{origin} reported {text}.",
        "status": "OPEN",
        "materiality": "MATERIAL" if "REQUIRED" in text else "ORDINARY",
    }


def calculate_synthesis(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: SynthesisCalculateRequest,
) -> ProductOpportunityRiskEvidenceSynthesis:
    _assessment(db, owner, opportunity_id, assessment_id)
    existing = db.scalar(
        select(ProductOpportunityRiskEvidenceSynthesis).where(
            ProductOpportunityRiskEvidenceSynthesis.owner_id == owner.id,
            ProductOpportunityRiskEvidenceSynthesis.assessment_id == assessment_id,
        )
    )
    if existing is not None:
        return existing
    intelligence = list(
        db.scalars(
            select(ProductOpportunityIntelligenceOutput).where(
                ProductOpportunityIntelligenceOutput.owner_id == owner.id,
                ProductOpportunityIntelligenceOutput.assessment_id == assessment_id,
            )
        )
    )
    commercial = db.scalar(
        select(ProductOpportunityCommercialOutput).where(
            ProductOpportunityCommercialOutput.owner_id == owner.id,
            ProductOpportunityCommercialOutput.assessment_id == assessment_id,
        )
    )
    sourcing = db.scalar(
        select(ProductOpportunitySourcingFeasibilityOutput).where(
            ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id,
            ProductOpportunitySourcingFeasibilityOutput.assessment_id == assessment_id,
        )
    )
    gaps: list[dict[str, Any]] = []
    for output in intelligence:
        for gap in output.research_gaps:
            gaps.append(
                _gap(output.kind.upper(), gap.get("type") if isinstance(gap, dict) else gap)
            )
    if commercial:
        for gap in commercial.research_gaps:
            gaps.append(_gap("COMMERCIAL", gap.get("type") if isinstance(gap, dict) else gap))
    if sourcing:
        for gap in sourcing.research_gaps:
            gaps.append(_gap("SOURCING", gap))
    dedup: dict[tuple[str, str], dict[str, Any]] = {
        (item["origin"], item["type"]): item for item in gaps
    }
    gaps = list(dedup.values())
    lineage = {
        "intelligence": {output.kind: str(output.id) for output in intelligence},
        "commercial": str(commercial.id) if commercial else None,
        "sourcing": str(sourcing.id) if sourcing else None,
    }
    fingerprint = hashlib.sha256(json.dumps(lineage, sort_keys=True).encode()).hexdigest()
    readiness = {
        "DEMAND": _readiness(next((x for x in intelligence if x.kind == "demand"), None), "DEMAND"),
        "COMPETITION": _readiness(
            next((x for x in intelligence if x.kind == "competition"), None), "COMPETITION"
        ),
        "COMMERCIAL": _readiness(commercial, "COMMERCIAL"),
        "SUPPLIER": _readiness(sourcing, "SUPPLIER"),
        "DUE_DILIGENCE": _readiness(sourcing, "DUE_DILIGENCE"),
        "SOURCING": _readiness(sourcing, "SOURCING"),
        "RESILIENCE": (
            "READY"
            if sourcing and sourcing.upstream_lineage.get("portfolio", {}).get("resilience")
            else "UNKNOWN"
        ),
    }
    blockers: list[dict[str, str]] = []
    if sourcing:
        blockers.extend(
            {"type": "EVIDENCE_BLOCKER", "reason": gap}
            for gap in sourcing.research_gaps
            if "REQUIRED" in str(gap)
        )
        if any(item.get("shortlist", {}).get("hard_block") for item in sourcing.candidates):
            blockers.append(
                {"type": "BUSINESS/RULE_BLOCKER", "reason": "Authoritative shortlist hard block."}
            )
    available = sum(state == "READY" for state in readiness.values())
    overall = (
        "READY_FOR_SCORING"
        if available >= 5 and not blockers and not gaps
        else (
            "BLOCKED"
            if blockers
            else (
                "RESEARCH_REQUIRED"
                if not intelligence and not sourcing and not commercial
                else "PARTIALLY_READY"
            )
        )
    )
    evidence_count = (
        sum(len(output.dimensions) for output in intelligence)
        + (len(commercial.dimensions) if commercial else 0)
        + (len(sourcing.dimensions) if sourcing else 0)
    )
    confidence = (
        "HIGH" if evidence_count >= 12 and not gaps else "MODERATE" if evidence_count else "UNKNOWN"
    )
    risks: list[dict[str, Any]] = []
    for item in gaps:
        risks.append(
            {
                "category": "EVIDENCE",
                "type": "MISSING_EVIDENCE",
                "severity": "UNKNOWN",
                "explanation": item["reason"],
                "evidence_state": "MISSING",
                "freshness": "UNKNOWN",
                "contradiction_state": "UNKNOWN",
                "materiality": item["materiality"],
                "research_gap": item["type"],
                "calculation_version": CALCULATION_VERSION,
            }
        )
    for blocker in blockers:
        risks.append(
            {
                "category": "SUPPLIER",
                "type": "AUTHORITATIVE_BLOCK",
                "severity": "HIGH",
                "explanation": blocker["reason"],
                "evidence_state": "VERIFIED",
                "freshness": "CURRENT",
                "contradiction_state": "UNKNOWN",
                "materiality": "MATERIAL",
                "research_gap": None,
                "calculation_version": CALCULATION_VERSION,
            }
        )
    dimensions = [
        {
            "dimension": "RISK_EXPOSURE",
            "value": {"count": len(risks)},
            "classification": "DERIVED_PROJECTION",
            "explanation": "Only authoritative blockers and reported gaps are synthesized.",
            "calculation_version": CALCULATION_VERSION,
        },
        {
            "dimension": "EVIDENCE_COVERAGE",
            "value": {"available": evidence_count, "gaps": len(gaps)},
            "classification": "DERIVED_PROJECTION",
            "explanation": (
                "Counts persisted upstream dimensions without treating absence "
                "as poor business performance."
            ),
            "calculation_version": CALCULATION_VERSION,
        },
        {
            "dimension": "ASSESSMENT_CONFIDENCE",
            "value": confidence,
            "classification": "DERIVED_PROJECTION",
            "explanation": (
                "Confidence reflects evidence coverage and gaps, not commercial positivity."
            ),
            "calculation_version": CALCULATION_VERSION,
        },
        {
            "dimension": "ASSESSMENT_READINESS",
            "value": overall,
            "classification": "DERIVED_PROJECTION",
            "explanation": (
                "Readiness describes whether later deterministic scoring has " "sufficient inputs."
            ),
            "calculation_version": CALCULATION_VERSION,
        },
    ]
    summary = {
        "assessment_readiness": overall,
        "confidence": confidence,
        "risk_count": len(risks),
        "evidence_dimension_count": evidence_count,
        "blocker_count": len(blockers),
    }
    prior = db.scalar(
        select(ProductOpportunityRiskEvidenceSynthesis)
        .where(
            ProductOpportunityRiskEvidenceSynthesis.owner_id == owner.id,
            ProductOpportunityRiskEvidenceSynthesis.opportunity_id == opportunity_id,
        )
        .order_by(ProductOpportunityRiskEvidenceSynthesis.created_at.desc())
    )
    changes: dict[str, Any] = {
        "material": bool(
            prior
            and (
                prior.summary.get("confidence") != confidence
                or prior.summary.get("risk_count") != len(risks)
            )
        ),
        "prior_synthesis_id": str(prior.id) if prior else None,
        "changed_fields": [],
    }
    if prior and changes["material"]:
        changes["changed_fields"] = ["confidence_or_risk_count"]
    row = ProductOpportunityRiskEvidenceSynthesis(
        owner_id=owner.id,
        opportunity_id=opportunity_id,
        assessment_id=assessment_id,
        calculation_version=CALCULATION_VERSION,
        input_fingerprint=fingerprint,
        upstream_lineage=lineage,
        summary=summary,
        risks=risks,
        domain_readiness=readiness,
        evidence_summary={
            "dimension_count": evidence_count,
            "source_domains": sorted(
                {key for key, value in readiness.items() if value != "UNKNOWN"}
            ),
            "confidence": confidence,
        },
        research_gaps=gaps,
        changes=changes,
        dimensions=dimensions,
        idempotency_key=request.idempotency_key or f"opportunity-synthesis:{assessment_id}",
    )
    db.add(row)
    return row


def history(
    db: Session, owner: User, opportunity_id: uuid.UUID
) -> list[ProductOpportunityRiskEvidenceSynthesis]:
    return list(
        db.scalars(
            select(ProductOpportunityRiskEvidenceSynthesis)
            .where(
                ProductOpportunityRiskEvidenceSynthesis.owner_id == owner.id,
                ProductOpportunityRiskEvidenceSynthesis.opportunity_id == opportunity_id,
            )
            .order_by(ProductOpportunityRiskEvidenceSynthesis.created_at.desc())
        )
    )


def output_or_404(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityRiskEvidenceSynthesis:
    _assessment(db, owner, opportunity_id, assessment_id)
    row = db.scalar(
        select(ProductOpportunityRiskEvidenceSynthesis).where(
            ProductOpportunityRiskEvidenceSynthesis.owner_id == owner.id,
            ProductOpportunityRiskEvidenceSynthesis.opportunity_id == opportunity_id,
            ProductOpportunityRiskEvidenceSynthesis.assessment_id == assessment_id,
        )
    )
    if row is None:
        raise LookupError("Product opportunity synthesis not found.")
    return row
