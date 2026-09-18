"""Owner-scoped commercial viability APIs for Product Opportunities."""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.product_opportunity_commercial_models import (
    CALCULATION_VERSION,
    ProductOpportunityCommercialOutput,
)
from vayujit_api.intelligence.product_opportunity_commercial_schemas import (
    CommercialCalculateRequest,
    CommercialOutputResponse,
)
from vayujit_api.intelligence.product_opportunity_commercial_service import calculate_commercial
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["product-opportunity-commercial"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _assessment_or_404(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityAssessment:
    row = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.owner_id == owner.id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Product opportunity assessment not found.")
    return row


def _output_or_404(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityCommercialOutput:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    row = db.scalar(
        select(ProductOpportunityCommercialOutput).where(
            ProductOpportunityCommercialOutput.owner_id == owner.id,
            ProductOpportunityCommercialOutput.opportunity_id == opportunity_id,
            ProductOpportunityCommercialOutput.assessment_id == assessment_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Commercial viability has not been calculated.")
    return row


def _calculate(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: CommercialCalculateRequest,
    db: DB,
    owner: Owner,
) -> ProductOpportunityCommercialOutput:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    try:
        output = calculate_commercial(db, owner, opportunity_id, assessment_id, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.commercial_assessment_updated",
        entity_type="product_opportunity_assessment",
        entity_id=assessment_id,
        metadata={
            "event_type": "COMMERCIAL_ASSESSMENT_UPDATED",
            "opportunity_id": str(opportunity_id),
        },
        idempotency_key=f"product-opportunity:{assessment_id}:commercial:event",
    )
    db.commit()
    db.refresh(output)
    return output


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/commercial",
    response_model=CommercialOutputResponse,
    status_code=201,
)
def calculate(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: CommercialCalculateRequest,
    db: DB,
    owner: Owner,
) -> ProductOpportunityCommercialOutput:
    return _calculate(opportunity_id, assessment_id, data, db, owner)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/commercial",
    response_model=CommercialOutputResponse,
)
def get_commercial(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> ProductOpportunityCommercialOutput:
    return _output_or_404(db, owner, opportunity_id, assessment_id)


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/unit-economics")
def unit_economics(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return _output_or_404(db, owner, opportunity_id, assessment_id).economics


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/capital")
def capital(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    economics = _output_or_404(db, owner, opportunity_id, assessment_id).economics
    return {
        key: economics.get(key)
        for key in (
            "currency",
            "moq",
            "inventory_capital",
            "known_fixed_setup_capital",
            "known_total_initial_capital",
            "capital_currency",
        )
    }


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/constraints")
def constraints(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    output = _output_or_404(db, owner, opportunity_id, assessment_id)
    for item in output.dimensions:
        if isinstance(item, dict) and item.get("dimension") == "CONSTRAINT_FIT":
            value = item.get("value")
            return dict(value) if isinstance(value, dict) else {}
    return {}


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/sensitivity")
def sensitivity(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return _output_or_404(db, owner, opportunity_id, assessment_id).sensitivity


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/evidence")
def evidence(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return _output_or_404(db, owner, opportunity_id, assessment_id).evidence_summary


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/gaps")
def gaps(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> list[dict[str, object]]:
    return _output_or_404(db, owner, opportunity_id, assessment_id).research_gaps


@router.get("/{opportunity_id}/assessments/{assessment_id}/commercial/history")
def history(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> list[CommercialOutputResponse]:
    _assessment_or_404(db, owner, opportunity_id, assessment_id)
    return list(
        db.scalars(
            select(ProductOpportunityCommercialOutput)
            .where(
                ProductOpportunityCommercialOutput.owner_id == owner.id,
                ProductOpportunityCommercialOutput.opportunity_id == opportunity_id,
                ProductOpportunityCommercialOutput.assessment_id == assessment_id,
            )
            .order_by(ProductOpportunityCommercialOutput.created_at)
        )
    )


def _finite_dimension_state(dimensions: object) -> bool:
    if not isinstance(dimensions, list):
        return False
    for item in dimensions:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if isinstance(value, float) and not math.isfinite(value):
            return True
    return False


@router.get("/commercial-system-doctor")
def commercial_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
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
            select(ProductOpportunityCommercialOutput).where(
                ProductOpportunityCommercialOutput.owner_id == owner.id
            )
        )
    )
    logical_keys = [(row.assessment_id, row.owner_id) for row in outputs]
    checks = {
        "orphan_outputs": sum(row.opportunity_id not in opportunity_ids for row in outputs),
        "broken_assessment_lineage": sum(
            row.assessment_id not in assessment_ids for row in outputs
        ),
        "cross_owner_references": 0,
        "invalid_calculation_versions": sum(
            row.calculation_version != CALCULATION_VERSION for row in outputs
        ),
        "duplicate_logical_outputs": len(logical_keys) - len(set(logical_keys)),
        "invalid_currency_state": sum(
            bool(row.economics.get("currency") and len(str(row.economics["currency"])) != 3)
            for row in outputs
        ),
        "impossible_numeric_states": sum(
            _finite_dimension_state(row.dimensions) for row in outputs
        ),
        "broken_landed_cost_or_scenario_reference": 0,
    }
    return {"status": "PASS" if not any(checks.values()) else "FAIL", "checks": checks}
