"""PR-8C evidence-backed procurement-readiness synthesis.

This module deliberately projects existing authorities.  It never verifies a
supplier, completes due diligence, recalculates economics, accepts an offer, or
authorizes procurement.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal, BusinessAgentRun
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.commercial_reassessment_models import CommercialReassessment
from vayujit_api.intelligence.cross_marketplace_models import (
    CrossMarketplaceSupplier,
    CrossMarketplaceSupplierLink,
)
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceAssessment,
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
)
from vayujit_api.intelligence.procurement_readiness_models import (
    SupplierProcurementReadinessAcknowledgement,
    SupplierProcurementReadinessAssessment,
)
from vayujit_api.intelligence.procurement_readiness_schemas import (
    ProcurementReadinessAcknowledgement,
    ProcurementReadinessCreate,
)
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.shortlisting_models import (
    SupplierShortlistContext,
    SupplierShortlistDecision,
    SupplierShortlistVersion,
)
from vayujit_api.intelligence.supplier_comparison_models import SupplierComparisonSnapshot
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCertificationClaim,
    SupplierCommercialTerm,
    SupplierContact,
    SupplierEvidence,
    SupplierProduct,
    SupplierVerification,
)

POLICY_VERSION = "pr8c-readiness-v1"
ALLOWED_SHORTLIST_DECISIONS = {"APPROVE_FOR_SOURCING", "KEEP_UNDER_REVIEW", "REQUEST_MORE_RESEARCH"}
ACK_DECISIONS = {"REVIEWED", "NEEDS_FURTHER_EVIDENCE", "KEEP_UNDER_REVIEW"}


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(v) for v in value]
    return value


def _fingerprint(value: object) -> str:
    payload = json.dumps(_json(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _owned(db: Session, model: Any, owner: User, ident: uuid.UUID, message: str) -> Any:
    row = db.scalar(select(model).where(model.id == ident, model.owner_id == owner.id))
    if row is None:
        raise HTTPException(404, message)
    return row


def _dimension(
    status: str,
    *,
    evidence_refs: Sequence[object] | None = None,
    provenance: str = "UNKNOWN",
    freshness: str = "UNKNOWN",
    missing: list[str] | None = None,
    contradictions: list[object] | None = None,
    blockers: list[str] | None = None,
    next_action: str = "Review the referenced evidence before advancing.",
    values: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "evidence_refs": sorted({str(v) for v in (evidence_refs or [])}),
        "provenance": provenance,
        "freshness": freshness,
        "missing_information": sorted(set(missing or [])),
        "contradictions": contradictions or [],
        "blockers": sorted(set(blockers or [])),
        "safe_next_action": next_action,
        "values": values or {},
    }


def _latest_shortlist(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    canonical_supplier_id: uuid.UUID,
    context_id: uuid.UUID | None,
    decision_id: uuid.UUID | None,
) -> tuple[
    SupplierShortlistContext | None,
    SupplierShortlistVersion | None,
    SupplierShortlistDecision | None,
]:
    decision = None
    context = None
    if decision_id is not None:
        decision = _owned(
            db, SupplierShortlistDecision, owner, decision_id, "Shortlist decision not found."
        )
        if decision.supplier_id != canonical_supplier_id:
            raise HTTPException(409, "Shortlist decision is outside the requested supplier scope.")
        context = _owned(
            db, SupplierShortlistContext, owner, decision.context_id, "Shortlist context not found."
        )
    elif context_id is not None:
        context = _owned(
            db, SupplierShortlistContext, owner, context_id, "Shortlist context not found."
        )
        decision = db.scalar(
            select(SupplierShortlistDecision)
            .where(
                SupplierShortlistDecision.owner_id == owner.id,
                SupplierShortlistDecision.context_id == context.id,
                SupplierShortlistDecision.supplier_id == canonical_supplier_id,
            )
            .order_by(
                SupplierShortlistDecision.created_at.desc(), SupplierShortlistDecision.id.desc()
            )
        )
    else:
        contexts = list(
            db.scalars(
                select(SupplierShortlistContext)
                .where(
                    SupplierShortlistContext.owner_id == owner.id,
                    SupplierShortlistContext.opportunity_id == opportunity.id,
                )
                .order_by(
                    SupplierShortlistContext.updated_at.desc(), SupplierShortlistContext.id.desc()
                )
            )
        )
        for candidate in contexts:
            row = db.scalar(
                select(SupplierShortlistDecision)
                .where(
                    SupplierShortlistDecision.owner_id == owner.id,
                    SupplierShortlistDecision.context_id == candidate.id,
                    SupplierShortlistDecision.supplier_id == canonical_supplier_id,
                )
                .order_by(
                    SupplierShortlistDecision.created_at.desc(), SupplierShortlistDecision.id.desc()
                )
            )
            if row is not None:
                context, decision = candidate, row
                break
    if context is not None:
        if context.opportunity_id != opportunity.id:
            raise HTTPException(409, "Shortlist context is not scoped to this product opportunity.")
        if decision is not None and decision.context_id != context.id:
            raise HTTPException(409, "Shortlist decision is not scoped to this context.")
    version = None
    if decision is not None:
        version = _owned(
            db,
            SupplierShortlistVersion,
            owner,
            decision.shortlist_version_id,
            "Shortlist version not found.",
        )
        if version.context_id != decision.context_id:
            raise HTTPException(409, "Shortlist version is not scoped to this context.")
    return context, version, decision


def _source_supplier(
    db: Session, owner: User, canonical: CrossMarketplaceSupplier, product_id: uuid.UUID | None
) -> tuple[Supplier | None, SupplierProduct | None, list[CrossMarketplaceSupplierLink]]:
    links = list(
        db.scalars(
            select(CrossMarketplaceSupplierLink)
            .where(
                CrossMarketplaceSupplierLink.owner_id == owner.id,
                CrossMarketplaceSupplierLink.canonical_supplier_id == canonical.id,
                CrossMarketplaceSupplierLink.match_state == "MATCH",
            )
            .order_by(CrossMarketplaceSupplierLink.created_at, CrossMarketplaceSupplierLink.id)
        )
    )
    product = None
    if product_id is not None:
        product = _owned(db, SupplierProduct, owner, product_id, "Supplier product not found.")
        if not any(link.supplier_id == product.supplier_id for link in links):
            raise HTTPException(409, "Supplier product does not belong to the canonical supplier.")
    supplier = None
    if product is not None:
        supplier = _owned(db, Supplier, owner, product.supplier_id, "Supplier not found.")
    elif links:
        supplier = _owned(db, Supplier, owner, links[0].supplier_id, "Supplier not found.")
    return supplier, product, links


def _resolve_product_id(
    db: Session,
    owner: User,
    requested: uuid.UUID | None,
    reassessment: CommercialReassessment | None,
    comparison: SupplierComparisonSnapshot | None,
    canonical_supplier_id: uuid.UUID,
) -> uuid.UUID | None:
    if requested is not None:
        return requested
    if reassessment is not None:
        return reassessment.supplier_product_id
    if comparison is not None:
        ids = [str(value) for value in comparison.supplier_product_ids]
        candidates = list(
            db.scalars(
                select(SupplierProduct)
                .where(
                    SupplierProduct.owner_id == owner.id,
                    SupplierProduct.id.in_([uuid.UUID(v) for v in ids]),
                )
                .order_by(SupplierProduct.created_at, SupplierProduct.id)
            )
        )
        links = set(
            db.scalars(
                select(CrossMarketplaceSupplierLink.supplier_id).where(
                    CrossMarketplaceSupplierLink.owner_id == owner.id,
                    CrossMarketplaceSupplierLink.canonical_supplier_id == canonical_supplier_id,
                    CrossMarketplaceSupplierLink.match_state == "MATCH",
                )
            )
        )
        candidate = next((row for row in candidates if row.supplier_id in links), None)
        return candidate.id if candidate else None
    return None


def _latest_due(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    canonical_supplier_id: uuid.UUID,
    requested_id: uuid.UUID | None,
) -> tuple[
    SupplierDueDiligenceContext | None,
    SupplierDueDiligenceAssessment | None,
    list[SupplierEvidenceGap],
]:
    context = None
    if requested_id is not None:
        context = _owned(
            db, SupplierDueDiligenceContext, owner, requested_id, "Due-diligence context not found."
        )
    else:
        context = db.scalar(
            select(SupplierDueDiligenceContext)
            .where(
                SupplierDueDiligenceContext.owner_id == owner.id,
                SupplierDueDiligenceContext.supplier_id == canonical_supplier_id,
                SupplierDueDiligenceContext.opportunity_id == opportunity.id,
            )
            .order_by(
                SupplierDueDiligenceContext.updated_at.desc(), SupplierDueDiligenceContext.id.desc()
            )
        )
    if context is None:
        return None, None, []
    if context.opportunity_id != opportunity.id or context.supplier_id != canonical_supplier_id:
        raise HTTPException(409, "Due-diligence context is outside the requested supplier scope.")
    assessment = db.scalar(
        select(SupplierDueDiligenceAssessment).where(
            SupplierDueDiligenceAssessment.owner_id == owner.id,
            SupplierDueDiligenceAssessment.context_id == context.id,
            SupplierDueDiligenceAssessment.version == context.current_assessment_version,
        )
    )
    gaps = list(
        db.scalars(
            select(SupplierEvidenceGap)
            .where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.context_id == context.id,
                SupplierEvidenceGap.assessment_version == context.current_assessment_version,
            )
            .order_by(SupplierEvidenceGap.dimension, SupplierEvidenceGap.id)
        )
    )
    return context, assessment, gaps


def _ref_id(row: Any) -> str | None:
    return str(row.id) if row is not None else None


def _dimension_payload(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    canonical_supplier_id: uuid.UUID,
    supplier_product_id: uuid.UUID | None,
    shortlist: tuple[
        SupplierShortlistContext | None,
        SupplierShortlistVersion | None,
        SupplierShortlistDecision | None,
    ],
    due: tuple[
        SupplierDueDiligenceContext | None,
        SupplierDueDiligenceAssessment | None,
        list[SupplierEvidenceGap],
    ],
    commercial: CommercialReadinessSnapshot | None,
    reassessment: CommercialReassessment | None,
    comparison: SupplierComparisonSnapshot | None,
    supplier: Supplier | None,
    product: SupplierProduct | None,
    links: list[CrossMarketplaceSupplierLink],
) -> tuple[dict[str, dict[str, object]], list[str], list[str], list[object], dict[str, object]]:
    context, shortlist_version, decision = shortlist
    due_context, due_assessment, gaps = due
    source_evidence: list[SupplierEvidence] = []
    if supplier is not None:
        source_evidence = list(
            db.scalars(
                select(SupplierEvidence)
                .where(
                    SupplierEvidence.owner_id == owner.id,
                    SupplierEvidence.supplier_id == supplier.id,
                    SupplierEvidence.archived.is_(False),
                )
                .order_by(SupplierEvidence.observed_at, SupplierEvidence.id)
            )
        )
    evidence_ids = [str(row.id) for row in source_evidence]
    verified = (
        db.scalar(
            select(SupplierVerification)
            .where(
                SupplierVerification.owner_id == owner.id,
                SupplierVerification.supplier_id == supplier.id if supplier else text("false"),
            )
            .order_by(SupplierVerification.observed_at.desc(), SupplierVerification.id.desc())
        )
        if supplier is not None
        else None
    )
    contacts = (
        list(
            db.scalars(
                select(SupplierContact)
                .where(
                    SupplierContact.owner_id == owner.id,
                    SupplierContact.supplier_id == supplier.id if supplier else text("false"),
                    SupplierContact.archived.is_(False),
                )
                .order_by(SupplierContact.created_at, SupplierContact.id)
            )
        )
        if supplier is not None
        else []
    )
    identity_refs = [str(item.id) for item in links] + ([str(verified.id)] if verified else [])
    identity_ok = bool(
        supplier is not None
        and supplier.verification_state in {"verified", "high_confidence"}
        and verified is not None
        and verified.state in {"verified", "high_confidence"}
        and verified.evidence_ids
        and any(link.match_state == "MATCH" for link in links)
    )
    identity = _dimension(
        "READY_FOR_HUMAN_REVIEW" if identity_ok else "NEEDS_EVIDENCE",
        evidence_refs=identity_refs,
        provenance="INDEPENDENTLY_VERIFIED" if identity_ok else "UNKNOWN",
        freshness=(
            product.freshness_status
            if product is not None
            else source_evidence[-1].freshness_status if source_evidence else "UNKNOWN"
        ),
        missing=[] if identity_ok else ["independent_supplier_identity_verification"],
        blockers=[] if identity_ok else ["supplier_identity_not_independently_verified"],
        next_action=(
            "Review independent identity evidence."
            if not identity_ok
            else "Keep identity evidence under review."
        ),
        values={
            "canonical_supplier_id": str(canonical_supplier_id),
            "supplier_id": _ref_id(supplier),
        },
    )
    contact_ok = any(
        row.verification_status in {"verified", "confirmed", "independently_verified"}
        for row in contacts
    )
    contact = _dimension(
        "READY_FOR_HUMAN_REVIEW" if contact_ok else "NEEDS_EVIDENCE",
        evidence_refs=[str(row.id) for row in contacts],
        provenance="INDEPENDENTLY_VERIFIED" if contact_ok else "UNKNOWN",
        missing=[] if contact_ok else ["authorized_contact_verification"],
        blockers=[] if contact_ok else ["contact_authorization_unknown"],
        next_action="Review contact verification evidence before any outreach.",
        values={"contacts": len(contacts)},
    )
    unresolved = [gap for gap in gaps if gap.status not in {"RESOLVED", "WAIVED_BY_HUMAN"}]
    critical = [gap for gap in unresolved if gap.severity in {"CRITICAL", "HIGH"}]
    due_ready = (
        due_assessment is not None
        and str(due_assessment.readiness).upper() == "SUFFICIENT"
        and not critical
    )
    due_dimension = _dimension(
        "READY_FOR_HUMAN_REVIEW" if due_ready else "BLOCKED" if critical else "NEEDS_EVIDENCE",
        evidence_refs=[str(gap.id) for gap in gaps],
        provenance="VAYUJIT_CANONICAL_DUE_DILIGENCE" if due_assessment else "UNKNOWN",
        freshness="UNKNOWN",
        missing=[str(gap.dimension) for gap in unresolved],
        contradictions=[
            {"gap_id": str(gap.id), "dimension": gap.dimension}
            for gap in unresolved
            if gap.contradiction_state != "none"
        ],
        blockers=[str(gap.reason) for gap in critical],
        next_action="Resolve required due-diligence gaps through the existing workflow.",
        values={
            "context_id": _ref_id(due_context),
            "assessment_version": due_context.current_assessment_version if due_context else None,
        },
    )
    product_specs = (
        product.specifications if product and isinstance(product.specifications, dict) else {}
    )
    product_ok = product is not None and bool(product.title and product.category)
    product_dimension = _dimension(
        "UNDER_REVIEW" if product_ok else "NEEDS_EVIDENCE",
        evidence_refs=(list(product.evidence_ids or []) if product else []) + evidence_ids,
        provenance="SOURCE_PROVIDED_CLAIM" if product_ok else "UNKNOWN",
        freshness=product.freshness_status if product else "UNKNOWN",
        missing=[] if product_ok else ["supplier_product_identity_and_specification"],
        blockers=(
            ["supplier_product_evidence_stale"]
            if product and product.freshness_status in {"stale", "expired"}
            else []
        ),
        next_action="Review product capability and specification evidence.",
        values={
            "supplier_product_id": _ref_id(product),
            "title": product.title if product else None,
            "category": product.category if product else None,
            "specifications": product_specs,
        },
    )
    commercial_overall = (
        str((commercial.readiness or {}).get("overall", "NEEDS_INPUT")) if commercial else "UNKNOWN"
    )
    commercial_blockers = [str(item) for item in (commercial.contradictions if commercial else [])]
    commercial_lineage = commercial.lineage if commercial else {}
    candidate_lineage = (
        commercial_lineage.get("candidate") if isinstance(commercial_lineage, dict) else None
    )
    candidate_evidence_ids = (
        candidate_lineage.get("evidence_ids", []) if isinstance(candidate_lineage, dict) else []
    )
    commercial_dimension = _dimension(
        (
            "READY_FOR_HUMAN_REVIEW"
            if commercial_overall == "READY" and not commercial_blockers
            else "BLOCKED" if commercial_blockers else "NEEDS_EVIDENCE"
        ),
        evidence_refs=[str(item) for item in candidate_evidence_ids],
        provenance="VAYUJIT_CANONICAL_PR5A" if commercial else "UNKNOWN",
        freshness="UNKNOWN",
        missing=[
            str(item)
            for item in (
                commercial.missing_inputs if commercial else ["commercial_readiness_snapshot"]
            )
        ],
        contradictions=commercial.contradictions if commercial else [],
        blockers=commercial_blockers,
        next_action=(
            "Review quote basis, currency, MOQ, lead time, freight, tax, and payment terms."
        ),
        values={"overall": commercial_overall, "commercial_readiness_id": _ref_id(commercial)},
    )
    economics = cast(
        dict[str, object],
        reassessment.current if reassessment and isinstance(reassessment.current, dict) else {},
    )
    unit = cast(
        dict[str, object],
        (
            economics.get("unit_economics")
            if isinstance(economics.get("unit_economics"), dict)
            else {}
        ),
    )
    landed = cast(
        dict[str, object],
        economics.get("landed_cost") if isinstance(economics.get("landed_cost"), dict) else {},
    )
    economics_ready = bool(
        reassessment
        and reassessment.status == "READY_FOR_HUMAN_REVIEW"
        and unit.get("calculable")
        and landed.get("calculable")
    )
    econ_dimension = _dimension(
        "READY_FOR_HUMAN_REVIEW" if economics_ready else "NEEDS_EVIDENCE",
        evidence_refs=[_ref_id(reassessment)] if reassessment else [],
        provenance="VAYUJIT_CALCULATED_PR8A_PR5B_PR5C" if reassessment else "UNKNOWN",
        missing=[] if economics_ready else ["current_landed_cost_and_unit_economics"],
        blockers=[
            str(item)
            for item in (reassessment.blockers if reassessment and not economics_ready else [])
        ],
        next_action="Review the referenced landed-cost and unit-economics calculations.",
        values={
            "reassessment_id": _ref_id(reassessment),
            "landed_cost": landed,
            "unit_economics": unit,
        },
    )
    capital_shortfall = unit.get("capital_shortfall")
    capital_fit = unit.get("capital_fit_status")
    capital_blocked = (
        capital_shortfall not in (None, "0", 0, 0.0) or str(capital_fit).upper() == "SHORTFALL"
    )
    capital_dimension = _dimension(
        "BLOCKED" if capital_blocked else "READY_FOR_HUMAN_REVIEW" if unit else "NEEDS_EVIDENCE",
        evidence_refs=[_ref_id(reassessment)] if reassessment else [],
        provenance="VAYUJIT_CALCULATED_PR5C" if unit else "UNKNOWN",
        missing=[] if unit else ["capital_fit_calculation"],
        blockers=["capital_shortfall"] if capital_blocked else [],
        next_action="Review capital assumptions and any shortfall before further review.",
        values={
            "capital_fit_status": capital_fit,
            "capital_shortfall": capital_shortfall,
            "capital_headroom": unit.get("capital_headroom"),
        },
    )
    claims = (
        list(
            db.scalars(
                select(SupplierCertificationClaim)
                .where(
                    SupplierCertificationClaim.owner_id == owner.id,
                    (
                        SupplierCertificationClaim.supplier_id == supplier.id
                        if supplier
                        else text("false")
                    ),
                    SupplierCertificationClaim.is_current.is_(True),
                )
                .order_by(SupplierCertificationClaim.claim, SupplierCertificationClaim.version)
            )
        )
        if supplier is not None
        else []
    )
    compliance_verified = bool(claims) and all(
        item.verification_state in {"verified", "independently_verified"} for item in claims
    )
    compliance = _dimension(
        "READY_FOR_HUMAN_REVIEW" if compliance_verified else "NEEDS_EVIDENCE",
        evidence_refs=[str(item.id) for item in claims for _ in [0]],
        provenance=(
            "INDEPENDENTLY_VERIFIED"
            if compliance_verified
            else "SOURCE_PROVIDED_CLAIM" if claims else "UNKNOWN"
        ),
        missing=[] if compliance_verified else ["independent_compliance_verification"],
        blockers=[] if compliance_verified else ["compliance_verification_unknown"],
        next_action=(
            "Obtain specialist verification where legal requirements are not represented "
            "by a trusted policy source."
        ),
        values={
            "claims": [
                {"claim": item.claim, "verification_state": item.verification_state}
                for item in claims
            ]
        },
    )
    shortlist_status = "NEEDS_EVIDENCE"
    shortlist_blockers: list[str] = []
    if decision is None:
        shortlist_status = "BLOCKED"
        shortlist_blockers = ["human_shortlist_decision_missing"]
    elif decision.decision == "REJECT":
        shortlist_status = "BLOCKED"
        shortlist_blockers = ["supplier_withdrawn_by_human"]
    elif decision.decision == "REQUEST_MORE_RESEARCH":
        shortlist_status = "UNDER_REVIEW"
    else:
        shortlist_status = "READY_FOR_HUMAN_REVIEW"
    shortlist_dimension = _dimension(
        shortlist_status,
        evidence_refs=[_ref_id(context), _ref_id(shortlist_version), _ref_id(decision)],
        provenance="HUMAN" if decision else "UNKNOWN",
        missing=[] if decision else ["human_shortlist_decision"],
        blockers=shortlist_blockers,
        next_action="Review the current HUMAN shortlist decision and context.",
        values={
            "decision": decision.decision if decision else None,
            "decision_id": _ref_id(decision),
        },
    )
    dimensions = {
        "identity": identity,
        "contact": contact,
        "due_diligence": due_dimension,
        "product_capability": product_dimension,
        "quote_commercial": commercial_dimension,
        "economics": econ_dimension,
        "capital_fit": capital_dimension,
        "compliance": compliance,
        "human_shortlist": shortlist_dimension,
    }
    blockers = sorted(
        {
            item
            for value in dimensions.values()
            for item in cast(list[str], value["blockers"])
            if item
        }
    )
    unknowns = sorted(
        {
            item
            for value in dimensions.values()
            for item in cast(list[str], value["missing_information"])
            if item
        }
    )
    contradictions = sorted(
        [
            item
            for value in dimensions.values()
            for item in cast(list[object], value["contradictions"])
        ],
        key=lambda item: json.dumps(_json(item), sort_keys=True),
    )
    lineage = {
        "opportunity_id": str(opportunity_id),
        "assessment_id": str(assessment_id),
        "canonical_supplier_id": str(canonical_supplier_id),
        "supplier_id": _ref_id(supplier),
        "supplier_product_id": _ref_id(product),
        "shortlist_context_id": _ref_id(context),
        "shortlist_version_id": _ref_id(shortlist_version),
        "shortlist_decision_id": _ref_id(decision),
        "due_diligence_context_id": _ref_id(due_context),
        "due_diligence_assessment_version": (
            due_context.current_assessment_version if due_context else None
        ),
        "due_diligence_gap_ids": [str(item.id) for item in gaps],
        "commercial_readiness_id": _ref_id(commercial),
        "reassessment_id": _ref_id(reassessment),
        "comparison_id": _ref_id(comparison),
        "source_evidence_ids": sorted(evidence_ids),
        "supplier_link_ids": sorted(str(item.id) for item in links),
    }
    provenance = {
        "authority": "PR-8C_PROJECTION",
        "identity": "canonical supplier and verification authorities",
        "contact": "canonical supplier contact authority",
        "due_diligence": "PR-4.2 due diligence ledger",
        "commercial": "PR-5A",
        "economics": "PR-8A/PR-5B/PR-5C",
        "comparison": "PR-8B" if comparison else "NOT_REFERENCED",
        "supplier_claims_are_not_verification": True,
        "external_writes": False,
    }
    return (
        dimensions,
        blockers,
        unknowns,
        contradictions,
        {"lineage": lineage, "provenance": provenance},
    )


def _references(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: ProcurementReadinessCreate,
) -> tuple[
    ProductOpportunity,
    ProductOpportunityAssessment,
    CrossMarketplaceSupplier,
    Supplier | None,
    SupplierProduct | None,
    tuple[
        SupplierShortlistContext | None,
        SupplierShortlistVersion | None,
        SupplierShortlistDecision | None,
    ],
    tuple[
        SupplierDueDiligenceContext | None,
        SupplierDueDiligenceAssessment | None,
        list[SupplierEvidenceGap],
    ],
    CommercialReadinessSnapshot | None,
    CommercialReassessment | None,
    SupplierComparisonSnapshot | None,
    list[CrossMarketplaceSupplierLink],
]:
    opportunity = _owned(
        db, ProductOpportunity, owner, opportunity_id, "Product opportunity not found."
    )
    assessment = _owned(
        db,
        ProductOpportunityAssessment,
        owner,
        assessment_id,
        "Product opportunity assessment not found.",
    )
    if assessment.opportunity_id != opportunity.id:
        raise HTTPException(404, "Product opportunity assessment not found.")
    canonical = _owned(
        db,
        CrossMarketplaceSupplier,
        owner,
        data.canonical_supplier_id,
        "Canonical supplier not found.",
    )
    if data.goal_id is not None:
        goal = _owned(db, BusinessAgentGoal, owner, data.goal_id, "Business goal not found.")
        structured_goal = goal.structured_goal if isinstance(goal.structured_goal, dict) else {}
        linked_opportunity = structured_goal.get("product_opportunity_id") or structured_goal.get(
            "selected_product_opportunity_id"
        )
        if linked_opportunity is not None and str(linked_opportunity) != str(opportunity.id):
            raise HTTPException(409, "Business goal is outside the requested product context.")
        goal_opportunities: set[uuid.UUID] = set()
        for run in db.scalars(
            select(BusinessAgentRun).where(
                BusinessAgentRun.owner_id == owner.id,
                BusinessAgentRun.goal_id == goal.id,
            )
        ):
            result = run.result if isinstance(run.result, dict) else {}
            candidates = result.get("candidates")
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                try:
                    goal_opportunities.add(uuid.UUID(str(candidate.get("id"))))
                except (TypeError, ValueError):
                    continue
        if goal_opportunities and opportunity.id not in goal_opportunities:
            raise HTTPException(409, "Business goal is outside the requested product context.")
    comparison = None
    if data.comparison_id is not None:
        comparison = _owned(
            db,
            SupplierComparisonSnapshot,
            owner,
            data.comparison_id,
            "Supplier comparison not found.",
        )
        if comparison.opportunity_id != opportunity.id or comparison.assessment_id != assessment.id:
            raise HTTPException(
                409, "Supplier comparison is outside the requested product context."
            )
        if str(canonical.id) not in {str(item) for item in comparison.canonical_supplier_ids}:
            raise HTTPException(409, "Supplier is not part of the selected comparison.")
    reassessment = None
    if data.reassessment_id is not None:
        reassessment = _owned(
            db,
            CommercialReassessment,
            owner,
            data.reassessment_id,
            "Commercial reassessment not found.",
        )
        if (
            reassessment.opportunity_id != opportunity.id
            or reassessment.assessment_id != assessment.id
        ):
            raise HTTPException(
                409, "Commercial reassessment is outside the requested product context."
            )
    resolved_product_id = _resolve_product_id(
        db, owner, data.supplier_product_id, reassessment, comparison, canonical.id
    )
    supplier, product, links = _source_supplier(db, owner, canonical, resolved_product_id)
    if product is not None:
        product._pr8c_terms = list(  # type: ignore[attr-defined]
            db.scalars(
                select(SupplierCommercialTerm)
                .where(
                    SupplierCommercialTerm.owner_id == owner.id,
                    SupplierCommercialTerm.supplier_product_id == product.id,
                    SupplierCommercialTerm.supplier_id == product.supplier_id,
                )
                .order_by(SupplierCommercialTerm.version, SupplierCommercialTerm.id)
            )
        )
    if reassessment is not None:
        if supplier is None or reassessment.supplier_id != supplier.id:
            raise HTTPException(409, "Reassessment supplier does not match canonical supplier.")
        if product is None or reassessment.supplier_product_id != product.id:
            raise HTTPException(409, "Reassessment product does not match supplier product.")
        if comparison is not None and str(reassessment.id) not in {
            str(value) for value in comparison.reassessment_ids
        }:
            raise HTTPException(409, "Reassessment is not part of the selected comparison.")
    shortlist = _latest_shortlist(
        db, owner, opportunity, canonical.id, data.shortlist_context_id, data.shortlist_decision_id
    )
    if shortlist[2] is not None and shortlist[2].decision not in ALLOWED_SHORTLIST_DECISIONS | {
        "REJECT"
    }:
        raise HTTPException(409, "Unsupported HUMAN shortlist state.")
    due = _latest_due(db, owner, opportunity, canonical.id, data.due_diligence_context_id)
    if (
        due[0] is not None
        and opportunity.product_id is not None
        and due[0].product_id not in {None, opportunity.product_id}
    ):
        raise HTTPException(409, "Due-diligence product context does not match the opportunity.")
    commercial = None
    if data.commercial_readiness_id is not None:
        commercial = _owned(
            db,
            CommercialReadinessSnapshot,
            owner,
            data.commercial_readiness_id,
            "Commercial readiness snapshot not found.",
        )
        if commercial.opportunity_id != opportunity.id or commercial.assessment_id != assessment.id:
            raise HTTPException(
                409, "Commercial readiness is outside the requested product context."
            )
        if supplier is not None and commercial.supplier_id not in {None, supplier.id}:
            raise HTTPException(
                409, "Commercial readiness supplier does not match canonical supplier."
            )
    elif reassessment is not None and reassessment.current_readiness_id:
        commercial = _owned(
            db,
            CommercialReadinessSnapshot,
            owner,
            reassessment.current_readiness_id,
            "Commercial readiness snapshot not found.",
        )
        if commercial.opportunity_id != opportunity.id or commercial.assessment_id != assessment.id:
            raise HTTPException(
                409, "Commercial readiness is outside the requested product context."
            )
        if supplier is None or commercial.supplier_id not in {None, supplier.id}:
            raise HTTPException(
                409, "Commercial readiness supplier does not match canonical supplier."
            )
    return (
        opportunity,
        assessment,
        canonical,
        supplier,
        product,
        shortlist,
        due,
        commercial,
        reassessment,
        comparison,
        links,
    )


def _scope_fingerprint(
    opportunity: ProductOpportunity,
    assessment: ProductOpportunityAssessment,
    canonical: CrossMarketplaceSupplier,
    supplier: Supplier | None,
    product: SupplierProduct | None,
    shortlist: tuple[
        SupplierShortlistContext | None,
        SupplierShortlistVersion | None,
        SupplierShortlistDecision | None,
    ],
    due: tuple[
        SupplierDueDiligenceContext | None,
        SupplierDueDiligenceAssessment | None,
        list[SupplierEvidenceGap],
    ],
    commercial: CommercialReadinessSnapshot | None,
    reassessment: CommercialReassessment | None,
    comparison: SupplierComparisonSnapshot | None,
    owner_id: uuid.UUID,
    goal_id: uuid.UUID | None,
    source_revision: object | None = None,
) -> str:
    context, version, decision = shortlist
    due_context, due_assessment, gaps = due
    return _fingerprint(
        {
            "owner_id": str(owner_id),
            "goal_id": str(goal_id) if goal_id else None,
            "opportunity_id": str(opportunity.id),
            "opportunity_updated_at": opportunity.updated_at,
            "assessment_id": str(assessment.id),
            "assessment_created_at": assessment.created_at,
            "canonical_supplier_id": str(canonical.id),
            "canonical_updated_at": canonical.updated_at,
            "supplier_id": _ref_id(supplier),
            "supplier_updated_at": supplier.updated_at if supplier else None,
            "supplier_product_id": _ref_id(product),
            "product_observed_at": product.observed_at if product else None,
            "product_freshness": product.freshness_status if product else None,
            "commercial_terms": (
                [
                    {
                        "id": str(term.id),
                        "version": term.version,
                        "unit_price": term.unit_price,
                        "currency": term.currency,
                        "moq": term.moq,
                        "lead_time_days": term.lead_time_days,
                        "is_current": term.is_current,
                    }
                    for term in sorted(
                        getattr(product, "_pr8c_terms", []),
                        key=lambda item: (item.version, str(item.id)),
                    )
                ]
                if product
                else []
            ),
            "shortlist_context_id": _ref_id(context),
            "shortlist_version_id": _ref_id(version),
            "shortlist_decision_id": _ref_id(decision),
            "shortlist_decision": decision.decision if decision else None,
            "shortlist_decision_at": decision.created_at if decision else None,
            "due_context_id": _ref_id(due_context),
            "due_version": due_context.current_assessment_version if due_context else None,
            "due_assessment_id": _ref_id(due_assessment),
            "gap_states": [(str(g.id), g.status, g.updated_at) for g in gaps],
            "commercial_id": _ref_id(commercial),
            "commercial_created_at": commercial.created_at if commercial else None,
            "reassessment_id": _ref_id(reassessment),
            "reassessment_fingerprint": reassessment.input_fingerprint if reassessment else None,
            "reassessment_quote_version": reassessment.quote_version if reassessment else None,
            "comparison_id": _ref_id(comparison),
            "comparison_fingerprint": comparison.input_fingerprint if comparison else None,
            "source_revision": source_revision,
            "policy_version": POLICY_VERSION,
        }
    )


def _source_revision(
    db: Session,
    owner: User,
    supplier: Supplier | None,
    product: SupplierProduct | None,
) -> dict[str, object]:
    """Return deterministic revisions for mutable canonical source evidence."""

    if supplier is None:
        return {"supplier": None, "product": str(product.id) if product else None}
    evidence = list(
        db.execute(
            select(
                SupplierEvidence.id,
                SupplierEvidence.updated_at,
                SupplierEvidence.observed_at,
                SupplierEvidence.freshness_status,
                SupplierEvidence.verification_status,
                SupplierEvidence.content_hash,
            ).where(
                SupplierEvidence.owner_id == owner.id,
                SupplierEvidence.supplier_id == supplier.id,
                SupplierEvidence.archived.is_(False),
            )
        )
    )
    verifications = list(
        db.execute(
            select(
                SupplierVerification.id,
                SupplierVerification.observed_at,
                SupplierVerification.state,
                SupplierVerification.evidence_ids,
            ).where(
                SupplierVerification.owner_id == owner.id,
                SupplierVerification.supplier_id == supplier.id,
            )
        )
    )
    contacts = list(
        db.execute(
            select(
                SupplierContact.id,
                SupplierContact.updated_at,
                SupplierContact.verification_status,
                SupplierContact.archived,
            ).where(
                SupplierContact.owner_id == owner.id,
                SupplierContact.supplier_id == supplier.id,
            )
        )
    )
    claims = list(
        db.execute(
            select(
                SupplierCertificationClaim.id,
                SupplierCertificationClaim.observed_at,
                SupplierCertificationClaim.verification_state,
                SupplierCertificationClaim.version,
                SupplierCertificationClaim.is_current,
            ).where(
                SupplierCertificationClaim.owner_id == owner.id,
                SupplierCertificationClaim.supplier_id == supplier.id,
            )
        )
    )
    return {
        "supplier": {
            "id": str(supplier.id),
            "updated_at": supplier.updated_at,
            "verification_state": supplier.verification_state,
        },
        "product": (
            {
                "id": str(product.id),
                "observed_at": product.observed_at,
                "freshness_status": product.freshness_status,
                "title": product.title,
                "category": product.category,
                "specifications": product.specifications,
            }
            if product
            else None
        ),
        "evidence": [tuple(row) for row in evidence],
        "verifications": [tuple(row) for row in verifications],
        "contacts": [tuple(row) for row in contacts],
        "claims": [tuple(row) for row in claims],
    }


def _assert_current_context(
    db: Session,
    owner: User,
    row: SupplierProcurementReadinessAssessment,
    values: tuple[object, ...],
) -> None:
    """Reject acknowledgement when a newer canonical context supersedes a snapshot."""

    canonical = cast(CrossMarketplaceSupplier, values[2])
    shortlist_context, _, shortlist_decision = cast(
        tuple[
            SupplierShortlistContext | None,
            SupplierShortlistVersion | None,
            SupplierShortlistDecision | None,
        ],
        values[5],
    )
    if row.shortlist_context_id is not None:
        current_decision = db.scalar(
            select(SupplierShortlistDecision)
            .where(
                SupplierShortlistDecision.owner_id == owner.id,
                SupplierShortlistDecision.context_id == row.shortlist_context_id,
                SupplierShortlistDecision.supplier_id == canonical.id,
            )
            .order_by(
                SupplierShortlistDecision.created_at.desc(),
                SupplierShortlistDecision.id.desc(),
            )
        )
        if current_decision is None or current_decision.id != row.shortlist_decision_id:
            raise HTTPException(
                409,
                "Assessment context is stale; the HUMAN shortlist decision changed.",
            )
        if shortlist_context is not None and row.shortlist_context_id != shortlist_context.id:
            raise HTTPException(409, "Assessment context is stale; shortlist context changed.")
    elif shortlist_decision is not None:
        raise HTTPException(409, "Assessment context is stale; a shortlist decision now exists.")

    due_context, _, _ = cast(
        tuple[
            SupplierDueDiligenceContext | None,
            SupplierDueDiligenceAssessment | None,
            list[SupplierEvidenceGap],
        ],
        values[6],
    )
    latest_due = db.scalar(
        select(SupplierDueDiligenceContext)
        .where(
            SupplierDueDiligenceContext.owner_id == owner.id,
            SupplierDueDiligenceContext.supplier_id == canonical.id,
            SupplierDueDiligenceContext.opportunity_id == row.opportunity_id,
        )
        .order_by(
            SupplierDueDiligenceContext.updated_at.desc(), SupplierDueDiligenceContext.id.desc()
        )
    )
    if (latest_due is None) != (row.due_diligence_context_id is None) or (
        latest_due is not None and latest_due.id != row.due_diligence_context_id
    ):
        raise HTTPException(
            409,
            "Assessment context is stale; the due-diligence context changed.",
        )
    if due_context is not None and latest_due is not None and due_context.id != latest_due.id:
        raise HTTPException(409, "Assessment context is stale; due-diligence context changed.")


def _view(
    db: Session, owner: User, row: SupplierProcurementReadinessAssessment, *, reuse: bool = False
) -> dict[str, object]:
    acks = [
        {
            "id": str(item.id),
            "decision": item.decision,
            "provenance": item.provenance,
            "actor_id": str(item.actor_id),
            "reason": item.reason,
            "assessment_fingerprint": item.assessment_fingerprint,
            "created_at": item.created_at.isoformat(),
        }
        for item in db.scalars(
            select(SupplierProcurementReadinessAcknowledgement)
            .where(
                SupplierProcurementReadinessAcknowledgement.owner_id == owner.id,
                SupplierProcurementReadinessAcknowledgement.assessment_id == row.id,
            )
            .order_by(
                SupplierProcurementReadinessAcknowledgement.created_at,
                SupplierProcurementReadinessAcknowledgement.id,
            )
        )
    ]
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id),
        "assessment_id": str(row.assessment_id),
        "canonical_supplier_id": str(row.canonical_supplier_id),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "supplier_product_id": str(row.supplier_product_id) if row.supplier_product_id else None,
        "shortlist_context_id": str(row.shortlist_context_id) if row.shortlist_context_id else None,
        "shortlist_version_id": str(row.shortlist_version_id) if row.shortlist_version_id else None,
        "shortlist_decision_id": (
            str(row.shortlist_decision_id) if row.shortlist_decision_id else None
        ),
        "due_diligence_context_id": (
            str(row.due_diligence_context_id) if row.due_diligence_context_id else None
        ),
        "commercial_readiness_id": (
            str(row.commercial_readiness_id) if row.commercial_readiness_id else None
        ),
        "reassessment_id": str(row.reassessment_id) if row.reassessment_id else None,
        "comparison_id": str(row.comparison_id) if row.comparison_id else None,
        "snapshot_version": row.snapshot_version,
        "status": row.status,
        "policy_version": row.policy_version,
        "calculation_versions": row.calculation_versions,
        "dimensions": row.dimensions,
        "blockers": row.blockers,
        "unknowns": row.unknowns,
        "contradictions": row.contradictions,
        "evidence_lineage": row.evidence_lineage,
        "provenance": row.provenance,
        "input_fingerprint": row.input_fingerprint,
        "idempotency_key": row.idempotency_key,
        "actor_id": str(row.actor_id),
        "actor_provenance": row.actor_provenance,
        "created_at": row.created_at.isoformat(),
        "notes": row.notes,
        "acknowledgements": acks,
        "idempotent_reuse": reuse,
    }


def create_assessment(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: ProcurementReadinessCreate,
) -> dict[str, object]:
    values = _references(db, owner, opportunity_id, assessment_id, data)
    (
        opportunity,
        assessment,
        canonical,
        supplier,
        product,
        shortlist,
        due,
        commercial,
        reassessment,
        comparison,
        links,
    ) = values
    fingerprint = _scope_fingerprint(
        opportunity,
        assessment,
        canonical,
        supplier,
        product,
        shortlist,
        due,
        commercial,
        reassessment,
        comparison,
        owner.id,
        data.goal_id,
        _source_revision(db, owner, supplier, product),
    )
    by_key = db.scalar(
        select(SupplierProcurementReadinessAssessment).where(
            SupplierProcurementReadinessAssessment.owner_id == owner.id,
            SupplierProcurementReadinessAssessment.idempotency_key == data.idempotency_key,
        )
    )
    if by_key is not None:
        if by_key.input_fingerprint != fingerprint:
            raise HTTPException(
                409, "Procurement-readiness idempotency key was used for different inputs."
            )
        return _view(db, owner, by_key, reuse=True)
    existing = db.scalar(
        select(SupplierProcurementReadinessAssessment).where(
            SupplierProcurementReadinessAssessment.owner_id == owner.id,
            SupplierProcurementReadinessAssessment.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return _view(db, owner, existing, reuse=True)
    dimensions, blockers, unknowns, contradictions, references = _dimension_payload(
        db,
        owner,
        opportunity.id,
        assessment.id,
        canonical.id,
        product.id if product else None,
        shortlist,
        due,
        commercial,
        reassessment,
        comparison,
        supplier,
        product,
        links,
    )
    status = "BLOCKED" if blockers else "READY_FOR_HUMAN_REVIEW"
    latest_version = (
        db.scalar(
            select(func.max(SupplierProcurementReadinessAssessment.snapshot_version)).where(
                SupplierProcurementReadinessAssessment.owner_id == owner.id,
                SupplierProcurementReadinessAssessment.opportunity_id == opportunity.id,
                SupplierProcurementReadinessAssessment.assessment_id == assessment.id,
                SupplierProcurementReadinessAssessment.canonical_supplier_id == canonical.id,
            )
        )
        or 0
    )
    context, shortlist_version, decision = shortlist
    row = SupplierProcurementReadinessAssessment(
        owner_id=owner.id,
        goal_id=data.goal_id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        canonical_supplier_id=canonical.id,
        supplier_id=supplier.id if supplier else None,
        supplier_product_id=product.id if product else None,
        shortlist_context_id=context.id if context else None,
        shortlist_version_id=shortlist_version.id if shortlist_version else None,
        shortlist_decision_id=decision.id if decision else None,
        due_diligence_context_id=due[0].id if due[0] else None,
        commercial_readiness_id=commercial.id if commercial else None,
        reassessment_id=reassessment.id if reassessment else None,
        comparison_id=comparison.id if comparison else None,
        snapshot_version=int(latest_version) + 1,
        status=status,
        policy_version=POLICY_VERSION,
        calculation_versions=sorted(
            {
                "pr8a": "commercial-reassessment-v1",
                "pr5b": "landed-cost-v1",
                "pr5c": "unit-economics-capital-fit-v1",
            }.values()
            if reassessment
            else set()
        ),
        dimensions=dimensions,
        blockers=blockers,
        unknowns=unknowns,
        contradictions=contradictions,
        evidence_lineage=references["lineage"],
        provenance={
            **cast(dict[str, object], references["provenance"]),
            "trust_environment": (
                (commercial.lineage or {}).get("mode") if commercial else "UNKNOWN"
            ),
        },
        input_fingerprint=fingerprint,
        idempotency_key=data.idempotency_key,
        actor_id=owner.id,
        actor_provenance="HUMAN",
        created_at=_now(),
        notes=(
            "Readiness assessment only. It is not supplier approval, quote acceptance, "
            "purchase authorization, or payment authorization."
        ),
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.procurement_readiness_assessed",
        entity_type="procurement_readiness_assessment",
        entity_id=row.id,
        metadata={"status": status, "policy_version": POLICY_VERSION, "external_writes": False},
        idempotency_key=f"pr8c:assessment:{row.id}",
    )
    db.commit()
    db.refresh(row)
    return _view(db, owner, row)


def list_assessments(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> list[dict[str, object]]:
    _owned(db, ProductOpportunity, owner, opportunity_id, "Product opportunity not found.")
    _owned(
        db,
        ProductOpportunityAssessment,
        owner,
        assessment_id,
        "Product opportunity assessment not found.",
    )
    rows = list(
        db.scalars(
            select(SupplierProcurementReadinessAssessment)
            .where(
                SupplierProcurementReadinessAssessment.owner_id == owner.id,
                SupplierProcurementReadinessAssessment.opportunity_id == opportunity_id,
                SupplierProcurementReadinessAssessment.assessment_id == assessment_id,
            )
            .order_by(
                SupplierProcurementReadinessAssessment.created_at,
                SupplierProcurementReadinessAssessment.id,
            )
        )
    )
    return [_view(db, owner, row) for row in rows]


def get_assessment(db: Session, owner: User, assessment_id: uuid.UUID) -> dict[str, object]:
    row = _owned(
        db,
        SupplierProcurementReadinessAssessment,
        owner,
        assessment_id,
        "Procurement-readiness assessment not found.",
    )
    return _view(db, owner, row)


def acknowledge_assessment(
    db: Session, owner: User, assessment_id: uuid.UUID, data: ProcurementReadinessAcknowledgement
) -> dict[str, object]:
    row = _owned(
        db,
        SupplierProcurementReadinessAssessment,
        owner,
        assessment_id,
        "Procurement-readiness assessment not found.",
    )
    if data.provenance != "HUMAN" or data.decision not in ACK_DECISIONS:
        raise HTTPException(403, "Only an authenticated HUMAN may acknowledge this assessment.")
    existing = db.scalar(
        select(SupplierProcurementReadinessAcknowledgement).where(
            SupplierProcurementReadinessAcknowledgement.owner_id == owner.id,
            SupplierProcurementReadinessAcknowledgement.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        if existing.assessment_id != row.id:
            raise HTTPException(
                409, "Acknowledgement idempotency key was used for another assessment."
            )
        return {
            "assessment": _view(db, owner, row, reuse=True),
            "acknowledgement_id": str(existing.id),
            "idempotent_reuse": True,
        }
    payload = ProcurementReadinessCreate(
        idempotency_key=f"reconstruct:{row.input_fingerprint}",
        canonical_supplier_id=row.canonical_supplier_id,
        supplier_product_id=row.supplier_product_id,
        goal_id=row.goal_id,
        shortlist_context_id=row.shortlist_context_id,
        shortlist_decision_id=row.shortlist_decision_id,
        due_diligence_context_id=row.due_diligence_context_id,
        commercial_readiness_id=row.commercial_readiness_id,
        reassessment_id=row.reassessment_id,
        comparison_id=row.comparison_id,
    )
    values = _references(db, owner, row.opportunity_id, row.assessment_id, payload)
    _assert_current_context(db, owner, row, values)
    current_fingerprint = _scope_fingerprint(
        values[0],
        values[1],
        values[2],
        values[3],
        values[4],
        values[5],
        values[6],
        values[7],
        values[8],
        values[9],
        owner.id,
        row.goal_id,
        _source_revision(
            db,
            owner,
            values[3],
            values[4],
        ),
    )
    if current_fingerprint != row.input_fingerprint:
        raise HTTPException(
            409,
            "Assessment context is stale; create a new readiness assessment before "
            "acknowledgement.",
        )
    ack = SupplierProcurementReadinessAcknowledgement(
        owner_id=owner.id,
        assessment_id=row.id,
        actor_id=owner.id,
        decision=data.decision,
        provenance="HUMAN",
        reason=data.reason,
        assessment_fingerprint=row.input_fingerprint,
        created_at=_now(),
        idempotency_key=data.idempotency_key,
    )
    db.add(ack)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.procurement_readiness_acknowledged",
        entity_type="procurement_readiness_acknowledgement",
        entity_id=ack.id,
        metadata={
            "assessment_id": str(row.id),
            "decision": data.decision,
            "provenance": "HUMAN",
            "purchase_authorized": False,
        },
        idempotency_key=f"pr8c:ack:{ack.id}",
    )
    db.commit()
    return {
        "assessment": _view(db, owner, row),
        "acknowledgement_id": str(ack.id),
        "idempotent_reuse": False,
        "purchase_authorized": False,
    }
