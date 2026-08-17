from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context
from test_ai_video_bulk_e2e import bulk_payload, create_products, run_worker

from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import get_settings
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import storage_path
from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
from vayujit_api.video.models import VideoGeneration, VideoOutput
from vayujit_api.video.service import cleanup_video_temp_files

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def _counts(db: Any) -> dict[str, int]:
    models = {
        "parents": VideoBulkOperation,
        "children": VideoBulkChild,
        "generations": VideoGeneration,
        "outputs": VideoOutput,
        "media": MediaAsset,
        "jobs": AIStudioJob,
        "attempts": AIStudioJobAttempt,
        "audit": AuditEvent,
    }
    return {
        name: int(db.scalar(select(func.count()).select_from(model)) or 0)
        for name, model in models.items()
    }


def _files() -> dict[str, int]:
    root = Path(get_settings().media_storage_directory).resolve()
    return {str(path): path.stat().st_size for path in root.rglob("*") if path.is_file()}


def _orphan_counts(db: Any) -> dict[str, int]:
    generation_ids = select(VideoGeneration.id)
    media_ids = select(MediaAsset.id)
    parent_ids = select(VideoBulkOperation.id)
    child_ids = select(VideoBulkChild.id)
    job_ids = select(AIStudioJob.id)
    return {
        "orphan_parent": int(
            db.scalar(
                select(func.count())
                .select_from(VideoBulkOperation)
                .where(VideoBulkOperation.owner_id.is_(None))
            )
            or 0
        ),
        "orphan_child": int(
            db.scalar(
                select(func.count())
                .select_from(VideoBulkChild)
                .where(~VideoBulkChild.bulk_id.in_(parent_ids))
            )
            or 0
        ),
        "orphan_generation": int(
            db.scalar(
                select(func.count())
                .select_from(VideoGeneration)
                .where(VideoGeneration.id.is_(None))
            )
            or 0
        ),
        "orphan_output": int(
            db.scalar(
                select(func.count())
                .select_from(VideoOutput)
                .where(~VideoOutput.generation_id.in_(generation_ids))
            )
            or 0
        ),
        "orphan_media": int(
            db.scalar(
                select(func.count()).select_from(MediaAsset).where(MediaAsset.owner_id.is_(None))
            )
            or 0
        ),
        "orphan_job": int(
            db.scalar(select(func.count()).select_from(AIStudioJob).where(AIStudioJob.id.is_(None)))
            or 0
        ),
        "orphan_attempt": int(
            db.scalar(
                select(func.count())
                .select_from(AIStudioJobAttempt)
                .where(~AIStudioJobAttempt.job_id.in_(job_ids))
            )
            or 0
        ),
        "broken_output_media": int(
            db.scalar(
                select(func.count()).select_from(VideoOutput).where(VideoOutput.media_id.is_(None))
            )
            or 0
        ),
        "broken_child_generation": int(
            db.scalar(
                select(func.count())
                .select_from(VideoBulkChild)
                .where(VideoBulkChild.generation_id.is_(None))
            )
            or 0
        ),
        "broken_child_output": int(
            db.scalar(
                select(func.count())
                .select_from(VideoBulkChild)
                .where(VideoBulkChild.output_id.is_(None))
            )
            or 0
        ),
        "unused_media_ids": int(
            db.scalar(
                select(func.count()).select_from(MediaAsset).where(MediaAsset.id.not_in(media_ids))
            )
            or 0
        ),
        "orphan_reference_sentinel": int(
            db.scalar(
                select(func.count())
                .select_from(VideoBulkChild)
                .where(VideoBulkChild.id.not_in(child_ids))
            )
            or 0
        ),
    }


def test_canonical_15_output_storage_growth_orphans_and_cleanup_are_exact(
    client: Any, tmp_path: Path
) -> None:
    context = setup_context(client)
    products = create_products(client, context["product"], 5)
    payload = bulk_payload(products, "bulk-integrity-canonical-15")
    before_files = _files()
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        before = _counts(db)

    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    assert run_worker("bulk-integrity-worker") == 15
    status = client.get(f"/api/v1/ai/video/bulk/{queued.json()['id']}", headers=ORIGIN)
    assert status.status_code == 200, status.text

    with test_ai_integration.factory() as db:
        after = _counts(db)
        deltas = {key: after[key] - before[key] for key in before}
        assert deltas == {
            "parents": 1,
            "children": 15,
            "generations": 15,
            "outputs": 15,
            "media": 15,
            "jobs": 15,
            "attempts": 15,
            "audit": 61,
        }
        media = list(db.scalars(select(MediaAsset)))
        outputs = list(db.scalars(select(VideoOutput)))
        assert len({item.storage_key for item in media}) == 15
        assert len({item.checksum_sha256 for item in media}) == 15
        assert {item.media_id for item in outputs} == {item.id for item in media}
        assert _orphan_counts(db) == {
            "orphan_parent": 0,
            "orphan_child": 0,
            "orphan_generation": 0,
            "orphan_output": 0,
            "orphan_media": 0,
            "orphan_job": 0,
            "orphan_attempt": 0,
            "broken_output_media": 0,
            "broken_child_generation": 0,
            "broken_child_output": 0,
            "unused_media_ids": 0,
            "orphan_reference_sentinel": 0,
        }
        for item in media:
            assert storage_path(item.storage_key).is_file()

    after_files = _files()
    new_files = {name: size for name, size in after_files.items() if name not in before_files}
    new_final_files = {
        name: size for name, size in new_files.items() if "video-checkpoints" not in name
    }
    new_checkpoint_files = {
        name: size for name, size in new_files.items() if "video-checkpoints" in name
    }
    assert len(new_final_files) == 15
    assert len(new_checkpoint_files) == 15
    assert sum(new_files.values()) == sum(new_final_files.values()) + sum(
        new_checkpoint_files.values()
    )
    checkpoint_cleanup = cleanup_video_temp_files(list(new_checkpoint_files))
    assert checkpoint_cleanup == {"removed": 15, "skipped": 0, "dry_run": False}
    assert cleanup_video_temp_files(list(new_checkpoint_files)) == {
        "removed": 0,
        "skipped": 0,
        "dry_run": False,
    }

    cleanup_root = Path(get_settings().media_storage_directory).resolve() / "acceptance-cleanup"
    cleanup_root.mkdir(parents=True, exist_ok=True)
    temp_paths = [cleanup_root / f"state-{index}.tmp" for index in range(11)]
    for path in temp_paths:
        path.write_bytes(b"temporary checkpoint")
    first = cleanup_video_temp_files([str(path) for path in temp_paths])
    second = cleanup_video_temp_files([str(path) for path in temp_paths])
    assert first == {"removed": 11, "skipped": 0, "dry_run": False}
    assert second == {"removed": 0, "skipped": 0, "dry_run": False}
    assert all(not path.exists() for path in temp_paths)
    assert all(Path(name).is_file() for name in new_final_files)
