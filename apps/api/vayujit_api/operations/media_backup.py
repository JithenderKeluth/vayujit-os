"""Quiesced local-filesystem media backup and restore primitives.

The archive is deliberately separate from the PostgreSQL dump.  Operators create
both at one recorded consistency point, then restore the database and this
archive into an isolated target before resuming writes.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class MediaBackupError(RuntimeError):
    """Raised when a media archive cannot be safely created or restored."""


@dataclass(frozen=True)
class MediaFileEntry:
    path: str
    size_bytes: int
    checksum_sha256: str
    mime_type: str


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(path: str) -> PurePosixPath:
    value = PurePosixPath(path)
    if value.is_absolute() or ".." in value.parts or not value.parts:
        raise MediaBackupError("Media archive contains an unsafe path.")
    return value


def _entries(source: Path) -> list[MediaFileEntry]:
    values: list[MediaFileEntry] = []
    for candidate in sorted(source.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.is_symlink():
            raise MediaBackupError("Media backup does not follow symbolic links.")
        relative = candidate.relative_to(source).as_posix()
        values.append(
            MediaFileEntry(
                path=relative,
                size_bytes=candidate.stat().st_size,
                checksum_sha256=_checksum(candidate),
                mime_type=mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
            )
        )
    return values


def create_media_backup(
    source_directory: str | Path,
    destination_directory: str | Path,
    *,
    lineage: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    source = Path(source_directory).expanduser().resolve()
    destination = Path(destination_directory).expanduser().resolve()
    if not source.is_dir():
        raise MediaBackupError("Media source directory is unavailable.")
    destination.mkdir(parents=True, exist_ok=True)
    entries = _entries(source)
    stamp = uuid.uuid4().hex[:12]
    archive = destination / f"media-{stamp}.zip"
    manifest = destination / f"media-{stamp}.json"
    payload = {
        "format": "vayujit-local-media-v1",
        "source_directory": str(source),
        "files": [asdict(item) for item in entries],
        "lineage": lineage or {},
    }
    temporary = archive.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for item in entries:
                bundle.write(source / Path(item.path), arcname=item.path)
        temporary.replace(archive)
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except (OSError, zipfile.BadZipFile) as error:
        temporary.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        raise MediaBackupError("Media backup could not be created safely.") from error
    return archive, manifest


def restore_media_backup(
    archive_path: str | Path,
    manifest_path: str | Path,
    destination_directory: str | Path,
) -> dict[str, Any]:
    archive = Path(archive_path).expanduser().resolve()
    manifest_file = Path(manifest_path).expanduser().resolve()
    destination = Path(destination_directory).expanduser().resolve()
    if not archive.is_file() or not manifest_file.is_file():
        raise MediaBackupError("Media backup archive or manifest is missing.")
    if destination.exists() and any(destination.iterdir()):
        raise MediaBackupError("Restore target must be empty to prevent partial overwrite.")
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        if payload.get("format") != "vayujit-local-media-v1":
            raise MediaBackupError("Media manifest format is unsupported.")
        entries = [MediaFileEntry(**item) for item in payload.get("files", [])]
        with zipfile.ZipFile(archive) as bundle:
            members = {_safe_relative(name).as_posix() for name in bundle.namelist()}
            expected = {item.path for item in entries}
            if members != expected:
                raise MediaBackupError("Media archive contents do not match its manifest.")
            parent = destination.parent
            parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix="vayujit-media-restore-", dir=parent))
            try:
                for item in entries:
                    target = staging / Path(_safe_relative(item.path))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(item.path) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    if (
                        target.stat().st_size != item.size_bytes
                        or _checksum(target) != item.checksum_sha256
                    ):
                        raise MediaBackupError("Media checksum or size verification failed.")
                staging.replace(destination)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as error:
        raise MediaBackupError("Media restore input is invalid or corrupt.") from error
    return {"files": len(entries), "lineage": payload.get("lineage", {})}
