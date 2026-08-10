import pytest
import test_ai_integration
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def run_worker(worker_id: str, limit: int = 10) -> None:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        from vayujit_api.ai.studio_worker import run_ai_jobs_once

        run_ai_jobs_once(db, worker_id, limit=limit)


def test_studio_generates_separate_three_marketplace_artifacts(client) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [context["product"]["id"]],
            "channels": ["amazon", "flipkart", "meesho"],
            "content_types": ["marketplace_listing", "seo_metadata"],
            "idempotency_key": "studio-three-market-001",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 202, response.text
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["completed_outputs"] == 0
    assert all(item["artifact_id"] is None for item in queued["outputs"])
    run_worker("studio-test-worker")
    result = client.get(f"/api/v1/ai/studio/generations/{queued['id']}", headers=ORIGIN).json()
    assert result["status"] == "completed"
    assert result["completed_outputs"] == 6
    assert {item["channel"] for item in result["outputs"]} == {"amazon", "flipkart", "meesho"}
    artifacts = client.get("/api/v1/ai/studio/artifacts", headers=ORIGIN)
    assert artifacts.status_code == 200
    assert len(artifacts.json()) == 6
    assert all(item["context_fingerprint"] for item in artifacts.json())


def test_studio_idempotency_context_privacy_and_handoff(client) -> None:
    context = setup_context(client)
    product_id = context["product"]["id"]
    payload = {
        "product_ids": [product_id],
        "channels": ["amazon"],
        "content_types": ["product_title"],
        "idempotency_key": "studio-idempotent-001",
    }
    first = client.post("/api/v1/ai/studio/generate", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/ai/studio/generate", json=payload, headers=ORIGIN)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    context_response = client.get(f"/api/v1/ai/studio/context/{product_id}", headers=ORIGIN)
    assert context_response.status_code == 200
    body = str(context_response.json())
    assert "password" not in body.casefold() and "token" not in body.casefold()
    run_worker("studio-idempotency-worker")
    completed = client.get(
        f"/api/v1/ai/studio/generations/{first.json()['id']}", headers=ORIGIN
    ).json()
    artifact_id = completed["outputs"][0]["artifact_id"]
    assert artifact_id
    assert (
        client.post(
            f"/api/v1/ai/studio/artifacts/{artifact_id}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    handoff = client.post(
        f"/api/v1/ai/studio/artifacts/{artifact_id}/listing-handoff",
        json={"marketplace": "amazon", "confirm": True},
        headers=ORIGIN,
    )
    assert handoff.status_code == 200
    assert handoff.json()["artifact_id"] == artifact_id
    assert handoff.json()["artifact_version"] == 1


def test_studio_brand_voice_keywords_and_seo(client) -> None:
    context = setup_context(client)
    voice = client.post(
        "/api/v1/ai/studio/brand-voices",
        json={
            "name": "Northstar voice",
            "brand_id": context["brand"]["id"],
            "tone": "warm",
            "is_default": True,
        },
        headers=ORIGIN,
    )
    assert voice.status_code == 201, voice.text
    keywords = client.post(
        "/api/v1/ai/studio/keywords",
        json={
            "name": "Launch",
            "product_id": context["product"]["id"],
            "primary_keywords": ["Trail Bottle", "trail bottle", "insulated bottle"],
        },
        headers=ORIGIN,
    )
    assert keywords.status_code == 201
    assert keywords.json()["primary_keywords"] == ["Trail Bottle", "insulated bottle"]
    seo = client.post(
        "/api/v1/ai/studio/seo/analyze",
        json={
            "product_id": context["product"]["id"],
            "channel": "amazon",
            "primary_keyword": "Trail Bottle",
        },
        headers=ORIGIN,
    )
    assert seo.status_code == 200
    assert 0 <= seo.json()["score"] <= 100
