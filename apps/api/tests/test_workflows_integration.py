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
from vayujit_api.publishing.models import PublishingExecution
from vayujit_api.workflows.models import WorkflowTemplate

URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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
                id=uuid.UUID("b1000000-0000-4000-8000-000000000001"),
                key="product-content-publish",
                name="Product content and publish",
                description="Generate, approve, and publish.",
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
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=URL)
    engine.dispose()


def setup_owner_business(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Workflow Owner",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    brand = client.post("/api/v1/brands", json={"name": "Workflow Brand"}, headers=ORIGIN).json()
    product = client.post(
        "/api/v1/products",
        json={
            "name": "Workflow Product",
            "product_type": "physical",
            "description": "A complete active product.",
            "short_description": "Ready",
            "price_amount": "30.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    ).json()
    client.post(f"/api/v1/products/{product['id']}/activate", headers=ORIGIN)
    return brand, product


def destination(
    client: TestClient,
    brand_id: str,
    *,
    name: str = "Workflow Channel",
    fail: bool = False,
) -> dict[str, object]:
    return client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": name,
            "brand_id": brand_id,
            "configuration": {
                "channel_name": name,
                "publication_prefix": "WF",
                "simulate_failure": fail,
                "failure_type": "retryable",
            },
        },
        headers=ORIGIN,
    ).json()


def create_workflow(
    client: TestClient,
    product_id: str,
    destination_id: str,
    instructions: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/workflows",
        json={
            "product_id": product_id,
            "destination_id": destination_id,
            "additional_instructions": instructions,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_orchestrated_journey_and_idempotent_continuation(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/workflows/templates").status_code == 401
    brand, product = setup_owner_business(client)
    target = destination(client, str(brand["id"]))
    templates = client.get("/api/v1/workflows/templates").json()
    assert templates[0]["key"] == "product-content-publish"
    assert "definition_json" not in templates[0]

    workflow = create_workflow(client, str(product["id"]), str(target["id"]))
    assert workflow["status"] == "draft"
    started = client.post(f"/api/v1/workflows/{workflow['id']}/start", headers=ORIGIN).json()
    assert started["status"] == "waiting_for_approval"
    assert [step["status"] for step in started["steps"]] == ["succeeded", "waiting"]
    artifact_id = started["artifact_id"]
    client.post(f"/api/v1/ai/artifacts/{artifact_id}/approve", headers=ORIGIN)
    completed = client.post(f"/api/v1/workflows/{workflow['id']}/continue", headers=ORIGIN).json()
    assert completed["status"] == "completed"
    assert completed["publishing_status"] == "succeeded"
    assert [step["status"] for step in completed["steps"]] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    repeated = client.post(f"/api/v1/workflows/{workflow['id']}/continue", headers=ORIGIN).json()
    assert repeated["publishing_execution_id"] == completed["publishing_execution_id"]
    assert factory is not None
    with factory() as db:
        assert len(db.scalars(select(PublishingExecution)).all()) == 1
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert {
            "workflow.created",
            "workflow.started",
            "workflow.waiting_for_approval",
            "workflow.continued",
            "workflow.completed",
        } <= actions
    assert (
        client.post(f"/api/v1/workflows/{workflow['id']}/cancel", headers=ORIGIN).status_code == 409
    )


def test_retryable_publish_failure_reuses_existing_execution(
    client: TestClient,
) -> None:
    brand, product = setup_owner_business(client)
    target = destination(client, str(brand["id"]), name="Retry Workflow", fail=True)
    workflow = create_workflow(client, str(product["id"]), str(target["id"]))
    started = client.post(f"/api/v1/workflows/{workflow['id']}/start", headers=ORIGIN).json()
    client.post(f"/api/v1/ai/artifacts/{started['artifact_id']}/approve", headers=ORIGIN)
    failed = client.post(f"/api/v1/workflows/{workflow['id']}/continue", headers=ORIGIN).json()
    assert failed["status"] == "failed" and failed["retryable"] is True
    publishing_id = failed["publishing_execution_id"]
    client.patch(
        f"/api/v1/publishing/destinations/{target['id']}",
        json={
            "configuration": {
                "channel_name": "Retry Workflow",
                "publication_prefix": "WF",
                "simulate_failure": False,
                "failure_type": "retryable",
            }
        },
        headers=ORIGIN,
    )
    retried = client.post(f"/api/v1/workflows/{workflow['id']}/retry", headers=ORIGIN).json()
    assert retried["status"] == "completed"
    assert retried["publishing_execution_id"] == publishing_id
    publish_steps = [step for step in retried["steps"] if step["step_key"] == "publish_content"]
    assert [step["attempt_number"] for step in publish_steps] == [1, 2]
    assert [step["status"] for step in publish_steps] == ["failed", "succeeded"]


def test_rejection_ai_failure_and_truthful_cancellation(client: TestClient) -> None:
    brand, product = setup_owner_business(client)
    target = destination(client, str(brand["id"]))
    draft = create_workflow(client, str(product["id"]), str(target["id"]))
    cancelled = client.post(f"/api/v1/workflows/{draft['id']}/cancel", headers=ORIGIN).json()
    assert cancelled["status"] == "cancelled"
    assert client.post(f"/api/v1/workflows/{draft['id']}/retry", headers=ORIGIN).status_code == 409

    rejected_workflow = create_workflow(client, str(product["id"]), str(target["id"]))
    waiting = client.post(
        f"/api/v1/workflows/{rejected_workflow['id']}/start", headers=ORIGIN
    ).json()
    client.post(
        f"/api/v1/ai/artifacts/{waiting['artifact_id']}/reject",
        json={"reason": "Not suitable"},
        headers=ORIGIN,
    )
    rejected = client.post(
        f"/api/v1/workflows/{rejected_workflow['id']}/continue", headers=ORIGIN
    ).json()
    assert rejected["status"] == "failed"
    assert rejected["error_code"] == "artifact_rejected"
    assert rejected["retryable"] is False

    failed_workflow = create_workflow(client, str(product["id"]), str(target["id"]), "[mock:fail]")
    failed = client.post(f"/api/v1/workflows/{failed_workflow['id']}/start", headers=ORIGIN).json()
    assert failed["status"] == "failed"
    assert failed["current_step_key"] == "generate_content"
    assert failed["retryable"] is True
    listing = client.get("/api/v1/workflows?status=failed&retryable=true").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == failed_workflow["id"]
