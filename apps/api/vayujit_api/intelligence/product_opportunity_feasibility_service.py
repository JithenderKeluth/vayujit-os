"""Deterministic supplier/sourcing feasibility projection over 8A�8E systems."""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import false, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import (
    CrossMarketplaceSupplier,
    CrossMarketplaceSupplierLink,
)
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceAssessment,
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
)
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAlternateReadiness,
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioConcentrationMetric,
    SupplierPortfolioContext,
    SupplierPortfolioDependencyFinding,
    SupplierPortfolioMembership,
)
from vayujit_api.intelligence.product_opportunity_commercial_models import (
    ProductOpportunityCommercialOutput,
)
from vayujit_api.intelligence.product_opportunity_feasibility_models import (
    CALCULATION_VERSION,
    ProductOpportunitySourcingFeasibilityOutput,
    feasibility_now,
)
from vayujit_api.intelligence.product_opportunity_feasibility_schemas import (
    FeasibilityCalculateRequest,
)
from vayujit_api.intelligence.product_opportunity_intelligence_service import _freshness
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
)
from vayujit_api.intelligence.resilience_models import (
    SupplierPortfolioResilienceScore,
)
from vayujit_api.intelligence.scenario_models import (
    ScenarioSupplierAllocation,
    SourcingScenario,
    SourcingScenarioContext,
    SourcingScenarioVersion,
)
from vayujit_api.intelligence.shortlisting_models import (
    SupplierShortlistContext,
    SupplierShortlistDecision,
    SupplierShortlistScoreVersion,
    SupplierShortlistVersion,
)
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCommercialTerm,
    SupplierEvidence,
    SupplierHistoryEvent,
    SupplierOpportunityMatch,
    SupplierProduct,
    SupplierRiskAssessment,
    SupplierSearch,
    SupplierSource,
    SupplierVerification,
)


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _owner_assessment(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[ProductOpportunity, ProductOpportunityAssessment, ProductOpportunityConstraintVersion]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    assessment = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if opportunity is None or assessment is None:
        raise LookupError("Product opportunity assessment not found.")
    constraint = db.scalar(
        select(ProductOpportunityConstraintVersion).where(
            ProductOpportunityConstraintVersion.id == assessment.constraint_version_id,
            ProductOpportunityConstraintVersion.opportunity_id == opportunity_id,
            ProductOpportunityConstraintVersion.owner_id == owner.id,
        )
    )
    if constraint is None:
        raise LookupError("Product opportunity constraint version not found.")
    return opportunity, assessment, constraint


def _latest(rows: list[Any], key: str = "version") -> dict[uuid.UUID, Any]:
    result: dict[uuid.UUID, Any] = {}
    for row in rows:
        ident = getattr(row, "supplier_id", None)
        if ident is None:
            continue
        previous = result.get(ident)
        if previous is None or getattr(row, key, 0) >= getattr(previous, key, 0):
            result[ident] = row
    return result


def _constraint_snapshot(constraint: ProductOpportunityConstraintVersion) -> dict[str, Any]:
    return {
        field: _json(getattr(constraint, field))
        for field in (
            "id",
            "version",
            "currency",
            "available_capital",
            "maximum_landed_cost",
            "maximum_moq",
            "maximum_lead_time_days",
            "country_region",
            "supplier_geography_preferences",
            "minimum_evidence_confidence",
        )
    }


def _number(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _fit(value: Decimal | None, limit: Decimal | None) -> str:
    if (
        value is None
        or limit is None
        or not value.is_finite()
        or not limit.is_finite()
        or value < 0
        or limit < 0
    ):
        return "UNKNOWN"
    return "MEETS" if value <= limit else "DOES_NOT_MEET"


def _dimension(
    name: str,
    value: Any,
    classification: str,
    explanation: str,
    evidence: list[Any],
    missing: list[str],
) -> dict[str, Any]:
    return {
        "dimension": name,
        "value": _json(value),
        "classification": classification,
        "evidence_state": "available" if evidence else "unknown",
        "explanation": explanation,
        "supporting_evidence": _json(evidence),
        "missing_evidence": missing,
        "calculation_version": CALCULATION_VERSION,
    }


def _portfolio_rows(
    db: Session, owner: User, opportunity: ProductOpportunity
) -> tuple[list[dict[str, Any]], list[Any], list[Any], list[Any], list[Any]]:
    portfolios = list(
        db.scalars(
            select(SupplierPortfolioContext).where(SupplierPortfolioContext.owner_id == owner.id)
        )
    )
    if not portfolios:
        return [], [], [], [], []
    portfolio_ids = [row.id for row in portfolios]
    memberships = list(
        db.scalars(
            select(SupplierPortfolioMembership).where(
                SupplierPortfolioMembership.owner_id == owner.id,
                SupplierPortfolioMembership.portfolio_id.in_(portfolio_ids),
            )
        )
    )
    membership_map: dict[tuple[uuid.UUID, uuid.UUID], Any] = {}
    for membership in memberships:
        identity = (membership.portfolio_id, membership.supplier_id)
        previous_membership = membership_map.get(identity)
        if previous_membership is None or membership.version > previous_membership.version:
            membership_map[identity] = membership
    memberships = list(membership_map.values())
    relevant = [
        row
        for row in memberships
        if str(opportunity.id) in {str(value) for value in row.associated_opportunities}
        or (
            opportunity.product_id is not None
            and str(opportunity.product_id) in {str(value) for value in row.associated_products}
        )
    ]
    relevant_ids = [row.portfolio_id for row in relevant]
    assessments = (
        list(
            db.scalars(
                select(SupplierPortfolioAssessmentVersion).where(
                    SupplierPortfolioAssessmentVersion.owner_id == owner.id,
                    SupplierPortfolioAssessmentVersion.portfolio_id.in_(relevant_ids),
                    SupplierPortfolioAssessmentVersion.id.in_(
                        [
                            row.current_assessment_version_id
                            for row in portfolios
                            if row.current_assessment_version_id
                        ]
                    ),
                )
            )
        )
        if relevant_ids
        else []
    )
    assessment_ids = [row.id for row in assessments]
    concentrations = (
        list(
            db.scalars(
                select(SupplierPortfolioConcentrationMetric).where(
                    SupplierPortfolioConcentrationMetric.owner_id == owner.id,
                    SupplierPortfolioConcentrationMetric.assessment_version_id.in_(assessment_ids),
                )
            )
        )
        if assessment_ids
        else []
    )
    resilience = (
        list(
            db.scalars(
                select(SupplierPortfolioResilienceScore).where(
                    SupplierPortfolioResilienceScore.owner_id == owner.id,
                    SupplierPortfolioResilienceScore.assessment_version_id.in_(assessment_ids),
                )
            )
        )
        if assessment_ids
        else []
    )
    alternates = (
        list(
            db.scalars(
                select(SupplierPortfolioAlternateReadiness).where(
                    SupplierPortfolioAlternateReadiness.owner_id == owner.id,
                    SupplierPortfolioAlternateReadiness.assessment_version_id.in_(assessment_ids),
                )
            )
        )
        if assessment_ids
        else []
    )
    dependencies = (
        list(
            db.scalars(
                select(SupplierPortfolioDependencyFinding).where(
                    SupplierPortfolioDependencyFinding.owner_id == owner.id,
                    SupplierPortfolioDependencyFinding.assessment_version_id.in_(assessment_ids),
                )
            )
        )
        if assessment_ids
        else []
    )
    return (
        [
            {
                "id": str(row.id),
                "assessment_ids": [
                    str(value.id) for value in assessments if value.portfolio_id == row.portfolio_id
                ],
                "portfolio_id": str(row.portfolio_id),
                "supplier_id": str(row.supplier_id),
                "allocation_percent": _json(row.allocation_percent),
                "country_region": row.country_region,
                "alternate_source_status": row.alternate_source_status,
                "risk": row.risk,
                "confidence": _json(row.confidence),
                "evidence_freshness": row.evidence_freshness,
            }
            for row in relevant
        ],
        concentrations,
        resilience,
        alternates,
        dependencies,
    )


def calculate_feasibility(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: FeasibilityCalculateRequest,
) -> ProductOpportunitySourcingFeasibilityOutput:
    opportunity, assessment, constraint = _owner_assessment(
        db, owner, opportunity_id, assessment_id
    )
    now = feasibility_now()
    existing = db.scalar(
        select(ProductOpportunitySourcingFeasibilityOutput).where(
            ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id,
            ProductOpportunitySourcingFeasibilityOutput.assessment_id == assessment.id,
        )
    )
    if existing is not None:
        return existing
    search_ids = (
        list(
            db.scalars(
                select(SupplierSearch.id).where(
                    SupplierSearch.owner_id == owner.id,
                    SupplierSearch.product_id == opportunity.product_id,
                )
            )
        )
        if opportunity.product_id is not None
        else []
    )
    relevant_product_ids = select(SupplierOpportunityMatch.supplier_product_id).where(
        SupplierOpportunityMatch.owner_id == owner.id,
        SupplierOpportunityMatch.search_id.in_(search_ids),
    )
    query = select(SupplierProduct).where(SupplierProduct.owner_id == owner.id)
    if request.supplier_product_ids:
        query = query.where(SupplierProduct.id.in_(request.supplier_product_ids))
    else:
        query = query.where(SupplierProduct.id.in_(relevant_product_ids))
    products = list(db.scalars(query.order_by(SupplierProduct.id).limit(200)))
    if request.supplier_product_ids and len(products) != len(set(request.supplier_product_ids)):
        raise LookupError("Supplier product references unavailable.")
    supplier_ids = sorted({row.supplier_id for row in products})
    identity_links = (
        list(
            db.scalars(
                select(CrossMarketplaceSupplierLink).where(
                    CrossMarketplaceSupplierLink.owner_id == owner.id,
                    CrossMarketplaceSupplierLink.supplier_id.in_(supplier_ids),
                    CrossMarketplaceSupplierLink.match_state == "MATCH",
                )
            )
        )
        if supplier_ids
        else []
    )
    canonical_ids = sorted({row.canonical_supplier_id for row in identity_links})
    canonical_rows = (
        list(
            db.scalars(
                select(CrossMarketplaceSupplier).where(
                    CrossMarketplaceSupplier.owner_id == owner.id,
                    CrossMarketplaceSupplier.id.in_(canonical_ids),
                )
            )
        )
        if canonical_ids
        else []
    )
    canonical_map = {row.id: row for row in canonical_rows}
    accepted_identities: dict[uuid.UUID, set[uuid.UUID]] = {}
    for row in identity_links:
        if row.canonical_supplier_id in canonical_map:
            accepted_identities.setdefault(row.supplier_id, set()).add(row.canonical_supplier_id)
    identity_map = {
        supplier_id: next(iter(ids))
        for supplier_id, ids in accepted_identities.items()
        if len(ids) == 1
    }
    suppliers = (
        list(
            db.scalars(
                select(Supplier).where(Supplier.owner_id == owner.id, Supplier.id.in_(supplier_ids))
            )
        )
        if supplier_ids
        else []
    )
    sources = (
        list(
            db.scalars(
                select(SupplierSource).where(
                    SupplierSource.owner_id == owner.id,
                    SupplierSource.supplier_id.in_(supplier_ids),
                )
            )
        )
        if supplier_ids
        else []
    )
    matches = (
        list(
            db.scalars(
                select(SupplierOpportunityMatch).where(
                    SupplierOpportunityMatch.owner_id == owner.id,
                    SupplierOpportunityMatch.supplier_product_id.in_([row.id for row in products]),
                    SupplierOpportunityMatch.search_id.in_(search_ids),
                )
            )
        )
        if products
        else []
    )
    verifications = (
        list(
            db.scalars(
                select(SupplierVerification).where(
                    SupplierVerification.owner_id == owner.id,
                    SupplierVerification.supplier_id.in_(supplier_ids),
                )
            )
        )
        if supplier_ids
        else []
    )
    risks = (
        list(
            db.scalars(
                select(SupplierRiskAssessment).where(
                    SupplierRiskAssessment.owner_id == owner.id,
                    SupplierRiskAssessment.supplier_id.in_(supplier_ids),
                )
            )
        )
        if supplier_ids
        else []
    )
    terms = (
        list(
            db.scalars(
                select(SupplierCommercialTerm).where(
                    SupplierCommercialTerm.owner_id == owner.id,
                    SupplierCommercialTerm.supplier_product_id.in_([row.id for row in products]),
                    SupplierCommercialTerm.is_current.is_(True),
                )
            )
        )
        if products
        else []
    )
    evidence = (
        list(
            db.scalars(
                select(SupplierEvidence).where(
                    SupplierEvidence.owner_id == owner.id,
                    SupplierEvidence.supplier_id.in_(supplier_ids),
                    SupplierEvidence.archived.is_(False),
                )
            )
        )
        if supplier_ids
        else []
    )
    shortlist_contexts = list(
        db.scalars(
            select(SupplierShortlistContext).where(
                SupplierShortlistContext.owner_id == owner.id,
                or_(
                    SupplierShortlistContext.opportunity_id == opportunity.id,
                    (
                        SupplierShortlistContext.product_id == opportunity.product_id
                        if opportunity.product_id is not None
                        else false()
                    ),
                ),
            )
        )
    )
    shortlist_ids = [row.id for row in shortlist_contexts]
    scores = (
        list(
            db.scalars(
                select(SupplierShortlistScoreVersion).where(
                    SupplierShortlistScoreVersion.owner_id == owner.id,
                    SupplierShortlistScoreVersion.context_id.in_(shortlist_ids),
                    SupplierShortlistScoreVersion.supplier_id.in_(canonical_ids),
                )
            )
        )
        if shortlist_ids and supplier_ids
        else []
    )
    shortlist_versions = (
        list(
            db.scalars(
                select(SupplierShortlistVersion).where(
                    SupplierShortlistVersion.owner_id == owner.id,
                    SupplierShortlistVersion.context_id.in_(shortlist_ids),
                )
            )
        )
        if shortlist_ids
        else []
    )
    decisions = (
        list(
            db.scalars(
                select(SupplierShortlistDecision).where(
                    SupplierShortlistDecision.owner_id == owner.id,
                    SupplierShortlistDecision.context_id.in_(shortlist_ids),
                    SupplierShortlistDecision.supplier_id.in_(canonical_ids),
                )
            )
        )
        if shortlist_ids and supplier_ids
        else []
    )
    dd_contexts = list(
        db.scalars(
            select(SupplierDueDiligenceContext).where(
                SupplierDueDiligenceContext.owner_id == owner.id,
                or_(
                    SupplierDueDiligenceContext.opportunity_id == opportunity.id,
                    (
                        SupplierDueDiligenceContext.product_id == opportunity.product_id
                        if opportunity.product_id is not None
                        else false()
                    ),
                ),
            )
        )
    )
    dd_contexts = [row for row in dd_contexts if row.supplier_id in canonical_ids]
    dd_ids = [row.id for row in dd_contexts]
    dd_assessments = (
        list(
            db.scalars(
                select(SupplierDueDiligenceAssessment).where(
                    SupplierDueDiligenceAssessment.owner_id == owner.id,
                    SupplierDueDiligenceAssessment.context_id.in_(dd_ids),
                )
            )
        )
        if dd_ids
        else []
    )
    dd_gaps = (
        list(
            db.scalars(
                select(SupplierEvidenceGap).where(
                    SupplierEvidenceGap.owner_id == owner.id,
                    SupplierEvidenceGap.context_id.in_(dd_ids),
                    SupplierEvidenceGap.status != "RESOLVED",
                )
            )
        )
        if dd_ids
        else []
    )
    scenario_contexts = (
        list(
            db.scalars(
                select(SourcingScenarioContext).where(
                    SourcingScenarioContext.owner_id == owner.id,
                    (
                        SourcingScenarioContext.product_id == opportunity.product_id
                        if opportunity.product_id is not None
                        else false()
                    ),
                )
            )
        )
        if opportunity.product_id is not None
        else []
    )
    scenario_context_ids = [row.id for row in scenario_contexts]
    scenarios = (
        list(
            db.scalars(
                select(SourcingScenario).where(
                    SourcingScenario.owner_id == owner.id,
                    SourcingScenario.context_id.in_(scenario_context_ids),
                )
            )
        )
        if scenario_context_ids
        else []
    )
    scenario_ids = [row.id for row in scenarios]
    scenario_versions = (
        list(
            db.scalars(
                select(SourcingScenarioVersion).where(
                    SourcingScenarioVersion.owner_id == owner.id,
                    SourcingScenarioVersion.scenario_id.in_(scenario_ids),
                )
            )
        )
        if scenario_ids
        else []
    )
    current_scenario_versions = {row.id: row.current_version for row in scenarios}
    scenario_versions = [
        row
        for row in scenario_versions
        if row.version == current_scenario_versions.get(row.scenario_id)
    ]
    allocations = (
        list(
            db.scalars(
                select(ScenarioSupplierAllocation).where(
                    ScenarioSupplierAllocation.owner_id == owner.id,
                    ScenarioSupplierAllocation.version_id.in_(
                        [row.id for row in scenario_versions]
                    ),
                )
            )
        )
        if scenario_versions
        else []
    )
    commercial = db.scalar(
        select(ProductOpportunityCommercialOutput).where(
            ProductOpportunityCommercialOutput.owner_id == owner.id,
            ProductOpportunityCommercialOutput.assessment_id == assessment.id,
        )
    )
    portfolio_memberships, concentration, resilience, alternates, dependencies = _portfolio_rows(
        db, owner, opportunity
    )
    supplier_map = {row.id: row for row in suppliers}
    source_map: dict[uuid.UUID, SupplierSource] = {}
    for source_row in sources:
        source_map.setdefault(source_row.supplier_id, source_row)
    match_map: dict[uuid.UUID, Any] = {}
    for match_row in matches:
        previous_match: Any = match_map.get(match_row.supplier_product_id)
        if previous_match is None or match_row.id >= previous_match.id:
            match_map[match_row.supplier_product_id] = match_row
    verification_map = _latest(verifications, "observed_at")
    risk_map = _latest(risks, "created_at")
    term_map: dict[uuid.UUID, SupplierCommercialTerm] = {}
    for term_row in terms:
        previous_term = term_map.get(term_row.supplier_product_id)
        if previous_term is None or term_row.version > previous_term.version:
            term_map[term_row.supplier_product_id] = term_row
    score_map = _latest(scores, "created_at")
    decision_map = _latest(decisions, "created_at")
    dd_context_supplier = {row.id: row.supplier_id for row in dd_contexts}
    dd_map: dict[uuid.UUID, Any] = {}
    for dd_row in dd_assessments:
        supplier_id = dd_context_supplier.get(dd_row.context_id)
        if supplier_id is None:
            continue
        previous_dd: Any = dd_map.get(supplier_id)
        if previous_dd is None or dd_row.version >= previous_dd.version:
            dd_map[supplier_id] = dd_row
    latest_shortlists: dict[uuid.UUID, Any] = {}
    for shortlist_row in shortlist_versions:
        previous_shortlist = latest_shortlists.get(shortlist_row.context_id)
        if previous_shortlist is None or shortlist_row.version > previous_shortlist.version:
            latest_shortlists[shortlist_row.context_id] = shortlist_row
    shortlist_items = {
        str(item["supplier_id"]): {**item, "shortlisted": section == "shortlist"}
        for version_row in latest_shortlists.values()
        for section in ("shortlist", "review_required", "blocked")
        for item in version_row.payload.get(section, [])
        if isinstance(item, dict) and item.get("supplier_id")
    }
    product_candidates: list[dict[str, Any]] = []
    for product in products:
        supplier = supplier_map.get(product.supplier_id)
        if supplier is None:
            continue
        source = next(
            (row for row in sources if row.id == product.source_id),
            source_map.get(product.supplier_id),
        )
        canonical_id = identity_map.get(product.supplier_id)
        canonical_supplier = canonical_map.get(canonical_id) if canonical_id else None
        match = match_map.get(product.id)
        score = score_map.get(canonical_id) if canonical_id else None
        decision = decision_map.get(canonical_id) if canonical_id else None
        dd = dd_map.get(canonical_id) if canonical_id else None
        term = term_map.get(product.id)
        verification = verification_map.get(product.supplier_id)
        commercial_freshness = _freshness(term.observed_at if term else product.observed_at, now)[
            "state"
        ]
        if term and term.valid_until is not None and term.valid_until < now:
            commercial_freshness = "stale"
        risk = risk_map.get(product.supplier_id)
        match_state = (
            "UNKNOWN"
            if match is None
            else (
                "MATCHED"
                if match.match_score > 0 and not match.unmatched_requirements
                else "PARTIAL" if match.match_score > 0 else "NO_MATCH"
            )
        )
        shortlist_item = shortlist_items.get(str(canonical_id), {})
        eligibility = str(
            shortlist_item.get("eligibility", score.eligibility if score is not None else "UNKNOWN")
        )
        dd_state = dd.readiness if dd is not None else "NOT_ASSESSED"
        alternate_rows = [
            row
            for row in alternates
            if row.supplier_id == canonical_id and row.product_id in {None, opportunity.product_id}
        ]
        alternate_states = sorted({row.readiness_state for row in alternate_rows})
        alternate = alternate_states[0] if len(alternate_states) == 1 else "UNKNOWN"
        product_candidates.append(
            {
                "supplier": {"id": str(supplier.id), "name": supplier.display_name},
                "canonical_supplier_id": str(canonical_id) if canonical_id else None,
                "country": supplier.country,
                "region": supplier.region,
                "identity_state": (
                    canonical_supplier.identity_state if canonical_supplier else "UNKNOWN"
                ),
                "source": source.source_type if source is not None else supplier.source_identity,
                "matched_product": {"id": str(product.id), "title": product.title},
                "match_state": match_state,
                "match_explanation": (
                    match.explanation
                    if match is not None
                    else "No authoritative opportunity match is available."
                ),
                "verification": (
                    verification.state if verification is not None else supplier.verification_state
                ),
                "verification_freshness": (
                    _json(verification.observed_at) if verification else "unknown"
                ),
                "confidence": _json(match.confidence if match else None),
                "price": _json(
                    _number(
                        term.unit_price
                        if term and term.unit_price is not None
                        else product.observed_price
                    )
                ),
                "currency": term.currency if term and term.currency else product.currency,
                "moq": _json(_number(term.moq if term and term.moq is not None else product.moq)),
                "lead_time_days": _json(
                    _number(
                        term.production_lead_days
                        if term and term.production_lead_days is not None
                        else product.production_lead_days
                    )
                ),
                "commercial_freshness": commercial_freshness,
                "availability": (
                    product.specifications.get("availability")
                    if isinstance(product.specifications, dict)
                    else None
                ),
                "shortlist": {
                    "eligibility": eligibility,
                    "score": _json(score.score if score else None),
                    "model_version": score.model_version if score else None,
                    "decision": decision.decision if decision else None,
                    "score_id": str(score.id) if score else None,
                    "shortlisted": shortlist_item.get("shortlisted", False),
                    "recommendation": shortlist_item.get("recommendation"),
                    "reasons": shortlist_item.get("reason", []),
                    "hard_block": eligibility == "INELIGIBLE",
                    "review_required": eligibility in {"REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"},
                    "explanation": _json(score.dimensions) if score else [],
                },
                "due_diligence": {
                    "state": dd_state,
                    "version": dd.version if dd else None,
                    "assessment_id": str(dd.id) if dd else None,
                    "context_id": str(dd.context_id) if dd else None,
                    "gaps": [
                        {
                            "id": str(gap.id),
                            "dimension": gap.dimension,
                            "status": gap.status,
                            "freshness": gap.freshness_state,
                            "contradiction": gap.contradiction_state,
                        }
                        for gap in dd_gaps
                        if gap.supplier_id == canonical_id
                        and dd is not None
                        and gap.assessment_version == dd.version
                    ],
                },
                "alternate_readiness": alternate,
                "alternate_assessments": [
                    {
                        "id": str(row.id),
                        "assessment_id": str(row.assessment_version_id),
                        "readiness_state": row.readiness_state,
                        "reasons": row.reasons,
                        "missing_evidence": row.missing_evidence,
                        "stale_evidence": row.stale_evidence,
                        "contradictions": row.contradictions,
                    }
                    for row in alternate_rows
                ],
                "risk": risk.warnings if risk else [],
                "freshness": product.freshness_status,
                "commercial_fit": {
                    "moq": (
                        _fit(
                            _number(term.moq if term and term.moq is not None else product.moq),
                            constraint.maximum_moq,
                        )
                        if commercial_freshness != "stale"
                        else "UNKNOWN"
                    ),
                    "lead_time": (
                        _fit(
                            _number(
                                term.lead_time_days
                                if term and term.lead_time_days is not None
                                else product.production_lead_days
                            ),
                            _number(constraint.maximum_lead_time_days),
                        )
                        if commercial_freshness != "stale"
                        else "UNKNOWN"
                    ),
                    "geography": (
                        "UNKNOWN"
                        if not constraint.supplier_geography_preferences
                        or not (supplier.country or supplier.region)
                        else (
                            "MEETS"
                            if any(
                                value.casefold()
                                in {
                                    str(supplier.country or "").casefold(),
                                    str(supplier.region or "").casefold(),
                                    str(supplier.country_code or "").casefold(),
                                }
                                for value in constraint.supplier_geography_preferences
                            )
                            else "DOES_NOT_MEET"
                        )
                    ),
                    "capital": "UNKNOWN",
                    "landed_cost": "UNKNOWN",
                },
                "evidence_lineage": {
                    "product_id": str(product.id),
                    "source_id": str(source.id) if source else None,
                    "match_id": str(match.id) if match else None,
                    "verification_id": str(verification.id) if verification else None,
                    "commercial_term_id": str(term.id) if term else None,
                    "commercial_term_version": term.version if term else None,
                    "evidence_ids": [
                        str(row.id) for row in evidence if row.supplier_id == supplier.id
                    ],
                },
            }
        )

    def count_suppliers(predicate: Any) -> int:
        return len(
            {
                row["canonical_supplier_id"] or row["supplier"]["id"]
                for row in product_candidates
                if predicate(row)
            }
        )

    discovered = count_suppliers(lambda row: True)
    matched = count_suppliers(lambda row: row["match_state"] in {"MATCHED", "PARTIAL"})
    eligible = count_suppliers(
        lambda row: row["shortlist"]["eligibility"] == "ELIGIBLE"
        and row["match_state"] in {"MATCHED", "PARTIAL"}
    )
    shortlisted = count_suppliers(lambda row: row["shortlist"].get("shortlisted", False))
    dd_ready = count_suppliers(
        lambda row: row["due_diligence"]["state"] in {"SUFFICIENT", "REVIEW_REQUIRED"}
    )
    dd_complete = count_suppliers(lambda row: row["due_diligence"]["state"] == "SUFFICIENT")
    qualified_alternatives = count_suppliers(
        lambda row: row["alternate_readiness"] == "READY"
        and row["shortlist"]["eligibility"] == "ELIGIBLE"
        and row["due_diligence"]["state"] == "SUFFICIENT"
    )
    commercial_constraint_fit = (
        next(
            (
                item.get("value", {})
                for item in commercial.dimensions
                if isinstance(item, dict) and item.get("dimension") == "CONSTRAINT_FIT"
            ),
            {},
        )
        if commercial
        else {}
    )
    if not isinstance(commercial_constraint_fit, dict):
        commercial_constraint_fit = {}
    scenario_statuses = [row.status for row in scenarios]
    viable_scenarios = [
        row
        for row in scenarios
        if row.status in {"SUFFICIENT", "APPROVED_FOR_INTERNAL_SOURCING"}
        and any(
            value.scenario_id == row.id
            and not value.result.get("missing_dimensions")
            and value.result.get("classification") != "INSUFFICIENT_EVIDENCE"
            and value.result.get("status") != "BLOCKED"
            for value in scenario_versions
        )
    ]
    scenario_availability = (
        "NO_SCENARIO"
        if not scenarios
        else (
            "MULTIPLE_VIABLE_SCENARIOS"
            if len(viable_scenarios) > 1
            else (
                "ONE_VIABLE_SCENARIO"
                if viable_scenarios
                else (
                    "INSUFFICIENT_EVIDENCE"
                    if not scenario_versions
                    or all(
                        value.result.get("classification") == "INSUFFICIENT_EVIDENCE"
                        for value in scenario_versions
                    )
                    else "SCENARIOS_REQUIRE_REVIEW"
                )
            )
        )
    )
    qualified_candidates = [
        row
        for row in product_candidates
        if row["shortlist"]["eligibility"] == "ELIGIBLE"
        and row["due_diligence"]["state"] == "SUFFICIENT"
        and row["match_state"] in {"MATCHED", "PARTIAL"}
    ]
    commercial_complete = bool(
        commercial
        and commercial.economics.get("landed_cost_per_unit") is not None
        and commercial_constraint_fit.get("currency_comparable") is True
    )
    if not product_candidates:
        feasibility_state = "INSUFFICIENT_EVIDENCE"
    elif all(
        row["shortlist"]["eligibility"] == "INELIGIBLE"
        or row["due_diligence"]["state"] == "BLOCKED"
        for row in product_candidates
    ):
        feasibility_state = "BLOCKED"
    elif not matched:
        feasibility_state = "RESEARCH_REQUIRED"
    elif all(row["shortlist"]["eligibility"] == "UNKNOWN" for row in product_candidates):
        feasibility_state = "INSUFFICIENT_EVIDENCE"
    elif not eligible:
        feasibility_state = "NO_ELIGIBLE_SUPPLIER"
    elif not qualified_candidates:
        feasibility_state = "DUE_DILIGENCE_REQUIRED"
    elif not commercial_complete:
        feasibility_state = "COMMERCIAL_VALIDATION_REQUIRED"
    elif any(row["commercial_freshness"] == "stale" for row in qualified_candidates) or any(
        str(value).startswith(("EXCEEDS", "BELOW")) for value in commercial_constraint_fit.values()
    ):
        feasibility_state = "PARTIAL"
    else:
        feasibility_state = "AVAILABLE"
    gaps: list[str] = []
    if not products:
        gaps.extend(["SUPPLIER_DISCOVERY_REQUIRED", "SUPPLIER_MATCH_REQUIRED"])
    if not matched:
        gaps.append("SUPPLIER_MATCH_REQUIRED")
    if not eligible:
        gaps.append("SUPPLIER_VERIFICATION_REQUIRED")
    if not dd_complete:
        gaps.append("DUE_DILIGENCE_REQUIRED")
    if commercial is None:
        gaps.extend(["PRICE_REQUIRED", "LANDED_COST_REQUIRED"])
    if not viable_scenarios:
        gaps.append("SOURCING_SCENARIO_REQUIRED")
    if qualified_alternatives < 2:
        gaps.append("ALTERNATIVE_SUPPLIER_REQUIRED")
    if not any(row["moq"] is not None for row in product_candidates):
        gaps.append("MOQ_REQUIRED")
    if not any(row["lead_time_days"] is not None for row in product_candidates):
        gaps.append("LEAD_TIME_REQUIRED")
    if not any(row["availability"] is not None for row in product_candidates):
        gaps.append("AVAILABILITY_REQUIRED")
    if not portfolio_memberships:
        gaps.append("PORTFOLIO_ASSESSMENT_REQUIRED")
    gaps = list(dict.fromkeys(gaps))
    supplier_changes = (
        list(
            db.scalars(
                select(SupplierHistoryEvent)
                .where(
                    SupplierHistoryEvent.owner_id == owner.id,
                    SupplierHistoryEvent.supplier_id.in_(supplier_ids),
                )
                .order_by(SupplierHistoryEvent.created_at.desc(), SupplierHistoryEvent.id)
                .limit(100)
            )
        )
        if supplier_ids
        else []
    )
    evidence_count = len(evidence) + len(matches) + len(verifications)
    source_types = sorted({row.source_type for row in sources})
    countries = (
        sorted(
            {
                str(supplier_map[uuid.UUID(row["supplier"]["id"])].country)
                for row in product_candidates
                if supplier_map[uuid.UUID(row["supplier"]["id"])].country
            }
        )
        if product_candidates
        else []
    )
    summary = {
        "feasibility_state": feasibility_state,
        "supplier_availability": {
            "discovered": discovered,
            "matched": matched,
            "eligible": eligible,
            "shortlisted": shortlisted,
            "dd_ready": dd_ready,
            "dd_complete": dd_complete,
            "qualified_alternatives": qualified_alternatives,
        },
        "scenario_availability": scenario_availability,
        "scenario_count": len(scenarios),
        "evidence_state": "available" if evidence_count else "insufficient_evidence",
        "confidence": "authoritative_values_available" if canonical_rows else "unknown",
        "confidence_sources": [
            {"supplier_id": str(row.id), "value": _json(row.confidence_score)}
            for row in canonical_rows
        ],
        "risk_exposures": [item for row in product_candidates for item in row["risk"]],
        "candidate_product_count": len(product_candidates),
    }
    commercial_constraint_fit = (
        next(
            (
                item.get("value", {})
                for item in commercial.dimensions
                if isinstance(item, dict) and item.get("dimension") == "CONSTRAINT_FIT"
            ),
            {},
        )
        if commercial
        else {}
    )
    if not isinstance(commercial_constraint_fit, dict):
        commercial_constraint_fit = {}
    dimensions = [
        _dimension(
            "SUPPLIER_AVAILABILITY",
            summary["supplier_availability"],
            "DERIVED_PROJECTION" if discovered else "UNKNOWN",
            "Descriptive counts distinguish discovery from eligibility "
            "and due-diligence readiness.",
            [str(row["matched_product"]["id"]) for row in product_candidates],
            ["supplier discovery"] if not discovered else [],
        ),
        _dimension(
            "SUPPLIER_VERIFICATION",
            [row["verification"] for row in product_candidates],
            "VERIFIED_FACT" if verifications else "UNKNOWN",
            "Uses authoritative supplier verification states; it is not a supplier quality score.",
            [str(row.id) for row in verifications],
            ["verification"] if not verifications else [],
        ),
        _dimension(
            "DUE_DILIGENCE_COVERAGE",
            {"ready": dd_ready, "complete": dd_complete, "gaps": len(dd_gaps)},
            "DERIVED_PROJECTION" if dd_contexts else "UNKNOWN",
            "Consumes 8C assessment readiness and unresolved evidence gaps.",
            [str(row.id) for row in dd_assessments],
            ["due diligence"] if not dd_contexts else [],
        ),
        _dimension(
            "COMMERCIAL_FIT",
            commercial.economics if commercial else None,
            "DERIVED_PROJECTION" if commercial else "UNKNOWN",
            "Reuses the assessment-bound 9C commercial projection without recalculating economics.",
            [str(commercial.id)] if commercial else [],
            ["commercial assessment"] if not commercial else [],
        ),
        *[
            _dimension(
                name,
                [
                    {
                        "supplier_product_id": row["matched_product"]["id"],
                        "state": row["commercial_fit"][key],
                    }
                    for row in product_candidates
                ],
                (
                    "DERIVED_PROJECTION"
                    if any(row["commercial_fit"][key] != "UNKNOWN" for row in product_candidates)
                    else "UNKNOWN"
                ),
                "Compares current authoritative supplier terms with the frozen opportunity "
                "constraint. Stale or missing evidence remains UNKNOWN.",
                [row["evidence_lineage"] for row in product_candidates],
                [] if product_candidates else ["supplier commercial evidence"],
            )
            for name, key in (
                ("MOQ_FIT", "moq"),
                ("LEAD_TIME_FIT", "lead_time"),
                ("GEOGRAPHY_FIT", "geography"),
            )
        ],
        *[
            _dimension(
                name,
                commercial_constraint_fit.get(key, "UNKNOWN"),
                (
                    "DERIVED_PROJECTION"
                    if commercial_constraint_fit.get(key, "UNKNOWN") != "UNKNOWN"
                    else "UNKNOWN"
                ),
                "Consumes the frozen 9C constraint-fit result, preserving its currency "
                "and capital semantics.",
                [str(commercial.id)] if commercial else [],
                (
                    []
                    if commercial_constraint_fit.get(key, "UNKNOWN") != "UNKNOWN"
                    else ["comparable 9C commercial evidence"]
                ),
            )
            for name, key in (
                ("CAPITAL_FIT", "available_capital"),
                ("LANDED_COST_FIT", "maximum_landed_cost"),
            )
        ],
        _dimension(
            "QUALIFIED_ALTERNATIVE_COVERAGE",
            qualified_alternatives,
            "DERIVED_PROJECTION" if portfolio_memberships else "UNKNOWN",
            "Counts authoritative 8E alternate-readiness states; quantity is not quality.",
            portfolio_memberships,
            ["portfolio alternate readiness"] if not portfolio_memberships else [],
        ),
        _dimension(
            "SOURCE_DIVERSITY",
            {"provider_count": len(source_types), "providers": source_types},
            "OBSERVED_FACT" if source_types else "UNKNOWN",
            "Uses persisted supplier source/provider lineage.",
            source_types,
            ["supplier source"] if not source_types else [],
        ),
        _dimension(
            "GEOGRAPHIC_DIVERSITY",
            {"country_count": len(countries), "countries": countries},
            "OBSERVED_FACT" if countries else "UNKNOWN",
            "Describes persisted supplier countries without treating diversity as quality.",
            countries,
            ["supplier country"] if not countries else [],
        ),
        _dimension(
            "SOURCING_SCENARIO_STRENGTH",
            {
                "availability": scenario_availability,
                "statuses": scenario_statuses,
                "allocations": len(allocations),
                "scenarios": [
                    {
                        "id": str(row.id),
                        "scenario_id": str(row.scenario_id),
                        "version": row.version,
                        "calculation_version": row.calculation_version,
                        "summary": {
                            key: _json(row.result.get(key))
                            for key in (
                                "currency",
                                "cost",
                                "capital",
                                "margin",
                                "moq_feasibility",
                                "lead_time",
                                "supplier_risk",
                                "supplier_confidence",
                                "classification",
                                "missing_dimensions",
                                "warnings",
                                "concentration",
                                "resilience",
                                "evidence_state",
                            )
                        },
                    }
                    for row in scenario_versions
                ],
            },
            "DERIVED_PROJECTION" if scenarios else "UNKNOWN",
            "Consumes 8D scenario status, allocation, and version lineage.",
            [str(row.id) for row in scenario_versions],
            ["sourcing scenario"] if not scenarios else [],
        ),
        _dimension(
            "SOURCING_RESILIENCE",
            "UNKNOWN" if not resilience else [row.classification for row in resilience],
            "UNKNOWN" if not resilience else "DERIVED_PROJECTION",
            "Consumes 8E resilience when a relevant portfolio assessment exists; "
            "no portfolio is fabricated.",
            [str(row.id) for row in resilience],
            ["portfolio resilience"] if not resilience else [],
        ),
        _dimension(
            "SUPPLIER_EVIDENCE_COVERAGE",
            evidence_count,
            "DERIVED_PROJECTION" if evidence_count else "UNKNOWN",
            "Counts bounded persisted supplier, match, verification, and DD evidence references.",
            [str(row.id) for row in evidence],
            ["supplier evidence"] if not evidence_count else [],
        ),
    ]
    dimensions.append(
        _dimension(
            "SUPPLIER_EVIDENCE_FRESHNESS",
            sorted(
                {row.freshness_status for row in evidence}
                | {row["commercial_freshness"] for row in product_candidates}
            ),
            "DERIVED_PROJECTION" if evidence or product_candidates else "UNKNOWN",
            "Consumes shared evidence freshness and timestamp rules. "
            "Commercial expiry remains explicit.",
            [str(row.id) for row in evidence],
            [] if evidence else ["supplier evidence timestamps"],
        )
    )
    portfolio_lineage = {
        "memberships": portfolio_memberships,
        "assessment_ids": sorted(
            {
                str(row.assessment_version_id)
                for row in concentration + resilience + alternates + dependencies
            }
            | {
                assessment_id
                for member in portfolio_memberships
                for assessment_id in member["assessment_ids"]
            }
        ),
        "concentration": [
            {
                "id": str(row.id),
                "dimension": row.dimension,
                "metric_type": row.metric_type,
                "value": _json(row.value),
                "classification": row.classification,
                "explanation": row.explanation,
                "calculation_version": row.calculation_version,
                "missing_data": row.missing_data,
            }
            for row in concentration
        ],
        "dependencies": [
            {
                "id": str(row.id),
                "type": row.dependency_type,
                "severity": row.severity,
                "explanation": row.explanation,
                "supplier_id": _json(row.affected_supplier_id),
            }
            for row in dependencies
        ],
        "alternates": [str(row.id) for row in alternates],
        "resilience": [
            {
                "id": str(row.id),
                "classification": row.classification,
                "score": _json(row.score),
                "confidence": _json(row.confidence_value),
                "confidence_classification": row.confidence_classification,
                "evidence_status": row.evidence_status,
                "explanation": row.explanation,
                "version": row.score_version,
            }
            for row in resilience
        ],
    }
    dimensions.append(
        _dimension(
            "SOURCING_CONCENTRATION",
            portfolio_lineage["concentration"],
            "DERIVED_PROJECTION" if concentration else "UNKNOWN",
            "Consumes 8E concentration metrics and dependencies without recalculating HHI "
            "or treating HHI alone as risk.",
            [str(row.id) for row in concentration],
            [] if concentration else ["relevant portfolio assessment"],
        )
    )
    upstream = {
        "suppliers": [str(row.id) for row in suppliers],
        "canonical_suppliers": [str(row.id) for row in canonical_rows],
        "identity_links": [str(row.id) for row in identity_links],
        "supplier_sources": [str(row.id) for row in sources],
        "supplier_evidence": [str(row.id) for row in evidence],
        "supplier_changes": [str(row.id) for row in supplier_changes],
        "verifications": [str(row.id) for row in verifications],
        "commercial_terms": [str(row.id) for row in terms],
        "shortlist_scores": [str(row.id) for row in scores],
        "supplier_products": [str(row.id) for row in products],
        "supplier_matches": [str(row.id) for row in matches],
        "shortlist_contexts": [str(row.id) for row in shortlist_contexts],
        "shortlist_versions": [str(row.id) for row in shortlist_versions],
        "due_diligence_contexts": [str(row.id) for row in dd_contexts],
        "due_diligence_assessments": [str(row.id) for row in dd_assessments],
        "scenario_versions": [str(row.id) for row in scenario_versions],
        "due_diligence_gaps": [str(row.id) for row in dd_gaps],
        "portfolio": portfolio_lineage,
        "commercial_output": str(commercial.id) if commercial else None,
    }
    now = feasibility_now()
    key = request.idempotency_key or f"opportunity-feasibility:{assessment.id}"
    output = ProductOpportunitySourcingFeasibilityOutput(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        calculation_version=CALCULATION_VERSION,
        constraint_snapshot=_json(_constraint_snapshot(constraint)),
        upstream_lineage=upstream,
        summary=summary,
        candidates=product_candidates,
        dimensions=dimensions,
        evidence_summary={
            "count": evidence_count,
            "providers": source_types,
            "dd_gaps": len(dd_gaps),
            "freshness": sorted(
                {row.freshness_status for row in products}
                | {row.freshness_status for row in evidence}
            ),
            "changes": [
                {
                    "id": str(row.id),
                    "supplier_id": str(row.supplier_id),
                    "event_type": row.event_type,
                    "occurred_at": row.created_at.isoformat(),
                }
                for row in supplier_changes
            ],
            "contradictions": [
                {"gap_id": str(row.id), "state": row.contradiction_state}
                for row in dd_gaps
                if row.contradiction_state not in {"none", ""}
            ],
            "supplier_confidence": [
                {"supplier_id": str(row.id), "value": _json(row.confidence_score)}
                for row in canonical_rows
            ],
        },
        research_gaps=gaps,
        idempotency_key=key,
        created_at=now,
        notes=(
            "Supplier and sourcing feasibility projection only; no supplier selection, "
            "contact, RFQ, procurement, or launch verdict."
        ),
    )
    db.add(output)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = db.scalar(
            select(ProductOpportunitySourcingFeasibilityOutput).where(
                ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id,
                ProductOpportunitySourcingFeasibilityOutput.assessment_id == assessment.id,
            )
        )
        if replay is not None:
            return replay
        raise ValueError("Sourcing feasibility idempotency key is already in use.") from exc
    db.refresh(output)
    return output


def output_or_404(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunitySourcingFeasibilityOutput:
    row = db.scalar(
        select(ProductOpportunitySourcingFeasibilityOutput).where(
            ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id,
            ProductOpportunitySourcingFeasibilityOutput.opportunity_id == opportunity_id,
            ProductOpportunitySourcingFeasibilityOutput.assessment_id == assessment_id,
        )
    )
    if row is None:
        raise LookupError("Supplier feasibility assessment not found.")
    return row


def history(
    db: Session, owner: User, opportunity_id: uuid.UUID
) -> list[ProductOpportunitySourcingFeasibilityOutput]:
    return list(
        db.scalars(
            select(ProductOpportunitySourcingFeasibilityOutput)
            .where(
                ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id,
                ProductOpportunitySourcingFeasibilityOutput.opportunity_id == opportunity_id,
            )
            .order_by(ProductOpportunitySourcingFeasibilityOutput.created_at.desc())
        )
    )


def doctor(db: Session, owner: User) -> dict[str, int]:
    """Check persisted projections and authoritative references with set-based retrieval."""
    rows = list(
        db.scalars(
            select(ProductOpportunitySourcingFeasibilityOutput).where(
                ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id
            )
        )
    )
    checks = {
        "orphan_outputs": 0,
        "broken_lineage": 0,
        "cross_owner_references": 0,
        "broken_supplier_lineage": 0,
        "broken_shortlist_lineage": 0,
        "broken_due_diligence_lineage": 0,
        "broken_scenario_lineage": 0,
        "broken_portfolio_lineage": 0,
        "duplicate_assessment_outputs": len(rows) - len({row.assessment_id for row in rows}),
        "invalid_numeric_state": 0,
        "invalid_calculation_version": sum(
            row.calculation_version != CALCULATION_VERSION for row in rows
        ),
    }
    opportunities = {
        row.id: row
        for row in db.scalars(
            select(ProductOpportunity).where(
                ProductOpportunity.id.in_({row.opportunity_id for row in rows})
            )
        )
    }
    assessments = {
        row.id: row
        for row in db.scalars(
            select(ProductOpportunityAssessment).where(
                ProductOpportunityAssessment.id.in_({row.assessment_id for row in rows})
            )
        )
    }
    references: list[tuple[str, Any, str]] = [
        ("suppliers", Supplier, "broken_supplier_lineage"),
        ("canonical_suppliers", CrossMarketplaceSupplier, "broken_supplier_lineage"),
        ("identity_links", CrossMarketplaceSupplierLink, "broken_supplier_lineage"),
        ("supplier_products", SupplierProduct, "broken_supplier_lineage"),
        ("supplier_sources", SupplierSource, "broken_supplier_lineage"),
        ("supplier_matches", SupplierOpportunityMatch, "broken_supplier_lineage"),
        ("supplier_evidence", SupplierEvidence, "broken_supplier_lineage"),
        ("supplier_changes", SupplierHistoryEvent, "broken_supplier_lineage"),
        ("verifications", SupplierVerification, "broken_supplier_lineage"),
        ("commercial_terms", SupplierCommercialTerm, "broken_supplier_lineage"),
        ("shortlist_contexts", SupplierShortlistContext, "broken_shortlist_lineage"),
        ("shortlist_versions", SupplierShortlistVersion, "broken_shortlist_lineage"),
        ("shortlist_scores", SupplierShortlistScoreVersion, "broken_shortlist_lineage"),
        ("due_diligence_contexts", SupplierDueDiligenceContext, "broken_due_diligence_lineage"),
        (
            "due_diligence_assessments",
            SupplierDueDiligenceAssessment,
            "broken_due_diligence_lineage",
        ),
        ("due_diligence_gaps", SupplierEvidenceGap, "broken_due_diligence_lineage"),
        ("scenario_versions", SourcingScenarioVersion, "broken_scenario_lineage"),
        ("portfolio_memberships", SupplierPortfolioMembership, "broken_portfolio_lineage"),
        ("portfolio_assessments", SupplierPortfolioAssessmentVersion, "broken_portfolio_lineage"),
        (
            "portfolio_concentration",
            SupplierPortfolioConcentrationMetric,
            "broken_portfolio_lineage",
        ),
        ("portfolio_resilience", SupplierPortfolioResilienceScore, "broken_portfolio_lineage"),
        ("portfolio_alternates", SupplierPortfolioAlternateReadiness, "broken_portfolio_lineage"),
        ("portfolio_dependencies", SupplierPortfolioDependencyFinding, "broken_portfolio_lineage"),
        ("commercial_outputs", ProductOpportunityCommercialOutput, "broken_lineage"),
        ("constraints", ProductOpportunityConstraintVersion, "broken_lineage"),
    ]
    normalized: list[dict[str, list[Any]]] = []
    for output in rows:
        opportunity = opportunities.get(output.opportunity_id)
        assessment = assessments.get(output.assessment_id)
        if opportunity is None or assessment is None:
            checks["orphan_outputs"] += 1
        elif opportunity.owner_id != owner.id or assessment.owner_id != owner.id:
            checks["cross_owner_references"] += 1
        elif assessment.opportunity_id != output.opportunity_id or str(
            assessment.constraint_version_id
        ) != str(output.constraint_snapshot.get("id")):
            checks["broken_lineage"] += 1
        lineage = {
            key: list(value)
            for key, value in output.upstream_lineage.items()
            if isinstance(value, list)
        }
        portfolio = output.upstream_lineage.get("portfolio", {})
        if not isinstance(portfolio, dict):
            portfolio = {}
        for section in ("memberships", "concentration", "resilience", "dependencies"):
            lineage["portfolio_" + section] = [
                item.get("id") for item in portfolio.get(section, []) if isinstance(item, dict)
            ]
        lineage["portfolio_assessments"] = portfolio.get("assessment_ids", [])
        lineage["portfolio_alternates"] = portfolio.get("alternates", [])
        commercial_id = output.upstream_lineage.get("commercial_output")
        lineage["commercial_outputs"] = [commercial_id] if commercial_id else []
        lineage["constraints"] = [output.constraint_snapshot.get("id")]
        normalized.append(lineage)
        if (
            _invalid_numeric(output.summary)
            or _invalid_numeric(output.candidates)
            or _invalid_numeric(output.dimensions)
        ):
            checks["invalid_numeric_state"] += 1
    for key, model, counter in references:
        requested: set[uuid.UUID] = set()
        invalid = 0
        for lineage in normalized:
            for value in lineage.get(key, []):
                try:
                    requested.add(uuid.UUID(str(value)))
                except (TypeError, ValueError, AttributeError):
                    invalid += 1
        checks[counter] += invalid
        found: dict[uuid.UUID, uuid.UUID] = (
            {
                record[0]: record[1]
                for record in db.execute(
                    select(model.id, model.owner_id).where(model.id.in_(requested))
                ).all()
            }
            if requested
            else {}
        )
        checks[counter] += len(requested - found.keys())
        checks["cross_owner_references"] += sum(value != owner.id for value in found.values())
    return checks


def _invalid_numeric(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_invalid_numeric(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_invalid_numeric(item) for item in value)
    if isinstance(value, (float, Decimal)):
        return not Decimal(str(value)).is_finite()
    return isinstance(value, str) and value.lower() in {
        "nan",
        "infinity",
        "-infinity",
        "inf",
        "-inf",
    }
