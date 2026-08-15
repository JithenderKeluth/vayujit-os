from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.video.models import VideoGeneration, VideoOutput


@dataclass
class MarketplaceVideoScenario:
    client: TestClient
    marketplace: str
    context: dict[str, Any]
    account_id: str
    listing_id: str
    generation_id: str
    output_id: str
    media_id: str
    version: int = 1


def db_session() -> Session:
    assert test_ai_integration.factory is not None
    return test_ai_integration.factory()


def _video_payload(context: dict[str, Any], key: str) -> dict[str, object]:
    return {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "video_type": "product_showcase",
        "target_channel": "youtube",
        "resolution": "320x240",
        "duration_seconds": 2,
        "idempotency_key": key,
    }


def _create_approved_video(
    client: TestClient, context: dict[str, Any], key: str
) -> tuple[str, str, str]:
    queued = client.post(
        "/api/v1/ai/video/queue", json=_video_payload(context, key), headers=ORIGIN
    )
    assert queued.status_code == 202, queued.text
    generation_id = queued.json()["id"]
    with db_session() as db:
        assert run_ai_jobs_once(db, f"marketplace-video-{key}", limit=1) == 1
    approved = client.post(
        f"/api/v1/ai/video/generations/{generation_id}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text
    with db_session() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation.id))
        assert output is not None and output.media_id is not None
        return str(generation.id), str(output.id), str(output.media_id)


def create_marketplace_video_scenario(
    client: TestClient, marketplace: str, context: dict[str, Any] | None = None
) -> MarketplaceVideoScenario:
    context = context or setup_context(client)
    account = client.post(
        "/api/v1/marketplaces/accounts",
        json={
            "marketplace": marketplace,
            "display_name": f"{marketplace.title()} acceptance account",
            "seller_account_id": f"seller-{marketplace}",
            "credentials": {"token": f"local-{marketplace}-token"},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    validated = client.post(f"/api/v1/marketplaces/accounts/{account_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    enabled = client.post(f"/api/v1/marketplaces/accounts/{account_id}/enable", headers=ORIGIN)
    assert enabled.status_code == 200, enabled.text
    listing = client.post(
        "/api/v1/marketplaces/listings",
        json={
            "product_id": context["product"]["id"],
            "brand_id": context["brand"]["id"],
            "account_id": account_id,
            "title": f"{marketplace.title()} video listing",
            "marketplace_sku": f"SKU-{marketplace}-video",
            "idempotency_key": f"listing-{marketplace}-video",
        },
        headers=ORIGIN,
    )
    assert listing.status_code == 201, listing.text
    generation_id, output_id, media_id = _create_approved_video(
        client, context, f"marketplace-video-{marketplace}-v1"
    )
    return MarketplaceVideoScenario(
        client=client,
        marketplace=marketplace,
        context=context,
        account_id=account_id,
        listing_id=listing.json()["id"],
        generation_id=generation_id,
        output_id=output_id,
        media_id=media_id,
    )


def request_payload(scenario: MarketplaceVideoScenario, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "listing_id": scenario.listing_id,
        "account_id": scenario.account_id,
        "video_generation_id": scenario.generation_id,
        "video_output_id": scenario.output_id,
        "video_media_id": scenario.media_id,
        "video_version": scenario.version,
        "correlation_id": f"corr-{scenario.marketplace}",
    }
    payload.update(overrides)
    return payload


def create_replacement_video(scenario: MarketplaceVideoScenario) -> tuple[str, str, str]:
    regenerated = scenario.client.post(
        f"/api/v1/ai/video/generations/{scenario.generation_id}/regenerate",
        json={"reason": "custom", "feedback": "Use a fresh approved video."},
        headers=ORIGIN,
    )
    assert regenerated.status_code == 202, regenerated.text
    generation_id = regenerated.json()["id"]
    with db_session() as db:
        assert (
            run_ai_jobs_once(db, f"marketplace-video-{scenario.marketplace}-replacement", limit=1)
            == 1
        )
    approved = scenario.client.post(
        f"/api/v1/ai/video/generations/{generation_id}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text
    with db_session() as db:
        generation = db.get(VideoGeneration, generation_id)
        assert generation is not None
        output = db.scalar(select(VideoOutput).where(VideoOutput.generation_id == generation.id))
        assert output is not None and output.media_id is not None
        return str(generation.id), str(output.id), str(output.media_id)
