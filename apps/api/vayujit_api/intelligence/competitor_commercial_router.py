"""Authenticated API for immutable competitor commercial analysis (Slice 10C)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.competitor_commercial_models import CompetitorCommercialAnalysis
from vayujit_api.intelligence.competitor_commercial_schemas import (
    AnalysisListResponse,
    CohortEntryResponse,
    CommercialAnalysisCreate,
    CommercialAnalysisResponse,
)
from vayujit_api.intelligence.competitor_commercial_service import (
    cohort_entries,
    current_analysis,
    get_analysis,
    integrity_report,
    list_analyses,
    run_analysis,
)
from vayujit_api.intelligence.competitor_service import get_context

router = APIRouter(
    prefix="/api/v1/intelligence/competitors/commercial-analysis",
    tags=["competitor-commercial-analysis"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/contexts/{context_id}/analyses",
    response_model=CommercialAnalysisResponse,
    status_code=201,
)
def analysis_create(
    context_id: uuid.UUID, data: CommercialAnalysisCreate, db: DB, owner: Owner
) -> CompetitorCommercialAnalysis:
    return run_analysis(db, owner, context_id, data)


@router.post(
    "/contexts/{context_id}/analyses/run",
    response_model=CommercialAnalysisResponse,
    status_code=201,
)
def analysis_run(
    context_id: uuid.UUID, data: CommercialAnalysisCreate, db: DB, owner: Owner
) -> CompetitorCommercialAnalysis:
    return run_analysis(db, owner, context_id, data)


@router.get(
    "/contexts/{context_id}/analyses/current",
    response_model=CommercialAnalysisResponse | None,
)
def analysis_current(
    context_id: uuid.UUID, db: DB, owner: Owner
) -> CompetitorCommercialAnalysis | None:
    get_context(db, owner, context_id)
    return current_analysis(db, owner, context_id)


@router.get("/contexts/{context_id}/analyses", response_model=AnalysisListResponse)
def analysis_history(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AnalysisListResponse:
    get_context(db, owner, context_id)
    items, total = list_analyses(db, owner, context_id, limit, offset)
    return AnalysisListResponse(
        items=[CommercialAnalysisResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/analyses/{analysis_id}", response_model=CommercialAnalysisResponse)
def analysis_get(analysis_id: uuid.UUID, db: DB, owner: Owner) -> CompetitorCommercialAnalysis:
    return get_analysis(db, owner, analysis_id)


@router.get("/analyses/{analysis_id}/cohort", response_model=list[CohortEntryResponse])
def analysis_cohort(
    analysis_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list:
    return cohort_entries(db, owner, analysis_id, limit, offset)


def _section(
    analysis_id: uuid.UUID, section: str, db: Session, owner: User
) -> dict[str, object] | list[dict[str, object]]:
    analysis = get_analysis(db, owner, analysis_id)
    value = getattr(analysis, section)
    return value


@router.get("/analyses/{analysis_id}/pricing")
def analysis_pricing(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "pricing_analysis", db, owner)


@router.get("/analyses/{analysis_id}/concentration")
def analysis_concentration(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "concentration_analysis", db, owner)


@router.get("/analyses/{analysis_id}/ratings")
def analysis_ratings(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "rating_analysis", db, owner)


@router.get("/analyses/{analysis_id}/reviews")
def analysis_reviews(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "review_analysis", db, owner)


@router.get("/analyses/{analysis_id}/assortment")
def analysis_assortment(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "assortment_analysis", db, owner)


@router.get("/analyses/{analysis_id}/positioning")
def analysis_positioning(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "positioning_analysis", db, owner)


@router.get("/analyses/{analysis_id}/differentiation")
def analysis_differentiation(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "differentiation_analysis", db, owner)


@router.get("/analyses/{analysis_id}/gaps")
def analysis_gaps(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "competitive_gaps", db, owner)


@router.get("/analyses/{analysis_id}/research-gaps")
def analysis_research_gaps(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "research_gaps", db, owner)


@router.get("/analyses/{analysis_id}/evidence")
def analysis_evidence(analysis_id: uuid.UUID, db: DB, owner: Owner) -> object:
    return _section(analysis_id, "evidence_coverage", db, owner)


@router.get("/system-doctor")
def commercial_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return integrity_report(db, owner)
