import pytest
import test_ai_integration
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def run_worker(worker_id: str) -> None:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        from vayujit_api.ai.studio_worker import run_ai_jobs_once

        run_ai_jobs_once(db, worker_id, limit=20)


def generate_artifact(
    client, product_id: str, *, locale: str, reason: str = "studio", key: str
) -> dict:
    response = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["wordpress"],
            "content_types": ["product_title"],
            "locale": locale,
            "generation_reason": reason,
            "operation": "localized_generation" if reason == "localized_generation" else None,
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 202, response.text
    run_worker(key + "-worker")
    generation = client.get(
        f"/api/v1/ai/studio/generations/{response.json()['id']}", headers=ORIGIN
    ).json()
    artifact_id = generation["outputs"][0]["artifact_id"]
    assert artifact_id
    return client.get(f"/api/v1/ai/studio/artifacts/{artifact_id}", headers=ORIGIN).json()


def test_translation_uses_exact_approved_source_lineage_and_locale_warning(client) -> None:
    context = setup_context(client)
    product_id = context["product"]["id"]
    pending = generate_artifact(client, product_id, locale="en-IN", key="translation-source")
    rejected_pending = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["wordpress"],
            "content_types": ["product_title"],
            "locale": "hi-IN",
            "generation_reason": "translation",
            "operation": "translation",
            "source_artifact_id": pending["id"],
            "source_artifact_version": pending["version_number"],
            "idempotency_key": "translation-pending",
        },
        headers=ORIGIN,
    )
    assert rejected_pending.status_code == 409
    approved = client.post(f"/api/v1/ai/studio/artifacts/{pending['id']}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    translated_request = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["wordpress"],
            "content_types": ["product_title"],
            "locale": "hi-IN",
            "generation_reason": "translation",
            "operation": "translation",
            "source_artifact_id": pending["id"],
            "source_artifact_version": pending["version_number"],
            "idempotency_key": "translation-approved",
        },
        headers=ORIGIN,
    )
    assert translated_request.status_code == 202, translated_request.text
    run_worker("translation-approved-worker")
    translated_generation = client.get(
        f"/api/v1/ai/studio/generations/{translated_request.json()['id']}", headers=ORIGIN
    ).json()
    translated_id = translated_generation["outputs"][0]["artifact_id"]
    translated = client.get(f"/api/v1/ai/studio/artifacts/{translated_id}", headers=ORIGIN).json()
    assert translated["generation_reason"] == "translation"
    assert translated["parent_artifact_id"] == pending["id"]
    assert translated["source_artifact_version"] == pending["version_number"]
    assert translated["source_locale"] == "en-IN"
    assert translated["source_product_context"]["product_id"] == product_id
    assert translated["locale"] == "hi-IN"
    assert (
        client.get(f"/api/v1/ai/studio/artifacts/{pending['id']}", headers=ORIGIN).json()["status"]
        == "approved"
    )
    same_locale = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["wordpress"],
            "content_types": ["product_title"],
            "locale": "en-IN",
            "generation_reason": "translation",
            "operation": "translation",
            "source_artifact_id": pending["id"],
            "source_artifact_version": pending["version_number"],
            "idempotency_key": "translation-same-locale",
        },
        headers=ORIGIN,
    )
    assert same_locale.status_code == 422
    comparison = client.get(
        f"/api/v1/ai/studio/artifacts/{translated_id}/compare",
        params={"against_id": pending["id"]},
        headers=ORIGIN,
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["different_locale"] is True
    assert "Different locales" in comparison.json()["locale_warning"]


def test_localized_generation_is_separate_from_translation(client) -> None:
    context = setup_context(client)
    artifact = generate_artifact(
        client,
        context["product"]["id"],
        locale="te-IN",
        reason="localized_generation",
        key="localized-generation",
    )
    assert artifact["generation_reason"] == "localized_generation"
    assert artifact["parent_artifact_id"] is None
    assert artifact["source_artifact_version"] is None
    assert artifact["source_locale"] is None
