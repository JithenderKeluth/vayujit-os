"""PR-6A canonical, target-specific decision evidence/readiness authority."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.decision_evidence_models import (
    DECISION_POLICY_VERSION,
    DecisionEvidenceSnapshot,
)
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceAssessment,
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
)
from vayujit_api.intelligence.economic_calculation_models import EconomicCalculation
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.product_opportunity_scoring_models import ProductOpportunityDecision
from vayujit_api.intelligence.product_opportunity_unit_economics_models import (
    ProductOpportunityUnitEconomics,
)
from vayujit_api.intelligence.shortlisting_models import SupplierShortlistDecision


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(item) for item in value]
    return value


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(_json(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _item(code: str, message: str, *, severity: str = "HIGH", **extra: Any) -> dict[str, Any]:
    return {"code": code, "message": message, "severity": severity, **extra}


def _owner_opportunity(db: Session, owner: User, opportunity_id: uuid.UUID) -> ProductOpportunity:
    row = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id,
            ProductOpportunity.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Product opportunity not found.")
    return row


def _goal(
    db: Session, owner: User, opportunity_id: uuid.UUID, goal_id: uuid.UUID | None
) -> BusinessAgentGoal | None:
    if goal_id is not None:
        row = db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.id == goal_id, BusinessAgentGoal.owner_id == owner.id
            )
        )
        if row is None:
            raise HTTPException(404, "Business Agent goal not found.")
        return row
    goals = list(
        db.scalars(
            select(BusinessAgentGoal)
            .where(BusinessAgentGoal.owner_id == owner.id)
            .order_by(BusinessAgentGoal.updated_at.desc(), BusinessAgentGoal.created_at.desc())
        )
    )
    for row in goals:
        if str((row.structured_goal or {}).get("product_opportunity_id") or "") == str(
            opportunity_id
        ):
            return row
    return goals[0] if goals else None


def _latest_assessment(
    db: Session, owner: User, opportunity: ProductOpportunity, assessment_id: uuid.UUID | None
) -> ProductOpportunityAssessment | None:
    if assessment_id is not None:
        row = db.scalar(
            select(ProductOpportunityAssessment).where(
                ProductOpportunityAssessment.id == assessment_id,
                ProductOpportunityAssessment.owner_id == owner.id,
                ProductOpportunityAssessment.opportunity_id == opportunity.id,
            )
        )
        if row is None:
            raise HTTPException(404, "Product opportunity assessment not found.")
        return row
    if opportunity.current_assessment_id:
        row = db.scalar(
            select(ProductOpportunityAssessment).where(
                ProductOpportunityAssessment.id == opportunity.current_assessment_id,
                ProductOpportunityAssessment.owner_id == owner.id,
            )
        )
        if row is not None:
            return row
    return db.scalar(
        select(ProductOpportunityAssessment)
        .where(
            ProductOpportunityAssessment.owner_id == owner.id,
            ProductOpportunityAssessment.opportunity_id == opportunity.id,
        )
        .order_by(ProductOpportunityAssessment.version.desc())
    )


def _latest_product_decision(
    db: Session, owner: User, opportunity_id: uuid.UUID
) -> ProductOpportunityDecision | None:
    return db.scalar(
        select(ProductOpportunityDecision)
        .where(
            ProductOpportunityDecision.owner_id == owner.id,
            ProductOpportunityDecision.opportunity_id == opportunity_id,
        )
        .order_by(ProductOpportunityDecision.created_at.desc())
    )


def _supplier_environment(supplier: CrossMarketplaceSupplier | None) -> dict[str, Any]:
    if supplier is None:
        return {
            "state": "MISSING",
            "trust": "UNKNOWN",
            "verification": "UNKNOWN",
            "freshness": "UNKNOWN",
        }
    view = supplier.view_json if isinstance(supplier.view_json, dict) else {}
    raw = " ".join(
        str(view.get(key, ""))
        for key in ("provider_mode", "provenance", "source_mode", "environment", "access_mode")
    ).upper()
    trust = "LIVE_READ_ONLY" if "LIVE" in raw else "DETERMINISTIC_TEST"
    verification = str(
        view.get("verification_state") or view.get("verification_status") or "UNVERIFIED"
    ).upper()
    return {
        "state": "PRESENT",
        "trust": trust,
        "verification": verification,
        "identity_state": supplier.identity_state,
        "freshness": supplier.freshness_status or "UNKNOWN",
        "source_diversity": str(supplier.source_diversity_score),
        "supplier_id": str(supplier.id),
    }


def _product_environment(opportunity: ProductOpportunity) -> dict[str, Any]:
    profile = (
        opportunity.intelligence_profile
        if isinstance(opportunity.intelligence_profile, dict)
        else {}
    )
    origin = str(opportunity.origin or "").lower()
    trust = (
        "LIVE_READ_ONLY"
        if "live" in json.dumps(profile).lower()
        or origin in {"marketplace_discovery", "external_research"}
        else "DERIVED"
    )
    return {
        "trust": trust,
        "origin": opportunity.origin,
        "evidence_state": opportunity.evidence_state,
        "freshness": profile.get("freshness") or profile.get("freshness_status") or "UNKNOWN",
        "source_ids": profile.get("source_ids") or profile.get("evidence_ids") or [],
    }


def _latest_supplier_context(
    db: Session, owner: User, opportunity_id: uuid.UUID, supplier_id: uuid.UUID | None
) -> tuple[SupplierDueDiligenceContext | None, SupplierDueDiligenceAssessment | None]:
    query = select(SupplierDueDiligenceContext).where(
        SupplierDueDiligenceContext.owner_id == owner.id,
        SupplierDueDiligenceContext.opportunity_id == opportunity_id,
    )
    if supplier_id is not None:
        query = query.where(SupplierDueDiligenceContext.supplier_id == supplier_id)
    context = db.scalars(query.order_by(SupplierDueDiligenceContext.updated_at.desc())).first()
    if context is None:
        return None, None
    assessment = db.scalar(
        select(SupplierDueDiligenceAssessment)
        .where(
            SupplierDueDiligenceAssessment.owner_id == owner.id,
            SupplierDueDiligenceAssessment.context_id == context.id,
        )
        .order_by(SupplierDueDiligenceAssessment.version.desc())
    )
    return context, assessment


def _latest_shortlist(
    db: Session, owner: User, supplier_id: uuid.UUID | None, context_id: uuid.UUID | None
) -> SupplierShortlistDecision | None:
    if supplier_id is None:
        return None
    query = select(SupplierShortlistDecision).where(
        SupplierShortlistDecision.owner_id == owner.id,
        SupplierShortlistDecision.supplier_id == supplier_id,
    )
    if context_id is not None:
        query = query.where(SupplierShortlistDecision.context_id == context_id)
    return db.scalars(query.order_by(SupplierShortlistDecision.created_at.desc())).first()


def _latest_economics(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
) -> tuple[
    CommercialReadinessSnapshot | None,
    EconomicCalculation | None,
    ProductOpportunityUnitEconomics | None,
]:
    readiness = db.scalars(
        select(CommercialReadinessSnapshot)
        .where(
            CommercialReadinessSnapshot.owner_id == owner.id,
            CommercialReadinessSnapshot.opportunity_id == opportunity_id,
        )
        .order_by(CommercialReadinessSnapshot.created_at.desc())
    ).first()
    calc_query = select(EconomicCalculation).where(
        EconomicCalculation.owner_id == owner.id,
        EconomicCalculation.product_opportunity_id == opportunity_id,
    )
    if assessment_id is not None:
        calc_query = calc_query.where(EconomicCalculation.assessment_id == assessment_id)
    if supplier_id is not None:
        calc_query = calc_query.where(EconomicCalculation.supplier_id == supplier_id)
    calculation = db.scalars(calc_query.order_by(EconomicCalculation.created_at.desc())).first()
    unit_query = select(ProductOpportunityUnitEconomics).where(
        ProductOpportunityUnitEconomics.owner_id == owner.id,
        ProductOpportunityUnitEconomics.opportunity_id == opportunity_id,
    )
    if assessment_id is not None:
        unit_query = unit_query.where(
            ProductOpportunityUnitEconomics.assessment_id == assessment_id
        )
    if supplier_id is not None:
        unit_query = unit_query.where(ProductOpportunityUnitEconomics.supplier_id == supplier_id)
    unit = db.scalars(
        unit_query.order_by(ProductOpportunityUnitEconomics.created_at.desc())
    ).first()
    return readiness, calculation, unit


def _policy(target: str) -> dict[str, Any]:
    target = target.upper()
    if target not in {
        "PRODUCT_SELECTION",
        "SUPPLIER_SELECTION",
        "COMMERCIAL_ASSESSMENT",
        "LAUNCH_DECISION",
    }:
        raise HTTPException(422, "Unsupported decision target.")
    return {
        "target": target,
        "version": DECISION_POLICY_VERSION,
        "required_human_decisions": {
            "PRODUCT_SELECTION": ["product_shortlist"],
            "SUPPLIER_SELECTION": ["product_shortlist", "supplier_shortlist"],
            "COMMERCIAL_ASSESSMENT": ["product_shortlist"],
            "LAUNCH_DECISION": ["product_shortlist", "supplier_shortlist"],
        }[target],
        "required_trust": {
            "COMMERCIAL_ASSESSMENT": ["product_identity"],
            "LAUNCH_DECISION": ["LIVE_READ_ONLY_supplier", "demand_evidence"],
        }.get(target, ["product_identity"]),
    }


def _safe_action(
    blockers: list[dict[str, Any]], warnings: list[dict[str, Any]], target: str
) -> dict[str, Any]:
    rows = blockers + warnings
    priority = {
        "PRODUCT_SELECTION_REQUIRED": 10,
        "ECONOMICS_CALCULATION_REQUIRED": 20,
        "CAPITAL_DOES_NOT_FIT": 25,
        "MATERIAL_CONTRADICTION": 30,
        "LIVE_SUPPLIER_EVIDENCE_MISSING": 40,
        "SUPPLIER_NOT_VERIFIED": 45,
        "DEMAND_EVIDENCE_MISSING": 50,
        "COMMERCIAL_INPUT_UNKNOWN": 60,
    }
    selected = sorted(
        rows, key=lambda item: (priority.get(str(item.get("code")), 999), str(item.get("code")))
    )
    if not selected:
        return {
            "code": "REVIEW_DECISION_EVIDENCE",
            "label": "Review decision evidence",
            "external_action": False,
        }
    item = selected[0]
    return {
        "code": str(item.get("code")),
        "label": {
            "PRODUCT_SELECTION_REQUIRED": "Select the product explicitly",
            "ECONOMICS_CALCULATION_REQUIRED": "Complete the economics scenario",
            "CAPITAL_DOES_NOT_FIT": "Review the capital shortfall",
            "LIVE_SUPPLIER_EVIDENCE_MISSING": "Obtain live supplier evidence",
            "SUPPLIER_NOT_VERIFIED": "Review supplier verification evidence",
            "DEMAND_EVIDENCE_MISSING": "Collect demand evidence",
        }.get(str(item.get("code")), "Review the highest-priority evidence gap"),
        "reason": str(item.get("message")),
        "target": target,
        "external_action": False,
    }


def _assemble(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str,
    assessment_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    policy = _policy(target)
    opportunity = _owner_opportunity(db, owner, opportunity_id)
    goal = _goal(db, owner, opportunity_id, goal_id)
    assessment = _latest_assessment(db, owner, opportunity, assessment_id)
    product_decision = _latest_product_decision(db, owner, opportunity_id)
    context, dd_assessment = _latest_supplier_context(db, owner, opportunity_id, supplier_id)
    if supplier_id is None and context is not None:
        supplier_id = context.supplier_id
    supplier = (
        db.scalar(
            select(CrossMarketplaceSupplier).where(
                CrossMarketplaceSupplier.id == supplier_id,
                CrossMarketplaceSupplier.owner_id == owner.id,
            )
        )
        if supplier_id is not None
        else None
    )
    if supplier_id is not None and supplier is None:
        raise HTTPException(404, "Supplier is not available in the owner scope.")
    shortlist = _latest_shortlist(db, owner, supplier_id, context.id if context else None)
    commercial, landed, unit = _latest_economics(
        db, owner, opportunity_id, assessment.id if assessment else None, supplier_id
    )

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    product_env = _product_environment(opportunity)
    if (
        not product_decision or product_decision.action != "shortlist"
    ) and target != "PRODUCT_SELECTION":
        blockers.append(
            _item(
                "PRODUCT_SELECTION_REQUIRED",
                "A human product selection is required before this decision.",
                decision="HUMAN",
            )
        )
    if not opportunity.name or opportunity.evidence_state in {"unknown", "insufficient_evidence"}:
        blockers.append(
            _item("PRODUCT_IDENTITY_INSUFFICIENT", "Product identity evidence is insufficient.")
        )
    demand = {
        "state": "MISSING",
        "trust": "UNKNOWN",
        "reason": "No canonical demand-evidence authority is available for this snapshot.",
    }
    unknowns.append(
        _item("DEMAND_EVIDENCE_MISSING", demand["reason"], severity="INFO", category="demand")
    )

    supplier_env = _supplier_environment(supplier)
    if target in {"SUPPLIER_SELECTION", "LAUNCH_DECISION"} and supplier is None:
        blockers.append(
            _item("SUPPLIER_REQUIRED", "A supplier context is required for this decision.")
        )
    if supplier is None:
        unknowns.append(
            _item(
                "LIVE_SUPPLIER_EVIDENCE_MISSING",
                "No supplier evidence is linked to this opportunity.",
                severity="INFO",
                category="supplier",
            )
        )
    else:
        if supplier_env["trust"] != "LIVE_READ_ONLY":
            warnings.append(
                _item(
                    "SUPPLIER_DETERMINISTIC_ONLY",
                    "Supplier evidence is deterministic/local, not live supplier evidence.",
                    severity="HIGH",
                    trust=supplier_env["trust"],
                )
            )
        if supplier_env["verification"] not in {"VERIFIED", "HIGH_CONFIDENCE"}:
            warnings.append(
                _item(
                    "SUPPLIER_NOT_VERIFIED",
                    "Supplier verification remains incomplete.",
                    severity="HIGH",
                    verification=supplier_env["verification"],
                )
            )
        if target == "LAUNCH_DECISION" and supplier_env["trust"] != "LIVE_READ_ONLY":
            blockers.append(
                _item(
                    "LIVE_SUPPLIER_EVIDENCE_MISSING",
                    "Launch decision requires live read-only supplier evidence.",
                )
            )
        if target == "LAUNCH_DECISION" and supplier_env["verification"] not in {
            "VERIFIED",
            "HIGH_CONFIDENCE",
        }:
            blockers.append(
                _item(
                    "SUPPLIER_NOT_VERIFIED",
                    "Launch decision requires supplier verification evidence.",
                )
            )
    if shortlist is None and supplier is not None:
        warnings.append(
            _item(
                "HUMAN_SUPPLIER_SHORTLIST_MISSING",
                "Supplier shortlist remains a human decision and is not recorded.",
                severity="HIGH",
                decision="HUMAN",
            )
        )
    if dd_assessment is not None:
        dd_gaps = list(
            db.scalars(
                select(SupplierEvidenceGap).where(
                    SupplierEvidenceGap.context_id == dd_assessment.context_id,
                    SupplierEvidenceGap.assessment_version == dd_assessment.version,
                )
            )
        )
        for gap in dd_gaps:
            if gap.contradiction_state == "present" or gap.status == "CONTRADICTORY":
                contradictions.append(
                    _item(
                        "MATERIAL_CONTRADICTION",
                        gap.reason,
                        severity=gap.severity,
                        dimension=gap.dimension,
                    )
                )
            elif gap.classification == "OPTIONAL":
                warnings.append(
                    _item(
                        "OPTIONAL_EVIDENCE_GAP",
                        gap.reason,
                        severity=gap.severity,
                        dimension=gap.dimension,
                    )
                )
            elif gap.status != "RESOLVED":
                unknowns.append(
                    _item(
                        "SUPPLIER_EVIDENCE_GAP",
                        gap.reason,
                        severity=gap.severity,
                        dimension=gap.dimension,
                    )
                )
    if commercial is not None:
        for row in commercial.contradictions or []:
            contradictions.append(
                _item("MATERIAL_CONTRADICTION", str(row), severity="HIGH", source="PR-5A")
            )
        unknowns.extend(
            _item("COMMERCIAL_INPUT_UNKNOWN", str(row), severity="INFO", category="commercial")
            for row in commercial.unknown_inputs or commercial.missing_inputs or []
        )
        warnings.extend(
            _item("COMMERCIAL_ASSUMPTION", str(row), severity="MEDIUM", category="commercial")
            for row in commercial.assumptions or []
        )
    if landed is None:
        if target in {"COMMERCIAL_ASSESSMENT", "LAUNCH_DECISION"}:
            blockers.append(
                _item(
                    "ECONOMICS_CALCULATION_REQUIRED",
                    "No PR-5B landed-cost calculation is linked to this decision.",
                )
            )
    else:
        if landed.status != "COMPLETE":
            blockers.append(
                _item(
                    "ECONOMICS_CALCULATION_REQUIRED",
                    "The linked landed-cost calculation is not complete.",
                    status=landed.status,
                )
            )
        unknowns.extend(
            _item("LANDED_COST_UNKNOWN", str(row), severity="INFO", category="landed_cost")
            for row in landed.missing_inputs or []
        )
        warnings.extend(
            _item("LANDED_COST_WARNING", str(row), severity="MEDIUM", category="landed_cost")
            for row in landed.warnings or []
        )
    if unit is None:
        if target in {"COMMERCIAL_ASSESSMENT", "LAUNCH_DECISION"}:
            blockers.append(
                _item(
                    "UNIT_ECONOMICS_REQUIRED",
                    "No PR-5C unit-economics calculation is linked to this decision.",
                )
            )
    else:
        if unit.status != "READY" and target in {"COMMERCIAL_ASSESSMENT", "LAUNCH_DECISION"}:
            blockers.append(
                _item(
                    "UNIT_ECONOMICS_REQUIRED",
                    "The linked unit-economics calculation is not ready.",
                    status=unit.status,
                )
            )
        if unit.capital_fit_status == "DOES_NOT_FIT":
            blockers.append(
                _item(
                    "CAPITAL_DOES_NOT_FIT",
                    "The modeled capital requirement exceeds the available capital.",
                    status=unit.capital_fit_status,
                )
            )
        elif unit.capital_fit_status == "FITS":
            warnings.append(
                _item(
                    "CAPITAL_FITS_NOT_RECOMMENDATION",
                    "Capital fits the modeled scenario; this is not a recommendation.",
                    severity="INFO",
                    status="FITS",
                )
            )
        unknowns.extend(
            _item("UNIT_ECONOMICS_UNKNOWN", str(row), severity="INFO", category="unit_economics")
            for row in unit.unknown_excluded or []
        )
        limitations.extend(
            _item(
                "UNIT_ECONOMICS_LIMITATION",
                str(row),
                severity="INFO",
                category="unit_economics",
            )
            for row in unit.limitations or []
        )
        contradictions.extend(
            _item("UNIT_ECONOMICS_CONTRADICTION", str(row), severity="HIGH", source="PR-5C")
            for row in unit.contradictions or []
        )
    contradictions = sorted(
        contradictions, key=lambda row: (str(row.get("code")), str(row.get("message")))
    )
    if contradictions:
        blockers.extend(contradictions)
    if target == "LAUNCH_DECISION":
        blockers.append(
            _item(
                "DEMAND_EVIDENCE_REQUIRED",
                "Launch decision has no canonical demand evidence.",
                severity="HIGH",
            )
        )
    if blockers:
        readiness = "BLOCKED"
    elif warnings or unknowns:
        readiness = "NEEDS_EVIDENCE"
    else:
        readiness = "READY"
    refs = {
        "goal_id": str(goal.id) if goal else None,
        "opportunity_id": str(opportunity.id),
        "assessment_id": str(assessment.id) if assessment else None,
        "product_decision_id": str(product_decision.id) if product_decision else None,
        "supplier_id": str(supplier.id) if supplier else None,
        "shortlist_decision_id": str(shortlist.id) if shortlist else None,
        "due_diligence_context_id": str(context.id) if context else None,
        "due_diligence_assessment_id": str(dd_assessment.id) if dd_assessment else None,
        "commercial_readiness_snapshot_id": str(commercial.id) if commercial else None,
        "landed_cost_calculation_id": str(landed.id) if landed else None,
        "unit_economics_id": str(unit.id) if unit else None,
    }
    trust = {
        "product": product_env,
        "product_selection": {
            "trust": (
                "HUMAN"
                if product_decision and product_decision.action == "shortlist"
                else "UNKNOWN"
            ),
            "action": product_decision.action if product_decision else None,
        },
        "supplier": supplier_env,
        "supplier_shortlist": {
            "trust": "HUMAN" if shortlist else "UNKNOWN",
            "decision": shortlist.decision if shortlist else None,
        },
        "due_diligence": {
            "trust": supplier_env.get("trust", "UNKNOWN"),
            "readiness": dd_assessment.readiness if dd_assessment else "NOT_ASSESSED",
        },
        "commercial": {
            "trust": "SOURCE_PROVIDED" if commercial else "UNKNOWN",
            "assumptions": "ASSUMED" if commercial and commercial.assumptions else "UNKNOWN",
        },
        "landed_cost": {
            "trust": "DERIVED" if landed else "UNKNOWN",
            "status": landed.status if landed else "UNKNOWN",
        },
        "unit_economics": {
            "trust": "DERIVED" if unit else "UNKNOWN",
            "status": unit.status if unit else "UNKNOWN",
        },
        "demand": demand,
    }
    evidence = {
        "product": {
            "name": opportunity.name,
            "category": opportunity.category,
            "subcategory": opportunity.subcategory,
            "identity": bool(opportunity.name),
            "source_lineage": product_env["source_ids"],
        },
        "product_selected": bool(product_decision and product_decision.action == "shortlist"),
        "supplier": {
            "present": supplier is not None,
            "verification": supplier_env.get("verification"),
            "trust": supplier_env.get("trust"),
        },
        "demand": demand,
        "economics": {
            "landed_cost_status": landed.status if landed else "MISSING",
            "unit_economics_status": unit.status if unit else "MISSING",
            "capital_fit": unit.capital_fit_status if unit else "UNKNOWN",
            "positive_contribution": bool(
                unit
                and unit.per_unit_contribution is not None
                and float(str(unit.per_unit_contribution)) > 0
            ),
        },
    }
    freshness = {
        "product": product_env.get("freshness", "UNKNOWN"),
        "supplier": supplier_env.get("freshness", "UNKNOWN"),
        "due_diligence": dd_assessment.created_at.isoformat() if dd_assessment else "UNKNOWN",
        "commercial": commercial.created_at.isoformat() if commercial else "UNKNOWN",
    }
    semantic = {
        "owner_id": str(owner.id),
        "target": policy["target"],
        "policy_version": policy["version"],
        "references": refs,
        "trust": trust,
        "readiness": readiness,
        "blockers": blockers,
        "warnings": warnings,
        "unknowns": unknowns,
        "contradictions": contradictions,
        "evidence": evidence,
        "limitations": limitations,
        "freshness": freshness,
    }
    fingerprint = _fingerprint(semantic)
    return {
        "opportunity": opportunity,
        "goal": goal,
        "assessment": assessment,
        "product_decision": product_decision,
        "supplier": supplier,
        "shortlist": shortlist,
        "context": context,
        "dd_assessment": dd_assessment,
        "commercial": commercial,
        "landed": landed,
        "unit": unit,
        "policy": policy,
        "refs": refs,
        "trust": trust,
        "evidence": evidence,
        "blockers": blockers,
        "warnings": warnings,
        "unknowns": unknowns,
        "contradictions": contradictions,
        "limitations": sorted(
            limitations,
            key=lambda row: (str(row.get("code")), str(row.get("message"))),
        ),
        "freshness": freshness,
        "readiness": readiness,
        "safe_next_action": _safe_action(blockers, warnings, target),
        "fingerprint": fingerprint,
    }


def project_decision_readiness(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str = "COMMERCIAL_ASSESSMENT",
    assessment_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    view = _assemble(
        db,
        owner,
        opportunity_id,
        target=target,
        assessment_id=assessment_id,
        goal_id=goal_id,
        supplier_id=supplier_id,
    )
    return _serialize_view(view, snapshot=None)


def create_decision_snapshot(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str = "COMMERCIAL_ASSESSMENT",
    assessment_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> DecisionEvidenceSnapshot:
    view = _assemble(
        db,
        owner,
        opportunity_id,
        target=target,
        assessment_id=assessment_id,
        goal_id=goal_id,
        supplier_id=supplier_id,
    )
    existing = db.scalar(
        select(DecisionEvidenceSnapshot).where(
            DecisionEvidenceSnapshot.owner_id == owner.id,
            DecisionEvidenceSnapshot.input_fingerprint == view["fingerprint"],
        )
    )
    if existing is not None:
        return existing
    previous = db.scalar(
        select(DecisionEvidenceSnapshot)
        .where(
            DecisionEvidenceSnapshot.owner_id == owner.id,
            DecisionEvidenceSnapshot.opportunity_id == opportunity_id,
            DecisionEvidenceSnapshot.decision_target == target.upper(),
        )
        .order_by(DecisionEvidenceSnapshot.decision_version.desc())
    )
    row = DecisionEvidenceSnapshot(
        owner_id=owner.id,
        goal_id=view["refs"]["goal_id"],
        opportunity_id=opportunity_id,
        product_decision_id=view["refs"]["product_decision_id"],
        supplier_id=view["refs"]["supplier_id"],
        shortlist_decision_id=view["refs"]["shortlist_decision_id"],
        due_diligence_context_id=view["refs"]["due_diligence_context_id"],
        due_diligence_assessment_id=view["refs"]["due_diligence_assessment_id"],
        commercial_readiness_snapshot_id=view["refs"]["commercial_readiness_snapshot_id"],
        landed_cost_calculation_id=view["refs"]["landed_cost_calculation_id"],
        unit_economics_id=view["refs"]["unit_economics_id"],
        decision_target=target.upper(),
        decision_version=(previous.decision_version + 1) if previous else 1,
        policy_version=view["policy"]["version"],
        input_references=view["refs"],
        trust_environment=view["trust"],
        evidence_summary=view["evidence"],
        blockers=view["blockers"],
        warnings=view["warnings"],
        unknowns=view["unknowns"],
        contradictions=view["contradictions"],
        limitations=view["limitations"],
        freshness_summary=view["freshness"],
        readiness_state=view["readiness"],
        safe_next_action=view["safe_next_action"],
        input_fingerprint=view["fingerprint"],
        idempotency_key=idempotency_key or f"decision-evidence:{view['fingerprint']}",
        created_at=_now(),
        notes="PR-6A immutable evidence snapshot; no recommendation or external action.",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _serialize_view(
    view: dict[str, Any], snapshot: DecisionEvidenceSnapshot | None
) -> dict[str, Any]:
    refs = dict(view["refs"])
    if snapshot is not None:
        refs["snapshot_id"] = str(snapshot.id)
    return {
        "id": str(snapshot.id) if snapshot else None,
        "decision_target": view["policy"]["target"],
        "readiness_state": snapshot.readiness_state if snapshot else view["readiness"],
        "policy_version": snapshot.policy_version if snapshot else view["policy"]["version"],
        "decision_version": snapshot.decision_version if snapshot else None,
        "input_fingerprint": snapshot.input_fingerprint if snapshot else view["fingerprint"],
        "input_references": snapshot.input_references if snapshot else refs,
        "trust_environment": snapshot.trust_environment if snapshot else view["trust"],
        "evidence_summary": snapshot.evidence_summary if snapshot else view["evidence"],
        "blockers": snapshot.blockers if snapshot else view["blockers"],
        "warnings": snapshot.warnings if snapshot else view["warnings"],
        "unknowns": snapshot.unknowns if snapshot else view["unknowns"],
        "contradictions": snapshot.contradictions if snapshot else view["contradictions"],
        "limitations": snapshot.limitations if snapshot else view["limitations"],
        "freshness_summary": snapshot.freshness_summary if snapshot else view["freshness"],
        "safe_next_action": snapshot.safe_next_action if snapshot else view["safe_next_action"],
        "external_writes": [],
        "recommendation": None,
        "created_at": snapshot.created_at.isoformat() if snapshot else None,
    }


def serialize_snapshot(row: DecisionEvidenceSnapshot) -> dict[str, Any]:
    return _serialize_view(
        {
            "policy": {"target": row.decision_target, "version": row.policy_version},
            "refs": row.input_references,
            "trust": row.trust_environment,
            "evidence": row.evidence_summary,
            "blockers": row.blockers,
            "warnings": row.warnings,
            "unknowns": row.unknowns,
            "contradictions": row.contradictions,
            "limitations": row.limitations,
            "freshness": row.freshness_summary,
            "readiness": row.readiness_state,
            "safe_next_action": row.safe_next_action,
            "fingerprint": row.input_fingerprint,
        },
        row,
    )


def latest_snapshot(
    db: Session, owner: User, opportunity_id: uuid.UUID, target: str = "COMMERCIAL_ASSESSMENT"
) -> DecisionEvidenceSnapshot | None:
    return db.scalars(
        select(DecisionEvidenceSnapshot)
        .where(
            DecisionEvidenceSnapshot.owner_id == owner.id,
            DecisionEvidenceSnapshot.opportunity_id == opportunity_id,
            DecisionEvidenceSnapshot.decision_target == target.upper(),
        )
        .order_by(
            DecisionEvidenceSnapshot.decision_version.desc(),
            DecisionEvidenceSnapshot.created_at.desc(),
        )
    ).first()
