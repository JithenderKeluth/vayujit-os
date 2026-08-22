from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_account, setup_ads_context
from test_ai_integration import ORIGIN
from test_marketing_plan_slice4_acceptance import _confirm_plan
from test_marketing_plan_slice4_final_proof import _payload

from vayujit_api.ads.worker import run_next_ads_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_marketing_storage_growth_and_integrity_are_canonical(client: Any) -> None:
    context = setup_ads_context(client)
    before_response = client.get("/api/v1/ads/marketing/storage/integrity", headers=ORIGIN)
    assert before_response.status_code == 200, before_response.text
    before = before_response.json()
    create_account(client, "meta", "storage-growth")
    plan = _confirm_plan(client, _payload(context, "meta", "storage-growth"))
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        job = run_next_ads_job(db, worker_id="storage-growth-proof")
        assert job is not None and job.status == "succeeded"
    after_response = client.get("/api/v1/ads/marketing/storage/integrity", headers=ORIGIN)
    assert after_response.status_code == 200, after_response.text
    after = after_response.json()
    assert after["status"] == "pass"
    assert after["owner_scoped"] is True
    assert all(value == 0 for value in after["integrity"].values())
    assert after["counts"]["plans"] - before["counts"]["plans"] == 1
    assert after["counts"]["plan_revisions"] - before["counts"]["plan_revisions"] == 1
    assert after["counts"]["channel_executions"] - before["counts"]["channel_executions"] == 1
    assert after["counts"]["jobs"] - before["counts"]["jobs"] == 1
    assert after["counts"]["job_attempts"] - before["counts"]["job_attempts"] == 1
    assert after["counts"]["schedules"] - before["counts"]["schedules"] == 1
    assert plan["id"]
