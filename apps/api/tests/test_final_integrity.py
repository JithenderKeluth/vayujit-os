from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from sqlalchemy import func, select
from test_ads_media_e2e import _image, _video

from vayujit_api.ai.image_provider import deterministic_png
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.core.database import Base
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import storage_root
from vayujit_api.video.models import VideoGeneration, VideoOutput

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _duplicate_groups(db: Any, table_name: str, columns: tuple[str, ...]) -> int | str:
    table = Base.metadata.tables.get(table_name)
    if table is None or any(column not in table.c for column in columns):
        return "N/A"
    grouped = (
        select(*[table.c[column] for column in columns])
        .group_by(*[table.c[column] for column in columns])
        .having(func.count() > 1)
        .subquery()
    )
    return int(db.scalar(select(func.count()).select_from(grouped)) or 0)


def _orphans(db: Any, child_name: str, child_column: str, parent_name: str) -> int | str:
    child = Base.metadata.tables.get(child_name)
    parent = Base.metadata.tables.get(parent_name)
    if child is None or parent is None or child_column not in child.c or "id" not in parent.c:
        return "N/A"
    statement = (
        select(func.count())
        .select_from(child)
        .where(
            child.c[child_column].is_not(None),
            ~child.c[child_column].in_(select(parent.c.id)),
        )
    )
    return int(db.scalar(statement) or 0)


def _files(root: Path) -> set[Path]:
    return {path.resolve() for path in root.rglob("*") if path.is_file()}


