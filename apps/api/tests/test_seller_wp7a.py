"""WP7A focused persisted correctness; synthetic single-owner installation only."""

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import func, select
from sqlalchemy import inspect as schema_inspect
from test_pr_sos_04_inventory_orders import _factory
from test_seller_wp6a_migration import engine as engine
from test_seller_wp6a_migration import migration
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.commerce.models import InventoryItem, InventoryMovement
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
OPTIONAL = (
    "failure_category",
    "retry_after_seconds",
    "calculated_delay_seconds",
    "applied_delay_seconds",
    "next_retry_at",
    "checkpoint_fingerprint",
)


@pytest.fixture
def local(pr56_client):
    c = pr56_client

    def post(path, data):
        r = c.post("/api/v1/" + path, json=data, headers=ORIGIN)
        assert r.status_code < 300
        return r.json()

    post(
        "auth/setup-owner",
        {
            "full_name": "[QA SYNTHETIC] WP7A",
            "email": "wp7a@example.com",
            "password": "SyntheticWP7AOnly123!",
            "password_confirmation": "SyntheticWP7AOnly123!",
        },
    )
    brand = post("brands", {"name": "[QA SYNTHETIC] WP7A"})
    product = post(
        "products",
        {
            "brand_id": brand["id"],
            "name": "[QA SYNTHETIC] WP7A item",
            "product_type": "physical",
            "sku": "QA-WP7A",
        },
    )
    item = post(
        "inventory/items",
        {
            "product_id": product["id"],
            "internal_sku": product["sku"],
            "opening_quantity": 10,
            "idempotency_key": "wp7a-opening",
        },
    )
    return c, post, brand, product, item


@pytest.mark.parametrize("delta", [3, -3])
def test_adjustment_replay_preserves_exact_database_balance_and_ledger(local, delta):
    c, post, _, product, item = local
    body = {
        "delta": delta,
        "reason": "[QA SYNTHETIC] observed count",
        "expected_version": item["version"],
        "idempotency_key": "wp7a-adjust",
    }
    first = post(f"inventory/{item['id']}/adjust", body)
    replay = post(f"inventory/{item['id']}/adjust", body)
    assert first["on_hand_quantity"] == replay["on_hand_quantity"] == 10 + delta
    with _factory()() as db:
        row = db.get(InventoryItem, uuid.UUID(item["id"]))
        assert str(row.product_id) == product["id"]
        assert row.on_hand_quantity == 10 + delta
        moves = db.scalars(
            select(InventoryMovement).where(InventoryMovement.inventory_item_id == row.id)
        ).all()
        assert len(moves) == 2 and sum(m.quantity for m in moves) == row.on_hand_quantity
        assert moves[-1].actor_type == "HUMAN"


@pytest.mark.parametrize("delta,status", [(0, 422), (-11, 409)])
def test_invalid_adjustment_never_writes_or_changes_version(local, delta, status):
    c, _, _, _, item = local
    r = c.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={
            "delta": delta,
            "reason": "[QA SYNTHETIC] invalid",
            "expected_version": item["version"],
            "idempotency_key": "wp7a-invalid",
        },
        headers=ORIGIN,
    )
    assert r.status_code == status
    with _factory()() as db:
        assert db.get(InventoryItem, uuid.UUID(item["id"])).on_hand_quantity == 10
        assert db.scalar(select(func.count()).select_from(InventoryMovement)) == 1


def test_uncertain_committed_adjustment_conflicting_key_cannot_duplicate(local):
    c, post, _, _, item = local
    body = {
        "delta": 2,
        "reason": "[QA SYNTHETIC] unknown response",
        "expected_version": item["version"],
        "idempotency_key": "wp7a-first",
    }
    post(f"inventory/{item['id']}/adjust", body)
    # Same stale version with a different intent/key must not silently adjust again.
    r = c.post(
        f"/api/v1/inventory/{item['id']}/adjust",
        json={**body, "idempotency_key": "wp7a-second"},
        headers=ORIGIN,
    )
    assert r.status_code == 409
    with _factory()() as db:
        assert db.get(InventoryItem, uuid.UUID(item["id"])).on_hand_quantity == 12
        assert db.scalar(select(func.count()).select_from(InventoryMovement)) == 2


def test_video_queue_is_local_idempotent_and_caption_validation_is_persisted(local):
    c, post, brand, product, _ = local
    body = {
        "brand_id": brand["id"],
        "product_id": product["id"],
        "duration_seconds": 3,
        "idempotency_key": "wp7a-local-video",
    }
    video = post("ai/video/queue", body)
    assert post("ai/video/queue", body)["id"] == video["id"]
    path = f"/api/v1/ai/video/generations/{video['id']}/captions"
    for text, timing in [
        ("", []),
        ("[QA SYNTHETIC] bad", [{"start": 4, "end": 5, "text": "bad"}]),
        ("<script>alert(1)</script>", []),
    ]:
        assert (
            c.post(path, json={"caption_text": text, "timing": timing}, headers=ORIGIN).status_code
            == 422
        )
    caption = post(
        f"ai/video/generations/{video['id']}/captions",
        {
            "caption_text": "[QA SYNTHETIC] local caption",
            "timing": [{"start": 0, "end": 1, "text": "[QA SYNTHETIC] local caption"}],
        },
    )
    assert caption["approval_state"] == "pending_review"
    assert c.get(path).json()[0]["caption_text"] == "[QA SYNTHETIC] local caption"
    assert c.get("/api/v1/ai/video/generations").json()[0]["status"] == "queued"


