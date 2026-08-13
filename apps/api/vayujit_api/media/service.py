import hashlib
import os
import re
import struct
import uuid
from pathlib import Path
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.media.models import MediaAsset, WordPressMediaMapping
from vayujit_api.media.schemas import MediaResponse

MIME_EXTENSIONS = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
    "video/mp4": {"mp4"},
    "video/webm": {"webm"},
    "audio/mpeg": {"mp3"},
    "audio/wav": {"wav"},
    "audio/ogg": {"ogg"},
    "audio/mp4": {"m4a"},
}
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def storage_root() -> Path:
    root = Path(get_settings().media_storage_directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_name(filename: str) -> tuple[str, str]:
    if not filename or len(filename) > 255 or Path(filename).name != filename:
        raise HTTPException(422, "Media filename is invalid.")
    normalized = SAFE_FILENAME.sub("-", filename.strip()).strip(".-")
    if not normalized or "." not in normalized:
        raise HTTPException(422, "Media filename is invalid.")
    return normalized[:255], normalized.rsplit(".", 1)[1].casefold()


def image_dimensions(data: bytes, mime_type: str) -> tuple[int, int]:
    try:
        if mime_type == "image/png":
            if (
                not data.startswith(b"\x89PNG\r\n\x1a\n")
                or len(data) < 33
                or data[12:16] != b"IHDR"
                or b"IEND" not in data[-32:]
            ):
                raise ValueError
            return struct.unpack(">II", data[16:24])
        if mime_type == "image/jpeg":
            if len(data) < 12 or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                raise ValueError
            offset = 2
            while offset + 9 < len(data):
                if data[offset] != 0xFF:
                    offset += 1
                    continue
                marker = data[offset + 1]
                if marker in {0xD8, 0xD9}:
                    offset += 2
                    continue
                length = int.from_bytes(data[offset + 2 : offset + 4], "big")
                if length < 2 or offset + 2 + length > len(data):
                    raise ValueError
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB}:
                    return (
                        int.from_bytes(data[offset + 7 : offset + 9], "big"),
                        int.from_bytes(data[offset + 5 : offset + 7], "big"),
                    )
                offset += 2 + length
            raise ValueError
        if mime_type == "image/webp":
            if (
                len(data) < 30
                or data[:4] != b"RIFF"
                or data[8:12] != b"WEBP"
                or int.from_bytes(data[4:8], "little") + 8 != len(data)
            ):
                raise ValueError
            kind = data[12:16]
            if kind == b"VP8X":
                return (
                    1 + int.from_bytes(data[24:27], "little"),
                    1 + int.from_bytes(data[27:30], "little"),
                )
            if kind == b"VP8L" and data[20] == 0x2F:
                bits = int.from_bytes(data[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if kind == b"VP8 ":
                start = data.find(b"\x9d\x01\x2a", 20)
                if start >= 0 and start + 7 <= len(data):
                    return (
                        int.from_bytes(data[start + 3 : start + 5], "little") & 0x3FFF,
                        int.from_bytes(data[start + 5 : start + 7], "little") & 0x3FFF,
                    )
            raise ValueError
    except (IndexError, struct.error, ValueError):
        pass
    raise HTTPException(422, "Media file is malformed or corrupted.")


def validate_upload(
    filename: str, declared_mime: str, data: bytes
) -> tuple[str, str, int, int, str]:
    settings = get_settings()
    safe_filename, extension = safe_name(filename)
    if declared_mime not in MIME_EXTENSIONS or extension not in MIME_EXTENSIONS[declared_mime]:
        raise HTTPException(422, "Media MIME type and extension do not match.")
    if not data or len(data) > settings.media_max_size_bytes:
        raise HTTPException(413, "Media file exceeds the configured upload limit.")
    if declared_mime.startswith("audio/"):
        if declared_mime == "audio/mpeg" and not (
            data.startswith(b"ID3") or data.startswith(b"\xff\xfb")
        ):
            raise HTTPException(422, "Media file is malformed or corrupted.")
        if declared_mime == "audio/wav" and not data.startswith(b"RIFF"):
            raise HTTPException(422, "Media file is malformed or corrupted.")
        if declared_mime == "audio/ogg" and not data.startswith(b"OggS"):
            raise HTTPException(422, "Media file is malformed or corrupted.")
        if declared_mime == "audio/mp4" and b"ftyp" not in data[:64]:
            raise HTTPException(422, "Media file is malformed or corrupted.")
        width, height = 1, 1
    else:
        width, height = image_dimensions(data, declared_mime)
    if max(width, height) > settings.media_max_dimension:
        raise HTTPException(422, "Media dimensions exceed the configured limit.")
    return safe_filename, extension, width, height, hashlib.sha256(data).hexdigest()


def owned_media(db: Session, owner_id: uuid.UUID, media_id: uuid.UUID) -> MediaAsset:
    value = db.scalar(
        select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.owner_id == owner_id)
    )
    if not value:
        raise HTTPException(404, "Media item not found.")
    return value


def response(db: Session, value: MediaAsset, *, duplicate: bool = False) -> MediaResponse:
    usage = (
        db.scalar(
            select(func.count())
            .select_from(WordPressMediaMapping)
            .where(WordPressMediaMapping.media_id == value.id)
        )
        or 0
    )
    return MediaResponse(
        id=value.id,
        original_filename=value.original_filename,
        safe_filename=value.safe_filename,
        mime_type=cast(
            Literal["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm"],
            value.mime_type,
        ),
        size_bytes=value.size_bytes,
        width=value.width,
        height=value.height,
        checksum_sha256=value.checksum_sha256,
        status=cast(Literal["ready", "archived"], value.status),
        usage_count=usage,
        duplicate_reused=duplicate,
        created_at=value.created_at,
        archived_at=value.archived_at,
        preview_url=f"/api/v1/media/{value.id}/preview",
    )


def storage_path(storage_key: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}/[a-f0-9]{64}\.(?:jpg|jpeg|png|webp|mp4|webm)", storage_key):
        raise RuntimeError("Stored media key is invalid.")
    root = storage_root()
    target = (root / storage_key).resolve()
    if root not in target.parents:
        raise RuntimeError("Stored media key escaped its root.")
    return target


def upload(
    db: Session, owner: User, filename: str, declared_mime: str, data: bytes
) -> MediaResponse:
    pending_id = uuid.uuid4()
    record_event(
        db,
        actor_id=owner.id,
        action="media.upload_started",
        entity_type="media_asset",
        entity_id=pending_id,
        metadata={"mime_type": declared_mime, "size_bytes": len(data)},
    )
    try:
        safe_filename, extension, width, height, checksum = validate_upload(
            filename, declared_mime, data
        )
    except HTTPException as error:
        record_event(
            db,
            actor_id=owner.id,
            action="media.upload_failed",
            entity_type="media_asset",
            entity_id=pending_id,
            metadata={"code": "media_validation_failed", "status_code": error.status_code},
        )
        db.commit()
        raise
    existing = db.scalar(
        select(MediaAsset).where(
            MediaAsset.owner_id == owner.id, MediaAsset.checksum_sha256 == checksum
        )
    )
    if existing:
        record_event(
            db,
            actor_id=owner.id,
            action="media.duplicate_reused",
            entity_type="media_asset",
            entity_id=existing.id,
            metadata={"checksum_prefix": checksum[:12]},
        )
        db.commit()
        return response(db, existing, duplicate=True)
    stamp = now()
    storage_key = f"{owner.id.hex[:12]}/{checksum}.{extension}"
    value = MediaAsset(
        id=pending_id,
        owner_id=owner.id,
        original_filename=filename,
        safe_filename=safe_filename,
        mime_type=declared_mime,
        size_bytes=len(data),
        width=width,
        height=height,
        checksum_sha256=checksum,
        storage_key=storage_key,
        status="ready",
        created_at=stamp,
    )
    db.add(value)
    db.flush()
    target = storage_path(storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        record_event(
            db,
            actor_id=owner.id,
            action="media.upload_completed",
            entity_type="media_asset",
            entity_id=value.id,
            metadata={
                "mime_type": declared_mime,
                "size_bytes": len(data),
                "width": width,
                "height": height,
                "checksum_prefix": checksum[:12],
            },
        )
        db.commit()
    except (OSError, IntegrityError) as error:
        temporary.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(507, "Media could not be stored safely.") from error
    return response(db, value)


def set_archived(db: Session, owner: User, value: MediaAsset, archived: bool) -> MediaResponse:
    value.status = "archived" if archived else "ready"
    value.archived_at = now() if archived else None
    record_event(
        db,
        actor_id=owner.id,
        action=f"media.{'archived' if archived else 'restored'}",
        entity_type="media_asset",
        entity_id=value.id,
        metadata={},
    )
    db.commit()
    return response(db, value)


def upload_generated_video(
    db: Session,
    owner: User,
    filename: str,
    data: bytes,
    *,
    width: int,
    height: int,
    mime_type: str = "video/mp4",
) -> MediaAsset:
    if mime_type not in {"video/mp4", "video/webm"} or not data:
        raise HTTPException(422, "Generated video is invalid.")
    settings = get_settings()
    if len(data) > settings.media_max_size_bytes:
        raise HTTPException(413, "Generated video exceeds the configured upload limit.")
    checksum = hashlib.sha256(data).hexdigest()
    safe_filename = SAFE_FILENAME.sub("-", filename).strip(".-")[:255] or "generated-video.mp4"
    extension = "webm" if mime_type == "video/webm" else "mp4"
    value = MediaAsset(
        id=uuid.uuid4(),
        owner_id=owner.id,
        original_filename=filename,
        safe_filename=safe_filename,
        mime_type=mime_type,
        size_bytes=len(data),
        width=width,
        height=height,
        checksum_sha256=checksum,
        storage_key=f"{owner.id.hex[:12]}/{checksum}.{extension}",
        status="ready",
        created_at=now(),
    )
    db.add(value)
    db.flush()
    target = storage_path(value.storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(507, "Generated video could not be stored safely.") from error
    return value
