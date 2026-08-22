from __future__ import annotations

import json
from pathlib import Path

import pytest

from vayujit_api.operations.media_backup import (
    MediaBackupError,
    create_media_backup,
    restore_media_backup,
)


def _media_fixture(root: Path) -> tuple[Path, dict[str, object]]:
    source = root / "media"
    source.mkdir()
    image = source / "owner-000000000001" / "image.png"
    video = source / "owner-000000000001" / "video.mp4"
    image.parent.mkdir()
    image.write_bytes(b"\x89PNG\r\n\x1a\napproved-image")
    video.write_bytes(b"\x00\x00\x00\x18ftypisomapproved-video")
    lineage: dict[str, object] = {
        "owner_id": "00000000-0000-4000-8000-000000000001",
        "product_id": "00000000-0000-4000-8000-000000000002",
        "media_ids": ["00000000-0000-4000-8000-000000000003"],
    }
    return source, lineage


def test_local_media_backup_restore_preserves_files_and_lineage(tmp_path: Path) -> None:
    source, lineage = _media_fixture(tmp_path)
    archive, manifest = create_media_backup(source, tmp_path / "backups", lineage=lineage)
    restored = tmp_path / "restored-media"
    result = restore_media_backup(archive, manifest, restored)

    assert result["files"] == 2
    assert result["lineage"] == lineage
    assert (restored / "owner-000000000001" / "image.png").read_bytes() == (
        source / "owner-000000000001" / "image.png"
    ).read_bytes()
    assert (restored / "owner-000000000001" / "video.mp4").read_bytes() == (
        source / "owner-000000000001" / "video.mp4"
    ).read_bytes()


def test_media_manifest_contains_checksum_size_and_mime(tmp_path: Path) -> None:
    source, _ = _media_fixture(tmp_path)
    _, manifest = create_media_backup(source, tmp_path / "backups")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert {item["mime_type"] for item in payload["files"]} == {
        "image/png",
        "video/mp4",
    }
    assert all(len(item["checksum_sha256"]) == 64 for item in payload["files"])
    assert all(item["size_bytes"] > 0 for item in payload["files"])


@pytest.mark.parametrize("case", ["missing_archive", "missing_manifest", "unsafe_target"])
def test_media_restore_failure_is_non_destructive(tmp_path: Path, case: str) -> None:
    source, _ = _media_fixture(tmp_path)
    archive, manifest = create_media_backup(source, tmp_path / "backups")
    destination = tmp_path / "restore-target"
    destination.mkdir()
    sentinel = destination / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    if case == "missing_archive":
        archive = tmp_path / "missing.zip"
    elif case == "missing_manifest":
        manifest = tmp_path / "missing.json"
    with pytest.raises(MediaBackupError):
        restore_media_backup(archive, manifest, destination)
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_corrupt_media_archive_is_rejected_without_partial_restore(
    tmp_path: Path,
) -> None:
    source, _ = _media_fixture(tmp_path)
    archive, manifest = create_media_backup(source, tmp_path / "backups")
    archive.write_bytes(b"not-a-zip")
    destination = tmp_path / "restored-media"
    with pytest.raises(MediaBackupError):
        restore_media_backup(archive, manifest, destination)
    assert not destination.exists()
