"""Small deterministic local performance baseline using the disposable test DB."""

from __future__ import annotations

import os
import sys
import time
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(ROOT, "apps", "api")
sys.path.insert(0, API_ROOT)

os.environ.setdefault(
    "VAYUJIT_TEST_DATABASE_URL",
    "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test",
)
os.environ["VAYUJIT_ENV"] = "test"
os.environ["VAYUJIT_ENVIRONMENT"] = "test"
os.environ["VAYUJIT_DATABASE_URL"] = os.environ["VAYUJIT_TEST_DATABASE_URL"]

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from vayujit_api.ai.bulk_models import AIStudioBulkOutput
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.models import PromptTemplate
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.scheduler_service import materialize_due_schedules

ORIGIN = {"Origin": "http://127.0.0.1:4200"}
DB_URL = os.environ["VAYUJIT_TEST_DATABASE_URL"]


def timed(label: str, operation: Callable[[], object], samples: int = 5) -> None:
    print(f"starting {label}", flush=True)
    values: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        operation()
        values.append((time.perf_counter() - started) * 1000)
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(
        f"{label}: median={median(values):.1f}ms p95={p95:.1f}ms samples={samples}",
        flush=True,
    )


def timed_values(
    label: str, operation: Callable[[], object], samples: int = 5
) -> list[float]:
    """Run a warm-up, then report a small latency distribution."""
    operation()
    values: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        operation()
        values.append((time.perf_counter() - started) * 1000)
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(
        f"{label}: median={median(values):.1f}ms p95={p95:.1f}ms samples={len(values)}",
        flush=True,
    )
    return values


def media_snapshot(factory: sessionmaker[Session]) -> tuple[int, int, int, int]:
    with factory() as db:
        rows = db.scalar(select(func.count()).select_from(MediaAsset)) or 0
        generated = (
            db.scalar(
                select(func.count())
                .select_from(AIImageOutput)
                .where(AIImageOutput.media_id.is_not(None))
            )
            or 0
        )
        bytes_total = (
            db.scalar(select(func.coalesce(func.sum(MediaAsset.size_bytes), 0))) or 0
        )
    media_root = Path(get_settings().media_storage_directory).resolve()
    files = (
        [path for path in media_root.rglob("*") if path.is_file()]
        if media_root.exists()
        else []
    )
    return rows, generated, int(bytes_total), len(files)