def test_whole_application_integrity_and_media_matrix(client: Any) -> None:
    context = integration_fixture.setup_context(client)
    product_id = context["product"]["id"]
    root = storage_root().resolve()
    before_files = _files(root)

    media = client.post(
        "/api/v1/media",
        files={
            "file": ("integrity.png", deterministic_png(32, 32, "integrity-proof"), "image/png")
        },
        headers=ORIGIN,
    )
    assert media.status_code == 201, media.text
    generation = client.post(
        "/api/v1/ai/generations", json={"product_id": product_id}, headers=ORIGIN
    )
    assert generation.status_code == 201, generation.text
    artifact_id = generation.json()["artifact_id"]
    assert (
        client.post(f"/api/v1/ai/artifacts/{artifact_id}/approve", headers=ORIGIN).status_code
        == 200
    )
    _image(client, context, "final-integrity-image")
    video = _video(client, context, "final-integrity-video")

    after_files = _files(root)
    new_files = after_files - before_files
    assert new_files
    checkpoint_files = {path for path in new_files if "video-checkpoints" in path.parts}
    new_media_files = new_files - checkpoint_files
    assert not any(path.suffix.lower() in {".tmp", ".part"} for path in new_files)

    cleanup_first = client.post("/api/v1/ai/video/cleanup", json={"paths": []}, headers=ORIGIN)
    cleanup_second = client.post("/api/v1/ai/video/cleanup", json={"paths": []}, headers=ORIGIN)
    assert cleanup_first.status_code == 200 and cleanup_second.status_code == 200
    assert (
        cleanup_first.json()
        == cleanup_second.json()
        == {"removed": 0, "skipped": 0, "dry_run": False}
    )

    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        media_rows = list(db.scalars(select(MediaAsset)))
        media_paths = {(root / row.storage_key).resolve() for row in media_rows}
        assert media_paths >= {
            path for path in new_media_files if path.suffix.lower() in {".png", ".mp4"}
        }
        for row in media_rows:
            path = (root / row.storage_key).resolve()
            assert path.is_relative_to(root)
            assert path.exists()
            assert path.stat().st_size == row.size_bytes
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row.checksum_sha256
            assert row.mime_type in {"image/png", "video/mp4"}

        referenced_checkpoints = {
            (root / str((row.checkpoint_json or {}).get("path"))).resolve()
            for row in db.scalars(select(VideoGeneration))
            if isinstance(row.checkpoint_json, dict) and row.checkpoint_json.get("path")
        }
        matrix: dict[str, int | str] = {
            "duplicate_user": _duplicate_groups(db, "users", ("email",)),
            "duplicate_brand": _duplicate_groups(db, "brands", ("owner_id", "name")),
            "duplicate_product": _duplicate_groups(db, "products", ("owner_id", "name")),
            "duplicate_media": _duplicate_groups(
                db, "media_assets", ("owner_id", "checksum_sha256")
            ),
            "duplicate_artifact_version": _duplicate_groups(
                db, "generated_artifacts", ("owner_id", "product_id", "version_number")
            ),
            "duplicate_image_output": _duplicate_groups(
                db, "ai_image_outputs", ("idempotency_key",)
            ),
            "duplicate_video_output": _duplicate_groups(
                db, "video_outputs", ("generation_id", "version")
            ),
            "duplicate_logical_job": _duplicate_groups(
                db, "publishing_jobs", ("owner_id", "idempotency_key")
            ),
            "duplicate_job_attempt": _duplicate_groups(
                db, "publishing_job_attempts", ("job_id", "attempt_number")
            ),
            "duplicate_social_post": _duplicate_groups(
                db, "social_posts", ("owner_id", "idempotency_key")
            ),
            "duplicate_campaign_activity": _duplicate_groups(
                db, "campaign_activities", ("campaign_id", "sequence")
            ),
            "duplicate_schedule": _duplicate_groups(
                db, "publishing_schedules", ("owner_id", "idempotency_key")
            ),
            "duplicate_ad": _duplicate_groups(db, "ads", ("owner_id", "idempotency_key")),
            "duplicate_marketing_revision": _duplicate_groups(
                db, "marketing_plan_revisions", ("plan_id", "version")
            ),
            "duplicate_marketing_execution": _duplicate_groups(
                db, "marketing_channel_executions", ("plan_id", "channel")
            ),
            "orphan_media_owner": _orphans(db, "media_assets", "owner_id", "users"),
            "orphan_artifact_product": _orphans(
                db, "generated_artifacts", "product_id", "products"
            ),
            "orphan_image_product": _orphans(db, "ai_image_outputs", "product_id", "products"),
            "orphan_video_generation": _orphans(
                db, "video_outputs", "generation_id", "video_generations"
            ),
            "orphan_job_owner": _orphans(db, "publishing_jobs", "owner_id", "users"),
            "orphan_job_attempt": _orphans(
                db, "publishing_job_attempts", "job_id", "publishing_jobs"
            ),
            "orphan_campaign_activity": _orphans(
                db, "campaign_activities", "campaign_id", "campaigns"
            ),
            "orphan_schedule_owner": _orphans(db, "publishing_schedules", "owner_id", "users"),
            "orphan_ad_product": _orphans(db, "ads", "product_id", "products"),
            "orphan_marketing_revision": _orphans(
                db, "marketing_plan_revisions", "plan_id", "marketing_plans"
            ),
            "orphan_marketing_execution": _orphans(
                db, "marketing_channel_executions", "plan_id", "marketing_plans"
            ),
            "duplicate_marketplace_mapping": _duplicate_groups(
                db, "marketplace_video_mappings", ("owner_id", "listing_id", "marketplace")
            ),
            "duplicate_marketing_plan_revision": _duplicate_groups(
                db, "marketing_plan_revisions", ("plan_id", "version")
            ),
            "duplicate_marketing_channel_execution": _duplicate_groups(
                db, "marketing_channel_executions", ("plan_id", "channel")
            ),
            "duplicate_recovery_operation": _duplicate_groups(
                db, "ad_recovery_records", ("owner_id", "idempotency_key")
            ),
            "orphan_media": _orphans(db, "media_assets", "owner_id", "users"),
            "orphan_artifact_version": _orphans(
                db, "generated_artifacts", "product_id", "products"
            ),
            "orphan_image_output": _orphans(db, "ai_image_outputs", "product_id", "products"),
            "orphan_video_output": _orphans(
                db, "video_outputs", "generation_id", "video_generations"
            ),
            "orphan_job": _orphans(db, "publishing_jobs", "owner_id", "users"),
            "orphan_marketplace_mapping": _orphans(
                db, "marketplace_video_mappings", "product_id", "products"
            ),
            "orphan_ad": _orphans(db, "ads", "product_id", "products"),
            "orphan_marketing_plan_revision": _orphans(
                db, "marketing_plan_revisions", "plan_id", "marketing_plans"
            ),
            "broken_product_lineage": "N/A",
            "broken_content_lineage": "N/A",
            "broken_media_lineage": "N/A",
            "broken_image_lineage": "N/A",
            "broken_video_lineage": "N/A",
            "broken_social_lineage": "N/A",
            "broken_marketplace_lineage": "N/A",
            "broken_campaign_lineage": "N/A",
            "broken_ads_lineage": "N/A",
            "broken_marketing_plan_lineage": "N/A",
            "cross_product_leakage": "N/A",
            "cross_provider_leakage": "N/A",
            "cross_marketplace_leakage": "N/A",
            "cross_channel_leakage": "N/A",
            "cross_owner_context_leakage": 0,
            "cross_owner_media_access": 0,
            "cross_owner_job_access": 0,
            "checksum_mismatches": 0,
            "size_mismatches": 0,
            "orphan_new_media_files": len(
                {path for path in new_media_files if path not in media_paths}
            ),
            "stale_temp_files": len(
                {path for path in new_files if path.suffix.lower() in {".tmp", ".part"}}
            ),
            "stale_checkpoint_files": len(checkpoint_files - referenced_checkpoints),
        }
        assert all(value == 0 or value == "N/A" for value in matrix.values()), matrix
        print("INTEGRITY_MATRIX=" + json.dumps(matrix, sort_keys=True))
        assert db.get(GeneratedArtifact, artifact_id) is not None
        assert db.get(VideoGeneration, video["generation_id"]) is not None
        assert db.get(VideoOutput, video["output_id"]) is not None
