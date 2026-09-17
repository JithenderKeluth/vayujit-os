"""Deterministic 8E.3 resilience scoring and advisory recommendations."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.portfolio_analysis import (
    _assessment,
    _dedupe_members,
    _members,
    calculate_concentration,
    calculate_dependencies,
    calculate_readiness,
)
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioContext,
)
from vayujit_api.intelligence.resilience_models import (
    SupplierPortfolioConfidenceProjection,
    SupplierPortfolioRecommendation,
    SupplierPortfolioResilienceDimensionResult,
    SupplierPortfolioResilienceScore,
    SupplierPortfolioRiskProjection,
)

DIMENSIONS = (
    "SUPPLIER_DIVERSITY",
    "GEOGRAPHIC_DIVERSITY",
    "QUALIFIED_ALTERNATIVE_COVERAGE",
    "VERIFIED_ALTERNATIVE_COVERAGE",
    "COMMERCIAL_FLEXIBILITY",
    "LEAD_TIME_RESILIENCE",
    "COST_RESILIENCE",
    "CAPABILITY_REDUNDANCY",
    "EVIDENCE_CONFIDENCE",
    "FRESHNESS",
    "CONTRADICTION_RISK",
    "DUE_DILIGENCE_COVERAGE",
)
WEIGHTS = {
    "SUPPLIER_DIVERSITY": Decimal("12"),
    "GEOGRAPHIC_DIVERSITY": Decimal("10"),
    "QUALIFIED_ALTERNATIVE_COVERAGE": Decimal("10"),
    "VERIFIED_ALTERNATIVE_COVERAGE": Decimal("10"),
    "COMMERCIAL_FLEXIBILITY": Decimal("8"),
    "LEAD_TIME_RESILIENCE": Decimal("8"),
    "COST_RESILIENCE": Decimal("8"),
    "CAPABILITY_REDUNDANCY": Decimal("8"),
    "EVIDENCE_CONFIDENCE": Decimal("8"),
    "FRESHNESS": Decimal("6"),
    "CONTRADICTION_RISK": Decimal("5"),
    "DUE_DILIGENCE_COVERAGE": Decimal("7"),
}
DIMENSION_VERSION = "8E.3-dimensions-v1"
SCORE_VERSION = "8E.3-score-v1"
CONFIDENCE_VERSION = "8E.3-confidence-v1"
RISK_VERSION = "8E.3-risk-v1"
RECOMMENDATION_VERSION = "8E.3-recommendations-v1"
THRESHOLD_VERSION = "8E.3-classification-thresholds-v1"
PRIORITY_VERSION = "8E.3-priority-v1"
assert sum(WEIGHTS.values(), Decimal("0")) == Decimal("100")


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _round(value: Decimal | None) -> Decimal | None:
    return value.quantize(Decimal("0.0001")) if value is not None else None


def _number(value: Decimal | None) -> float | None:
    value = _round(value)
    return float(value) if value is not None else None


def _clamp(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def _classify(value: Decimal | None) -> str:
    if value is None:
        return "INSUFFICIENT_EVIDENCE"
    if value <= 20:
        return "VERY_LOW"
    if value <= 40:
        return "LOW"
    if value <= 60:
        return "MODERATE"
    if value <= 80:
        return "HIGH"
    return "VERY_HIGH"


def _metric(facts: dict[str, Any], dimension: str, metric_type: str) -> dict[str, Any]:
    return next(
        (
            row
            for row in facts.get("concentration", {}).get("results", [])
            if row.get("dimension") == dimension and row.get("metric_type") == metric_type
        ),
        {},
    )


def _dimension(
    name: str,
    score: Decimal | None,
    *,
    status: str,
    inputs: dict[str, Any],
    refs: list[Any],
    explanation: str,
    missing: list[Any] | None = None,
    limitations: list[Any] | None = None,
    penalties: list[Any] | None = None,
) -> dict[str, Any]:
    score = _round(_clamp(score)) if score is not None else None
    return {
        "dimension": name,
        "score": score,
        "classification": _classify(score),
        "evidence_status": status,
        "calculation_version": DIMENSION_VERSION,
        "supporting_inputs": inputs,
        "evidence_references": refs,
        "penalties": penalties or [],
        "limitations": limitations or [],
        "missing_evidence": missing or [],
        "explanation": explanation,
    }


def _evidence_dimension(
    name: str, members: list[dict[str, Any]], keys: tuple[str, ...], explanation: str
) -> dict[str, Any]:
    present = [m for m in members if any(m.get(k) is not None for k in keys)]
    if not present:
        return _dimension(
            name,
            None,
            status="INSUFFICIENT",
            inputs={},
            refs=[],
            missing=[keys[0]],
            explanation=explanation,
        )
    score = Decimal(len(present)) * 100 / Decimal(len(members) or 1)
    return _dimension(
        name,
        score,
        status="SUFFICIENT" if len(present) == len(members) else "PARTIAL",
        inputs={"members_with_evidence": len(present), "member_count": len(members)},
        refs=["immutable assessment snapshot"],
        missing=[] if len(present) == len(members) else [keys[0]],
        limitations=(
            [] if len(present) == len(members) else ["not all members have comparable evidence"]
        ),
        explanation=explanation,
    )


def _build_dimensions(members: list[dict[str, Any]], facts: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    largest = _decimal(_metric(facts, "supplier", "largest_supplier_share").get("value"))
    hhi = _decimal(_metric(facts, "supplier", "supplier_allocation_hhi").get("value"))
    if largest is None or hhi is None:
        result.append(
            _dimension(
                "SUPPLIER_DIVERSITY",
                None,
                status="INSUFFICIENT",
                inputs={},
                refs=[],
                missing=["supplier allocation"],
                explanation="Supplier allocation evidence is insufficient for diversity scoring.",
            )
        )
    else:
        result.append(
            _dimension(
                "SUPPLIER_DIVERSITY",
                ((100 - largest) + (100 * (1 - hhi))) / 2,
                status="SUFFICIENT",
                inputs={"largest_supplier_share": float(largest), "hhi": float(hhi)},
                refs=["8E.2 concentration metrics"],
                penalties=[{"type": "single_supplier_concentration", "applied": largest >= 50}],
                explanation=(
                    "Supplier diversity combines largest allocation share and HHI; "
                    "confidence is not a resilience bonus."
                ),
            )
        )
    chhi = _decimal(_metric(facts, "country", "country_allocation_hhi").get("value"))
    rhhi = _decimal(_metric(facts, "region", "region_allocation_hhi").get("value"))
    if chhi is None or rhhi is None:
        result.append(
            _dimension(
                "GEOGRAPHIC_DIVERSITY",
                None,
                status="INSUFFICIENT",
                inputs={},
                refs=[],
                missing=["country/region allocation"],
                explanation="Country or region evidence is insufficient for geographic diversity.",
            )
        )
    else:
        result.append(
            _dimension(
                "GEOGRAPHIC_DIVERSITY",
                100 * (1 - (chhi + rhhi) / 2),
                status="SUFFICIENT",
                inputs={"country_hhi": float(chhi), "region_hhi": float(rhhi)},
                refs=["8E.2 concentration metrics"],
                explanation="Geographic diversity is derived from country and region HHI.",
            )
        )
    readiness = list(facts.get("readiness", {}).get("results", []))
    products = [r for r in readiness if r.get("product_id")]
    if products:
        q = sum(r.get("readiness_state") in {"READY", "CONDITIONALLY_READY"} for r in products)
        v = sum(r.get("readiness_state") == "READY" for r in products)
        total = Decimal(len(products))
        result += [
            _dimension(
                "QUALIFIED_ALTERNATIVE_COVERAGE",
                Decimal(q) * 100 / total,
                status="SUFFICIENT",
                inputs={"eligible_product_assessments": len(products), "qualified_count": q},
                refs=["8E.2 alternate readiness"],
                explanation=(
                    "READY counts fully and CONDITIONALLY_READY counts as bounded "
                    "partial qualified coverage."
                ),
            ),
            _dimension(
                "VERIFIED_ALTERNATIVE_COVERAGE",
                Decimal(v) * 100 / total,
                status="SUFFICIENT",
                inputs={"eligible_product_assessments": len(products), "verified_count": v},
                refs=["8E.2 readiness and due diligence"],
                explanation=(
                    "Verified coverage counts only READY assessments with due diligence " "lineage."
                ),
            ),
        ]
    else:
        result += [
            _dimension(
                "QUALIFIED_ALTERNATIVE_COVERAGE",
                None,
                status="INSUFFICIENT",
                inputs={},
                refs=[],
                missing=["product requirement context"],
                explanation="No product-scoped alternate requirement is available.",
            ),
            _dimension(
                "VERIFIED_ALTERNATIVE_COVERAGE",
                None,
                status="INSUFFICIENT",
                inputs={},
                refs=[],
                missing=["product requirement context"],
                explanation="No product-scoped alternate requirement is available.",
            ),
        ]
    result += [
        _evidence_dimension(
            "COMMERCIAL_FLEXIBILITY",
            members,
            ("commercial_evidence", "availability", "moq", "payment_terms"),
            "Commercial flexibility uses explicitly supplied comparable evidence.",
        ),
        _evidence_dimension(
            "LEAD_TIME_RESILIENCE",
            members,
            ("lead_time_days", "lead_time", "lead_time_evidence"),
            "Lead-time resilience requires explicit lead-time evidence.",
        ),
        _evidence_dimension(
            "COST_RESILIENCE",
            members,
            ("normalized_landed_cost", "landed_cost", "cost_evidence"),
            "Cost resilience uses normalized comparable landed-cost evidence.",
        ),
    ]
    caps: dict[str, set[str]] = {}
    for m in members:
        for c in m.get("capabilities") or []:
            caps.setdefault(str(c).upper(), set()).add(str(m.get("supplier_id")))
    result.append(
        _dimension(
            "CAPABILITY_REDUNDANCY",
            (
                Decimal(sum(len(v) >= 2 for v in caps.values())) * 100 / Decimal(len(caps))
                if caps
                else None
            ),
            status="SUFFICIENT" if caps else "INSUFFICIENT",
            inputs={"capability_count": len(caps)},
            refs=["canonical supplier capability evidence"] if caps else [],
            missing=[] if caps else ["capability evidence"],
            explanation=(
                "Capability redundancy counts capabilities evidenced by at least " "two suppliers."
            ),
        )
    )
    confidences: list[Decimal] = []
    for member in members:
        confidence_observation = _decimal(member.get("confidence"))
        if confidence_observation is not None:
            confidences.append(confidence_observation)
    result.append(
        _dimension(
            "EVIDENCE_CONFIDENCE",
            sum(confidences, Decimal("0")) / len(confidences) if confidences else None,
            status="SUFFICIENT" if confidences else "INSUFFICIENT",
            inputs={"confidence_observations": len(confidences)},
            refs=["supplier evidence confidence"] if confidences else [],
            missing=[] if confidences else ["confidence evidence"],
            explanation=(
                "Evidence confidence is reported separately and never added as a "
                "resilience bonus."
            ),
        )
    )
    freshness = [str(m.get("evidence_freshness", "")).lower() for m in members]
    known = [v for v in freshness if v]
    if known:
        fresh = sum(v in {"fresh", "current", "verified"} for v in known)
        result.append(
            _dimension(
                "FRESHNESS",
                Decimal(fresh) * 100 / Decimal(len(known)),
                status="SUFFICIENT" if len(known) == len(members) else "PARTIAL",
                inputs={"fresh_count": fresh, "observations": len(known)},
                refs=["supplier evidence freshness"],
                missing=[] if len(known) == len(members) else ["freshness for all members"],
                explanation="Freshness reflects explicit evidence freshness states only.",
            )
        )
    else:
        result.append(
            _dimension(
                "FRESHNESS",
                None,
                status="INSUFFICIENT",
                inputs={},
                refs=[],
                missing=["freshness evidence"],
                explanation="Freshness evidence is unavailable.",
            )
        )
    provided = facts.get("provided", {})
    contradictions = provided.get("contradictions", []) if isinstance(provided, dict) else []
    result.append(
        _dimension(
            "CONTRADICTION_RISK",
            Decimal(100 - min(100, len(contradictions) * 20) if contradictions else 100),
            status="SUFFICIENT" if contradictions else "PARTIAL",
            inputs={"contradiction_count": len(contradictions)},
            refs=["authoritative contradiction records"] if contradictions else [],
            limitations=[] if contradictions else ["No contradiction records were supplied."],
            explanation=(
                "Contradiction risk decreases with authoritative unresolved "
                "contradictions; absence of records is not proof none exist."
            ),
        )
    )
    alloc: list[Decimal] = []
    for member in members:
        allocation = _decimal(member.get("allocation_percent"))
        if allocation is not None:
            alloc.append(allocation)
    total = sum(alloc, Decimal("0"))
    covered = Decimal("0")
    for member in members:
        if member.get("due_diligence_lineage_id") is not None:
            allocation = _decimal(member.get("allocation_percent"))
            if allocation is not None:
                covered += allocation
    result.append(
        _dimension(
            "DUE_DILIGENCE_COVERAGE",
            covered,
            status="SUFFICIENT" if total == Decimal("100") else "INSUFFICIENT",
            inputs={"allocation_total": float(total), "covered_exposure": float(covered)},
            refs=["8C due diligence lineage"] if total == Decimal("100") else [],
            missing=[] if total == Decimal("100") else ["complete allocation total"],
            explanation="Due diligence coverage is weighted by evidenced allocation exposure.",
        )
    )
    return result


def _dimension_payload(row: SupplierPortfolioResilienceDimensionResult) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "dimension": row.dimension,
        "score": _number(_decimal(row.score)),
        "classification": row.classification,
        "evidence_status": row.evidence_status,
        "calculation_version": row.calculation_version,
        "supporting_inputs": row.supporting_inputs,
        "evidence_references": row.evidence_references,
        "penalties": row.penalties,
        "limitations": row.limitations,
        "missing_evidence": row.missing_evidence,
        "explanation": row.explanation,
        "calculated_at": row.calculated_at.isoformat(),
    }


def _score_payload(row: SupplierPortfolioResilienceScore) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "score": _number(_decimal(row.score)),
        "classification": row.classification,
        "evidence_status": row.evidence_status,
        "confidence_value": _number(_decimal(row.confidence_value)),
        "confidence_classification": row.confidence_classification,
        "score_version": row.score_version,
        "component_snapshot": row.component_snapshot,
        "penalty_snapshot": row.penalty_snapshot,
        "missing_evidence": row.missing_evidence,
        "explanation": row.explanation,
        "calculated_at": row.calculated_at.isoformat(),
    }


def _confidence_payload(row: SupplierPortfolioConfidenceProjection) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "value": _number(_decimal(row.value)),
        "classification": row.classification,
        "evidence_status": row.evidence_status,
        "explanation": row.explanation,
        "limitations": row.limitations,
        "calculation_version": row.calculation_version,
        "calculated_at": row.calculated_at.isoformat(),
    }


def _risk_payload(row: SupplierPortfolioRiskProjection) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "classification": row.classification,
        "exposure": _number(_decimal(row.exposure)),
        "supporting_inputs": row.supporting_inputs,
        "explanation": row.explanation,
        "calculation_version": row.calculation_version,
        "calculated_at": row.calculated_at.isoformat(),
    }


def _recommendation_payload(row: SupplierPortfolioRecommendation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "recommendation_type": row.recommendation_type,
        "priority": row.priority,
        "affected_supplier_id": str(row.affected_supplier_id) if row.affected_supplier_id else None,
        "affected_product_id": str(row.affected_product_id) if row.affected_product_id else None,
        "affected_dependency_type": row.affected_dependency_type,
        "reason": row.reason,
        "evidence": row.evidence,
        "dimensions_affected": row.dimensions_affected,
        "expected_benefit": row.expected_benefit,
        "missing_evidence": row.missing_evidence,
        "recommendation_version": row.recommendation_version,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


def _priority(severity: str | None, score: Decimal | None) -> str:
    if severity == "CRITICAL" or (score is not None and score <= 20):
        return "CRITICAL"
    if severity == "HIGH" or (score is not None and score <= 40):
        return "HIGH"
    if score is not None and score <= 60:
        return "MEDIUM"
    return "LOW"


def _recommendations(
    assessment: SupplierPortfolioAssessmentVersion,
    portfolio: SupplierPortfolioContext,
    dimensions: list[dict[str, Any]],
    facts: dict[str, Any],
) -> list[SupplierPortfolioRecommendation]:
    by = {row["dimension"]: row for row in dimensions}
    rows = []
    seen = set()

    def add(
        kind: str,
        priority: str,
        reason: str,
        evidence: list[Any],
        *,
        supplier: str | None = None,
        product: str | None = None,
        dependency: str | None = None,
        dims: list[str] | None = None,
        missing: list[Any] | None = None,
    ) -> None:
        key = "|".join((kind, supplier or "", product or "", dependency or ""))
        if key in seen:
            return
        seen.add(key)
        rows.append(
            SupplierPortfolioRecommendation(
                owner_id=assessment.owner_id,
                portfolio_id=portfolio.id,
                assessment_version_id=assessment.id,
                recommendation_type=kind,
                priority=priority,
                affected_supplier_id=uuid.UUID(supplier) if supplier else None,
                affected_product_id=uuid.UUID(product) if product else None,
                affected_dependency_type=dependency,
                logical_key=key,
                reason=reason,
                evidence=evidence,
                dimensions_affected=dims or [],
                expected_benefit=(
                    "Improve human decision quality by addressing the identified "
                    "resilience limitation."
                ),
                missing_evidence=missing or [],
                recommendation_version=RECOMMENDATION_VERSION,
                status="OPEN",
            )
        )

    for finding in facts.get("dependencies", {}).get("results", []):
        dep = finding.get("dependency_type")
        supplier = finding.get("affected_supplier_id")
        product = finding.get("affected_product_id")
        score = _decimal(by.get("SUPPLIER_DIVERSITY", {}).get("score"))
        if dep == "ONLY_SUPPLIER_FOR_PRODUCT":
            add(
                "QUALIFY_SECOND_SUPPLIER",
                _priority(finding.get("severity"), score),
                (
                    "Consider qualifying a second supplier because the product has "
                    "a single evidenced source."
                ),
                [finding.get("supporting_evidence")],
                supplier=supplier,
                product=product,
                dependency=dep,
                dims=["QUALIFIED_ALTERNATIVE_COVERAGE", "SUPPLIER_DIVERSITY"],
            )
        elif dep in {"ONLY_COUNTRY_SOURCE", "ONLY_REGION_SOURCE"}:
            add(
                "RESEARCH_ALTERNATE_COUNTRY",
                _priority(
                    finding.get("severity"),
                    _decimal(by.get("GEOGRAPHIC_DIVERSITY", {}).get("score")),
                ),
                (
                    "Consider researching an alternate geography because allocation is "
                    "concentrated in one location."
                ),
                [finding.get("supporting_evidence")],
                supplier=supplier,
                dependency=dep,
                dims=["GEOGRAPHIC_DIVERSITY"],
            )
        elif dep == "ONLY_SUPPLIER_FOR_CRITICAL_CAPABILITY":
            add(
                "RESEARCH_CAPABILITY_REDUNDANCY",
                _priority(
                    finding.get("severity"),
                    _decimal(by.get("CAPABILITY_REDUNDANCY", {}).get("score")),
                ),
                (
                    "Consider researching capability redundancy because one supplier is "
                    "the only evidenced source for a critical capability."
                ),
                [finding.get("supporting_evidence")],
                supplier=supplier,
                dependency=dep,
                dims=["CAPABILITY_REDUNDANCY"],
            )
        elif dep in {"ONLY_LOW_RISK_SUPPLIER", "ONLY_CURRENTLY_AVAILABLE_SOURCE"}:
            add(
                "REVIEW_HIGH_RISK_SUPPLIER",
                _priority(finding.get("severity"), score),
                "Review the dependency and evidence before relying on a single acceptable source.",
                [finding.get("supporting_evidence")],
                supplier=supplier,
                dependency=dep,
                dims=["SUPPLIER_DIVERSITY"],
            )
    for row in facts.get("readiness", {}).get("results", []):
        supplier = row.get("supplier_id")
        product = row.get("product_id")
        if row.get("readiness_state") == "DUE_DILIGENCE_REQUIRED":
            add(
                "COMPLETE_DUE_DILIGENCE",
                "HIGH",
                (
                    "Consider completing due diligence before treating this supplier as a "
                    "verified alternate."
                ),
                ["8E.2 readiness"],
                supplier=supplier,
                product=product,
                dims=["VERIFIED_ALTERNATIVE_COVERAGE"],
                missing=row.get("dd_gaps"),
            )
        elif row.get("readiness_state") == "RESEARCH_REQUIRED":
            add(
                "REFRESH_COMMERCIAL_EVIDENCE",
                "MEDIUM",
                "Consider refreshing stale supplier evidence before relying on this alternate.",
                ["8E.2 readiness"],
                supplier=supplier,
                product=product,
                dims=["FRESHNESS", "COMMERCIAL_FLEXIBILITY"],
                missing=row.get("missing_evidence"),
            )
    if (s := _decimal(by.get("SUPPLIER_DIVERSITY", {}).get("score"))) is not None and s <= 40:
        add(
            "REDUCE_SINGLE_SUPPLIER_CONCENTRATION",
            _priority(None, s),
            (
                "Consider reducing single-supplier concentration because evidenced "
                "allocation diversity is low."
            ),
            [by["SUPPLIER_DIVERSITY"]["supporting_inputs"]],
            dims=["SUPPLIER_DIVERSITY"],
        )
    if by.get("EVIDENCE_CONFIDENCE", {}).get("score") is None:
        add(
            "VERIFY_CERTIFICATION",
            "MEDIUM",
            (
                "Consider verifying critical supplier certifications because confidence "
                "evidence is incomplete."
            ),
            ["missing confidence evidence"],
            dims=["EVIDENCE_CONFIDENCE"],
            missing=by.get("EVIDENCE_CONFIDENCE", {}).get("missing_evidence"),
        )
    return rows


def calculate_resilience(
    db: Session,
    owner: User,
    portfolio: SupplierPortfolioContext,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    assessment = _assessment(db, owner, portfolio, assessment_version_id)

    def query_rows(model: Any) -> list[Any]:
        return list(
            db.scalars(
                select(model).where(
                    model.owner_id == owner.id,
                    model.portfolio_id == portfolio.id,
                    model.assessment_version_id == assessment.id,
                )
            )
        )

    q = query_rows
    dimensions_existing = q(SupplierPortfolioResilienceDimensionResult)
    score_existing = db.scalar(
        select(SupplierPortfolioResilienceScore).where(
            SupplierPortfolioResilienceScore.owner_id == owner.id,
            SupplierPortfolioResilienceScore.portfolio_id == portfolio.id,
            SupplierPortfolioResilienceScore.assessment_version_id == assessment.id,
        )
    )
    confidence_existing = db.scalar(
        select(SupplierPortfolioConfidenceProjection).where(
            SupplierPortfolioConfidenceProjection.owner_id == owner.id,
            SupplierPortfolioConfidenceProjection.portfolio_id == portfolio.id,
            SupplierPortfolioConfidenceProjection.assessment_version_id == assessment.id,
        )
    )
    risk_existing = db.scalar(
        select(SupplierPortfolioRiskProjection).where(
            SupplierPortfolioRiskProjection.owner_id == owner.id,
            SupplierPortfolioRiskProjection.portfolio_id == portfolio.id,
            SupplierPortfolioRiskProjection.assessment_version_id == assessment.id,
        )
    )
    rec_existing = q(SupplierPortfolioRecommendation)
    if (
        len(dimensions_existing) == len(DIMENSIONS)
        and score_existing
        and confidence_existing
        and risk_existing
    ):
        return _bundle(
            score_existing,
            dimensions_existing,
            confidence_existing,
            risk_existing,
            rec_existing,
            assessment,
        )
    members = _dedupe_members(_members(assessment))
    snapshot = assessment.input_snapshot if isinstance(assessment.input_snapshot, dict) else {}
    facts = {
        "concentration": calculate_concentration(db, owner, portfolio, assessment.id),
        "dependencies": calculate_dependencies(db, owner, portfolio, assessment.id),
        "readiness": calculate_readiness(db, owner, portfolio, assessment.id),
        "provided": snapshot.get("provided", {}),
    }
    dimensions = _build_dimensions(members, facts)
    available = [row for row in dimensions if row["score"] is not None]
    weight = sum((WEIGHTS[row["dimension"]] for row in available), Decimal("0"))
    base = (
        sum((_decimal(row["score"]) or 0) * WEIGHTS[row["dimension"]] for row in available) / weight
        if weight
        else None
    )
    penalties = []
    largest = _decimal(_metric(facts, "supplier", "largest_supplier_share").get("value"))
    if largest is not None and largest >= 50:
        penalties.append(
            {
                "type": "critical_single_source_dependency",
                "points": 10,
                "reason": "largest supplier share is at least 50%",
            }
        )
    if any(r.get("severity") == "CRITICAL" for r in facts["dependencies"]["results"]):
        penalties.append(
            {
                "type": "critical_dependency",
                "points": 10,
                "reason": "critical dependency finding exists",
            }
        )
    score = (
        _clamp(base - sum((Decimal(str(p["points"])) for p in penalties), Decimal("0")))
        if base is not None
        else None
    )
    evidence = (
        "SUFFICIENT"
        if len(available) == len(DIMENSIONS)
        else ("PARTIAL" if available else "INSUFFICIENT")
    )
    missing = sorted({x for row in dimensions for x in row["missing_evidence"]})
    cv: list[Decimal] = []
    for member in members:
        confidence_observation = _decimal(member.get("confidence"))
        if confidence_observation is not None:
            cv.append(confidence_observation)
    cvalue = sum(cv, Decimal("0")) / Decimal(len(cv)) if cv else None
    confidence = SupplierPortfolioConfidenceProjection(
        owner_id=assessment.owner_id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id,
        value=_round(cvalue),
        classification=_classify(cvalue),
        evidence_status=(
            "SUFFICIENT"
            if cv and evidence == "SUFFICIENT"
            else ("PARTIAL" if cv else "INSUFFICIENT")
        ),
        explanation="Confidence summarizes evidence quality separately from resilience.",
        limitations=[] if cv else ["No member confidence observations are available."],
        calculation_version=CONFIDENCE_VERSION,
    )
    risks = [str(m.get("risk", "unknown")).lower() for m in members]
    rank = {"low": 1, "moderate": 2, "medium": 2, "high": 3, "critical": 4, "unknown": 0}
    rlabel = {0: "UNKNOWN", 1: "LOW", 2: "MODERATE", 3: "HIGH", 4: "CRITICAL"}[
        max((rank.get(r, 0) for r in risks), default=0)
    ]
    risk = SupplierPortfolioRiskProjection(
        owner_id=assessment.owner_id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id,
        classification=rlabel,
        exposure=_round(largest),
        supporting_inputs={"supplier_risk_values": risks},
        explanation=(
            "Risk is a separate supplier-risk projection and does not alter " "resilience scoring."
        ),
        calculation_version=RISK_VERSION,
    )
    dimension_rows = [
        SupplierPortfolioResilienceDimensionResult(
            owner_id=assessment.owner_id,
            portfolio_id=portfolio.id,
            assessment_version_id=assessment.id,
            dimension=row["dimension"],
            score=row["score"],
            classification=row["classification"],
            evidence_status=row["evidence_status"],
            calculation_version=row["calculation_version"],
            supporting_inputs={
                "weight": float(WEIGHTS[row["dimension"]]),
                **row["supporting_inputs"],
            },
            evidence_references=row["evidence_references"],
            penalties=row["penalties"],
            limitations=row["limitations"],
            missing_evidence=row["missing_evidence"],
            explanation=row["explanation"],
        )
        for row in dimensions
    ]
    score_row = SupplierPortfolioResilienceScore(
        owner_id=assessment.owner_id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id,
        score=_round(score),
        classification=_classify(score),
        evidence_status=evidence,
        confidence_value=_round(cvalue),
        confidence_classification=_classify(cvalue),
        score_version=SCORE_VERSION,
        component_snapshot={
            "weights": {k: float(v) for k, v in WEIGHTS.items()},
            "dimensions": {r["dimension"]: _number(_decimal(r["score"])) for r in dimensions},
            "threshold_version": THRESHOLD_VERSION,
        },
        penalty_snapshot=penalties,
        missing_evidence=missing,
        explanation=(
            "Overall resilience is the weighted mean of available dimensions minus "
            "explicit non-overlapping penalties; missing dimensions are excluded "
            "and surfaced."
        ),
    )
    recs = _recommendations(assessment, portfolio, dimensions, facts)
    try:
        db.add_all([*dimension_rows, score_row, confidence, risk, *recs])
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_dimensions = q(SupplierPortfolioResilienceDimensionResult)
        existing_score = db.scalar(
            select(SupplierPortfolioResilienceScore).where(
                SupplierPortfolioResilienceScore.assessment_version_id == assessment.id
            )
        )
        existing_confidence = db.scalar(
            select(SupplierPortfolioConfidenceProjection).where(
                SupplierPortfolioConfidenceProjection.assessment_version_id == assessment.id
            )
        )
        existing_risk = db.scalar(
            select(SupplierPortfolioRiskProjection).where(
                SupplierPortfolioRiskProjection.assessment_version_id == assessment.id
            )
        )
        existing_recommendations = q(SupplierPortfolioRecommendation)
        if (
            existing_score is not None
            and existing_confidence is not None
            and existing_risk is not None
        ):
            return _bundle(
                existing_score,
                existing_dimensions,
                existing_confidence,
                existing_risk,
                existing_recommendations,
                assessment,
            )
        raise HTTPException(500, "Resilience assessment could not be completed safely.") from None
    if score_row is None or confidence is None or risk is None:
        raise HTTPException(500, "Resilience assessment could not be completed safely.")
    return _bundle(score_row, dimension_rows, confidence, risk, recs, assessment)


def _bundle(
    score: SupplierPortfolioResilienceScore,
    dimensions: list[SupplierPortfolioResilienceDimensionResult],
    confidence: SupplierPortfolioConfidenceProjection,
    risk: SupplierPortfolioRiskProjection,
    recommendations: list[SupplierPortfolioRecommendation],
    assessment: SupplierPortfolioAssessmentVersion,
) -> dict[str, Any]:
    return {
        "assessment_version_id": str(assessment.id),
        "score": _score_payload(score),
        "dimensions": [
            _dimension_payload(row) for row in sorted(dimensions, key=lambda row: row.dimension)
        ],
        "confidence": _confidence_payload(confidence),
        "risk": _risk_payload(risk),
        "recommendations": [
            _recommendation_payload(row)
            for row in sorted(recommendations, key=lambda row: row.logical_key)
        ],
    }
