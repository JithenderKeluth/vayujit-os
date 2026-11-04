"""Mixed content review must preserve exact schemas and HUMAN decisions."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import test_ai_integration
from pydantic import ValidationError
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context
from test_ai_integration import client as client
from vayujit_api.ads.marketing import MarketingPlanCreate
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "budget",
    [
        {
            "total": "250.50",
            "currency": "INR",
            "allocations": {"social": "250.50", "campaign": "250.50"},
        },
        {"total": "-1", "currency": "INR", "allocations": {}},
        {"total": "250.50", "currency": "INR", "allocations": {"social": "not-numeric"}},
    ],
)
def test_initial_marketing_budget_uses_existing_canonical_validation(budget):
    with pytest.raises(ValidationError):
        MarketingPlanCreate(
            brand_id=uuid.uuid4(),
            product_ids=[uuid.uuid4()],
            target_channels=["social", "campaign"],
            idempotency_key="wp7a4-budget",
            budget_envelope=budget,
        )


def test_initial_marketing_budget_preserves_unknown_allocations():
    request = MarketingPlanCreate(
        brand_id=uuid.uuid4(),
        product_ids=[uuid.uuid4()],
        target_channels=["social", "campaign"],
        idempotency_key="wp7a4-unknown-budget",
        budget_envelope={"total": "250.50", "currency": "INR", "allocations": {}},
    )
    assert request.budget_envelope["allocations"] == {}


def test_parallel_portfolio_projections_emit_each_audit_key_once(client):
    setup_context(client)
    created = client.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={
            "name": "[QA SYNTHETIC] WP7A4 concurrent projection",
            "scope_type": "manual",
            "idempotency_key": "wp7a4-portfolio-race",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201
    portfolio_id = created.json()["id"]
    assert (
        client.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
            json={"idempotency_key": "wp7a4-assess-race"},
            headers=ORIGIN,
        ).status_code
        == 201
    )
    barrier = Barrier(6)

    def request(index):
        barrier.wait(timeout=10)
        try:
            return client.get(
                f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/"
                + ("events" if index % 2 else "product-channel")
            ).status_code
        except Exception:
            return 500

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(request, range(6))) == [200] * 6
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        rows = db.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == uuid.UUID(portfolio_id),
                AuditEvent.idempotency_key.is_not(None),
            )
        ).all()
        assert rows
        assert len(rows) == len({row.idempotency_key for row in rows})


@pytest.mark.parametrize(
    "kind", ["marketplace_listing", "product_title", "seo_metadata", "social_caption"]
)
def test_channel_specific_review_preserves_content_without_invented_fields(client, kind):
    context = setup_context(client)
    product_id = context["product"]["id"]
    old = client.post("/api/v1/ai/generations", json={"product_id": product_id}, headers=ORIGIN)
    assert old.status_code == 201
    original_id = old.json()["artifact_id"]
    assert (
        client.post(f"/api/v1/ai/artifacts/{original_id}/approve", headers=ORIGIN).status_code
        == 200
    )
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["amazon"],
            "content_types": [kind],
            "idempotency_key": "wp7a4-" + kind,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert run_ai_jobs_once(db, "wp7a4-mixed-review", limit=5) == 1
    result = client.get(f"/api/v1/ai/studio/generations/{queued.json()['id']}").json()
    artifact_id = result["outputs"][0]["artifact_id"]
    canonical = client.get(f"/api/v1/ai/studio/artifacts/{artifact_id}").json()
    for endpoint in [
        f"ai/artifacts/{artifact_id}",
        f"approvals/{artifact_id}",
        f"approvals/{original_id}",
    ]:
        response = client.get("/api/v1/" + endpoint)
        assert response.status_code == 200
        body = response.json()
        if endpoint.endswith(artifact_id):
            view = body.get("artifact", body)
            assert view["content"] == canonical["content"]
            assert view["status"] == "pending_review"
            assert "product_title" not in view["content"]
    assert client.get(f"/api/v1/ai/artifacts/{original_id}").json()["status"] == "approved"
    assert (
        client.get(f"/api/v1/ai/artifacts/{artifact_id}").json()["content"] == canonical["content"]
    )
    assert (
        client.get("/api/v1/ai/artifacts/00000000-0000-0000-0000-000000000001").status_code == 404
    )
