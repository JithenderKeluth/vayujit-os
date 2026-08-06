import base64
import os
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Barrier

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.ai.models import PromptTemplate
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.identity.router import attempts
from vayujit_api.identity.service import now
from vayujit_api.main import create_app
from vayujit_api.publishing.connector import ConnectorResult, WordPressConnector
from vayujit_api.publishing.job_queue import (
    claim_jobs,
    recover_expired_leases,
    start_attempt,
)
from vayujit_api.publishing.models import (
    PublishingExecution,
    PublishingJob,
    PublishingJobAttempt,
    PublishingRecoveryRecord,
)
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.schemas import CreateExecution
from vayujit_api.publishing.service import create_execution
from vayujit_api.publishing.shopify_connector import ShopifyThrottle
from vayujit_api.publishing.worker import execute_job
from vayujit_api.workflows.models import WorkflowInstance, WorkflowPublishingWait, WorkflowTemplate

URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
factory: sessionmaker[Session] | None = None


@dataclass
class FakeConnectorState:
    wordpress_posts: dict[int, dict[str, object]] = field(default_factory=dict)
    wordpress_requests: list[tuple[str, str]] = field(default_factory=list)
    shopify_products: dict[str, dict[str, object]] = field(default_factory=dict)
    shopify_requests: list[str] = field(default_factory=list)


connector_state = FakeConnectorState()


