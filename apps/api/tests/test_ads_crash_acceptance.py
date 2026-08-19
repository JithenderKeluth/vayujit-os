from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
import test_ai_integration
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import func, select
from test_ai_integration import ORIGIN

from vayujit_api.ads import service as ads_service
from vayujit_api.ads.connectors import CONNECTORS
from vayujit_api.ads.models import Ad, AdCampaign, AdCreative, AdGroup, AdJob, AdRemoteMapping
from vayujit_api.ads.service import now
from vayujit_api.ads.worker import run_next_ads_job
from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _queue_campaign(client: Any, context: dict[str, Any], provider: str) -> dict[str, Any]:
    account = create_account(client, provider, f"crash-{provider}")
    payload = {
        "provider": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": f"{provider} crash acceptance",
        "objective": "awareness" if provider == "meta" else "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"{provider}-crash-{id(client)}",
    }
    preview = client.post("/api/v1/ads/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    return {"campaign": confirmed.json()["campaign"], "job_id": confirmed.json()["job"]["id"]}


def _reset_connector(provider: str) -> Any:
    connector = CONNECTORS[provider]
    connector.state.calls.clear()
    for entities in connector.state.entities.values():
        entities.clear()
    connector.state.failures.clear()
    return connector


def _owner_id() -> Any:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        return db.scalar(select(User.id).where(User.email == "owner@example.com"))


@pytest.mark.parametrize("provider", ["meta", "google"])
def test_ads_crash_before_connector_recovers_once(
    client: Any, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    context = setup_ads_context(client)
    connector = _reset_connector(provider)
    queued = _queue_campaign(client, context, provider)
    original = connector.create_campaign

    def crash_before(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("simulated Ads worker crash before connector invocation")

    monkeypatch.setattr(connector, "create_campaign", crash_before)
    owner_id = _owner_id()
    assert owner_id is not None
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db, pytest.raises(RuntimeError, match="before connector"):
        run_next_ads_job(db, owner_id=owner_id, worker_id="ads-crash-before-a")
    with test_ai_integration.factory() as db:
        job = db.get(AdJob, queued["job_id"])
        assert job is not None and job.status == "running"
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(connector, "create_campaign", original)
    with test_ai_integration.factory() as db:
        resumed = run_next_ads_job(db, owner_id=owner_id, worker_id="ads-crash-before-b")
        assert resumed is not None and resumed.status == "succeeded"
        assert resumed.attempt_count == 2
        campaign = db.get(AdCampaign, queued["campaign"]["id"])
        assert campaign is not None and campaign.remote_campaign_id
        assert db.scalar(select(func.count()).select_from(AdCampaign)) == 1
        assert db.scalar(select(func.count()).select_from(AdGroup)) == 0
        assert db.scalar(select(func.count()).select_from(Ad)) == 0
        assert db.scalar(select(func.count()).select_from(AdCreative)) == 0
        assert db.scalar(select(func.count()).select_from(AdRemoteMapping)) == 1
        completion_count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "ads.ad_campaign_created")
        )
        assert completion_count == 1
    assert (
        len([call for call in connector.state.calls if call["operation"] == "create_campaign"]) == 1
    )
    assert len(connector.state.entities["campaign"]) == 1


@pytest.mark.parametrize("provider", ["meta", "google"])
def test_ads_crash_after_remote_checkpoint_reuses_id(
    client: Any, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    context = setup_ads_context(client)
    _reset_connector(provider)
    queued = _queue_campaign(client, context, provider)
    original_record_event = ads_service.record_event
    raised = False

    def crash_after(*args: Any, **kwargs: Any) -> Any:
        nonlocal raised
        if kwargs.get("action") == "ads.ad_campaign_created" and not raised:
            raised = True
            raise RuntimeError("simulated Ads worker crash after checkpoint")
        return original_record_event(*args, **kwargs)

    monkeypatch.setattr(ads_service, "record_event", crash_after)
    owner_id = _owner_id()
    assert owner_id is not None
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        with pytest.raises(RuntimeError, match="after checkpoint"):
            run_next_ads_job(db, owner_id=owner_id, worker_id="ads-crash-after-a")
        db.rollback()
        checkpointed = db.get(AdJob, queued["job_id"])
        assert checkpointed is not None and checkpointed.result_json is not None
        checkpoint = checkpointed.result_json.get("remote_checkpoint")
        assert isinstance(checkpoint, dict)
        remote_id = checkpoint.get("remote_id")
        assert isinstance(remote_id, str)
    with test_ai_integration.factory() as db:
        job = db.get(AdJob, queued["job_id"])
        assert job is not None
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(ads_service, "record_event", original_record_event)
    with test_ai_integration.factory() as db:
        resumed = run_next_ads_job(db, owner_id=owner_id, worker_id="ads-crash-after-b")
        assert resumed is not None and resumed.status == "succeeded"
        assert resumed.result_json is not None
        assert resumed.result_json["remote_campaign_id"] == remote_id