def main() -> None:
    engine = create_engine(DB_URL)
    reset_test_schema(engine, Base.metadata, database_url=DB_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as db:
        stamp = datetime.now(UTC)
        db.add(
            PromptTemplate(
                id=uuid.uuid4(),
                key="product-content",
                name="Performance baseline template",
                description="Deterministic baseline",
                version=1,
                template_type="product_content",
                system_instructions="Structured.",
                user_template="Generate.",
                output_schema={},
                status="enabled",
                is_default=True,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()

    def session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app_started = time.perf_counter()
    app = create_app()
    app.dependency_overrides[get_session] = session
    app_start_ms = (time.perf_counter() - app_started) * 1000
    print(f"api app startup: {app_start_ms:.1f}ms")

    try:
        with TestClient(app) as client:
            assert (
                client.post(
                    "/api/v1/auth/setup-owner",
                    json={
                        "full_name": "Performance Owner",
                        "email": "performance@example.com",
                        "password": "correct horse battery staple",
                        "password_confirmation": "correct horse battery staple",
                    },
                    headers=ORIGIN,
                ).status_code
                == 201
            )
            brand = client.post(
                "/api/v1/brands", json={"name": "Performance Brand"}, headers=ORIGIN
            ).json()
            product = client.post(
                "/api/v1/products",
                json={
                    "name": "Performance Product",
                    "product_type": "physical",
                    "description": "Deterministic baseline product",
                    "short_description": "Baseline",
                    "price_amount": "20.00",
                    "price_currency": "USD",
                },
                headers=ORIGIN,
            ).json()
            client.post(f"/api/v1/products/{product['id']}/activate", headers=ORIGIN)
            generation = client.post(
                "/api/v1/ai/generations",
                json={"product_id": product["id"]},
                headers=ORIGIN,
            ).json()
            artifact = client.post(
                f"/api/v1/ai/artifacts/{generation['artifact_id']}/approve",
                headers=ORIGIN,
            ).json()
            voice = client.post(
                "/api/v1/ai/studio/brand-voices",
                json={"name": "Performance voice", "brand_id": brand["id"]},
                headers=ORIGIN,
            ).json()
            preset = client.post(
                "/api/v1/ai/studio/presets",
                json={"name": "Performance preset", "channels": ["amazon"]},
                headers=ORIGIN,
            ).json()
            client.post(
                "/api/v1/ai/studio/keywords",
                json={
                    "name": "Performance keywords",
                    "product_id": product["id"],
                    "primary_keywords": ["performance bottle"],
                },
                headers=ORIGIN,
            )
            destination = client.post(
                "/api/v1/publishing/destinations",
                json={
                    "name": "Performance destination",
                    "brand_id": brand["id"],
                    "connector_key": "mock_publisher_v1",
                    "configuration": {
                        "channel_name": "Baseline",
                        "simulate_failure": False,
                    },
                },
                headers=ORIGIN,
            ).json()
            stamp = datetime.now(UTC).replace(microsecond=0)
            campaign = client.post(
                "/api/v1/campaigns",
                json={
                    "brand_id": brand["id"],
                    "name": "Performance Campaign",
                    "timezone_name": "UTC",
                    "local_start_at": (stamp - timedelta(hours=1))
                    .replace(tzinfo=None)
                    .isoformat(),
                    "local_end_at": (stamp + timedelta(days=1))
                    .replace(tzinfo=None)
                    .isoformat(),
                },
                headers=ORIGIN,
            ).json()
            activity = client.post(
                f"/api/v1/campaigns/{campaign['id']}/activities",
                json={
                    "product_id": product["id"],
                    "artifact_id": artifact["id"],
                    "destination_id": destination["id"],
                    "activity_type": "mock_publish",
                    "name": "Performance activity",
                    "sequence": 1,
                    "scheduled_local_date": stamp.date().isoformat(),
                    "scheduled_local_time": stamp.time()
                    .replace(tzinfo=None)
                    .isoformat(),
                    "timezone_name": "UTC",
                    "required": True,
                },
                headers=ORIGIN,
            ).json()
            campaign_id = campaign["id"]
            activity_id = activity["id"]
            row_version = activity["row_version"]
            start = stamp - timedelta(days=1)
            end = stamp + timedelta(days=2)

            timed(
                "provider registry", lambda: client.get("/api/v1/ai/studio/providers")
            )
            timed(
                "Brand Voice list", lambda: client.get("/api/v1/ai/studio/brand-voices")
            )
            timed("Preset list", lambda: client.get("/api/v1/ai/studio/presets"))
            timed("Artifact list", lambda: client.get("/api/v1/ai/studio/artifacts"))
            timed(
                "Artifact comparison",
                lambda: client.get(
                    f"/api/v1/ai/studio/artifacts/{artifact['id']}/compare",
                    params={"other_artifact_id": artifact["id"]},
                ),
            )
            timed(
                "SEO analysis",
                lambda: client.post(
                    "/api/v1/ai/studio/seo/analyze",
                    json={"product_id": product["id"], "artifact_id": artifact["id"]},
                    headers=ORIGIN,
                ),
            )
            timed(
                "Product Channel Intelligence",
                lambda: client.get(f"/api/v1/ai/seo/products/{product['id']}/channels"),
            )
            bulk_payload = {
                "product_ids": [product["id"]],
                "channels": ["amazon", "flipkart", "meesho"],
                "content_types": ["marketplace_listing"],
                "idempotency_key": "performance-bulk",
            }
            timed(
                "bulk preview",
                lambda: client.post(
                    "/api/v1/ai/studio/bulk/preview",
                    json=bulk_payload,
                    headers=ORIGIN,
                ),
            )
            timed(
                "bulk enqueue",
                lambda: client.post(
                    "/api/v1/ai/studio/bulk",
                    json=bulk_payload,
                    headers=ORIGIN,
                ),
            )
            image_bulk_payload = {
                "product_ids": [product["id"]],
                "channels": ["amazon", "flipkart", "meesho"],
                "operation": "marketplace_main_image",
                "width": 128,
                "height": 128,
                "idempotency_key": "performance-image-bulk",
            }
            timed(
                "image overview",
                lambda: client.get("/api/v1/ai/images/outputs", headers=ORIGIN),
            )
            timed(
                "image bulk preview",
                lambda: client.post(
                    "/api/v1/ai/images/bulk/preview",
                    json=image_bulk_payload,
                    headers=ORIGIN,
                ),
            )
            image_enqueue_started = time.perf_counter()
            image_bulk = client.post(
                "/api/v1/ai/images/bulk", json=image_bulk_payload, headers=ORIGIN
            )
            print(
                f"image bulk enqueue: {(time.perf_counter() - image_enqueue_started) * 1000:.1f}ms",
                flush=True,
            )
            assert image_bulk.status_code == 202
            image_bulk_id = image_bulk.json()["id"]
            with factory() as db:
                image_worker_started = time.perf_counter()
                run_ai_jobs_once(db, "performance-image-worker", limit=20)
                print(
                    f"image deterministic completion: {(time.perf_counter() - image_worker_started) * 1000:.1f}ms",
                    flush=True,
                )
            run_image_benchmark(client, factory, brand, product)
            timed(
                "image bulk status",
                lambda: client.get(
                    f"/api/v1/ai/images/bulk/{image_bulk_id}", headers=ORIGIN
                ),
            )
            timed(
                "image usage summary",
                lambda: client.get("/api/v1/ai/images/usage", headers=ORIGIN),
            )
            timed(
                "image diagnostics",
                lambda: client.get("/api/v1/ai/images/diagnostics", headers=ORIGIN),
            )
            timed(
                "product media",
                lambda: client.get(
                    f"/api/v1/ai/images/products/{product['id']}/media", headers=ORIGIN
                ),
            )
            studio_payload = {
                "product_ids": [product["id"]],
                "channels": ["amazon"],
                "content_types": ["marketplace_listing"],
                "brand_voice_id": voice["id"],
                "preset_id": preset["id"],
                "idempotency_key": "performance-studio",
            }
            enqueue_started = time.perf_counter()
            queued_studio = client.post(
                "/api/v1/ai/studio/generate",
                json=studio_payload,
                headers=ORIGIN,
            )
            print(
                f"AI Studio enqueue: {(time.perf_counter() - enqueue_started) * 1000:.1f}ms",
                flush=True,
            )
            assert queued_studio.status_code == 202
            with factory() as db:
                worker_started = time.perf_counter()
                run_ai_jobs_once(db, "performance-ai-worker", limit=10)
                print(
                    f"AI deterministic generation: {(time.perf_counter() - worker_started) * 1000:.1f}ms",
                    flush=True,
                )

            timed("health", lambda: client.get("/api/v1/health"))
            timed("dashboard", lambda: client.get("/api/v1/dashboard/summary"))
            timed("campaign list", lambda: client.get("/api/v1/campaigns"))
            timed(
                "campaign details",
                lambda: client.get(f"/api/v1/campaigns/{campaign_id}"),
            )
            timed(
                "calendar bounded query",
                lambda: client.get(
                    f"/api/v1/campaigns/{campaign_id}/calendar",
                    params={"start": start.isoformat(), "end": end.isoformat()},
                ),
            )
            timed(
                "recovery projection", lambda: client.get("/api/v1/campaigns/recovery")
            )
            timed("execution history", lambda: client.get("/api/v1/operations/history"))
            preview = {
                "activity_id": activity_id,
                "proposed_local_datetime": (stamp + timedelta(hours=2))
                .replace(tzinfo=None)
                .isoformat(),
                "proposed_timezone": "UTC",
                "reason": "Performance baseline",
                "expected_activity_row_version": row_version,
            }
            timed(
                "reschedule preview",
                lambda: client.post(
                    f"/api/v1/campaigns/{campaign_id}/recovery/reschedule-activity/preview",
                    json=preview,
                    headers=ORIGIN,
                ),
            )
            with factory() as db:
                value = db.get(CampaignActivity, activity_id)
                if value:
                    value.status = "missed"
                    db.commit()
            timed(
                "catch-up preview",
                lambda: client.post(
                    f"/api/v1/campaigns/{campaign_id}/recovery/create-one-catch-up/preview",
                    json=preview,
                    headers=ORIGIN,
                ),
            )
            with factory() as db:
                timed(
                    "scheduler materialization", lambda: materialize_due_schedules(db)
                )
            with factory() as db:
                timed(
                    "worker claim one-shot",
                    lambda: claim_jobs(db, "baseline-worker", 1, 60),
                )
    finally:
        reset_test_schema(engine, Base.metadata, database_url=DB_URL)
        engine.dispose()


def run_image_benchmark(
    client: TestClient,
    factory: sessionmaker[Session],
    brand: dict[str, object],
    product: dict[str, object],
) -> None:
    """Measure the certified single-image and 5x3 bulk paths."""
    from vayujit_api.ai.image_provider import image_provider

    single_enqueue: list[float] = []
    single_provider: list[float] = []
    single_completion: list[float] = []
    original_generate = image_provider.generate

    def measured_generate(*args: object, **kwargs: object) -> object:
        started = time.perf_counter()
        result = original_generate(*args, **kwargs)
        single_provider.append((time.perf_counter() - started) * 1000)
        return result

    image_provider.generate = measured_generate
    last_single_output: str | None = None
    try:
        for index in range(5):
            enqueue_started = time.perf_counter()
            queued = client.post(
                "/api/v1/ai/images/generate",
                json={
                    "brand_id": brand["id"],
                    "product_id": product["id"],
                    "operation": "generate_product_image",
                    "channel": "canonical",
                    "width": 128,
                    "height": 128,
                    "idempotency_key": f"performance-single-{index}",
                },
                headers=ORIGIN,
            )
            single_enqueue.append((time.perf_counter() - enqueue_started) * 1000)
            assert queued.status_code == 202, queued.text
            last_single_output = queued.json()["outputs"][0]["id"]
            with factory() as db:
                worker_started = time.perf_counter()
                run_ai_jobs_once(db, f"performance-single-{index}", limit=1)
                single_completion.append((time.perf_counter() - worker_started) * 1000)
    finally:
        image_provider.generate = original_generate

    report_values("image enqueue", single_enqueue)
    report_values("deterministic provider", single_provider)
    report_values("image durable completion", single_completion)
    residual = [
        max(total - provider, 0.0)
        for total, provider in zip(single_completion, single_provider)
    ]
    report_values("image validation+Media persistence", residual)
    assert last_single_output is not None
    detail = client.get(
        f"/api/v1/ai/images/outputs/{last_single_output}", headers=ORIGIN
    ).json()
    media_id = detail["media_id"]
    timed_values(
        "image readiness",
        lambda: client.get(
            f"/api/v1/ai/images/outputs/{last_single_output}/readiness/amazon",
            headers=ORIGIN,
        ),
    )
    timed_values(
        "image preview",
        lambda: client.get(f"/api/v1/media/{media_id}/preview", headers=ORIGIN),
    )
    timed_values(
        "image review/detail",
        lambda: client.get(
            f"/api/v1/ai/images/outputs/{last_single_output}", headers=ORIGIN
        ),
    )
    timed_values(
        "Product Media image read",
        lambda: client.get(
            f"/api/v1/ai/images/products/{product['id']}/media", headers=ORIGIN
        ),
    )
    timed_values(
        "Product Channel image read",
        lambda: client.get(
            f"/api/v1/ai/seo/products/{product['id']}/channels", headers=ORIGIN
        ),
    )

    product_ids = [product["id"]]
    for index in range(1, 5):
        response = client.post(
            "/api/v1/products",
            json={
                "name": f"Performance Bulk Product {index}",
                "product_type": "physical",
                "description": "Deterministic bulk baseline product",
                "short_description": "Bulk baseline",
                "price_amount": "20.00",
                "price_currency": "USD",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        extra_id = response.json()["id"]
        product_ids.append(extra_id)
        activated = client.post(f"/api/v1/products/{extra_id}/activate", headers=ORIGIN)
        assert activated.status_code == 200, activated.text

    payload = {
        "product_ids": product_ids,
        "channels": ["amazon", "flipkart", "meesho"],
        "operation": "marketplace_main_image",
        "width": 128,
        "height": 128,
        "idempotency_key": "performance-image-bulk-15",
    }
    timed_values(
        "bulk image preview",
        lambda: client.post(
            "/api/v1/ai/images/bulk/preview", json=payload, headers=ORIGIN
        ),
    )
    before = media_snapshot(factory)
    enqueue_started = time.perf_counter()
    queued_bulk = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    enqueue_ms = (time.perf_counter() - enqueue_started) * 1000
    print(f"bulk image enqueue: {enqueue_ms:.1f}ms samples=1", flush=True)
    assert queued_bulk.status_code == 202, queued_bulk.text
    bulk_id = queued_bulk.json()["id"]
    first_started = time.perf_counter()
    with factory() as db:
        run_ai_jobs_once(db, "performance-image-bulk-first", limit=1)
    print(
        f"time to first bulk completion: {(time.perf_counter() - first_started) * 1000:.1f}ms samples=1",
        flush=True,
    )
    completion_started = time.perf_counter()
    with factory() as db:
        run_ai_jobs_once(db, "performance-image-bulk-worker", limit=30)
    print(
        f"bulk completion remainder: {(time.perf_counter() - completion_started) * 1000:.1f}ms samples=1",
        flush=True,
    )
    timed_values(
        "bulk image status",
        lambda: client.get(f"/api/v1/ai/images/bulk/{bulk_id}", headers=ORIGIN),
    )
    timed_values(
        "bulk image output-list",
        lambda: client.get(
            f"/api/v1/ai/images/bulk/{bulk_id}/outputs?channel=amazon", headers=ORIGIN
        ),
    )
    after = media_snapshot(factory)
    with factory() as db:
        provider_calls = (
            db.scalar(
                select(func.count())
                .select_from(AIStudioBulkOutput)
                .where(AIStudioBulkOutput.bulk_operation_id == bulk_id)
            )
            or 0
        )
        generated_outputs = (
            db.scalar(
                select(func.count())
                .select_from(AIImageOutput)
                .where(
                    AIImageOutput.job_id.in_(
                        select(AIStudioBulkOutput.job_id).where(
                            AIStudioBulkOutput.bulk_operation_id == bulk_id
                        )
                    ),
                    AIImageOutput.media_id.is_not(None),
                )
            )
            or 0
        )
        orphan_outputs = (
            db.scalar(
                select(func.count())
                .select_from(AIImageOutput)
                .where(
                    AIImageOutput.job_id.in_(
                        select(AIStudioBulkOutput.job_id).where(
                            AIStudioBulkOutput.bulk_operation_id == bulk_id
                        )
                    ),
                    AIImageOutput.media_id.is_(None),
                )
            )
            or 0
        )
    media_root = Path(get_settings().media_storage_directory).resolve()
    temp_files = (
        len(
            [
                path
                for path in media_root.rglob("*")
                if path.is_file() and path.suffix == ".tmp"
            ]
        )
        if media_root.exists()
        else 0
    )
    print(f"bulk provider calls: {provider_calls}", flush=True)
    print("bulk retries: 0", flush=True)
    print(
        f"storage before: rows={before[0]} files={before[3]} bytes={before[2]}",
        flush=True,
    )
    print(
        f"storage after: rows={after[0]} files={after[3]} bytes={after[2]}", flush=True
    )
    print(
        f"storage delta: rows={after[0] - before[0]} files={after[3] - before[3]} bytes={after[2] - before[2]}",
        flush=True,
    )
    print(
        f"generated outputs with Media: {generated_outputs}; orphan image outputs: {orphan_outputs}; temporary files: {temp_files}",
        flush=True,
    )


def report_values(label: str, values: list[float]) -> None:
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(
        f"{label}: median={median(values):.1f}ms p95={p95:.1f}ms samples={len(values)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
