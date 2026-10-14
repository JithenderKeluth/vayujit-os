"""PR-8A orchestration over the canonical PR-5A/B/C authorities.

This module intentionally contains no commercial mathematics.  It validates a
reviewed PR-7C promotion, creates a product-scoped PR-5A snapshot, delegates
landed cost and unit economics to PR-5B and PR-5C, then stores an immutable
comparison and an explicit HUMAN reassessment review.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.commercial_readiness_schemas import CommercialReadinessCreate
from vayujit_api.intelligence.commercial_readiness_service import project_readiness
from vayujit_api.intelligence.commercial_reassessment_models import (
    CommercialReassessment,
    CommercialReassessmentReview,
)
from vayujit_api.intelligence.commercial_reassessment_schemas import (
    CommercialReassessmentCreate,
    CommercialReassessmentReviewCreate,
)
from vayujit_api.intelligence.economic_calculation_models import (
    EconomicCalculation,
    EconomicCalculationBreakdown,
)
from vayujit_api.intelligence.landed_cost_service import calculate_landed_cost
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.product_opportunity_unit_economics_models import (
    ProductOpportunityUnitEconomics,
)
from vayujit_api.intelligence.product_opportunity_unit_economics_service import (
    calculate_unit_economics,
    latest_unit_economics,
)
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCommercialTerm,
    SupplierProduct,
)
from vayujit_api.intelligence.supplier_response_models import (
    SupplierInboundResponse,
    SupplierResponseExtraction,
    SupplierResponsePromotion,
    SupplierResponseReview,
)


def _json(value: Any) -> Any:
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(v) for v in value]
    return value


def _fingerprint(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(_json(payload), sort_keys=True).encode()).hexdigest()


def _owned_context(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[ProductOpportunity, ProductOpportunityAssessment]:
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
        raise HTTPException(404, "Product opportunity assessment not found.")
    return opportunity, assessment


def _promotion_scope(
    db: Session, owner: User, promotion_id: uuid.UUID, opportunity_id: uuid.UUID
) -> tuple[
    SupplierResponsePromotion,
    SupplierInboundResponse,
    SupplierResponseExtraction,
    SupplierResponseReview,
    Supplier,
    SupplierProduct,
    SupplierCommercialTerm,
]:
    promotion = db.scalar(
        select(SupplierResponsePromotion).where(
            SupplierResponsePromotion.id == promotion_id,
            SupplierResponsePromotion.owner_id == owner.id,
        )
    )
    if promotion is None or promotion.status != "PROMOTED":
        raise HTTPException(409, "A promoted supplier quote is required for reassessment.")
    response = db.scalar(
        select(SupplierInboundResponse).where(
            SupplierInboundResponse.id == promotion.response_id,
            SupplierInboundResponse.owner_id == owner.id,
        )
    )
    extraction = db.scalar(
        select(SupplierResponseExtraction).where(
            SupplierResponseExtraction.id == promotion.extraction_id,
            SupplierResponseExtraction.owner_id == owner.id,
        )
    )
    review = db.scalar(
        select(SupplierResponseReview).where(
            SupplierResponseReview.id == promotion.review_id,
            SupplierResponseReview.owner_id == owner.id,
        )
    )
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == (response.supplier_id if response else uuid.uuid4()),
            Supplier.owner_id == owner.id,
        )
    )
    product = db.scalar(
        select(SupplierProduct).where(
            SupplierProduct.id == promotion.supplier_product_id,
            SupplierProduct.owner_id == owner.id,
        )
    )
    term = db.scalar(
        select(SupplierCommercialTerm).where(
            SupplierCommercialTerm.id == promotion.commercial_term_id,
            SupplierCommercialTerm.owner_id == owner.id,
        )
    )
    if (
        response is None
        or extraction is None
        or review is None
        or supplier is None
        or product is None
        or term is None
    ):
        raise HTTPException(409, "The promoted quote lineage is incomplete.")
    if response.opportunity_id != opportunity_id:
        raise HTTPException(409, "The reviewed quote belongs to a different product opportunity.")
    if (
        response.supplier_id != supplier.id
        or product.supplier_id != supplier.id
        or term.supplier_id != supplier.id
        or term.supplier_product_id != product.id
    ):
        raise HTTPException(409, "Supplier and supplier-product scope do not match the quote.")
    if response.correlation_state != "CORRELATED" or response.classification != "QUOTE":
        raise HTTPException(409, "Only a correlated supplier quote can be reassessed.")
    if review.provenance != "HUMAN" or review.decision not in {
        "ACCEPT_EXTRACTION",
        "CORRECT_EXTRACTION",
    }:
        raise HTTPException(
            409, "Explicit HUMAN extraction review is required before reassessment."
        )
    if extraction.status not in {"EXTRACTED", "PARTIAL"}:
        raise HTTPException(409, "The supplier extraction is not eligible for reassessment.")
    if not term.is_current:
        raise HTTPException(
            409, "The selected quote version is stale; review the current quote first."
        )
    return promotion, response, extraction, review, supplier, product, term


def _row_view(db: Session, owner: User, row: CommercialReassessment) -> dict[str, object]:
    review = db.scalar(
        select(CommercialReassessmentReview)
        .where(
            CommercialReassessmentReview.owner_id == owner.id,
            CommercialReassessmentReview.reassessment_id == row.id,
        )
        .order_by(CommercialReassessmentReview.created_at.desc())
    )
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id),
        "assessment_id": str(row.assessment_id),
        "supplier_id": str(row.supplier_id),
        "supplier_product_id": str(row.supplier_product_id),
        "promotion_id": str(row.promotion_id),
        "commercial_term_id": str(row.commercial_term_id),
        "baseline_landed_cost_id": (
            str(row.baseline_landed_cost_id) if row.baseline_landed_cost_id else None
        ),
        "baseline_unit_economics_id": (
            str(row.baseline_unit_economics_id) if row.baseline_unit_economics_id else None
        ),
        "current_readiness_id": str(row.current_readiness_id) if row.current_readiness_id else None,
        "current_landed_cost_id": (
            str(row.current_landed_cost_id) if row.current_landed_cost_id else None
        ),
        "current_unit_economics_id": (
            str(row.current_unit_economics_id) if row.current_unit_economics_id else None
        ),
        "scenario_key": row.scenario_key,
        "status": row.status,
        "review_status": row.review_status,
        "input_fingerprint": row.input_fingerprint,
        "idempotency_key": row.idempotency_key,
        "quote_version": row.quote_version,
        "quote_evidence": _json(row.quote_evidence),
        "assumptions": _json(row.assumptions),
        "baseline": _json(row.baseline),
        "current": _json(row.current),
        "comparison": _json(row.comparison),
        "blockers": _json(row.blockers),
        "provenance": _json(row.provenance),
        "lineage": _json(row.lineage),
        "created_at": row.created_at.isoformat(),
        "notes": row.notes,
        "review": (
            {
                "id": str(review.id),
                "decision": review.decision,
                "provenance": review.provenance,
                "reason": review.reason,
                "created_at": review.created_at.isoformat(),
            }
            if review
            else None
        ),
    }


def _calculation_view(db: Session, row: EconomicCalculation | None) -> dict[str, object]:
    if row is None:
        return {"status": "UNKNOWN", "calculable": False}
    breakdown = list(
        db.scalars(
            select(EconomicCalculationBreakdown)
            .where(EconomicCalculationBreakdown.calculation_id == row.id)
            .order_by(EconomicCalculationBreakdown.line_order)
        )
    )
    return {
        "id": str(row.id),
        "status": row.status,
        "calculable": row.per_unit_cost is not None,
        "currency": row.currency,
        "target_quantity": _json(row.target_quantity),
        "total_included_cost": _json(row.total_included_cost),
        "per_unit_cost": _json(row.per_unit_cost),
        "calculation_version": row.calculation_version,
        "policy_version": row.policy_version,
        "calculation_fingerprint": row.calculation_fingerprint,
        "missing_inputs": _json(row.missing_inputs),
        "warnings": _json(row.warnings),
        "assumptions": _json(row.assumptions),
        "breakdown": [
            {
                "category": item.category,
                "original_amount": _json(item.original_amount),
                "converted_amount": _json(item.converted_amount),
                "currency": item.currency,
                "basis": item.basis,
                "provenance": item.provenance,
                "inclusion_status": item.inclusion_status,
                "exclusion_reason": item.exclusion_reason,
                "evidence_ref": str(item.evidence_ref) if item.evidence_ref else None,
            }
            for item in breakdown
        ],
    }


def _input_value(snapshot: CommercialReadinessSnapshot | None, key: str) -> object | None:
    if snapshot is None:
        return None
    lineage = snapshot.lineage if isinstance(snapshot.lineage, dict) else {}
    candidate = lineage.get("candidate")
    effective_inputs = candidate.get("effective_inputs", []) if isinstance(candidate, dict) else []
    for item in effective_inputs if isinstance(effective_inputs, list) else []:
        if isinstance(item, dict) and item.get("key") == key:
            return item.get("value")
    for item in snapshot.known_inputs or []:
        if isinstance(item, dict) and item.get("key") == key:
            return item.get("value")
    for item in snapshot.assumptions or []:
        if isinstance(item, dict) and item.get("key") == key:
            return item.get("value")
    return None


def _metric_value(
    name: str,
    readiness: CommercialReadinessSnapshot | None,
    economics: dict[str, object],
    landed: dict[str, object],
) -> object | None:
    if name == "supplier_unit_price":
        return _input_value(readiness, name)
    if name == "moq":
        return _input_value(readiness, "supplier_moq")
    if name == "order_quantity":
        return (
            economics.get("quantity")
            or economics.get("target_quantity")
            or landed.get("target_quantity")
        )
    mapping = {
        "landed_cost_per_unit": "per_unit_landed_cost",
        "selling_cost_per_unit": "per_unit_selling_cost",
        "contribution_per_unit": "per_unit_contribution",
        "contribution_margin": "contribution_margin",
        "capital_required": "capital_required",
        "capital_headroom": "capital_headroom",
    }
    if name in mapping:
        return economics.get(mapping[name])
    if name == "freight":
        breakdown = landed.get("breakdown", [])
        breakdown_items = breakdown if isinstance(breakdown, list) else []
        return next(
            (
                item.get("converted_amount")
                for item in breakdown_items
                if isinstance(item, dict)
                if item.get("category") == "FREIGHT" and item.get("inclusion_status") == "INCLUDED"
            ),
            None,
        )
    return None


def _comparison(
    baseline_readiness: CommercialReadinessSnapshot | None,
    baseline_landed: dict[str, object],
    baseline_economics: dict[str, object],
    current_readiness: CommercialReadinessSnapshot | None,
    current_landed: dict[str, object],
    current_economics: dict[str, object],
) -> dict[str, object]:
    metrics: dict[str, object] = {}
    for name in (
        "supplier_unit_price",
        "moq",
        "order_quantity",
        "freight",
        "landed_cost_per_unit",
        "selling_cost_per_unit",
        "contribution_per_unit",
        "contribution_margin",
        "capital_required",
        "capital_headroom",
    ):
        before = _metric_value(name, baseline_readiness, baseline_economics, baseline_landed)
        after = _metric_value(name, current_readiness, current_economics, current_landed)
        delta: object | None = None
        state = "AVAILABLE"
        try:
            if before is not None and after is not None:
                delta = str(Decimal(str(after)) - Decimal(str(before)))
            else:
                state = "UNKNOWN"
        except (ValueError, ArithmeticError):
            state = "NOT_COMPARABLE"
        metrics[name] = {
            "baseline": _json(before),
            "reassessment": _json(after),
            "delta": delta,
            "state": state,
        }
    return {
        "metrics": metrics,
        "automatic_winner": None,
        "note": "Trade-off comparison only; no supplier recommendation.",
    }


def create_reassessment(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: CommercialReassessmentCreate,
) -> dict[str, object]:
    opportunity, assessment = _owned_context(db, owner, opportunity_id, assessment_id)
    promotion, response, extraction, review, supplier, product, term = _promotion_scope(
        db, owner, data.promotion_id, opportunity_id
    )
    if data.goal_id is not None:
        from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal

        goal = db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.id == data.goal_id, BusinessAgentGoal.owner_id == owner.id
            )
        )
        if goal is None:
            raise HTTPException(404, "Business goal is not available in the owner scope.")

    baseline_landed = None
    if data.baseline_landed_cost_id:
        baseline_landed = db.scalar(
            select(EconomicCalculation).where(
                EconomicCalculation.id == data.baseline_landed_cost_id,
                EconomicCalculation.owner_id == owner.id,
                EconomicCalculation.product_opportunity_id == opportunity_id,
                EconomicCalculation.assessment_id == assessment_id,
            )
        )
        if baseline_landed is None:
            raise HTTPException(
                404, "Baseline landed-cost calculation is not available in this context."
            )
    else:
        baseline_landed = db.scalar(
            select(EconomicCalculation)
            .where(
                EconomicCalculation.owner_id == owner.id,
                EconomicCalculation.product_opportunity_id == opportunity_id,
                EconomicCalculation.assessment_id == assessment_id,
            )
            .order_by(EconomicCalculation.created_at.asc())
        )
    baseline_economics = None
    if data.baseline_unit_economics_id:
        baseline_economics = db.scalar(
            select(ProductOpportunityUnitEconomics).where(
                ProductOpportunityUnitEconomics.id == data.baseline_unit_economics_id,
                ProductOpportunityUnitEconomics.owner_id == owner.id,
                ProductOpportunityUnitEconomics.opportunity_id == opportunity_id,
                ProductOpportunityUnitEconomics.assessment_id == assessment_id,
            )
        )
        if baseline_economics is None:
            raise HTTPException(404, "Baseline unit economics is not available in this context.")
    else:
        baseline_economics = db.scalar(
            select(ProductOpportunityUnitEconomics)
            .where(
                ProductOpportunityUnitEconomics.owner_id == owner.id,
                ProductOpportunityUnitEconomics.opportunity_id == opportunity_id,
                ProductOpportunityUnitEconomics.assessment_id == assessment_id,
            )
            .order_by(ProductOpportunityUnitEconomics.created_at.asc())
        )

    payload = {
        "promotion_id": str(promotion.id),
        "response_id": str(response.id),
        "extraction_id": str(extraction.id),
        "review_id": str(review.id),
        "commercial_term_id": str(term.id),
        "quote_version": term.version,
        "scenario_key": data.scenario_key,
        "assumptions": [item.model_dump(mode="json") for item in data.assumptions],
        "landed_cost": data.landed_cost.model_dump(mode="json") if data.landed_cost else None,
        "unit_economics": (
            data.unit_economics.model_dump(mode="json") if data.unit_economics else None
        ),
        "baseline_landed_cost_id": str(baseline_landed.id) if baseline_landed else None,
        "baseline_unit_economics_id": str(baseline_economics.id) if baseline_economics else None,
    }
    fingerprint = _fingerprint(payload)
    existing = db.scalar(
        select(CommercialReassessment).where(
            CommercialReassessment.owner_id == owner.id,
            CommercialReassessment.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        result = _row_view(db, owner, existing)
        result["idempotent_reuse"] = True
        return result
    by_key = db.scalar(
        select(CommercialReassessment).where(
            CommercialReassessment.owner_id == owner.id,
            CommercialReassessment.idempotency_key == data.idempotency_key,
        )
    )
    if by_key is not None:
        if by_key.input_fingerprint != fingerprint:
            raise HTTPException(
                409, "The idempotency key was already used for different reassessment inputs."
            )
        result = _row_view(db, owner, by_key)
        result["idempotent_reuse"] = True
        return result

    readiness, _ = project_readiness(
        db,
        owner,
        opportunity_id,
        assessment_id,
        CommercialReadinessCreate(
            idempotency_key=f"pr8a-readiness:{fingerprint}",
            supplier_id=supplier.id,
            supplier_product_id=product.id,
            scenario_key=data.scenario_key,
            assumptions=data.assumptions,
        ),
    )
    current_landed: dict[str, object] = {"status": "NOT_EVALUATED", "calculable": False}
    current_landed_row = None
    blockers: list[object] = []
    if data.landed_cost is not None:
        landed_payload = data.landed_cost.model_copy(
            update={"idempotency_key": f"pr8a-landed:{fingerprint}"}
        )
        landed_result = calculate_landed_cost(
            db, owner, opportunity_id, assessment_id, landed_payload
        )
        current_landed = _json(landed_result)
        calculation = landed_result.get("calculation")
        if isinstance(calculation, dict) and calculation.get("id"):
            current_landed_row = db.get(EconomicCalculation, uuid.UUID(str(calculation["id"])))
        if not landed_result.get("calculable"):
            missing_inputs = landed_result.get("missing_inputs")
            if isinstance(missing_inputs, list):
                blockers.extend(missing_inputs)
    else:
        blockers.append("landed_cost_request_required")
    current_economics: dict[str, object] = {"status": "NOT_EVALUATED", "calculable": False}
    current_economics_row = None
    if (
        data.unit_economics is not None
        and current_landed_row is not None
        and current_landed.get("calculable")
    ):
        unit_payload = data.unit_economics.model_copy(
            update={
                "idempotency_key": f"pr8a-unit:{fingerprint}",
                "landed_cost_calculation_id": current_landed_row.id,
                "commercial_readiness_snapshot_id": readiness.id,
                "supplier_id": supplier.id,
            }
        )
        current_economics = _json(
            calculate_unit_economics(db, owner, opportunity_id, assessment_id, unit_payload)
        )
        if current_economics.get("id"):
            current_economics_row = db.get(
                ProductOpportunityUnitEconomics, uuid.UUID(str(current_economics["id"]))
            )
    elif data.unit_economics is None:
        blockers.append("unit_economics_request_required")
    elif not current_landed.get("calculable"):
        blockers.append("landed_cost_not_calculable")

    baseline_readiness = (
        db.get(CommercialReadinessSnapshot, baseline_landed.commercial_readiness_snapshot_id)
        if baseline_landed and baseline_landed.commercial_readiness_snapshot_id
        else (
            db.get(CommercialReadinessSnapshot, baseline_economics.commercial_readiness_snapshot_id)
            if baseline_economics and baseline_economics.commercial_readiness_snapshot_id
            else None
        )
    )
    baseline_landed_view = _calculation_view(db, baseline_landed)
    baseline_economics_view = (
        latest_unit_economics(db, owner, opportunity_id, assessment_id)
        if baseline_economics is None
        else _json(
            {
                "id": str(baseline_economics.id),
                "status": baseline_economics.status,
                "calculable": baseline_economics.status == "READY",
                "quantity": baseline_economics.quantity,
                "per_unit_landed_cost": baseline_economics.per_unit_landed_cost,
                "per_unit_selling_cost": baseline_economics.per_unit_selling_cost,
                "per_unit_contribution": baseline_economics.per_unit_contribution,
                "contribution_margin": baseline_economics.contribution_margin,
                "capital_required": baseline_economics.capital_required,
                "capital_headroom": baseline_economics.capital_headroom,
            }
        )
    )
    if not isinstance(baseline_economics_view, dict):
        baseline_economics_view = {}
    quote_fields = dict(extraction.extracted_fields or {})
    quote_evidence = {
        "promotion_id": str(promotion.id),
        "response_id": str(response.id),
        "extraction_id": str(extraction.id),
        "review_id": str(review.id),
        "commercial_term_id": str(term.id),
        "version": term.version,
        "provenance": promotion.provenance,
        "claim_semantics": "SOURCE_PROVIDED_CLAIM",
        "trust_environment": response.trust_environment,
        "evidence_environment": response.evidence_environment,
        "fields": _json(quote_fields),
        "source_evidence_id": (
            str(promotion.supplier_evidence_id) if promotion.supplier_evidence_id else None
        ),
    }
    comparison = _comparison(
        baseline_readiness,
        baseline_landed_view,
        baseline_economics_view,
        readiness,
        current_landed,
        current_economics,
    )
    status = (
        "READY_FOR_HUMAN_REVIEW"
        if current_landed.get("calculable") and current_economics.get("calculable")
        else "BLOCKED"
    )
    row = CommercialReassessment(
        owner_id=owner.id,
        goal_id=data.goal_id,
        opportunity_id=opportunity_id,
        assessment_id=assessment_id,
        supplier_id=supplier.id,
        supplier_product_id=product.id,
        promotion_id=promotion.id,
        commercial_term_id=term.id,
        baseline_landed_cost_id=baseline_landed.id if baseline_landed else None,
        baseline_unit_economics_id=baseline_economics.id if baseline_economics else None,
        current_readiness_id=readiness.id,
        current_landed_cost_id=current_landed_row.id if current_landed_row else None,
        current_unit_economics_id=current_economics_row.id if current_economics_row else None,
        scenario_key=data.scenario_key,
        status=status,
        review_status="NEEDS_HUMAN_REVIEW",
        input_fingerprint=fingerprint,
        idempotency_key=data.idempotency_key,
        quote_version=term.version,
        quote_evidence=quote_evidence,
        assumptions=[item.model_dump(mode="json") for item in data.assumptions],
        baseline={
            "landed_cost": baseline_landed_view,
            "unit_economics": baseline_economics_view,
            "readiness_id": str(baseline_readiness.id) if baseline_readiness else None,
        },
        current={
            "readiness": _json(
                {
                    "id": str(readiness.id),
                    "status": readiness.readiness,
                    "missing_inputs": readiness.missing_inputs,
                    "unknown_inputs": readiness.unknown_inputs,
                    "contradictions": readiness.contradictions,
                }
            ),
            "landed_cost": current_landed,
            "unit_economics": current_economics,
        },
        comparison=comparison,
        blockers=[str(item) for item in blockers],
        provenance={
            "quote": "SOURCE_PROVIDED_CLAIM",
            "human_extraction_review": "HUMAN",
            "calculations": "VAYUJIT_CANONICAL_PR5A_PR5B_PR5C",
            "supplier_verification": supplier.verification_state,
        },
        lineage={
            "promotion_id": str(promotion.id),
            "response_id": str(response.id),
            "extraction_id": str(extraction.id),
            "review_id": str(review.id),
            "commercial_term_id": str(term.id),
            "supplier_id": str(supplier.id),
            "supplier_product_id": str(product.id),
            "opportunity_id": str(opportunity_id),
            "assessment_id": str(assessment_id),
        },
        notes=(
            "PR-8A reassessment is comparison-only; no supplier approval, order, "
            "payment, or external write was performed."
        ),
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.commercial_reassessment_created",
        entity_type="commercial_reassessment",
        entity_id=row.id,
        metadata={
            "opportunity_id": str(opportunity_id),
            "supplier_id": str(supplier.id),
            "status": status,
        },
        idempotency_key=f"pr8a:reassessment:{row.id}",
    )
    db.commit()
    db.refresh(row)
    result = _row_view(db, owner, row)
    result["idempotent_reuse"] = False
    return result


def get_reassessment(db: Session, owner: User, reassessment_id: uuid.UUID) -> dict[str, object]:
    row = db.scalar(
        select(CommercialReassessment).where(
            CommercialReassessment.id == reassessment_id,
            CommercialReassessment.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Commercial reassessment not found.")
    return _row_view(db, owner, row)


def list_reassessments(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(CommercialReassessment)
            .where(
                CommercialReassessment.owner_id == owner.id,
                CommercialReassessment.opportunity_id == opportunity_id,
                CommercialReassessment.assessment_id == assessment_id,
            )
            .order_by(CommercialReassessment.created_at.desc())
        )
    )
    return [_row_view(db, owner, row) for row in rows]


def review_reassessment(
    db: Session, owner: User, reassessment_id: uuid.UUID, data: CommercialReassessmentReviewCreate
) -> dict[str, object]:
    row = db.scalar(
        select(CommercialReassessment).where(
            CommercialReassessment.id == reassessment_id,
            CommercialReassessment.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Commercial reassessment not found.")
    existing = db.scalar(
        select(CommercialReassessmentReview).where(
            CommercialReassessmentReview.owner_id == owner.id,
            CommercialReassessmentReview.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        result = _row_view(db, owner, row)
        result["idempotent_reuse"] = True
        return result
    review = CommercialReassessmentReview(
        owner_id=owner.id,
        reassessment_id=row.id,
        actor_id=owner.id,
        decision=data.decision,
        provenance="HUMAN",
        reason=data.reason,
        idempotency_key=data.idempotency_key,
    )
    db.add(review)
    row.review_status = data.decision
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.commercial_reassessment_reviewed",
        entity_type="commercial_reassessment",
        entity_id=row.id,
        metadata={"decision": data.decision, "provenance": "HUMAN"},
        idempotency_key=f"pr8a:review:{review.id}",
    )
    db.commit()
    db.refresh(row)
    return _row_view(db, owner, row)
