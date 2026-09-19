"""Authenticated API for Slice 10D competitive change intelligence."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.competitor_change_models import (
    CompetitorChangeComparison,
    CompetitorChangeEvent,
)
from vayujit_api.intelligence.competitor_change_schemas import (
    ChangeComparisonCreate,
    ChangeComparisonResponse,
    ChangeComparisonResult,
    ChangeEventResponse,
    ChangeListResponse,
    ChangeReviewRequest,
)
from vayujit_api.intelligence.competitor_change_service import (
    current_events,
    get_comparison,
    get_event,
    history,
    integrity_report,
    list_events,
    review_event,
    run_comparison,
)
from vayujit_api.intelligence.competitor_service import get_context

router = APIRouter(
    prefix="/api/v1/intelligence/competitors/change-intelligence",
    tags=["competitor-change-intelligence"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _events(db: Session, owner: User, comparison_id: uuid.UUID) -> list[CompetitorChangeEvent]:
    return list(
        db.scalars(
            select(CompetitorChangeEvent)
            .where(
                CompetitorChangeEvent.owner_id == owner.id,
                CompetitorChangeEvent.comparison_id == comparison_id,
            )
            .order_by(CompetitorChangeEvent.created_at.asc())
        )
    )


@router.post(
    "/contexts/{context_id}/comparisons", response_model=ChangeComparisonResult, status_code=201
)
def comparison_create(
    context_id: uuid.UUID, data: ChangeComparisonCreate, db: DB, owner: Owner
) -> ChangeComparisonResult:
    get_context(db, owner, context_id)
    comparison = run_comparison(db, owner, context_id, data)
    return ChangeComparisonResult(
        comparison=ChangeComparisonResponse.model_validate(comparison),
        events=[
            ChangeEventResponse.model_validate(item) for item in _events(db, owner, comparison.id)
        ],
    )


@router.post(
    "/contexts/{context_id}/comparisons/run", response_model=ChangeComparisonResult, status_code=201
)
def comparison_run(
    context_id: uuid.UUID, data: ChangeComparisonCreate, db: DB, owner: Owner
) -> ChangeComparisonResult:
    return comparison_create(context_id, data, db, owner)


@router.get("/contexts/{context_id}/changes", response_model=ChangeListResponse)
def changes_current(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    change_type: str | None = None,
    materiality: str | None = None,
    status: str | None = None,
    product_id: uuid.UUID | None = None,
) -> ChangeListResponse:
    get_context(db, owner, context_id)
    items, total = list_events(
        db,
        owner,
        context_id,
        limit,
        offset,
        change_type=change_type,
        materiality=materiality,
        status=status,
        product_id=product_id,
    )
    return ChangeListResponse(
        items=[ChangeEventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/contexts/{context_id}/changes/current", response_model=ChangeListResponse)
def changes_current_alias(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChangeListResponse:
    get_context(db, owner, context_id)
    items, total = current_events(db, owner, context_id, limit, offset)
    return ChangeListResponse(
        items=[ChangeEventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/contexts/{context_id}/history", response_model=list[ChangeComparisonResponse])
def comparison_history(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompetitorChangeComparison]:
    get_context(db, owner, context_id)
    rows, _ = history(db, owner, context_id, limit, offset)
    return rows


@router.get("/comparisons/{comparison_id}", response_model=ChangeComparisonResult)
def comparison_detail(comparison_id: uuid.UUID, db: DB, owner: Owner) -> ChangeComparisonResult:
    value = get_comparison(db, owner, comparison_id)
    return ChangeComparisonResult(
        comparison=ChangeComparisonResponse.model_validate(value),
        events=[
            ChangeEventResponse.model_validate(item) for item in _events(db, owner, comparison_id)
        ],
    )


@router.get("/changes/{event_id}", response_model=ChangeEventResponse)
def change_detail(event_id: uuid.UUID, db: DB, owner: Owner) -> CompetitorChangeEvent:
    return get_event(db, owner, event_id)


@router.post("/changes/{event_id}/review", response_model=ChangeEventResponse)
def change_review(
    event_id: uuid.UUID, data: ChangeReviewRequest, db: DB, owner: Owner
) -> CompetitorChangeEvent:
    return review_event(db, owner, event_id, data)


@router.get("/contexts/{context_id}/material-changes", response_model=ChangeListResponse)
def material_changes(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChangeListResponse:
    get_context(db, owner, context_id)
    items, total = list_events(db, owner, context_id, limit, offset, materiality="HIGH")
    moderate, moderate_total = list_events(
        db, owner, context_id, limit, offset, materiality="MODERATE"
    )
    items = items + moderate
    return ChangeListResponse(
        items=[ChangeEventResponse.model_validate(item) for item in items[:limit]],
        total=total + moderate_total,
        limit=limit,
        offset=offset,
    )


@router.get("/contexts/{context_id}/unresolved", response_model=ChangeListResponse)
def unresolved_changes(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChangeListResponse:
    get_context(db, owner, context_id)
    items, total = list_events(db, owner, context_id, limit, offset, status="UNRESOLVED")
    return ChangeListResponse(
        items=[ChangeEventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/contexts/{context_id}/alert-eligible", response_model=ChangeListResponse)
def alert_eligible_changes(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChangeListResponse:
    get_context(db, owner, context_id)
    items, total = list_events(db, owner, context_id, limit, offset)
    selected = [item for item in items if item.alert_eligibility in {"REVIEW", "ALERT"}]
    return ChangeListResponse(
        items=[ChangeEventResponse.model_validate(item) for item in selected],
        total=min(total, len(selected)),
        limit=limit,
        offset=offset,
    )


@router.get("/system-doctor")
def change_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return integrity_report(db, owner)
