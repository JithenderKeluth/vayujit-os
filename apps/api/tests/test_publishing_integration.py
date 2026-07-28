import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.ai.models import PromptTemplate
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.router import attempts
from vayujit_api.identity.service import now
from vayujit_api.main import create_app

URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
test_factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    global test_factory
    assert URL and URL.startswith("postgresql")
    engine = create_engine(URL)
    reset_test_schema(engine, Base.metadata, database_url=URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    test_factory = factory
    with factory() as db:
        stamp = now()
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
        db.commit()

    def session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=URL)
    engine.dispose()


def setup(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Owner",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    brand = client.post("/api/v1/brands", json={"name": "Publish Brand"}, headers=ORIGIN).json()
    product = client.post(
        "/api/v1/products",
        json={
            "name": "Publish Product",
            "product_type": "physical",
            "description": "Ready product",
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
    return brand, artifact


def test_complete_publish_idempotency_failure_and_retry(client: TestClient) -> None:
    assert client.get("/api/v1/publishing/connectors").status_code == 401
    brand, artifact = setup(client)
    assert client.get("/api/v1/publishing/connectors").json()[0]["local"] is True
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Local Channel",
            "brand_id": brand["id"],
            "connector_key": "mock_publisher_v1",
            "configuration": {
                "channel_name": "Demo",
                "publication_prefix": "DEMO",
                "simulate_failure": False,
                "failure_type": "non_retryable",
            },
        },
        headers=ORIGIN,
    )
    assert destination.status_code == 201
    key = "publish-test-key-001"
    first = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": destination.json()["id"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert first.status_code == 201 and first.json()["status"] == "succeeded"
    assert first.json()["attempt_count"] == 1
    repeated = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": destination.json()["id"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert repeated.json()["id"] == first.json()["id"]
    assert repeated.json()["attempt_count"] == 1
    assert first.json()["content_snapshot"]["product_name"] == "Publish Product"
    assert first.json()["external_url"].startswith("https://example.invalid/")

    failure = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Retry Channel",
            "configuration": {
                "channel_name": "Retry",
                "publication_prefix": "TRY",
                "simulate_failure": True,
                "failure_type": "retryable",
            },
        },
        headers=ORIGIN,
    ).json()
    failed = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": failure["id"],
            "idempotency_key": "retry-test-key-001",
        },
        headers=ORIGIN,
    ).json()
    assert failed["status"] == "failed" and failed["retryable"] is True
    client.patch(
        f"/api/v1/publishing/destinations/{failure['id']}",
        json={
            "configuration": {
                "channel_name": "Retry",
                "publication_prefix": "TRY",
                "simulate_failure": False,
                "failure_type": "retryable",
            }
        },
        headers=ORIGIN,
    )
    retried = client.post(
        f"/api/v1/publishing/executions/{failed['id']}/retry", headers=ORIGIN
    ).json()
    assert retried["status"] == "succeeded" and retried["attempt_count"] == 2
    assert [item["status"] for item in retried["attempts"]] == ["failed", "succeeded"]
    history = client.get("/api/v1/publishing/executions?status=succeeded").json()
    assert history["total"] == 2
    assert test_factory is not None
    with test_factory() as db:
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert {
            "publishing.destination_created",
            "publishing.destination_updated",
            "publishing.execution_requested",
            "publishing.execution_succeeded",
            "publishing.execution_failed",
            "publishing.execution_retried",
        } <= actions
