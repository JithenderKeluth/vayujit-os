"""Small deterministic local performance baseline using the disposable test DB."""

from __future__ import annotations

import os
import sys
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Callable

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

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from vayujit_api.ai.models import PromptTemplate  # noqa: E402
from vayujit_api.campaigns.models import CampaignActivity  # noqa: E402
from vayujit_api.core.database import Base, get_session  # noqa: E402
from vayujit_api.core.test_database import reset_test_schema  # noqa: E402
from vayujit_api.main import create_app  # noqa: E402
from vayujit_api.publishing.job_queue import claim_jobs  # noqa: E402
from vayujit_api.publishing.scheduler_service import (
    materialize_due_schedules,
)  # noqa: E402

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


if __name__ == "__main__":
    main()
