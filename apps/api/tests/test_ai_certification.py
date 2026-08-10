from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import AIStudioJob, AIStudioOutput
from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.commerce.models import MarketplaceListing

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def db_session():
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def run_worker(worker_id: str, limit: int = 50) -> int:
    from vayujit_api.ai.studio_worker import run_ai_jobs_once

    with db_session() as db:
        return run_ai_jobs_once(db, worker_id, limit=limit)


def test_full_ai_product_certification_e2e(client: Any) -> None:
    context = setup_context(client)
    brand_id = context["brand"]["id"]
    product_id = context["product"]["id"]
    voice = client.post(
        "/api/v1/ai/studio/brand-voices",
        json={"name": "Certification voice", "brand_id": brand_id, "tone": "clear"},
        headers=ORIGIN,
    )
    assert voice.status_code == 201, voice.text
    voice_id = voice.json()["id"]
    channels = ["amazon", "flipkart", "meesho", "wordpress", "shopify"]
    preset = client.post(
        "/api/v1/ai/studio/presets",
        json={
            "name": "Certification preset",
            "channels": channels,
            "output_types": ["marketplace_listing"],
            "brand_voice_id": voice_id,
        },
        headers=ORIGIN,
    )
    assert preset.status_code == 201, preset.text
    preset_id = preset.json()["id"]
    keywords = client.post(
        "/api/v1/ai/studio/keywords",
        json={
            "name": "Certification keywords",
            "product_id": product_id,
            "primary_keywords": ["trail bottle", "insulated bottle"],
            "website_keywords": ["reusable bottle"],
        },
        headers=ORIGIN,
    )
    assert keywords.status_code == 201, keywords.text

    queued = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": channels,
            "content_types": ["marketplace_listing"],
            "brand_voice_id": voice_id,
            "preset_id": preset_id,
            "idempotency_key": "certification-five-channel",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    assert run_worker("certification-worker") == 5
    generation = client.get(f"/api/v1/ai/studio/generations/{queued.json()['id']}", headers=ORIGIN)
    assert generation.status_code == 200, generation.text
    outputs = generation.json()["outputs"]
    assert generation.json()["status"] == "completed"
    assert {item["channel"] for item in outputs} == set(channels)
    artifacts: dict[str, dict[str, Any]] = {}
    for output in outputs:
        response = client.get(
            f"/api/v1/ai/studio/artifacts/{output['artifact_id']}", headers=ORIGIN
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["context_fingerprint"]
        assert body["brand_voice_version"] == 1
        assert body["preset_version"] == "1"
        artifacts[body["channel"]] = body
    assert set(artifacts) == set(channels)

    # Historical lineage survives newer Voice/Preset records.
    assert (
        client.patch(
            f"/api/v1/ai/studio/brand-voices/{voice_id}",
            json={"name": "Certification voice v2", "brand_id": brand_id, "tone": "warm"},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/ai/studio/presets/{preset_id}",
            json={
                "name": "Certification preset v2",
                "channels": channels,
                "output_types": ["marketplace_listing"],
                "brand_voice_id": voice_id,
            },
            headers=ORIGIN,
        ).status_code
        == 200
    )
    for body in artifacts.values():
        assert (
            client.get(f"/api/v1/ai/studio/artifacts/{body['id']}", headers=ORIGIN).json()[
                "brand_voice_version"
            ]
            == 1
        )

    compared = client.get(
        f"/api/v1/ai/studio/artifacts/{artifacts['amazon']['id']}/compare",
        params={"against_id": artifacts["flipkart"]["id"]},
        headers=ORIGIN,
    )
    assert compared.status_code == 200, compared.text

    editable = artifacts["shopify"]
    key = next(k for k, value in editable["content"].items() if isinstance(value, str))
    edited = client.patch(
        f"/api/v1/ai/studio/artifacts/{editable['id']}",
        json={
            "content": {**editable["content"], key: "Human-certified edit"},
            "expected_source_version": editable["version_number"],
        },
        headers=ORIGIN,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["source"] == "ai_human_edited"
    assert (
        client.get(f"/api/v1/ai/studio/artifacts/{editable['id']}", headers=ORIGIN).json()[
            "content"
        ]
        == editable["content"]
    )
    assert (
        client.post(
            f"/api/v1/ai/studio/artifacts/{edited.json()['id']}/approve", headers=ORIGIN
        ).status_code
        == 200
    )

    rejected = artifacts["wordpress"]
    assert (
        client.post(
            f"/api/v1/ai/studio/artifacts/{rejected['id']}/reject",
            json={"reason": "Certification rejection", "regeneration_guidance": "Shorten title"},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    regenerated = client.post(
        f"/api/v1/ai/studio/artifacts/{rejected['id']}/regenerate", headers=ORIGIN
    )
    assert regenerated.status_code in {201, 202}, regenerated.text
    assert run_worker("certification-regeneration") == 1
    regen = client.get(
        f"/api/v1/ai/studio/generations/{regenerated.json()['id']}", headers=ORIGIN
    ).json()["outputs"][0]["artifact_id"]
    regen_body = client.get(f"/api/v1/ai/studio/artifacts/{regen}", headers=ORIGIN).json()
    assert regen_body["parent_artifact_id"] == rejected["id"]
    assert (
        client.post(f"/api/v1/ai/studio/artifacts/{regen}/approve", headers=ORIGIN).status_code
        == 200
    )

    approved_channels = ["amazon", "flipkart", "meesho"]
    listings: dict[str, str] = {}
    destinations: dict[str, str] = {}
    for channel in approved_channels:
        assert (
            client.post(
                f"/api/v1/ai/studio/artifacts/{artifacts[channel]['id']}/approve", headers=ORIGIN
            ).status_code
            == 200
        )
        account = client.post(
            "/api/v1/marketplaces/accounts",
            json={
                "marketplace": channel,
                "display_name": f"Certification {channel}",
                "seller_account_id": f"cert-{channel}",
            },
            headers=ORIGIN,
        )
        assert account.status_code == 201, account.text
        listing = client.post(
            "/api/v1/marketplaces/listings",
            json={
                "brand_id": brand_id,
                "product_id": product_id,
                "account_id": account.json()["id"],
                "title": f"Certification {channel} listing",
                "idempotency_key": f"cert-listing-{channel}",
            },
            headers=ORIGIN,
        )
        assert listing.status_code == 201, listing.text
        listings[channel] = listing.json()["id"]
        handoff = client.post(
            f"/api/v1/ai/studio/artifacts/{artifacts[channel]['id']}/listing-handoff",
            json={
                "marketplace": channel,
                "listing_id": listings[channel],
                "confirm": True,
                "expected_artifact_version": artifacts[channel]["version_number"],
            },
            headers=ORIGIN,
        )
        assert handoff.status_code == 200, handoff.text
        destination = client.post(
            "/api/v1/publishing/destinations",
            json={
                "name": f"Certification {channel}",
                "brand_id": brand_id,
                "connector_key": "mock_publisher_v1",
                "configuration": {"channel_name": channel, "simulate_failure": False},
            },
            headers=ORIGIN,
        )
        assert destination.status_code == 201, destination.text
        destinations[channel] = destination.json()["id"]

    stamp = datetime.now(UTC).replace(microsecond=0)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": brand_id,
            "name": "Certification campaign",
            "timezone_name": "UTC",
            "local_start_at": (stamp - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
            "local_end_at": (stamp + timedelta(days=1)).replace(tzinfo=None).isoformat(),
        },
        headers=ORIGIN,
    )
    assert campaign.status_code == 201, campaign.text
    activities: dict[str, str] = {}
    for sequence, channel in enumerate(approved_channels, start=1):
        activity = client.post(
            f"/api/v1/campaigns/{campaign.json()['id']}/activities",
            json={
                "product_id": product_id,
                "artifact_id": artifacts[channel]["id"],
                "destination_id": destinations[channel],
                "activity_type": "mock_publish",
                "name": f"Certification {channel}",
                "sequence": sequence,
                "scheduled_local_date": stamp.date().isoformat(),
                "scheduled_local_time": stamp.time().replace(tzinfo=None).isoformat(),
                "timezone_name": "UTC",
                "required": True,
            },
            headers=ORIGIN,
        )
        assert activity.status_code == 201, activity.text
        activities[channel] = activity.json()["id"]
        handoff = client.post(
            f"/api/v1/ai/studio/artifacts/{artifacts[channel]['id']}/campaign-handoff",
            json={
                "activity_id": activities[channel],
                "confirm": True,
                "expected_artifact_version": artifacts[channel]["version_number"],
            },
            headers=ORIGIN,
        )
        assert handoff.status_code == 200, handoff.text

    amazon_v2_response = client.post(
        f"/api/v1/ai/studio/artifacts/{artifacts['amazon']['id']}/regenerate", headers=ORIGIN
    )
    assert amazon_v2_response.status_code in {201, 202}, amazon_v2_response.text
    assert run_worker("certification-amazon-regeneration") == 1
    amazon_v2_id = client.get(
        f"/api/v1/ai/studio/generations/{amazon_v2_response.json()['id']}", headers=ORIGIN
    ).json()["outputs"][0]["artifact_id"]
    amazon_v2 = client.get(f"/api/v1/ai/studio/artifacts/{amazon_v2_id}", headers=ORIGIN).json()
    assert amazon_v2["version_number"] > artifacts["amazon"]["version_number"]
    assert (
        client.post(
            f"/api/v1/ai/studio/artifacts/{amazon_v2_id}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    with db_session() as db:
        for channel in approved_channels:
            listing = db.get(MarketplaceListing, listings[channel])
            activity = db.get(CampaignActivity, activities[channel])
            assert listing is not None and activity is not None
            assert listing.content_artifact_version == artifacts[channel]["version_number"]
            assert activity.artifact_version == artifacts[channel]["version_number"]

    localized = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["amazon"],
            "content_types": ["marketplace_listing"],
            "locale": "hi-IN",
            "generation_reason": "localized_generation",
            "operation": "localized_generation",
            "idempotency_key": "cert-localized-hi",
        },
        headers=ORIGIN,
    )
    assert localized.status_code == 202, localized.text
    assert run_worker("certification-localized") == 1
    localized_id = client.get(
        f"/api/v1/ai/studio/generations/{localized.json()['id']}", headers=ORIGIN
    ).json()["outputs"][0]["artifact_id"]
    localized_body = client.get(
        f"/api/v1/ai/studio/artifacts/{localized_id}", headers=ORIGIN
    ).json()
    assert localized_body["locale"] == "hi-IN"

    translated = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["amazon"],
            "content_types": ["marketplace_listing"],
            "locale": "te-IN",
            "source_artifact_id": artifacts["amazon"]["id"],
            "source_artifact_version": artifacts["amazon"]["version_number"],
            "generation_reason": "translation",
            "operation": "translation",
            "idempotency_key": "cert-translation-te",
        },
        headers=ORIGIN,
    )
    assert translated.status_code == 202, translated.text
    assert run_worker("certification-translated") == 1
    translated_id = client.get(
        f"/api/v1/ai/studio/generations/{translated.json()['id']}", headers=ORIGIN
    ).json()["outputs"][0]["artifact_id"]
    translated_body = client.get(
        f"/api/v1/ai/studio/artifacts/{translated_id}", headers=ORIGIN
    ).json()
    assert translated_body["locale"] == "te-IN"
    assert translated_body["source_artifact_version"] == artifacts["amazon"]["version_number"]
    assert translated_body["source_locale"] == "en-IN"

    seo = client.post(
        "/api/v1/ai/studio/seo/analyze",
        json={
            "product_id": product_id,
            "artifact_id": artifacts["amazon"]["id"],
            "channel": "amazon",
        },
        headers=ORIGIN,
    )
    assert seo.status_code == 200, seo.text
    intelligence = client.get(f"/api/v1/ai/seo/products/{product_id}/channels")
    assert intelligence.status_code == 200, intelligence.text
    assert {item["channel"] for item in intelligence.json()} == {
        "canonical",
        "wordpress",
        "shopify",
        "amazon",
        "flipkart",
        "meesho",
    }
    assert all(item.get("search_volume") is None for item in intelligence.json())
    assert client.get("/api/v1/ai/studio/usage", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/ai/studio/diagnostics", headers=ORIGIN).status_code == 200
    with db_session() as db:
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "ai.artifact_listing_handoff_completed" in actions
        assert "ai.translated_artifact_generated" in actions
        assert "ai.localized_artifact_generated" in actions


def test_ai_certification_concurrent_idempotency(client: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    context = setup_context(client)
    payload = {
        "product_ids": [context["product"]["id"]],
        "channels": ["amazon"],
        "content_types": ["product_title"],
        "idempotency_key": "cert-concurrent-generation",
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda _: client.post("/api/v1/ai/studio/generate", json=payload, headers=ORIGIN),
                range(4),
            )
        )
    assert all(response.status_code == 202 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    assert run_worker("cert-concurrency") == 1
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(GeneratedArtifact)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ai.content_generated")
            )
            == 1
        )


def test_ai_certification_database_integrity_and_api_restart(client: Any) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [context["product"]["id"]],
            "channels": ["amazon", "flipkart"],
            "content_types": ["product_title"],
            "idempotency_key": "cert-restart-persistence",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    assert test_ai_integration.factory is not None
    from fastapi.testclient import TestClient

    from vayujit_api.core.database import get_session
    from vayujit_api.main import create_app

    app = create_app()

    def session_override():
        with test_ai_integration.factory() as db:
            yield db

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as restarted:
        restarted.cookies.update(client.cookies)
        persisted = restarted.get(
            f"/api/v1/ai/studio/generations/{queued.json()['id']}", headers=ORIGIN
        )
        assert persisted.status_code == 200, persisted.text
        assert persisted.json()["status"] == "queued"
    assert run_worker("cert-restart-worker") == 2
    with db_session() as db:
        jobs = list(db.scalars(select(AIStudioJob)))
        artifacts = list(db.scalars(select(GeneratedArtifact)))
        assert len(jobs) == 2
        assert len(artifacts) == 2
        assert all(job.state == "succeeded" for job in jobs)
        assert all(str(artifact.product_id) == context["product"]["id"] for artifact in artifacts)
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIStudioOutput)
                .where(AIStudioOutput.artifact_id.is_(None))
            )
            == 0
        )
