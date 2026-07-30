import base64
import json
import os
import secrets
import threading
import uuid
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.ai import configuration as ai_configuration
from vayujit_api.ai.models import AIGenerationRequest, GeneratedArtifact, PromptTemplate
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
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
    assert providers[0] == {
        "key": "deterministic_mock_v1",
        "name": "Deterministic Local Mock",
        "provider_type": "mock",
        "available": True,
        "deterministic": True,
        "local": True,
    }
    assert providers[1]["key"] == "openai_compatible"
    assert providers[1]["available"] is False
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


def test_encrypted_provider_fake_server_generation_and_usage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeProvider(BaseHTTPRequestHandler):
        repair_calls = 0

        def log_message(self, _format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            body = {
                "data": [
                    {"id": "fake-product-model"},
                    {"id": "fake-repair-model"},
                    {"id": "fake-fail-model"},
                    {"id": "fake-invalid-key-model"},
                ]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            request_body = json.loads(self.rfile.read(length))
            model = request_body["model"]
            if model == "fake-fail-model":
                self.send_response(500)
                self.end_headers()
                return
            if model == "fake-invalid-key-model":
                self.send_response(401)
                self.end_headers()
                return
            content = {
                "product_title": "Northstar Trail Bottle",
                "short_description": "A useful insulated bottle.",
                "long_description": "A durable insulated bottle for long outdoor days.",
                "key_features": ["Insulated", "Reusable"],
                "seo_title": "Trail Bottle | Northstar",
                "seo_description": "Discover the reusable Northstar Trail Bottle.",
                "social_caption": "Meet the Northstar Trail Bottle.",
                "keywords": ["trail bottle", "northstar"],
                "generation_summary": "Fake-provider content generated for review.",
            }
            response_content = json.dumps(content)
            if model == "fake-repair-model" and FakeProvider.repair_calls == 0:
                FakeProvider.repair_calls += 1
                response_content = "not-json"
            body = {
                "id": "fake-request-1",
                "choices": [{"message": {"content": response_content}}],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 30,
                    "total_tokens": 50,
                },
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeProvider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    settings = get_settings().model_copy(
        update={"credential_encryption_key": encryption_key, "environment": "development"}
    )
    monkeypatch.setattr(ai_configuration, "get_settings", lambda: settings)
    try:
        context = setup_context(client)
        configured = client.put(
            "/api/v1/ai/providers/openai_compatible",
            json={
                "api_key": "fake-provider-secret",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "default_model": "fake-product-model",
                "manual_model_allowed": False,
                "enabled": True,
                "fallback_provider_key": "deterministic_mock_v1",
                "request_timeout_seconds": 10,
                "max_retry_attempts": 1,
            },
            headers=ORIGIN,
        )
        assert configured.status_code == 200
        assert configured.json()["masked_credential"] == "••••cret"
        assert "fake-provider-secret" not in configured.text
        validated = client.post("/api/v1/ai/providers/openai_compatible/validate", headers=ORIGIN)
        assert validated.status_code == 200 and validated.json()["valid"] is True
        generated = client.post(
            "/api/v1/ai/generations",
            json={
                "product_id": context["product"]["id"],
                "provider_key": "openai_compatible",
                "model": "fake-product-model",
                "allow_fallback": True,
            },
            headers=ORIGIN,
        )
        assert generated.status_code == 201
        payload = generated.json()
        assert payload["status"] == "completed"
        assert payload["provider_key"] == "openai_compatible"
        attempts_response = client.get(f"/api/v1/ai/generations/{payload['id']}/attempts")
        assert attempts_response.json()[0]["total_tokens"] == 50
        usage = client.get("/api/v1/ai/usage/summary").json()
        assert usage["total_tokens"] == 50
        artifact = client.get(f"/api/v1/ai/artifacts/{payload['artifact_id']}").json()
        assert artifact["status"] == "pending_review"
        assert "fake-provider-secret" not in json.dumps(artifact)

        repaired = client.post(
            "/api/v1/ai/generations",
            json={
                "product_id": context["product"]["id"],
                "provider_key": "openai_compatible",
                "model": "fake-repair-model",
            },
            headers=ORIGIN,
        ).json()
        assert repaired["status"] == "completed"
        assert repaired["attempt_count"] == 2

        fallback = client.post(
            "/api/v1/ai/generations",
            json={
                "product_id": context["product"]["id"],
                "provider_key": "openai_compatible",
                "model": "fake-fail-model",
                "allow_fallback": True,
            },
            headers=ORIGIN,
        ).json()
        assert fallback["status"] == "completed"
        assert fallback["provider_key"] == "deterministic_mock_v1"
        assert fallback["fallback_used"] is True

        invalid_key = client.post(
            "/api/v1/ai/generations",
            json={
                "product_id": context["product"]["id"],
                "provider_key": "openai_compatible",
                "model": "fake-invalid-key-model",
                "allow_fallback": True,
            },
            headers=ORIGIN,
        ).json()
        assert invalid_key["status"] == "failed"
        assert invalid_key["error_code"] == "invalid_credential"
        assert invalid_key["fallback_used"] is False

        assert factory is not None
        with factory() as db:
            pending = AIGenerationRequest(
                owner_id=db.scalar(select(User.id).limit(1)),
                brand_id=uuid.UUID(context["brand"]["id"]),
                product_id=uuid.UUID(context["product"]["id"]),
                prompt_template_id=uuid.UUID("a1000000-0000-4000-8000-000000000001"),
                provider_key="openai_compatible",
                selected_model="fake-product-model",
                status="pending",
                fallback_used=False,
                final_attempt_count=0,
                created_at=now(),
                updated_at=now(),
            )
            db.add(pending)
            db.commit()
            pending_id = pending.id
        cancelled = client.post(
            f"/api/v1/ai/generations/{pending_id}/cancel", headers=ORIGIN
        ).json()
        assert cancelled["status"] == "cancelled"
        assert cancelled["remote_cancellation"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
