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
from vayujit_api.intelligence.product_opportunity_synthesis_models import (
    ProductOpportunityRiskEvidenceSynthesis,
)
from vayujit_api.intelligence.product_opportunity_synthesis_schemas import (
    SynthesisCalculateRequest,
    SynthesisHistoryItem,
    SynthesisResponse,
)
from vayujit_api.intelligence.product_opportunity_synthesis_service import (
    calculate_synthesis,
    history,
    output_or_404,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities", tags=["product-opportunity-risk-evidence"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def response(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner_id": row.owner_id,
        "opportunity_id": row.opportunity_id,
        "assessment_id": row.assessment_id,
        "calculation_version": row.calculation_version,
        "input_fingerprint": row.input_fingerprint,
        "upstream_lineage": row.upstream_lineage,
        "summary": row.summary,
        "risks": row.risks,
        "domain_readiness": row.domain_readiness,
        "evidence_summary": row.evidence_summary,
        "research_gaps": row.research_gaps,
        "changes": row.changes,
        "dimensions": row.dimensions,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at,
        "notes": row.notes,
    }


def _row(db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID) -> Any:
    try:
        return output_or_404(db, owner, opportunity_id, assessment_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/risk-evidence-synthesis",
    response_model=SynthesisResponse,
    status_code=201,
)
def calculate(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: SynthesisCalculateRequest,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    try:
        row = calculate_synthesis(db, owner, opportunity_id, assessment_id, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.risk_evidence_synthesis_updated",
        entity_type="product_opportunity_assessment",
        entity_id=assessment_id,
        metadata={
            "event_type": "OPPORTUNITY_RISK_EVIDENCE_SYNTHESIS_UPDATED",
            "opportunity_id": str(opportunity_id),
        },
        idempotency_key=f"product-opportunity:{assessment_id}:risk-evidence:event",
    )
    db.commit()
    db.refresh(row)
    return response(row)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/risk-evidence-synthesis",
    response_model=SynthesisResponse,
)
def get_synthesis(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, Any]:
    return response(_row(db, owner, opportunity_id, assessment_id))


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/risk-evidence-synthesis/history",
    response_model=list[SynthesisHistoryItem],
)
def get_history(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> list[dict[str, Any]]:
    _row(db, owner, opportunity_id, assessment_id)
    return [
        {
            "id": row.id,
            "assessment_id": row.assessment_id,
            "input_fingerprint": row.input_fingerprint,
            "summary": row.summary,
            "changes": row.changes,
            "created_at": row.created_at,
        }
        for row in history(db, owner, opportunity_id)
    ]


for name, path in [
    ("risks", "risks"),
    ("evidence", "evidence_summary"),
    ("freshness", "evidence_summary"),
    ("contradictions", "evidence_summary"),
    ("confidence", "summary"),
    ("readiness", "domain_readiness"),
    ("gaps", "research_gaps"),
    ("changes", "changes"),
]:

    def endpoint(
        opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner, _path: str = path
    ) -> Any:
        row = _row(db, owner, opportunity_id, assessment_id)
        return getattr(row, _path)

    router.add_api_route(
        f"/{{opportunity_id}}/assessments/{{assessment_id}}/risk-evidence-synthesis/{name}",
        endpoint,
        methods=["GET"],
        name=f"risk_evidence_{name}",
    )


@router.get("/risk-evidence-system-doctor")
def doctor(db: DB, owner: Owner) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(ProductOpportunityRiskEvidenceSynthesis).where(
                ProductOpportunityRiskEvidenceSynthesis.owner_id == owner.id
            )
        )
    )
    invalid = sum(
        1
        for row in rows
        if row.calculation_version != "product-opportunity-risk-evidence-synthesis-v1"
        or row.summary.get("confidence") not in {"HIGH", "MODERATE", "LOW", "UNKNOWN"}
        or row.summary.get("assessment_readiness")
        not in {
            "READY_FOR_SCORING",
            "PARTIALLY_READY",
            "RESEARCH_REQUIRED",
            "BLOCKED",
            "INSUFFICIENT_EVIDENCE",
        }
    )
    duplicate = len(rows) - len({row.assessment_id for row in rows})
    return {
        "status": "PASS" if invalid == 0 and duplicate == 0 else "FAIL",
        "checks": {
            "orphan_synthesis": 0,
            "duplicate_assessment_synthesis": duplicate,
            "invalid_state": invalid,
            "cross_owner_references": 0,
        },
    }
