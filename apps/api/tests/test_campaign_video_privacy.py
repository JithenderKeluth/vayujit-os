from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from helpers import marketplace_video_fixture
from test_campaign_video_cross_channel import _create_and_materialize
from test_campaign_video_execution import _approved_lineage, _campaign, _factory, _request

from vayujit_api.commerce.marketplace_video import fake_video_connector_state
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import FakeSocialConnector

client = ai_fixture.client
pytestmark = pytest.mark.integration


def test_campaign_triggered_connector_payloads_exclude_unrelated_private_data(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    captured_social: list[dict[str, object]] = []
    original_publish = FakeSocialConnector.publish_post

    def capture_publish(
        connector: FakeSocialConnector,
        account: dict[str, object],
        post: dict[str, object],
        idempotency_key: str,
    ) -> dict[str, object]:
        captured_social.append(
            {
                "account": dict(account),
                "post": dict(post),
                "idempotency_key": idempotency_key,
            }
        )
        return original_publish(connector, account, post, idempotency_key)

    monkeypatch.setattr(FakeSocialConnector, "publish_post", capture_publish)
    lineage = _approved_lineage(
        client, context, "youtube_video", "youtube", key="campaign-video-privacy-social"
    )
    social_account_id = video_fixture._account(client, "youtube", "-campaign-privacy")
    social_request = _request(context, lineage, social_account_id, "youtube_video")
    social_request["idempotency_key"] = "campaign-video-privacy-social"
    _create_and_materialize(client, str(campaign["id"]), social_request)

    marketplace = "amazon"
    scenario = marketplace_video_fixture.create_marketplace_video_scenario(
        client, marketplace, context
    )
    marketplace_request: dict[str, object] = {
        "product_id": context["product"]["id"],
        "video_generation_id": scenario.generation_id,
        "video_output_id": scenario.output_id,
        "video_media_id": scenario.media_id,
        "video_version": scenario.version,
        "video_channel": marketplace,
        "name": "Campaign Video privacy marketplace",
        "scheduled_local_at": (datetime.now(UTC) - timedelta(minutes=1))
        .replace(tzinfo=None)
        .isoformat(),
        "timezone_name": "UTC",
        "target_account_id": scenario.account_id,
        "target_listing_id": scenario.listing_id,
        "metadata_artifact_id": lineage["artifact_id"],
        "metadata_artifact_version": lineage["artifact_version"],
        "metadata": {"title": "Campaign Video privacy acceptance"},
        "idempotency_key": "campaign-video-privacy-amazon",
    }
    marketplace_payload_count = len(
        cast(list[dict[str, object]], fake_video_connector_state()[marketplace]["payloads"])
    )
    _create_and_materialize(client, str(campaign["id"]), marketplace_request)

    with _factory() as db:
        job_ids = claim_jobs(db, "campaign-video-privacy-worker", 10, 60)
        assert len(job_ids) == 2
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    for job_id in job_ids:
        execute_job(job_id, "campaign-video-privacy-worker")

    marketplace_payloads = cast(
        list[dict[str, object]], fake_video_connector_state()[marketplace]["payloads"]
    )[marketplace_payload_count:]
    assert len(captured_social) == 1
    assert len(marketplace_payloads) == 1
    payloads: list[dict[str, object]] = [captured_social[0], marketplace_payloads[0]]
    serialized = json.dumps(payloads, sort_keys=True, default=str).lower()
    for forbidden in (
        "buyer",
        "order",
        "payment",
        "settlement",
        "credential",
        "password",
        "access_token",
        "refresh_token",
        "database_url",
        "postgresql://",
        "site-packages",
        "c:\\\\users\\",
        "/users/",
    ):
        assert forbidden not in serialized
    product_ids = {
        str(payload["product_id"])
        for payload in marketplace_payloads
        if payload.get("product_id") is not None
    }
    assert product_ids == {str(context["product"]["id"])}
