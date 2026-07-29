import math
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.schemas import MediaPage, MediaResponse
from vayujit_api.media.service import (
    owned_media,
    response,
    set_archived,
    storage_path,
    upload,
)

router = APIRouter(prefix="/api/v1/media", tags=["media"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("", response_model=MediaPage)
def list_media(
    db: DB,
    owner: Owner,
    search: Annotated[str | None, Query(max_length=100)] = None,
    mime_type: str | None = None,
    archived: bool | None = False,
    sort: str = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> MediaPage:
    filters = [MediaAsset.owner_id == owner.id]
    if archived is not None:
        filters.append(MediaAsset.status == ("archived" if archived else "ready"))
    if mime_type:
        filters.append(MediaAsset.mime_type == mime_type)
    if search:
        filters.append(
            or_(
                MediaAsset.original_filename.ilike(f"%{search}%"),
                MediaAsset.safe_filename.ilike(f"%{search}%"),
            )
        )
    if sort == "oldest":
        ordering: Any = MediaAsset.created_at.asc()
    elif sort == "name":
        ordering = MediaAsset.safe_filename.asc()
    elif sort == "size":
        ordering = MediaAsset.size_bytes.desc()
    else:
        ordering = MediaAsset.created_at.desc()
    total = db.scalar(select(func.count()).select_from(MediaAsset).where(*filters)) or 0
    items = db.scalars(
        select(MediaAsset)
        .where(*filters)
        .order_by(ordering, MediaAsset.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return MediaPage(
        items=[response(db, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=MediaResponse, status_code=201)
async def upload_media(db: DB, owner: Owner, file: Annotated[UploadFile, File()]) -> MediaResponse:
    data = await file.read(get_settings().media_max_size_bytes + 1)
    return upload(
        db,
        owner,
        file.filename or "",
        file.content_type or "application/octet-stream",
        data,
    )


@router.get("/{media_id}", response_model=MediaResponse)
def get_media(media_id: uuid.UUID, db: DB, owner: Owner) -> MediaResponse:
    return response(db, owned_media(db, owner.id, media_id))


@router.post("/{media_id}/archive", response_model=MediaResponse)
def archive_media(media_id: uuid.UUID, db: DB, owner: Owner) -> MediaResponse:
    return set_archived(db, owner, owned_media(db, owner.id, media_id), True)


@router.post("/{media_id}/restore", response_model=MediaResponse)
def restore_media(media_id: uuid.UUID, db: DB, owner: Owner) -> MediaResponse:
    return set_archived(db, owner, owned_media(db, owner.id, media_id), False)


@router.get("/{media_id}/preview")
def preview_media(media_id: uuid.UUID, db: DB, owner: Owner) -> Response:
    value = owned_media(db, owner.id, media_id)
    data = storage_path(value.storage_key).read_bytes()
    return Response(
        content=data,
        media_type=value.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{value.safe_filename}"',
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
