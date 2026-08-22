from __future__ import annotations

import concurrent.futures
from datetime import timedelta
from typing import Any, cast

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN
from test_marketing_plan_slice4_acceptance import _confirm_plan
from test_marketing_plan_slice4_final_proof import _payload

from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.models import AdJob
from vayujit_api.ads.service import now
from vayujit_api.ads.worker import run_next_ads_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _prepare_remote_v2(
    client: Any, context: dict[str, Any], suffix: str
) -> tuple[str, Any, dict[str, Any]]:
    create_account(client, "meta", suffix)
    plan = _confirm_plan(client, _payload(context, "meta", suffix))
    plan_id = plan["id"]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        first = run_next_ads_job(db, worker_id=f"{suffix}-v1")
        assert first is not None and first.status == "succeeded"
    connector = connector_for("meta")
    remote = list(connector.state.entities["campaign"].values())[-1]
    version = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/versions",
        json={
            "expected_version": 1,
            "creative_mapping": {"meta": {"artifact_version": 2}},
            "schedule": {"mode": "scheduled", "scheduled_at": "2030-02-01T00:00:00Z"},
        },
        headers=ORIGIN,
    )
    assert version.status_code == 200, version.text
    connector.update_campaign(
        str(remote["remote_id"]),
        {
            "budget_version": 2,
            "creative_mapping": {"meta": {"artifact_version": 2}},
            "schedule": {"mode": "scheduled", "scheduled_at": "2030-02-01T00:00:00Z"},
        },
    )
    return plan_id, connector, remote


def _confirm_rollback(client: Any, plan_id: str) -> None:
    preview = client.post(f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
        params={"preview_fingerprint": preview.json()["fingerprint"], "confirm": "true"},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text


def test_creative_rollback_restores_provider_mapping(client: Any) -> None:
    context = setup_ads_context(client)
    plan_id, connector, remote = _prepare_remote_v2(client, context, "creative-rollback")
    _confirm_rollback(client, plan_id)
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        job = run_next_ads_job(db, worker_id="creative-rollback-proof")
        assert job is not None and job.status == "succeeded"
    assert remote["creative_mapping"] == {"meta": {"artifact_version": 1}}
    assert connector.state.calls[-1]["payload"]["rollback"] is True


def test_schedule_rollback_restores_provider_schedule(client: Any) -> None:
    context = setup_ads_context(client)
    plan_id, connector, remote = _prepare_remote_v2(client, context, "schedule-rollback")
    _confirm_rollback(client, plan_id)
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        job = run_next_ads_job(db, worker_id="schedule-rollback-proof")
        assert job is not None and job.status == "succeeded"
    assert remote["schedule"] == {"mode": "immediate"}
    assert connector.state.calls[-1]["payload"]["rollback"] is True


@pytest.mark.parametrize("mutation", ["creative", "schedule"])
def test_concurrent_creative_and_schedule_rollback_is_idempotent(
    client: Any, mutation: str
) -> None:
    context = setup_ads_context(client)
    plan_id, connector, remote = _prepare_remote_v2(
        client, context, f"concurrent-{mutation}-rollback"
    )
    before_rollbacks = len(
        [call for call in connector.state.calls if call["payload"].get("rollback")]
    )
    preview = client.post(f"/api/v1/ads/marketing/plans/{plan_id}/rollback/preview", headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    params = {"preview_fingerprint": preview.json()["fingerprint"], "confirm": "true"}

    def submit() -> Any:
        return client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/rollback/confirm",
            params=params,
            headers=ORIGIN,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert sorted(response.json()["idempotent_reuse"] for response in responses) == [False, True]
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        jobs = list(
            db.scalars(
                select(AdJob).where(
                    AdJob.operation == "marketing_plan_rollback",
                    AdJob.request_json["plan_id"].astext == plan_id,
                )
            )
        )
        assert len(jobs) == 1
        job = run_next_ads_job(db, worker_id=f"concurrent-{mutation}-rollback-worker")
        assert job is not None and job.status == "succeeded"
    assert remote["creative_mapping"] == {"meta": {"artifact_version": 1}}
    assert remote["schedule"] == {"mode": "immediate"}
    assert (
        len([call for call in connector.state.calls if call["payload"].get("rollback")])
        == before_rollbacks + 1
    )


def test_marketing_crash_before_connector_recovers_once(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", "crash-before")
    plan = _confirm_plan(client, _payload(context, "meta", "crash-before"))
    connector = connector_for("meta")
    initial_create_calls = len(
        [call for call in connector.state.calls if call["operation"] == "create_campaign"]
    )
    original = connector.create_campaign

    def crash_before(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("simulated marketing crash before connector")

    monkeypatch.setattr(connector, "create_campaign", crash_before)
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        failed = run_next_ads_job(db, worker_id="marketing-crash-before-a")
        assert failed is not None and failed.status == "failed"
    with integration_fixture.factory() as db:
        job = db.scalar(select(AdJob).where(AdJob.request_json["plan_id"].astext == plan["id"]))
        assert job is not None
        job.status = "queued"
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(connector, "create_campaign", original)
    with integration_fixture.factory() as db:
        resumed = run_next_ads_job(db, worker_id="marketing-crash-before-b")
        assert resumed is not None and resumed.status == "succeeded"
        assert resumed.attempt_count == 2
    assert (
        len([call for call in connector.state.calls if call["operation"] == "create_campaign"])
        == initial_create_calls + 1
    )


def test_marketing_crash_after_checkpoint_reuses_provider_result(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_ads_context(client)
    create_account(client, "meta", "crash-after")
    plan = _confirm_plan(client, _payload(context, "meta", "crash-after"))
    connector = connector_for("meta")
    import vayujit_api.ads.marketing_execution as execution_module

    initial_create_calls = len(
        [call for call in connector.state.calls if call["operation"] == "create_campaign"]
    )
    original_record_event = execution_module.record_event
    raised = False

    def crash_after(*args: Any, **kwargs: Any) -> Any:
        nonlocal raised
        if kwargs.get("action") == "ads.marketing_plan_execution_completed" and not raised:
            raised = True
            raise RuntimeError("simulated marketing crash after checkpoint")
        return original_record_event(*args, **kwargs)

    monkeypatch.setattr(execution_module, "record_event", crash_after)
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        failed = run_next_ads_job(db, worker_id="marketing-crash-after-a")
        assert failed is not None
    with integration_fixture.factory() as db:
        job = db.scalar(select(AdJob).where(AdJob.request_json["plan_id"].astext == plan["id"]))
        assert job is not None and job.result_json is not None
        checkpoint_payload = cast(dict[str, Any], job.result_json)
        assert cast(dict[str, Any], checkpoint_payload.get("checkpoint", {})).get("remote_id")
        job.status = "queued"
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(execution_module, "record_event", original_record_event)
    with integration_fixture.factory() as db:
        resumed = run_next_ads_job(db, worker_id="marketing-crash-after-b")
        assert resumed is not None and resumed.status == "succeeded"
    assert (
        len([call for call in connector.state.calls if call["operation"] == "create_campaign"])
        == initial_create_calls + 1
    )
