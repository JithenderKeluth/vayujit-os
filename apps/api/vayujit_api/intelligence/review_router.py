"""Owner-scoped Review Intelligence foundation API (11A)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewAnalysisItem,
    ReviewContext,
    ReviewIngestionBatch,
    ReviewIngestionCandidate,
    ReviewRecord,
    ReviewSnapshot,
    ReviewSource,
)
from vayujit_api.intelligence.review_schemas import (
    ReviewAnalysisAnnotationResponse,
    ReviewAnalysisDetail,
    ReviewAnalysisItemResponse,
    ReviewAnalysisRequest,
    ReviewAnalysisResponse,
    ReviewContextCreate,
    ReviewContextResponse,
    ReviewContextUpdate,
    ReviewGapAnalysisDetail,
    ReviewGapAnalysisRequest,
    ReviewGapAnalysisResponse,
    ReviewIngestionBatchResponse,
    ReviewIngestionCandidateResponse,
    ReviewIngestionRequest,
    ReviewIngestionResult,
    ReviewIntegrityResponse,
    ReviewOpportunitySignalResponse,
    ReviewPage,
    ReviewProductGapResponse,
    ReviewRecordCreate,
    ReviewRecordResponse,
    ReviewSnapshotCreate,
    ReviewSnapshotResponse,
    ReviewSourceCreate,
    ReviewSourceResponse,
    ReviewStatisticsResponse,
)
from vayujit_api.intelligence.review_service import (
    _context_or_404,
    archive_context,
    create_context,
    create_review,
    create_snapshot,
    create_source,
    integrity_report,
    statistics,
    update_context,
)

router = APIRouter(prefix="/api/v1/intelligence/reviews", tags=["review-intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/contexts", response_model=ReviewContextResponse, status_code=201)
def context_create(data: ReviewContextCreate, db: DB, owner: Owner) -> ReviewContext:
    return create_context(db, owner, data)


@router.get("/contexts", response_model=list[ReviewContextResponse])
def context_list(
    db: DB,
    owner: Owner,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewContext]:
    query = select(ReviewContext).where(ReviewContext.owner_id == owner.id)
    if status:
        query = query.where(ReviewContext.status == status.upper())
    return list(
        db.scalars(query.order_by(ReviewContext.updated_at.desc()).offset(offset).limit(limit))
    )


@router.get("/contexts/{context_id}", response_model=ReviewContextResponse)
def context_get(context_id: uuid.UUID, db: DB, owner: Owner) -> ReviewContext:
    from vayujit_api.intelligence.review_service import _context_or_404

    return _context_or_404(db, owner, context_id)


@router.patch("/contexts/{context_id}", response_model=ReviewContextResponse)
def context_update(
    context_id: uuid.UUID, data: ReviewContextUpdate, db: DB, owner: Owner
) -> ReviewContext:
    from vayujit_api.intelligence.review_service import _context_or_404

    return update_context(db, owner, _context_or_404(db, owner, context_id), data)


@router.post("/contexts/{context_id}/archive", response_model=ReviewContextResponse)
def context_archive(context_id: uuid.UUID, db: DB, owner: Owner) -> ReviewContext:
    from vayujit_api.intelligence.review_service import _context_or_404

    return archive_context(db, owner, _context_or_404(db, owner, context_id))


@router.post("/contexts/{context_id}/sources", response_model=ReviewSourceResponse, status_code=201)
def source_create(
    context_id: uuid.UUID, data: ReviewSourceCreate, db: DB, owner: Owner
) -> ReviewSource:
    from vayujit_api.intelligence.review_service import _context_or_404

    value = create_source(db, owner, _context_or_404(db, owner, context_id), data)
    db.commit()
    return value


@router.get("/contexts/{context_id}/sources", response_model=list[ReviewSourceResponse])
def source_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewSource]:
    from vayujit_api.intelligence.review_service import _context_or_404

    _context_or_404(db, owner, context_id)
    return list(
        db.scalars(
            select(ReviewSource)
            .where(ReviewSource.owner_id == owner.id, ReviewSource.context_id == context_id)
            .order_by(ReviewSource.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.post("/contexts/{context_id}/reviews", response_model=ReviewRecordResponse, status_code=201)
def review_create(
    context_id: uuid.UUID, data: ReviewRecordCreate, db: DB, owner: Owner
) -> ReviewRecord:
    from vayujit_api.intelligence.review_service import _context_or_404

    return create_review(db, owner, _context_or_404(db, owner, context_id), data)


@router.get("/contexts/{context_id}/reviews", response_model=ReviewPage)
def review_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    provider: str | None = None,
    freshness_status: str | None = None,
) -> ReviewPage:
    from vayujit_api.intelligence.review_service import _context_or_404

    _context_or_404(db, owner, context_id)
    query = select(ReviewRecord).where(
        ReviewRecord.owner_id == owner.id, ReviewRecord.context_id == context_id
    )
    if provider:
        query = query.where(ReviewRecord.provider == provider)
    if freshness_status:
        query = query.where(ReviewRecord.freshness_status == freshness_status.upper())
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    values = list(
        db.scalars(
            query.order_by(
                ReviewRecord.review_date.desc().nullslast(), ReviewRecord.created_at.desc()
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return ReviewPage(
        items=[ReviewRecordResponse.model_validate(value) for value in values],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/contexts/{context_id}/reviews/{review_id}", response_model=ReviewRecordResponse)
def review_get(context_id: uuid.UUID, review_id: uuid.UUID, db: DB, owner: Owner) -> ReviewRecord:
    from fastapi import HTTPException

    from vayujit_api.intelligence.review_service import _context_or_404

    _context_or_404(db, owner, context_id)
    value = db.scalar(
        select(ReviewRecord).where(
            ReviewRecord.id == review_id,
            ReviewRecord.owner_id == owner.id,
            ReviewRecord.context_id == context_id,
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    return value


@router.post(
    "/contexts/{context_id}/snapshots", response_model=ReviewSnapshotResponse, status_code=201
)
def snapshot_create(
    context_id: uuid.UUID, data: ReviewSnapshotCreate, db: DB, owner: Owner
) -> ReviewSnapshot:
    from vayujit_api.intelligence.review_service import _context_or_404

    return create_snapshot(db, owner, _context_or_404(db, owner, context_id), data)


@router.get("/contexts/{context_id}/snapshots", response_model=list[ReviewSnapshotResponse])
def snapshot_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewSnapshot]:
    from vayujit_api.intelligence.review_service import _context_or_404

    _context_or_404(db, owner, context_id)
    return list(
        db.scalars(
            select(ReviewSnapshot)
            .where(ReviewSnapshot.owner_id == owner.id, ReviewSnapshot.context_id == context_id)
            .order_by(ReviewSnapshot.snapshot_version.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get(
    "/contexts/{context_id}/snapshots/current", response_model=ReviewSnapshotResponse | None
)
def snapshot_current(context_id: uuid.UUID, db: DB, owner: Owner) -> ReviewSnapshot | None:
    from vayujit_api.intelligence.review_service import _context_or_404

    _context_or_404(db, owner, context_id)
    return db.scalar(
        select(ReviewSnapshot)
        .where(ReviewSnapshot.owner_id == owner.id, ReviewSnapshot.context_id == context_id)
        .order_by(ReviewSnapshot.snapshot_version.desc())
        .limit(1)
    )


@router.get("/contexts/{context_id}/snapshots/{snapshot_id}", response_model=ReviewSnapshotResponse)
def snapshot_get(
    context_id: uuid.UUID, snapshot_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewSnapshot:
    from fastapi import HTTPException

    from vayujit_api.intelligence.review_service import _context_or_404

    _context_or_404(db, owner, context_id)
    value = db.scalar(
        select(ReviewSnapshot).where(
            ReviewSnapshot.id == snapshot_id,
            ReviewSnapshot.owner_id == owner.id,
            ReviewSnapshot.context_id == context_id,
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Review snapshot not found.")
    return value


@router.get("/contexts/{context_id}/statistics", response_model=ReviewStatisticsResponse)
def context_statistics(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return statistics(db, owner, context_id)


@router.get("/contexts/{context_id}/source-inventory")
def source_inventory(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return statistics(db, owner, context_id)["source_counts"]  # type: ignore[return-value]


@router.post(
    "/contexts/{context_id}/ingestions",
    response_model=ReviewIngestionResult,
    status_code=201,
)
def ingestion_create(
    context_id: uuid.UUID, data: ReviewIngestionRequest, db: DB, owner: Owner
) -> ReviewIngestionResult:
    from vayujit_api.intelligence.review_ingestion_service import _summary, execute_ingestion
    from vayujit_api.intelligence.review_service import _context_or_404

    batch, candidates, snapshot = execute_ingestion(
        db, owner, _context_or_404(db, owner, context_id), data
    )
    return ReviewIngestionResult(
        batch=ReviewIngestionBatchResponse.model_validate(batch),
        candidates=[ReviewIngestionCandidateResponse.model_validate(item) for item in candidates],
        snapshot=ReviewSnapshotResponse.model_validate(snapshot) if snapshot else None,
        summary=_summary(db, owner, batch),
    )


@router.get(
    "/contexts/{context_id}/ingestions",
    response_model=list[ReviewIngestionBatchResponse],
)
def ingestion_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewIngestionBatch]:
    from vayujit_api.intelligence.review_ingestion_service import batch_list

    return batch_list(db, owner, context_id, limit, offset)


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}",
    response_model=ReviewIngestionResult,
)
def ingestion_get(
    context_id: uuid.UUID, batch_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewIngestionResult:
    from vayujit_api.intelligence.review_ingestion_service import _summary, batch_detail

    batch, candidates = batch_detail(db, owner, context_id, batch_id)
    snapshot = db.scalar(
        select(ReviewSnapshot)
        .where(ReviewSnapshot.owner_id == owner.id, ReviewSnapshot.context_id == context_id)
        .order_by(ReviewSnapshot.snapshot_version.desc())
        .limit(1)
    )
    return ReviewIngestionResult(
        batch=ReviewIngestionBatchResponse.model_validate(batch),
        candidates=[ReviewIngestionCandidateResponse.model_validate(item) for item in candidates],
        snapshot=ReviewSnapshotResponse.model_validate(snapshot) if snapshot else None,
        summary=_summary(db, owner, batch),
    )


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}/candidates",
    response_model=list[ReviewIngestionCandidateResponse],
)
def ingestion_candidates(
    context_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(500, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ReviewIngestionCandidate]:
    from vayujit_api.intelligence.review_ingestion_service import batch_detail

    _, candidates = batch_detail(db, owner, context_id, batch_id)
    return candidates[offset : offset + limit]


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}/rejections",
    response_model=list[ReviewIngestionCandidateResponse],
)
def ingestion_rejections(
    context_id: uuid.UUID, batch_id: uuid.UUID, db: DB, owner: Owner
) -> list[ReviewIngestionCandidate]:
    from vayujit_api.intelligence.review_ingestion_service import batch_detail

    _, candidates = batch_detail(db, owner, context_id, batch_id)
    return [item for item in candidates if not item.accepted and item.rejection_reason]


@router.get("/contexts/{context_id}/ingestion-summary")
def ingestion_summary(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.intelligence.review_ingestion_service import (
        ingestion_summary as service_summary,
    )

    return service_summary(db, owner, context_id)


@router.get("/system-doctor", response_model=ReviewIntegrityResponse)
def review_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return integrity_report(db, owner)


def _analysis_response(value: ReviewAnalysis) -> ReviewAnalysisResponse:
    return ReviewAnalysisResponse.model_validate(value)


def _analysis_detail_response(
    db: Session, owner: User, context_id: uuid.UUID, analysis_id: uuid.UUID
) -> ReviewAnalysisDetail:
    from vayujit_api.intelligence.review_analysis_service import analysis_detail

    analysis, items, annotations = analysis_detail(db, owner, context_id, analysis_id)
    return ReviewAnalysisDetail(
        analysis=_analysis_response(analysis),
        items=[ReviewAnalysisItemResponse.model_validate(item) for item in items],
        annotations=[ReviewAnalysisAnnotationResponse.model_validate(item) for item in annotations],
        summary={"item_count": len(items), "annotation_count": len(annotations)},
    )


@router.post(
    "/contexts/{context_id}/analyses", response_model=ReviewAnalysisDetail, status_code=201
)
def analysis_create(
    context_id: uuid.UUID, data: ReviewAnalysisRequest, db: DB, owner: Owner
) -> ReviewAnalysisDetail:
    from vayujit_api.intelligence.review_analysis_service import create_analysis

    value = create_analysis(db, owner, _context_or_404(db, owner, context_id), data)
    return _analysis_detail_response(db, owner, context_id, value.id)


@router.get("/contexts/{context_id}/analyses", response_model=list[ReviewAnalysisResponse])
def analysis_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewAnalysis]:
    _context_or_404(db, owner, context_id)
    return list(
        db.scalars(
            select(ReviewAnalysis)
            .where(ReviewAnalysis.owner_id == owner.id, ReviewAnalysis.context_id == context_id)
            .order_by(ReviewAnalysis.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/contexts/{context_id}/analyses/current", response_model=ReviewAnalysisDetail | None)
def analysis_current(context_id: uuid.UUID, db: DB, owner: Owner) -> ReviewAnalysisDetail | None:
    from vayujit_api.intelligence.review_analysis_service import current_analysis

    value = current_analysis(db, owner, context_id)
    return _analysis_detail_response(db, owner, context_id, value.id) if value else None


@router.get("/contexts/{context_id}/analyses/{analysis_id}", response_model=ReviewAnalysisDetail)
def analysis_get(
    context_id: uuid.UUID, analysis_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewAnalysisDetail:
    return _analysis_detail_response(db, owner, context_id, analysis_id)


@router.get(
    "/contexts/{context_id}/analyses/{analysis_id}/{item_type}",
    response_model=list[ReviewAnalysisItemResponse],
)
def analysis_items(
    context_id: uuid.UUID, analysis_id: uuid.UUID, item_type: str, db: DB, owner: Owner
) -> list[ReviewAnalysisItem]:
    _analysis_detail_response(db, owner, context_id, analysis_id)
    return list(
        db.scalars(
            select(ReviewAnalysisItem)
            .where(
                ReviewAnalysisItem.owner_id == owner.id,
                ReviewAnalysisItem.analysis_id == analysis_id,
                ReviewAnalysisItem.item_type == item_type.upper(),
            )
            .order_by(ReviewAnalysisItem.canonical_label)
        )
    )


def _gap_detail_response(
    db: Session, owner: User, context_id: uuid.UUID, analysis_id: uuid.UUID
) -> ReviewGapAnalysisDetail:
    from vayujit_api.intelligence.review_gap_service import gap_analysis_detail

    analysis, gaps, signals = gap_analysis_detail(db, owner, context_id, analysis_id)
    return ReviewGapAnalysisDetail(
        analysis=ReviewGapAnalysisResponse.model_validate(analysis),
        product_gaps=[ReviewProductGapResponse.model_validate(item) for item in gaps],
        opportunity_signals=[
            ReviewOpportunitySignalResponse.model_validate(item) for item in signals
        ],
        summary={"gap_count": len(gaps), "signal_count": len(signals), "review_derived": True},
    )


@router.post(
    "/contexts/{context_id}/gap-analyses", response_model=ReviewGapAnalysisDetail, status_code=201
)
def gap_analysis_create(
    context_id: uuid.UUID, data: ReviewGapAnalysisRequest, db: DB, owner: Owner
) -> ReviewGapAnalysisDetail:
    from vayujit_api.intelligence.review_gap_service import create_gap_analysis

    value = create_gap_analysis(
        db, owner, _context_or_404(db, owner, context_id), data.review_analysis_id
    )
    return _gap_detail_response(db, owner, context_id, value.id)


@router.get("/contexts/{context_id}/gap-analyses", response_model=list[ReviewGapAnalysisResponse])
def gap_analysis_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewGapAnalysisResponse]:

    _context_or_404(db, owner, context_id)
    from vayujit_api.intelligence.review_models import ReviewProductGapAnalysis

    return list(
        db.scalars(
            select(ReviewProductGapAnalysis)
            .where(
                ReviewProductGapAnalysis.owner_id == owner.id,
                ReviewProductGapAnalysis.context_id == context_id,
            )
            .order_by(ReviewProductGapAnalysis.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get(
    "/contexts/{context_id}/gap-analyses/current", response_model=ReviewGapAnalysisDetail | None
)
def gap_analysis_current(
    context_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewGapAnalysisDetail | None:

    from vayujit_api.intelligence.review_gap_service import current_gap_analysis

    value = current_gap_analysis(db, owner, context_id)
    return _gap_detail_response(db, owner, context_id, value.id) if value else None


@router.get(
    "/contexts/{context_id}/gap-analyses/{analysis_id}", response_model=ReviewGapAnalysisDetail
)
def gap_analysis_get(
    context_id: uuid.UUID, analysis_id: uuid.UUID, db: DB, owner: Owner
) -> ReviewGapAnalysisDetail:
    return _gap_detail_response(db, owner, context_id, analysis_id)


@router.get(
    "/contexts/{context_id}/gap-analyses/{analysis_id}/product-gaps",
    response_model=list[ReviewProductGapResponse],
)
def product_gaps_get(
    context_id: uuid.UUID,
    analysis_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewProductGapResponse]:
    _context_or_404(db, owner, context_id)
    from vayujit_api.intelligence.review_models import ReviewProductGap

    return [
        ReviewProductGapResponse.model_validate(item)
        for item in db.scalars(
            select(ReviewProductGap)
            .where(
                ReviewProductGap.owner_id == owner.id, ReviewProductGap.analysis_id == analysis_id
            )
            .order_by(ReviewProductGap.canonical_label)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get(
    "/contexts/{context_id}/gap-analyses/{analysis_id}/opportunity-signals",
    response_model=list[ReviewOpportunitySignalResponse],
)
def opportunity_signals_get(
    context_id: uuid.UUID,
    analysis_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewOpportunitySignalResponse]:
    _context_or_404(db, owner, context_id)
    from vayujit_api.intelligence.review_models import ReviewOpportunitySignal

    return [
        ReviewOpportunitySignalResponse.model_validate(item)
        for item in db.scalars(
            select(ReviewOpportunitySignal)
            .where(
                ReviewOpportunitySignal.owner_id == owner.id,
                ReviewOpportunitySignal.analysis_id == analysis_id,
            )
            .order_by(ReviewOpportunitySignal.signal_type)
            .offset(offset)
            .limit(limit)
        )
    ]
