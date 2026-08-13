import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MediaResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    safe_filename: str
    mime_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/webm",
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        "audio/mp4",
    ]
    size_bytes: int
    width: int
    height: int
    checksum_sha256: str
    status: Literal["ready", "archived"]
    upload_state: Literal["ready"] = "ready"
    usage_count: int
    duplicate_reused: bool = False
    created_at: datetime
    archived_at: datetime | None
    preview_url: str


class MediaPage(BaseModel):
    items: list[MediaResponse]
    page: int
    page_size: int
    total: int
    pages: int
