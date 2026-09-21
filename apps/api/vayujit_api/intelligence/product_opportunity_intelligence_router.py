"""Owner-scoped demand and competition intelligence APIs."""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.competitor_change_models import (
    CALCULATION_VERSION as TEN_D_CALCULATION_VERSION,
)
from vayujit_api.intelligence.competitor_change_models import (
    CompetitorChangeComparison,
)
from vayujit_api.intelligence.competitor_commercial_models import (
    CALCULATION_VERSION as TEN_C_CALCULATION_VERSION,
)
from vayujit_api.intelligence.competitor_commercial_models import (
    CompetitorCommercialAnalysis,
)
from vayujit_api.intelligence.competitor_models import CompetitorContext
from vayujit_api.intelligence.competitor_winning_product_models import (
    CompetitorWinningProductProjection,
)
from vayujit_api.intelligence.competitor_winning_product_schemas import (
    CompetitorWinningProductProjectionResponse,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    ProductOpportunityIntelligenceOutput,
)
from vayujit_api.intelligence.product_opportunity_intelligence_schemas import (
    IntelligenceCalculateRequest,
    IntelligenceOutputResponse,
)
from vayujit_api.intelligence.product_opportunity_intelligence_service import (
    calculate_intelligence,
)
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.review_winning_product_models import ReviewWinningProductProjection
from vayujit_api.intelligence.review_winning_product_schemas import (
    ReviewWinningProductProjectionResponse,
)
from vayujit_api.intelligence.review_winning_product_service import (
    current_projection,
    get_or_create_projection,
)
from vayujit_api.intelligence.review_winning_product_service import (
    integrity_report as review_projection_integrity_report,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities", tags=["product-opportunity-intelligence"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]
Kind = Literal["demand", "competition"]


def _assessment_or_404(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityAssessment:
    value = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Product opportunity assessment not found.")
    return value


def _output_or_404(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID, kind: Kind
) -> ProductOpportunityIntelligenceOutput:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    value = db.scalar(
        select(ProductOpportunityIntelligenceOutput).where(
            ProductOpportunityIntelligenceOutput.owner_id == owner.id,
            ProductOpportunityIntelligenceOutput.opportunity_id == opportunity_id,
            ProductOpportunityIntelligenceOutput.assessment_id == assessment_id,
            ProductOpportunityIntelligenceOutput.kind == kind,
        )
    )
    if value is None:
        raise HTTPException(404, f"{kind.title()} intelligence has not been calculated.")
    return value


def _calculate(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    kind: Kind,
    data: IntelligenceCalculateRequest,
    db: DB,
    owner: Owner,
) -> ProductOpportunityIntelligenceOutput:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    try:
        output = calculate_intelligence(
            db, owner, opportunity_id, assessment_id, kind, data.idempotency_key
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.{kind}_assessment_updated",
        entity_type="product_opportunity_assessment",
        entity_id=assessment_id,
        metadata={
            "event_type": f"{kind.upper()}_ASSESSMENT_UPDATED",
            "opportunity_id": str(opportunity_id),
        },
        idempotency_key=f"product-opportunity:{assessment_id}:{kind}:event",
    )
    db.commit()
    db.refresh(output)
    return output


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/demand",
    response_model=IntelligenceOutputResponse,
    status_code=201,
)
def calculate_demand(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: IntelligenceCalculateRequest,
    db: DB,
    owner: Owner,
) -> ProductOpportunityIntelligenceOutput:
    return _calculate(opportunity_id, assessment_id, "demand", data, db, owner)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/demand",
    response_model=IntelligenceOutputResponse,
)
def get_demand(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> ProductOpportunityIntelligenceOutput:
    return _output_or_404(db, owner, opportunity_id, assessment_id, "demand")


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/competition",
    response_model=IntelligenceOutputResponse,
    status_code=201,
)
def calculate_competition(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: IntelligenceCalculateRequest,
    db: DB,
    owner: Owner,
) -> ProductOpportunityIntelligenceOutput:
    return _calculate(opportunity_id, assessment_id, "competition", data, db, owner)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/competition",
    response_model=IntelligenceOutputResponse,
)
def get_competition(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> ProductOpportunityIntelligenceOutput:
    return _output_or_404(db, owner, opportunity_id, assessment_id, "competition")


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/competition-projection",
    response_model=CompetitorWinningProductProjectionResponse,
)
def get_competition_projection(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> CompetitorWinningProductProjection:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    value = db.scalar(
        select(CompetitorWinningProductProjection)
        .where(
            CompetitorWinningProductProjection.owner_id == owner.id,
            CompetitorWinningProductProjection.opportunity_id == opportunity_id,
            CompetitorWinningProductProjection.assessment_id == assessment_id,
        )
        .order_by(CompetitorWinningProductProjection.created_at.desc())
    )
    if value is None:
        raise HTTPException(404, "Competition projection has not been calculated.")
    return value


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/review-projection",
    response_model=ReviewWinningProductProjectionResponse,
)
def get_review_projection(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewWinningProductProjection:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    value = current_projection(db, owner, opportunity_id, assessment_id)
    if value is None:
        raise HTTPException(404, "Review projection has not been calculated.")
    return value


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/review-projection",
    response_model=ReviewWinningProductProjectionResponse,
    status_code=201,
)
def create_review_projection(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewWinningProductProjection:
    assessment = _assessment_or_404(db, owner, opportunity_id, assessment_id)
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    if opportunity is None:
        raise HTTPException(404, "Product opportunity not found.")
    value = get_or_create_projection(db, owner, opportunity, assessment)
    db.commit()
    db.refresh(value)
    return value


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/intelligence",
    response_model=list[IntelligenceOutputResponse],
)
def list_intelligence(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> list[ProductOpportunityIntelligenceOutput]:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    return list(
        db.scalars(
            select(ProductOpportunityIntelligenceOutput)
            .where(
                ProductOpportunityIntelligenceOutput.owner_id == owner.id,
                ProductOpportunityIntelligenceOutput.opportunity_id == opportunity_id,
                ProductOpportunityIntelligenceOutput.assessment_id == assessment_id,
            )
            .order_by(ProductOpportunityIntelligenceOutput.kind)
        )
    )


def _has_impossible_numeric_state(dimensions: object) -> bool:
    if not isinstance(dimensions, list):
        return False
    for item in dimensions:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if isinstance(value, float) and not math.isfinite(value):
            return True
    return False


@router.get("/review-projection-system-doctor")
def review_projection_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return review_projection_integrity_report(db, owner)


@router.get("/intelligence-system-doctor")
def intelligence_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    opportunity_ids = set(
        db.scalars(select(ProductOpportunity.id).where(ProductOpportunity.owner_id == owner.id))
    )
    assessment_ids = set(
        db.scalars(
            select(ProductOpportunityAssessment.id).where(
                ProductOpportunityAssessment.owner_id == owner.id
            )
        )
    )
    outputs = list(
        db.scalars(
            select(ProductOpportunityIntelligenceOutput).where(
                ProductOpportunityIntelligenceOutput.owner_id == owner.id
            )
        )
    )
    projections = list(
        db.scalars(
            select(CompetitorWinningProductProjection).where(
                CompetitorWinningProductProjection.owner_id == owner.id
            )
        )
    )
    context_ids = set(
        db.scalars(select(CompetitorContext.id).where(CompetitorContext.owner_id == owner.id))
    )
    analysis_ids = set(
        db.scalars(
            select(CompetitorCommercialAnalysis.id).where(
                CompetitorCommercialAnalysis.owner_id == owner.id
            )
        )
    )
    comparison_ids = set(
        db.scalars(
            select(CompetitorChangeComparison.id).where(
                CompetitorChangeComparison.owner_id == owner.id
            )
        )
    )
    projections_by_id = {str(row.id): row for row in projections}
    dedicated_outputs_without_lineage = 0
    for output in outputs:
        if not isinstance(output.input_snapshot, dict):
            continue
        if output.input_snapshot.get("competition_source") != "DEDICATED_COMPETITOR_INTELLIGENCE":
            continue
        projection_id = output.input_snapshot.get("competition_projection_id")
        projection = projections_by_id.get(str(projection_id))
        if (
            projection is None
            or projection.opportunity_id != output.opportunity_id
            or projection.assessment_id != output.assessment_id
            or projection.competitor_analysis_id not in analysis_ids
        ):
            dedicated_outputs_without_lineage += 1

    def _projection_payload(row: CompetitorWinningProductProjection) -> dict[str, object]:
        return row.projection if isinstance(row.projection, dict) else {}

    def _analysis_payload(row: CompetitorWinningProductProjection) -> dict[str, object]:
        value = _projection_payload(row).get("analysis")
        return value if isinstance(value, dict) else {}

    def _cohort_payload(row: CompetitorWinningProductProjection) -> dict[str, object]:
        value = _projection_payload(row).get("cohort")
        return value if isinstance(value, dict) else {}

    mixed_currency_comparable = 0
    ambiguous_or_rejected_counted = 0
    stale_marked_current = 0
    for row in projections:
        cohort = _cohort_payload(row)
        confirmed = cohort.get("confirmed_count")
        probable = cohort.get("probable_count")
        authoritative = cohort.get("authoritative_count")
        if (
            isinstance(confirmed, int)
            and isinstance(probable, int)
            and authoritative != confirmed + probable
        ):
            ambiguous_or_rejected_counted += 1
        pricing = _analysis_payload(row).get("pricing")
        currencies = pricing.get("currencies") if isinstance(pricing, dict) else None
        if (
            isinstance(currencies, dict)
            and len(currencies) > 1
            and isinstance(pricing, dict)
            and pricing.get("status") != "MULTI_CURRENCY_NOT_COMPARABLE"
        ):
            mixed_currency_comparable += 1
        freshness = row.evidence_summary.get("freshness") if row.evidence_summary else None
        if row.freshness_state == "CURRENT" and freshness not in (None, "CURRENT"):
            stale_marked_current += 1
    duplicate_projection_keys = len(projections) - len(
        {(row.opportunity_id, row.assessment_id, row.input_fingerprint) for row in projections}
    )
    checks = {
        "orphan_outputs": sum(row.opportunity_id not in opportunity_ids for row in outputs),
        "broken_assessment_lineage": sum(
            row.assessment_id not in assessment_ids for row in outputs
        ),
        "cross_owner_references": 0,
        "invalid_calculation_versions": sum(
            row.calculation_version != "product-opportunity-intelligence-v1" for row in outputs
        ),
        "duplicate_logical_outputs": 0,
        "impossible_numeric_states": sum(
            _has_impossible_numeric_state(row.dimensions) for row in outputs
        ),
        "orphan_competitor_projections": sum(
            row.opportunity_id not in opportunity_ids for row in projections
        ),
        "broken_projection_assessments": sum(
            row.assessment_id not in assessment_ids for row in projections
        ),
        "broken_projection_contexts": sum(
            row.context_id is not None and row.context_id not in context_ids for row in projections
        ),
        "duplicate_competitor_projections": duplicate_projection_keys,
        "dedicated_projection_missing_analysis": sum(
            row.source_state == "DEDICATED_COMPETITOR_INTELLIGENCE"
            and row.competitor_analysis_id is None
            for row in projections
        ),
        "broken_projection_analyses": sum(
            row.competitor_analysis_id is not None
            and row.competitor_analysis_id not in analysis_ids
            for row in projections
        ),
        "broken_projection_comparisons": sum(
            row.change_comparison_id is not None and row.change_comparison_id not in comparison_ids
            for row in projections
        ),
        "incompatible_projection_versions": sum(
            row.source_state == "DEDICATED_COMPETITOR_INTELLIGENCE"
            and (
                row.ten_c_calculation_version != TEN_C_CALCULATION_VERSION
                or (
                    row.ten_d_calculation_version is not None
                    and row.ten_d_calculation_version != TEN_D_CALCULATION_VERSION
                )
            )
            for row in projections
        ),
        "stale_projection_marked_current": stale_marked_current,
        "ambiguous_or_rejected_competitors_counted": ambiguous_or_rejected_counted,
        "mixed_currency_treated_comparable": mixed_currency_comparable,
        "dedicated_output_missing_projection_lineage": dedicated_outputs_without_lineage,
    }
    return {"status": "PASS" if not any(checks.values()) else "FAIL", "checks": checks}
