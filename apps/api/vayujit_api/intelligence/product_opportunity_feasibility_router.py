"""Assessment-bound supplier and sourcing feasibility APIs."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.due_diligence_schemas import DueDiligenceContextCreate
from vayujit_api.intelligence.due_diligence_service import create_context
from vayujit_api.intelligence.product_opportunity_feasibility_schemas import (
    FeasibilityCalculateRequest,
    FeasibilityHandoffRequest,
    FeasibilityHistoryItem,
    FeasibilityOutputResponse,
)
from vayujit_api.intelligence.product_opportunity_feasibility_service import (
    calculate_feasibility,
    doctor,
    output_or_404,
)
from vayujit_api.intelligence.product_opportunity_feasibility_service import (
    history as feasibility_history,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["product-opportunity-sourcing-feasibility"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _response(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner_id": row.owner_id,
        "opportunity_id": row.opportunity_id,
        "assessment_id": row.assessment_id,
        "calculation_version": row.calculation_version,
        "constraint_snapshot": row.constraint_snapshot,
        "upstream_lineage": row.upstream_lineage,
        "summary": row.summary,
        "candidates": row.candidates,
        "dimensions": row.dimensions,
        "evidence_summary": row.evidence_summary,
        "research_gaps": row.research_gaps,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at,
        "notes": row.notes,
    }


def _row(db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID) -> Any:
    try:
        return output_or_404(db, owner, opportunity_id, assessment_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility/handoff")
def handoff(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: FeasibilityHandoffRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    output = _row(db, owner, opportunity_id, assessment_id)
    if not data.confirm:
        raise HTTPException(422, "Confirm the internal due-diligence handoff.")
    candidate = next(
        (
            item
            for item in output.candidates
            if item.get("matched_product", {}).get("id") == str(data.supplier_product_id)
        ),
        None,
    )
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id,
            ProductOpportunity.owner_id == owner.id,
        )
    )
    if (
        candidate is None
        or not candidate.get("canonical_supplier_id")
        or opportunity is None
        or opportunity.product_id is None
    ):
        raise HTTPException(404, "Supplier due-diligence handoff unavailable.")
    context, reused = create_context(
        db,
        owner,
        DueDiligenceContextCreate(
            supplier_id=uuid.UUID(candidate["canonical_supplier_id"]),
            product_id=opportunity.product_id,
            idempotency_key=f"9d-handoff:{assessment_id}:{candidate['canonical_supplier_id']}",
        ),
    )
    return {
        "context_id": str(context.id),
        "state": context.status,
        "reused": reused,
        "external_work_started": False,
    }


@router.get("/sourcing-feasibility-system-doctor")
def sourcing_feasibility_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    checks = doctor(db, owner)
    return {"status": "PASS" if not any(checks.values()) else "FAIL", "checks": checks}


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility",
    response_model=FeasibilityOutputResponse,
    status_code=201,
)
def calculate(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: FeasibilityCalculateRequest,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    try:
        output = calculate_feasibility(db, owner, opportunity_id, assessment_id, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.sourcing_feasibility_updated",
        entity_type="product_opportunity_assessment",
        entity_id=assessment_id,
        metadata={
            "event_type": "SOURCING_FEASIBILITY_UPDATED",
            "opportunity_id": str(opportunity_id),
            "output_id": str(output.id),
        },
        idempotency_key=f"product-opportunity:{assessment_id}:sourcing-feasibility:event",
    )
    db.commit()
    db.refresh(output)
    return _response(output)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility",
    response_model=FeasibilityOutputResponse,
)
def get_feasibility(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, Any]:
    return _response(_row(db, owner, opportunity_id, assessment_id))


def _section(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    section: str,
    db: DB,
    owner: Owner,
) -> Any:
    row = _row(db, owner, opportunity_id, assessment_id)
    if section == "history":
        return [
            {
                "id": item.id,
                "assessment_id": item.assessment_id,
                "calculation_version": item.calculation_version,
                "created_at": item.created_at,
                "summary": item.summary,
            }
            for item in feasibility_history(db, owner, opportunity_id)
        ]
    if section == "concentration":
        return row.upstream_lineage.get("portfolio", {})
    if section == "suppliers":
        return {
            "summary": row.summary.get("supplier_availability", {}),
            "candidates": row.candidates,
        }
    if section == "shortlist":
        return [candidate.get("shortlist", {}) for candidate in row.candidates]
    if section == "due-diligence":
        return {
            "summary": row.summary.get("supplier_availability", {}),
            "candidates": [candidate.get("due_diligence", {}) for candidate in row.candidates],
        }
    if section == "commercial":
        return next(
            (
                item.get("value")
                for item in row.dimensions
                if item.get("dimension") == "COMMERCIAL_FIT"
            ),
            None,
        )
    if section == "scenarios":
        return next(
            (
                item.get("value")
                for item in row.dimensions
                if item.get("dimension") == "SOURCING_SCENARIO_STRENGTH"
            ),
            {},
        )
    if section == "alternatives":
        return next(
            (
                item.get("value")
                for item in row.dimensions
                if item.get("dimension") == "QUALIFIED_ALTERNATIVE_COVERAGE"
            ),
            0,
        )
    if section == "resilience":
        return next(
            (
                item.get("value")
                for item in row.dimensions
                if item.get("dimension") == "SOURCING_RESILIENCE"
            ),
            "UNKNOWN",
        )
    if section == "evidence":
        return row.evidence_summary
    return row.research_gaps


for _section_name in (
    "suppliers",
    "shortlist",
    "due-diligence",
    "commercial",
    "scenarios",
    "alternatives",
    "resilience",
    "concentration",
    "evidence",
    "gaps",
):

    def _endpoint(
        opportunity_id: uuid.UUID,
        assessment_id: uuid.UUID,
        db: DB,
        owner: Owner,
        _name: str = _section_name,
    ) -> Any:
        return _section(opportunity_id, assessment_id, _name, db, owner)

    router.add_api_route(
        "/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility/" + _section_name,
        _endpoint,
        methods=["GET"],
        name="sourcing_feasibility_" + _section_name,
    )


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility/history",
    response_model=list[FeasibilityHistoryItem],
)
def history(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> list[dict[str, Any]]:
    _row(db, owner, opportunity_id, assessment_id)
    return [
        {
            "id": row.id,
            "assessment_id": row.assessment_id,
            "calculation_version": row.calculation_version,
            "created_at": row.created_at,
            "summary": row.summary,
        }
        for row in feasibility_history(db, owner, opportunity_id)
    ]
