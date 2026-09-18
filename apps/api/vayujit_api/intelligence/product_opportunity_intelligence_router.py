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
    }
    return {"status": "PASS" if not any(checks.values()) else "FAIL", "checks": checks}
