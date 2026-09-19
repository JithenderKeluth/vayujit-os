"""Authenticated API for read-only competitor discovery (Slice 10B)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.competitor_discovery_models import (
    CompetitorDiscoveryCandidate,
    CompetitorDiscoveryRequest,
    CompetitorDiscoverySnapshot,
)
from vayujit_api.intelligence.competitor_discovery_schemas import (
    CandidateResolutionRequest,
    CandidateResponse,
    DiscoveryExecutionResponse,
    DiscoveryRequestCreate,
    DiscoveryRequestResponse,
    DiscoverySnapshotResponse,
    DiscoverySystemDoctorResponse,
)
from vayujit_api.intelligence.competitor_discovery_service import (
    create_request,
    execute_request,
    get_candidate,
    get_request,
    integrity_report,
    resolve_candidate,
)
from vayujit_api.intelligence.competitor_service import get_context

router = APIRouter(
    prefix="/api/v1/intelligence/competitors/discovery", tags=["competitor-discovery"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _execution(
    request: CompetitorDiscoveryRequest,
    candidates: list[CompetitorDiscoveryCandidate],
    snapshot: CompetitorDiscoverySnapshot,
) -> DiscoveryExecutionResponse:
    return DiscoveryExecutionResponse(
        request=DiscoveryRequestResponse.model_validate(request),
        candidates=[CandidateResponse.model_validate(value) for value in candidates],
        snapshot=DiscoverySnapshotResponse.model_validate(snapshot),
    )


@router.post(
    "/contexts/{context_id}/requests", response_model=DiscoveryRequestResponse, status_code=201
)
def discovery_request_create(
    context_id: uuid.UUID, data: DiscoveryRequestCreate, db: DB, owner: Owner
) -> CompetitorDiscoveryRequest:
    return create_request(db, owner, context_id, data)


@router.get("/requests", response_model=list[DiscoveryRequestResponse])
def discovery_request_list(
    db: DB,
    owner: Owner,
    context_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[CompetitorDiscoveryRequest]:
    query = select(CompetitorDiscoveryRequest).where(
        CompetitorDiscoveryRequest.owner_id == owner.id
    )
    if context_id is not None:
        get_context(db, owner, context_id)
        query = query.where(CompetitorDiscoveryRequest.context_id == context_id)
    return list(
        db.scalars(
            query.order_by(CompetitorDiscoveryRequest.created_at.desc()).offset(offset).limit(limit)
        )
    )


@router.get("/requests/{request_id}", response_model=DiscoveryRequestResponse)
def discovery_request_get(
    request_id: uuid.UUID, db: DB, owner: Owner
) -> CompetitorDiscoveryRequest:
    return get_request(db, owner, request_id)


@router.post("/requests/{request_id}/execute", response_model=DiscoveryExecutionResponse)
def discovery_request_execute(
    request_id: uuid.UUID, db: DB, owner: Owner
) -> DiscoveryExecutionResponse:
    request, candidates, snapshot = execute_request(db, owner, get_request(db, owner, request_id))
    return _execution(request, candidates, snapshot)


@router.post("/requests/{request_id}/refresh", response_model=DiscoveryExecutionResponse)
def discovery_request_refresh(
    request_id: uuid.UUID, db: DB, owner: Owner
) -> DiscoveryExecutionResponse:
    request, candidates, snapshot = execute_request(
        db, owner, get_request(db, owner, request_id), refresh=True
    )
    return _execution(request, candidates, snapshot)


@router.get("/requests/{request_id}/candidates", response_model=list[CandidateResponse])
def discovery_candidate_list(
    request_id: uuid.UUID,
    db: DB,
    owner: Owner,
    identity_state: str | None = None,
    source_mode: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[CompetitorDiscoveryCandidate]:
    get_request(db, owner, request_id)
    query = select(CompetitorDiscoveryCandidate).where(
        CompetitorDiscoveryCandidate.owner_id == owner.id,
        CompetitorDiscoveryCandidate.request_id == request_id,
    )
    if identity_state:
        query = query.where(CompetitorDiscoveryCandidate.identity_state == identity_state.upper())
    if source_mode:
        query = query.where(CompetitorDiscoveryCandidate.source_mode == source_mode.upper())
    return list(
        db.scalars(
            query.order_by(CompetitorDiscoveryCandidate.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def discovery_candidate_get(
    candidate_id: uuid.UUID, db: DB, owner: Owner
) -> CompetitorDiscoveryCandidate:
    return get_candidate(db, owner, candidate_id)


@router.get("/candidates/{candidate_id}/explanation")
def discovery_candidate_explanation(
    candidate_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    candidate = get_candidate(db, owner, candidate_id)
    return {
        "candidate_id": str(candidate.id),
        "identity_state": candidate.identity_state,
        "match_level": candidate.match_level,
        "score": candidate.match_score,
        "supporting_signals": candidate.supporting_signals,
        "conflicting_signals": candidate.conflicting_signals,
        "missing_signals": candidate.missing_signals,
        "rule_version": candidate.rule_version,
        "evidence_state": candidate.evidence_state,
        "freshness_state": candidate.freshness_state,
    }


def _resolve(
    candidate_id: uuid.UUID, state: str, data: CandidateResolutionRequest, db: DB, owner: Owner
) -> CompetitorDiscoveryCandidate:
    return resolve_candidate(
        db,
        owner,
        get_candidate(db, owner, candidate_id),
        state=state,
        reason=data.reason,
        confirm=data.confirm,
    )


@router.post("/candidates/{candidate_id}/confirm", response_model=CandidateResponse)
def discovery_candidate_confirm(
    candidate_id: uuid.UUID, data: CandidateResolutionRequest, db: DB, owner: Owner
) -> CompetitorDiscoveryCandidate:
    return _resolve(candidate_id, "CONFIRMED", data, db, owner)


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateResponse)
def discovery_candidate_reject(
    candidate_id: uuid.UUID, data: CandidateResolutionRequest, db: DB, owner: Owner
) -> CompetitorDiscoveryCandidate:
    return _resolve(candidate_id, "REJECTED", data, db, owner)


@router.post("/candidates/{candidate_id}/ambiguous", response_model=CandidateResponse)
def discovery_candidate_ambiguous(
    candidate_id: uuid.UUID, data: CandidateResolutionRequest, db: DB, owner: Owner
) -> CompetitorDiscoveryCandidate:
    return _resolve(candidate_id, "AMBIGUOUS", data, db, owner)


@router.get("/requests/{request_id}/snapshots", response_model=list[DiscoverySnapshotResponse])
def discovery_snapshot_list(
    request_id: uuid.UUID, db: DB, owner: Owner, limit: int = Query(100, ge=1, le=200)
) -> list[CompetitorDiscoverySnapshot]:
    get_request(db, owner, request_id)
    return list(
        db.scalars(
            select(CompetitorDiscoverySnapshot)
            .where(
                CompetitorDiscoverySnapshot.owner_id == owner.id,
                CompetitorDiscoverySnapshot.request_id == request_id,
            )
            .order_by(CompetitorDiscoverySnapshot.snapshot_version.desc())
            .limit(limit)
        )
    )


@router.get("/snapshots/{snapshot_id}", response_model=DiscoverySnapshotResponse)
def discovery_snapshot_get(
    snapshot_id: uuid.UUID, db: DB, owner: Owner
) -> CompetitorDiscoverySnapshot:
    value = db.scalar(
        select(CompetitorDiscoverySnapshot).where(
            CompetitorDiscoverySnapshot.id == snapshot_id,
            CompetitorDiscoverySnapshot.owner_id == owner.id,
        )
    )
    if value is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Discovery snapshot not found.")
    return value


@router.get("/system-doctor", response_model=DiscoverySystemDoctorResponse)
def discovery_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return integrity_report(db, owner)
