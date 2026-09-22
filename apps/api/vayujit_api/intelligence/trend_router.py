"""Owner-scoped Trend Intelligence 12A API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.trend_ingestion_models import TrendIngestionBatch
from vayujit_api.intelligence.trend_ingestion_schemas import (
    TrendIngestionBatchResponse,
    TrendIngestionCandidateResponse,
    TrendIngestionRequest,
    TrendIngestionSummary,
)
from vayujit_api.intelligence.trend_ingestion_service import (
    batch_or_404,
    ingest,
)
from vayujit_api.intelligence.trend_ingestion_service import (
    candidates as ingestion_candidates,
)
from vayujit_api.intelligence.trend_models import (
    TrendContext,
    TrendObservation,
    TrendSignalDefinition,
    TrendSnapshot,
)
from vayujit_api.intelligence.trend_schemas import (
    TrendContextCreate,
    TrendContextResponse,
    TrendContextUpdate,
    TrendCoverageResponse,
    TrendDoctorResponse,
    TrendObservationCreate,
    TrendObservationResponse,
    TrendOperationsResponse,
    TrendPage,
    TrendSignalDefinitionCreate,
    TrendSignalDefinitionResponse,
    TrendSnapshotCreate,
    TrendSnapshotResponse,
)
from vayujit_api.intelligence.trend_service import (
    archive_context,
    context_or_404,
    coverage,
    create_context,
    create_observation,
    create_signal_definition,
    create_snapshot,
    doctor,
    list_signal_definitions,
    operations,
    update_context,
)

router = APIRouter(prefix="/api/v1/intelligence/trends", tags=["trend-intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/contexts", response_model=TrendContextResponse, status_code=201)
def context_create(data: TrendContextCreate, db: DB, owner: Owner) -> TrendContext:
    return create_context(db, owner, data)


@router.get("/contexts", response_model=list[TrendContextResponse])
def context_list(
    db: DB,
    owner: Owner,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[TrendContext]:
    query = select(TrendContext).where(TrendContext.owner_id == owner.id)
    if status:
        query = query.where(TrendContext.status == status.upper())
    return list(
        db.scalars(query.order_by(TrendContext.updated_at.desc()).offset(offset).limit(limit))
    )


@router.get("/contexts/{context_id}", response_model=TrendContextResponse)
def context_get(context_id: uuid.UUID, db: DB, owner: Owner) -> TrendContext:
    return context_or_404(db, owner, context_id)


@router.patch("/contexts/{context_id}", response_model=TrendContextResponse)
def context_patch(
    context_id: uuid.UUID, data: TrendContextUpdate, db: DB, owner: Owner
) -> TrendContext:
    return update_context(db, owner, context_or_404(db, owner, context_id), data)


@router.post("/contexts/{context_id}/archive", response_model=TrendContextResponse)
def context_archive(context_id: uuid.UUID, db: DB, owner: Owner) -> TrendContext:
    return archive_context(db, owner, context_or_404(db, owner, context_id))


@router.get("/signal-definitions", response_model=list[TrendSignalDefinitionResponse])
def signal_definition_list(db: DB, owner: Owner) -> list[TrendSignalDefinition]:
    return list_signal_definitions(db, owner)


@router.post("/signal-definitions", response_model=TrendSignalDefinitionResponse, status_code=201)
def signal_definition_create(
    data: TrendSignalDefinitionCreate, db: DB, owner: Owner
) -> TrendSignalDefinition:
    return create_signal_definition(db, owner, data)


@router.post(
    "/contexts/{context_id}/observations", response_model=TrendObservationResponse, status_code=201
)
def observation_create(
    context_id: uuid.UUID, data: TrendObservationCreate, db: DB, owner: Owner
) -> TrendObservation:
    return create_observation(db, owner, context_or_404(db, owner, context_id), data)


@router.get("/contexts/{context_id}/observations", response_model=TrendPage)
def observation_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> TrendPage:
    context_or_404(db, owner, context_id)
    query = select(TrendObservation).where(
        TrendObservation.owner_id == owner.id, TrendObservation.context_id == context_id
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(query.order_by(TrendObservation.observed_at.desc()).offset(offset).limit(limit))
    )
    return TrendPage(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/contexts/{context_id}/snapshots", response_model=TrendSnapshotResponse, status_code=201
)
def snapshot_create(
    context_id: uuid.UUID, data: TrendSnapshotCreate, db: DB, owner: Owner
) -> TrendSnapshot:
    return create_snapshot(db, owner, context_or_404(db, owner, context_id), data)


@router.get("/contexts/{context_id}/snapshots", response_model=list[TrendSnapshotResponse])
def snapshot_list(
    context_id: uuid.UUID, db: DB, owner: Owner, limit: int = Query(50, ge=1, le=200)
) -> list[TrendSnapshot]:
    context_or_404(db, owner, context_id)
    return list(
        db.scalars(
            select(TrendSnapshot)
            .where(TrendSnapshot.owner_id == owner.id, TrendSnapshot.context_id == context_id)
            .order_by(TrendSnapshot.snapshot_version.desc())
            .limit(limit)
        )
    )


@router.get("/contexts/{context_id}/snapshots/current", response_model=TrendSnapshotResponse | None)
def snapshot_current(context_id: uuid.UUID, db: DB, owner: Owner) -> TrendSnapshot | None:
    context_or_404(db, owner, context_id)
    return db.scalar(
        select(TrendSnapshot)
        .where(TrendSnapshot.owner_id == owner.id, TrendSnapshot.context_id == context_id)
        .order_by(TrendSnapshot.snapshot_version.desc())
    )


@router.get("/contexts/{context_id}/sources")
def context_sources(context_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    context_or_404(db, owner, context_id)
    rows = db.execute(
        select(TrendObservation.source_id, func.count())
        .where(TrendObservation.owner_id == owner.id, TrendObservation.context_id == context_id)
        .group_by(TrendObservation.source_id)
    ).all()
    return [{"source_id": str(source_id), "observation_count": count} for source_id, count in rows]


@router.get("/contexts/{context_id}/coverage", response_model=TrendCoverageResponse)
def context_coverage(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return coverage(db, owner, context_or_404(db, owner, context_id))


@router.get("/system-doctor", response_model=TrendDoctorResponse)
def system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return doctor(db, owner)


@router.get("/operations", response_model=TrendOperationsResponse)
def operation_metrics(db: DB, owner: Owner) -> dict[str, object]:
    return operations(db, owner)


@router.post(
    "/contexts/{context_id}/ingestions", response_model=TrendIngestionBatchResponse, status_code=201
)
def ingestion_create(
    context_id: uuid.UUID, data: TrendIngestionRequest, db: DB, owner: Owner
) -> TrendIngestionBatch:
    return ingest(db, owner, context_or_404(db, owner, context_id), data)


@router.get("/contexts/{context_id}/ingestions", response_model=list[TrendIngestionBatchResponse])
def ingestion_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[TrendIngestionBatch]:
    context_or_404(db, owner, context_id)
    query = select(TrendIngestionBatch).where(
        TrendIngestionBatch.owner_id == owner.id, TrendIngestionBatch.context_id == context_id
    )
    return list(
        db.scalars(
            query.order_by(TrendIngestionBatch.created_at.desc()).offset(offset).limit(limit)
        )
    )


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}", response_model=TrendIngestionBatchResponse
)
def ingestion_get(
    context_id: uuid.UUID, batch_id: uuid.UUID, db: DB, owner: Owner
) -> TrendIngestionBatch:
    context_or_404(db, owner, context_id)
    batch = batch_or_404(db, owner, batch_id)
    if batch.context_id != context_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Trend ingestion batch not found.")
    return batch


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}/candidates",
    response_model=list[TrendIngestionCandidateResponse],
)
def ingestion_candidate_list(
    context_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list:
    context_or_404(db, owner, context_id)
    return ingestion_candidates(
        db, owner, batch_or_404(db, owner, batch_id), limit=limit, offset=offset
    )


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}/rejections",
    response_model=list[TrendIngestionCandidateResponse],
)
def ingestion_rejection_list(
    context_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list:
    context_or_404(db, owner, context_id)
    return ingestion_candidates(
        db, owner, batch_or_404(db, owner, batch_id), rejected_only=True, limit=limit, offset=offset
    )


@router.get(
    "/contexts/{context_id}/ingestions/{batch_id}/summary", response_model=TrendIngestionSummary
)
def ingestion_summary(
    context_id: uuid.UUID, batch_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    context = context_or_404(db, owner, context_id)
    batch = batch_or_404(db, owner, batch_id)
    return {
        "batch": batch,
        "coverage": batch.summary_json.get("coverage", coverage(db, owner, context)),
        "quality_distribution": batch.summary_json.get("quality_distribution", {}),
        "freshness_distribution": batch.summary_json.get("freshness_distribution", {}),
        "rejection_distribution": batch.summary_json.get("rejection_distribution", {}),
        "gaps": batch.summary_json.get("gaps", []),
    }