def test_missing_marketplace_credentials_never_establish_connection(local):
    c, post, *_ = local
    account = post(
        "marketplaces/accounts",
        {
            "marketplace": "amazon",
            "display_name": "[QA SYNTHETIC] WP7A",
            "seller_account_id": "qa3-wp7a-account",
            "environment": "sandbox",
            "credentials": {},
        },
    )
    assert account["connection_state"] == "AUTHORIZATION_REQUIRED"
    assert account["permission_state"] == "UNVERIFIED" and not account["enabled"]
    assert (
        c.post(
            f"/api/v1/marketplaces/accounts/{account['id']}/enable", json={}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert c.get("/api/v1/marketplaces/accounts/" + str(uuid.uuid4())).status_code == 404
    for mode in ("LIVE_READ_ONLY", "SANDBOX"):
        response = c.post(
            f"/api/v1/marketplaces/accounts/{account['id']}/imports",
            json={"operation": "catalog", "mode": mode, "idempotency_key": "wp7a-denied-import"},
            headers=ORIGIN,
        )
        assert (
            response.status_code == 409 and response.headers["X-VAYUJIT-External-Write"] == "denied"
        )
    assert c.get(f"/api/v1/marketplaces/accounts/{account['id']}/import-jobs").json() == []
    c.cookies.clear()
    assert c.get("/api/v1/marketplaces/accounts/" + account["id"]).status_code == 401


@pytest.mark.parametrize("category", ["kids", "sports and outdoor fitness"])
def test_unavailable_local_category_is_persisted_replayable_and_never_relaxed(local, category):
    c, post, *_ = local
    goal = post(
        "intelligence/business-agent/goals",
        {
            "raw_goal": f"[QA SYNTHETIC] Find 1 product in {category} category for Amazon India.",
            "idempotency_key": "wp7a-no-category",
        },
    )
    post(f"intelligence/business-agent/goals/{goal['id']}/plan", {})
    run = post(
        f"intelligence/business-agent/goals/{goal['id']}/runs",
        {
            "idempotency_key": "wp7a-no-category-run",
            "max_steps": 20,
        },
    )
    for operation in ("start", "start", "retry"):
        result = post(f"intelligence/business-agent/runs/{run['id']}/{operation}", {})
        assert result["status"] == "PARTIAL"
        assert result["failure"]["code"] == "NO_USEFUL_PRODUCT_CANDIDATES"
        assert result["candidates"] == [] and result["result"]["external_writes"] == []
    loaded = c.get(f"/api/v1/intelligence/business-agent/runs/{run['id']}").json()
    assert loaded["failure"]["code"] == "NO_USEFUL_PRODUCT_CANDIDATES"
    with _factory()() as db:
        assert db.scalar(select(func.count()).select_from(ProductOpportunity)) == 0


def test_optional_job_metadata_migration_empty_roundtrip(local, engine):
    assert all(
        c["nullable"]
        for c in schema_inspect(engine).get_columns("ai_studio_jobs")
        if c["name"] in OPTIONAL
    )
    command.downgrade(migration(), "20261206_0149")
    assert all(
        not c["nullable"]
        for c in schema_inspect(engine).get_columns("ai_studio_jobs")
        if c["name"] in OPTIONAL
    )
    command.upgrade(migration(), "head")
    assert all(
        c["nullable"] and c["default"] is None
        for c in schema_inspect(engine).get_columns("ai_studio_jobs")
        if c["name"] in OPTIONAL
    )


def test_optional_job_metadata_rollback_refuses_to_invent_absent_values(local, engine):
    _, post, brand, product, _ = local
    post(
        "ai/video/queue",
        {"brand_id": brand["id"], "product_id": product["id"], "idempotency_key": "wp7a-null-job"},
    )
    with _factory()() as db:
        job = db.scalar(select(AIStudioJob))
        assert all(getattr(job, name) is None for name in OPTIONAL)
        identity = job.id
    with pytest.raises(RuntimeError, match="WP7A_DOWNGRADE_WOULD_INVALIDATE_OPTIONAL_JOB_METADATA"):
        command.downgrade(migration(), "20261206_0149")
    with _factory()() as db:
        job = db.get(AIStudioJob, identity)
        assert job.state == "queued" and all(getattr(job, name) is None for name in OPTIONAL)
    assert all(
        c["nullable"]
        for c in schema_inspect(engine).get_columns("ai_studio_jobs")
        if c["name"] in OPTIONAL
    )


def test_optional_job_metadata_preserves_nonnull_historical_values(local, engine):
    _, post, brand, product, _ = local
    post(
        "ai/video/queue",
        {
            "brand_id": brand["id"],
            "product_id": product["id"],
            "idempotency_key": "wp7a-historical-job",
        },
    )
    values = {
        "failure_category": "provider_unavailable",
        "retry_after_seconds": 30,
        "calculated_delay_seconds": 30,
        "applied_delay_seconds": 30,
        "next_retry_at": datetime(2026, 11, 1, tzinfo=UTC),
        "checkpoint_fingerprint": "qa-synthetic-checkpoint",
    }
    with _factory()() as db:
        job = db.scalar(select(AIStudioJob))
        identity = job.id
        for name, value in values.items():
            setattr(job, name, value)
        job.state = "failed"
        db.commit()
    command.downgrade(migration(), "20261206_0149")
    command.upgrade(migration(), "head")
    with _factory()() as db:
        job = db.get(AIStudioJob, identity)
        assert job.state == "failed" and all(
            getattr(job, name) == value for name, value in values.items()
        )