@pytest.fixture
def harness(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    global factory
    assert URL and URL.startswith("postgresql")
    engine = create_engine(URL)
    reset_test_schema(engine, Base.metadata, database_url=URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    stamp = now()
    with factory() as db:
        db.add(
            PromptTemplate(
                id=uuid.uuid4(),
                key="product-content",
                name="Product content",
                description="Default",
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
        db.add(
            WorkflowTemplate(
                id=uuid.uuid4(),
                key="product-content-publish",
                name="Scheduled product content",
                description="Generate, approve, and schedule.",
                version=1,
                workflow_type="product_content_publish",
                definition_json={
                    "schema_version": 1,
                    "steps": [
                        {"key": "generate_content", "type": "ai_generate"},
                        {
                            "key": "wait_for_approval",
                            "type": "human_approval",
                            "depends_on": ["generate_content"],
                        },
                        {
                            "key": "publish_content",
                            "type": "publish",
                            "depends_on": ["wait_for_approval"],
                        },
                    ],
                },
                status="enabled",
                is_default=True,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()

    def session() -> Generator[Session, None, None]:
        assert factory is not None
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = session
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", factory)
    connector_state.wordpress_posts.clear()
    connector_state.wordpress_requests.clear()
    connector_state.shopify_products.clear()
    connector_state.shopify_requests.clear()
    posts = connector_state.wordpress_posts

    def wordpress_handler(request: httpx.Request) -> httpx.Response:
        connector_state.wordpress_requests.append((request.method, request.url.path))
        if request.url.path.endswith("/users/me"):
            return httpx.Response(200, json={"id": 1, "name": "Owner"})
        if request.url.path.endswith("/posts") and request.method == "POST":
            body = __import__("json").loads(request.content)
            posts.setdefault(
                81,
                {
                    "id": 81,
                    "status": body["status"],
                    "slug": body["slug"],
                    "link": "http://127.0.0.1/?p=81",
                    "title": {"rendered": body["title"]},
                    "excerpt": {"rendered": body["excerpt"]},
                    "categories": [],
                    "tags": [],
                    "author": 1,
                    "featured_media": 0,
                    "modified_gmt": "2026-08-06T00:00:00",
                },
            )
            return httpx.Response(201, json=posts[81])
        if request.url.path.endswith("/posts/81"):
            return httpx.Response(200, json=posts[81])
        raise AssertionError(request.url.path)

    wordpress = WordPressConnector(
        site_url="http://127.0.0.1",
        username="owner",
        application_password="fake-only",
        timeout_seconds=10,
        environment="development",
        transport=httpx.MockTransport(wordpress_handler),
    )
    monkeypatch.setattr("vayujit_api.publishing.service.connector_for", lambda _value: wordpress)
    monkeypatch.setattr("vayujit_api.publishing.router.connector_for", lambda _value: wordpress)

    class FakeShopify:
        last_throttle = ShopifyThrottle(currently_available=992, restore_rate=50.0)

        def validate(self) -> dict[str, object]:
            return {
                "shop": {
                    "id": "gid://shopify/Shop/1",
                    "name": "Scheduler Store",
                    "primaryDomain": {"host": "test-shop.myshopify.com"},
                }
            }

        def publish(
            self, destination: dict[str, object], snapshot: dict[str, object]
        ) -> ConnectorResult:
            connector_state.shopify_requests.append("publish")
            connector_state.shopify_products.setdefault(
                "gid://shopify/Product/42",
                {
                    "id": "gid://shopify/Product/42",
                    "title": snapshot["product_name"],
                    "status": "DRAFT",
                    "variants": [{"id": "gid://shopify/ProductVariant/42"}],
                    "media": [],
                    "collections": [],
                    "publications": [],
                },
            )
            return ConnectorResult(
                "gid://shopify/Product/42",
                "https://test-shop.myshopify.com/admin/products/42",
                {
                    "product": {
                        "id": "gid://shopify/Product/42",
                        "title": snapshot["product_name"],
                        "status": "DRAFT",
                    },
                    "throttle": self.last_throttle.__dict__,
                },
                remote_status="draft",
                remote_slug="scheduler-product",
            )

        def reconcile(self, remote_id: str) -> ConnectorResult:
            connector_state.shopify_requests.append("reconcile")
            return ConnectorResult(
                remote_id,
                "https://test-shop.myshopify.com/admin/products/42",
                {"id": remote_id, "title": "Scheduler Product", "status": "DRAFT"},
                remote_status="draft",
            )

    shopify = FakeShopify()
    monkeypatch.setattr(
        get_settings(),
        "credential_encryption_key",
        base64.urlsafe_b64encode(b"0" * 32).decode(),
    )
    monkeypatch.setattr("vayujit_api.publishing.shopify.validate_shop_domain", lambda value: value)
    monkeypatch.setattr(
        "vayujit_api.publishing.service.shopify_connector_for", lambda _value: shopify
    )
    monkeypatch.setattr(
        "vayujit_api.publishing.router.shopify_connector_for", lambda _value: shopify
    )
    with TestClient(app) as client:
        yield client, factory
    reset_test_schema(engine, Base.metadata, database_url=URL)
    engine.dispose()


def business(client: TestClient) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Scheduler Owner",
            "email": "scheduler@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    brand = client.post("/api/v1/brands", json={"name": "Scheduler Brand"}, headers=ORIGIN).json()
    product = client.post(
        "/api/v1/products",
        json={
            "name": "Scheduler Product",
            "product_type": "physical",
            "description": "Ready",
            "short_description": "Ready",
            "price_amount": "20.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    ).json()
    client.post(f"/api/v1/products/{product['id']}/activate", headers=ORIGIN)
    generation = client.post(
        "/api/v1/ai/generations", json={"product_id": product["id"]}, headers=ORIGIN
    ).json()
    artifact = client.post(
        f"/api/v1/ai/artifacts/{generation['artifact_id']}/approve", headers=ORIGIN
    ).json()
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Scheduler loopback",
            "brand_id": brand["id"],
            "connector_key": "mock_publisher_v1",
            "configuration": {
                "channel_name": "Scheduler",
                "publication_prefix": "SCH",
                "simulate_failure": False,
                "failure_type": "retryable",
            },
        },
        headers=ORIGIN,
    ).json()
    return product, artifact, destination


def schedule(client: TestClient, artifact_id: object, destination_id: object, name: str) -> str:
    response = client.post(
        "/api/v1/publishing/schedules",
        json={
            "name": name,
            "artifact_id": str(artifact_id),
            "destination_id": str(destination_id),
            "requested_action": "publish",
            "local_scheduled_at": (datetime.now(UTC) - timedelta(minutes=1))
            .replace(tzinfo=None)
            .isoformat(),
            "timezone_name": "UTC",
            "schedule_type": "one_time",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_two_workers_one_job_claim_exactly_once(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    _, artifact, destination = business(client)
    schedule(client, artifact["id"], destination["id"], "One job")
    with sessions() as db:
        assert materialize_due_schedules(db) == 1
    barrier = Barrier(2)

    def compete(worker: str) -> list[uuid.UUID]:
        with sessions() as db:
            barrier.wait()
            return claim_jobs(db, worker, 1, 60)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ["worker-a", "worker-b"]))
    assert sum(len(value) for value in results) == 1
    with sessions() as db:
        job = db.scalar(select(PublishingJob))
        assert job and job.state == "claimed" and job.claim_count == 1
        assert job.lease_owner in {"worker-a", "worker-b"}


def test_two_workers_two_jobs_and_priority_ordering(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    _, artifact, destination = business(client)
    schedule(client, artifact["id"], destination["id"], "First")
    schedule(client, artifact["id"], destination["id"], "Second")
    with sessions() as db:
        assert materialize_due_schedules(db) == 2
        jobs = list(db.scalars(select(PublishingJob).order_by(PublishingJob.created_at)))
        jobs[1].priority = 10
        db.commit()
        first = claim_jobs(db, "priority-worker", 1, 60)
        assert first == [jobs[1].id]
    with sessions() as db:
        second = claim_jobs(db, "other-worker", 1, 60)
        assert len(second) == 1 and second[0] != first[0]


def test_completed_paused_cancelled_dead_letter_and_future_retry_are_not_claimed(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    _, artifact, destination = business(client)
    for name in ("succeeded", "paused", "cancelled", "dead_letter", "retry"):
        schedule(client, artifact["id"], destination["id"], name)
    with sessions() as db:
        materialize_due_schedules(db)
        jobs = list(db.scalars(select(PublishingJob).order_by(PublishingJob.created_at)))
        for job, state in zip(
            jobs,
            ["succeeded", "paused", "cancelled", "dead_letter", "retry_wait"],
            strict=True,
        ):
            job.state = state
        jobs[-1].available_at_utc = now() + timedelta(hours=1)
        db.commit()
        assert claim_jobs(db, "worker", 10, 60) == []
        assert claim_jobs(db, "worker", 10, 60, maintenance_mode=True) == []


def test_crash_after_remote_success_reconciles_without_duplicate(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    _, artifact, destination = business(client)
    schedule(client, artifact["id"], destination["id"], "Crash")
    with sessions() as db:
        materialize_due_schedules(db)
        job_id = claim_jobs(db, "crashed-worker", 1, 1)[0]
        assert start_attempt(db, job_id, "crashed-worker")
        job = db.get(PublishingJob, job_id)
        owner = db.scalar(select(User))
        assert job and owner
        result = create_execution(
            db,
            owner,
            CreateExecution(
                artifact_id=job.artifact_id,
                destination_id=job.destination_id,
                idempotency_key=f"job:{job.id}",
            ),
        )
        assert result.status == "succeeded"
        job = db.get(PublishingJob, job_id)
        assert job
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_leases(db) == 1
        db.refresh(job)
        assert job.state == "succeeded"
        assert job.publishing_execution_id == result.id
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingRecoveryRecord)) == 1
        assert db.scalar(select(PublishingRecoveryRecord.result)) == "remote_succeeded"


def test_worker_execution_is_idempotent_and_records_attempt(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    _, artifact, destination = business(client)
    schedule(client, artifact["id"], destination["id"], "Worker")
    with sessions() as db:
        materialize_due_schedules(db)
        job_id = claim_jobs(db, "worker", 1, 60)[0]
    execute_job(job_id, "worker")
    execute_job(job_id, "worker")
    with sessions() as db:
        job = db.get(PublishingJob, job_id)
        assert job and job.state == "succeeded"
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingJobAttempt)) == 1
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "publishing.execution_succeeded" in actions


def test_workflow_creates_durable_schedule_waits_and_resumes(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    product, _, _ = business(client)
    client.put(
        "/api/v1/publishing/connectors/wordpress",
        json={
            "site_url": "http://127.0.0.1",
            "username": "owner",
            "enabled": False,
            "default_post_status": "draft",
            "request_timeout_seconds": 10,
            "max_retry_attempts": 2,
        },
        headers=ORIGIN,
    )
    client.post("/api/v1/publishing/connectors/wordpress/validate", headers=ORIGIN)
    client.post("/api/v1/publishing/connectors/wordpress/enable", headers=ORIGIN)
    brand_id = client.get(f"/api/v1/products/{product['id']}").json()["brand_id"]
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Scheduled WordPress",
            "brand_id": brand_id,
            "connector_key": "wordpress",
            "configuration": {
                "post_status": "publish",
                "category_ids": [],
                "tag_ids": [],
                "media_policy": "fail",
                "featured_image_policy": "none",
                "update_existing_remote_post": True,
                "content_mapping_version": 1,
            },
        },
        headers=ORIGIN,
    ).json()
    created = client.post(
        "/api/v1/workflows",
        json={
            "product_id": product["id"],
            "destination_id": destination["id"],
            "publishing_action": "schedule_wordpress_publish",
            "schedule_at_local": (datetime.now(UTC) - timedelta(minutes=1))
            .replace(tzinfo=None)
            .isoformat(),
            "schedule_timezone": "UTC",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    started = client.post(f"/api/v1/workflows/{workflow_id}/start", headers=ORIGIN)
    assert started.status_code == 200
    artifact_id = started.json()["artifact_id"]
    client.post(f"/api/v1/ai/artifacts/{artifact_id}/approve", headers=ORIGIN)
    waiting = client.post(f"/api/v1/workflows/{workflow_id}/continue", headers=ORIGIN)
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["status"] == "waiting_for_publishing"
    assert waiting.json()["publishing_schedule_id"]
    job_id = uuid.UUID(waiting.json()["publishing_job_id"])
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(WorkflowPublishingWait)) == 1
        assert claim_jobs(db, "workflow-worker", 1, 60) == [job_id]
    execute_job(job_id, "workflow-worker")
    with sessions() as db:
        workflow = db.get(WorkflowInstance, uuid.UUID(workflow_id))
        wait = db.scalar(select(WorkflowPublishingWait))
        assert workflow and workflow.status == "completed"
        assert wait and wait.status == "succeeded"


def test_fake_shopify_scheduled_draft_is_idempotent(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    product, artifact, _ = business(client)
    brand_id = client.get(f"/api/v1/products/{product['id']}").json()["brand_id"]
    saved = client.put(
        "/api/v1/publishing/connectors/shopify",
        json={
            "shop_domain": "test-shop.myshopify.com",
            "access_token": "shpat_scheduler_fake_only",
            "api_version": "2026-07",
            "default_product_status": "draft",
            "default_publication_ids": [],
            "inventory_policy": "no_inventory_write",
            "variant_policy": "default_variant",
            "media_policy": "fail",
            "request_timeout_seconds": 45,
            "max_retry_attempts": 3,
        },
        headers=ORIGIN,
    )
    assert saved.status_code == 200
    assert client.post("/api/v1/publishing/connectors/shopify/validate", headers=ORIGIN).json()[
        "valid"
    ]
    client.post("/api/v1/publishing/connectors/shopify/enable", headers=ORIGIN)
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Scheduled Shopify",
            "brand_id": brand_id,
            "connector_key": "shopify",
            "configuration": {
                "default_product_status": "draft",
                "default_collection_ids": [],
                "default_publication_ids": [],
                "default_vendor": "",
                "default_product_type": "",
                "default_tags": [],
                "variant_policy": "default_variant",
                "inventory_policy": "no_inventory_write",
                "media_policy": "fail",
                "update_existing_remote_product": True,
                "content_mapping_version": 1,
            },
        },
        headers=ORIGIN,
    ).json()
    response = client.post(
        "/api/v1/publishing/schedules",
        json={
            "name": "Shopify draft",
            "artifact_id": artifact["id"],
            "destination_id": destination["id"],
            "requested_action": "create_draft",
            "local_scheduled_at": (datetime.now(UTC) - timedelta(minutes=1))
            .replace(tzinfo=None)
            .isoformat(),
            "timezone_name": "UTC",
            "schedule_type": "one_time",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    with sessions() as db:
        materialize_due_schedules(db)
        job_id = claim_jobs(db, "shopify-worker", 1, 60)[0]
    execute_job(job_id, "shopify-worker")
    execute_job(job_id, "shopify-worker")
    with sessions() as db:
        job = db.get(PublishingJob, job_id)
        execution = db.scalar(select(PublishingExecution))
        assert job and job.state == "succeeded"
        assert execution and execution.remote_entity_id == "gid://shopify/Product/42"
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 1
