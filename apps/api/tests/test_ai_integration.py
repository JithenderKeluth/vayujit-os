import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.ai.models import AIGenerationRequest, GeneratedArtifact, PromptTemplate
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.router import attempts
from vayujit_api.identity.service import now
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"
factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    global factory
    assert TEST_DATABASE_URL is not None and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        stamp = now()
        db.add(
            PromptTemplate(
                id=uuid.UUID("a1000000-0000-4000-8000-000000000001"),
                key="product-content",
                name="Product content",
                description="Structured content",
                version=1,
                template_type="product_content",
                system_instructions="Structured output only.",
                user_template="Generate product content.",
                output_schema={"type": "object"},
                status="enabled",
                is_default=True,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()

    def test_session() -> Generator[Session, None, None]:
        assert factory is not None
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def setup_context(client: TestClient) -> dict[str, Any]:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "AI Owner",
            "email": "owner@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201
    brand = client.post(
        "/api/v1/brands",
        json={"name": "Northstar", "tagline": "Built for the journey"},
        headers=ORIGIN,
    ).json()
    product = client.post(
        "/api/v1/products",
        json={
            "name": "Trail Bottle",
            "product_type": "physical",
            "short_description": "An insulated reusable bottle",
            "description": "A durable bottle for long outdoor days.",
            "category": "Outdoors",
            "tags": ["insulated", "reusable"],
            "price_amount": "29.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    ).json()
    return {"brand": brand, "product": product}


def generate(client: TestClient, product_id: str, instructions: str | None = None):
    return client.post(
        "/api/v1/ai/generations",
        json={"product_id": product_id, "additional_instructions": instructions},
        headers=ORIGIN,
    )


def test_provider_templates_and_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/ai/providers").status_code == 401
    context = setup_context(client)
    providers = client.get("/api/v1/ai/providers").json()
    assert providers == [
        {
            "key": "deterministic_mock_v1",
            "name": "Deterministic Local Mock",
            "provider_type": "mock",
            "available": True,
            "deterministic": True,
            "local": True,
        }
    ]
    templates = client.get("/api/v1/ai/templates").json()
    assert templates[0]["is_default"] is True
    assert "system_instructions" not in templates[0]
    assert context["product"]


def test_generate_review_regenerate_history_and_audit(client: TestClient) -> None:
    context = setup_context(client)
    product = context["product"]
    first = generate(client, product["id"])
    assert first.status_code == 201
    assert first.json()["status"] == "completed"
    first_id = first.json()["artifact_id"]
    artifact = client.get(f"/api/v1/ai/artifacts/{first_id}").json()
    assert artifact["status"] == "pending_review"
    assert artifact["version_number"] == 1
    assert artifact["content"]["product_title"] == "Northstar Trail Bottle"

    approved = client.post(f"/api/v1/ai/artifacts/{first_id}/approve", headers=ORIGIN)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert (
        client.post(f"/api/v1/ai/artifacts/{first_id}/approve", headers=ORIGIN).status_code == 200
    )
    assert (
        client.post(
            f"/api/v1/ai/artifacts/{first_id}/reject",
            json={"reason": "No"},
            headers=ORIGIN,
        ).status_code
        == 409
    )

    second = client.post(f"/api/v1/ai/artifacts/{first_id}/regenerate", headers=ORIGIN)
    second_id = second.json()["artifact_id"]
    second_artifact = client.get(f"/api/v1/ai/artifacts/{second_id}").json()
    assert second_artifact["version_number"] == 2
    rejected = client.post(
        f"/api/v1/ai/artifacts/{second_id}/reject",
        json={"reason": "Needs a quieter tone"},
        headers=ORIGIN,
    )
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Needs a quieter tone"
    assert (
        client.post(
            f"/api/v1/ai/artifacts/{second_id}/reject",
            json={"reason": "Ignored on idempotent retry"},
            headers=ORIGIN,
        ).status_code
        == 200
    )

    history = client.get(
        f"/api/v1/ai/generations?product_id={product['id']}&artifact_status=rejected"
    ).json()
    assert history["total"] == 1
    assert history["items"][0]["artifact_id"] == second_id
    assert factory is not None
    with factory() as db:
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert {
            "ai.generation_requested",
            "ai.generation_completed",
            "ai.artifact_approved",
            "ai.artifact_rejected",
            "ai.artifact_regenerated",
        } <= actions


def test_determinism_superseding_and_input_change(client: TestClient) -> None:
    product = setup_context(client)["product"]
    first = generate(client, product["id"]).json()
    first_content = client.get(f"/api/v1/ai/artifacts/{first['artifact_id']}").json()["content"]
    second = generate(client, product["id"]).json()
    second_content = client.get(f"/api/v1/ai/artifacts/{second['artifact_id']}").json()["content"]
    assert first_content == second_content
    assert (
        client.get(f"/api/v1/ai/artifacts/{first['artifact_id']}").json()["status"] == "superseded"
    )

    third = generate(client, product["id"], "Use a calm professional voice").json()
    third_content = client.get(f"/api/v1/ai/artifacts/{third['artifact_id']}").json()["content"]
    assert third_content != second_content


def test_safe_failures_validation_and_archived_scope(client: TestClient) -> None:
    context = setup_context(client)
    product = context["product"]
    failed = generate(client, product["id"], "[mock:fail]")
    assert failed.status_code == 201
    assert failed.json()["status"] == "failed"
    assert failed.json()["artifact_id"] is None
    assert failed.json()["error_code"] == "mock_generation_failed"
    assert "traceback" not in failed.text.lower()

    invalid = generate(client, product["id"], "[mock:invalid]").json()
    assert invalid["status"] == "failed"
    assert invalid["error_code"] == "invalid_provider_output"
    assert (
        client.post(
            "/api/v1/ai/generations",
            json={"product_id": product["id"], "additional_instructions": "x" * 2001},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/ai/generations",
            json={"product_id": product["id"], "prompt_template_id": str(uuid.uuid4())},
            headers=ORIGIN,
        ).status_code
        == 404
    )
    client.post(f"/api/v1/products/{product['id']}/archive", headers=ORIGIN)
    assert generate(client, product["id"]).status_code == 409
    assert factory is not None
    with factory() as db:
        requests = db.scalars(select(AIGenerationRequest)).all()
        artifacts = db.scalars(select(GeneratedArtifact)).all()
        assert len(requests) == 2 and not artifacts
