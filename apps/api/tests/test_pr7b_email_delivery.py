"""Focused PR-7B controlled RFQ EMAIL boundary certification."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_pr5b_landed_cost import _ok, _prepare
from test_pr7a_supplier_engagement import (
    ORIGIN,
    _engagement,
    _seed_current_proceed,
    _supplier_and_contact,
)

from vayujit_api.core.config import get_settings
from vayujit_api.intelligence.email_delivery_provider import reset_fake_provider

pytestmark = pytest.mark.integration
pytest_plugins = ["test_pr5b_landed_cost"]


def _enable_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAYUJIT_EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("VAYUJIT_EMAIL_DELIVERY_PROVIDER_MODE", "FAKE")
    monkeypatch.delenv("VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP", raising=False)
    get_settings.cache_clear()
    reset_fake_provider()


def _approved_flow(client: TestClient, key: str) -> dict[str, Any]:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity_id, supplier_id)
    engagement = _engagement(client, opportunity_id, supplier_id, contact_id, key)
    approved = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement['id']}/approve",
            json={"idempotency_key": f"{key}-approve", "reason": "Human reviewed"},
            headers=ORIGIN,
        )
    )
    assert approved["status"] == "APPROVED_FOR_SEND"
    return approved


def _second_opportunity(client: TestClient, key: str) -> tuple[str, str, str]:
    opportunity = _ok(
        client.post(
            "/api/v1/intelligence/product-opportunities",
            json={
                "name": f"Kids Lunch Box {key}",
                "description": "A reusable lunch box for children.",
                "product_concept": "reusable kids lunch box",
                "category": "Kids",
                "subcategory": "Lunch Boxes",
                "target_marketplace": "AMAZON_IN",
                "target_region": "IN",
                "origin": "external_research",
                "research_state": "completed",
                "evidence_state": "available",
                "intelligence_profile": {"evidence_environment": "DETERMINISTIC_TEST"},
                "lifecycle_status": "ready_for_assessment",
                "idempotency_key": f"{key}-opportunity",
            },
            headers=ORIGIN,
        )
    )
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity["id"], supplier_id)
    return opportunity["id"], supplier_id, contact_id


def test_pr7b_requires_second_human_action_and_has_no_provider_call(client: TestClient) -> None:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity_id, supplier_id)
    engagement = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7b-no-auth")
    readiness = _ok(
        client.get(
            f"/api/v1/intelligence/engagements/{engagement['id']}/send-eligibility",
            headers=ORIGIN,
        )
    )
    assert readiness["can_authorize_send"] is False
    assert (
        _ok(
            client.get(
                f"/api/v1/intelligence/engagements/{engagement['id']}/send-readiness",
                headers=ORIGIN,
            )
        )["provider_calls"]
        == 0
    )
    assert reset_fake_provider() is None


def test_pr7b_external_mutation_kill_switch_blocks_before_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAYUJIT_EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("VAYUJIT_EMAIL_DELIVERY_PROVIDER_MODE", "FAKE")
    monkeypatch.setenv("VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP", "true")
    get_settings.cache_clear()
    reset_fake_provider()
    approved = _approved_flow(client, "pr7b-kill-switch")
    readiness = _ok(
        client.get(
            f"/api/v1/intelligence/engagements/{approved['id']}/send-eligibility",
            headers=ORIGIN,
        )
    )
    assert readiness["can_authorize_send"] is False
    assert any(
        item["code"] == "EMAIL_PROVIDER_NOT_CONFIGURED" for item in readiness["blocking_reasons"]
    )
    assert (
        _ok(
            client.get(
                f"/api/v1/intelligence/engagements/{approved['id']}/send-readiness",
                headers=ORIGIN,
            )
        )["provider_calls"]
        == 0
    )


def test_pr7b_fake_acceptance_is_idempotent_and_reconstructable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_fake(monkeypatch)
    approved = _approved_flow(client, "pr7b-accepted")
    engagement_id = approved["id"]
    authorization = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send-authorize",
            json={
                "draft_version": approved["current_draft"]["version"],
                "channel": "EMAIL",
                "idempotency_key": "pr7b-send-auth",
                "confirm": True,
                "provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    auth_id = authorization["authorization"]["id"]
    sent = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send",
            json={
                "authorization_id": auth_id,
                "idempotency_key": "pr7b-logical-send",
                "confirm": True,
                "provider_outcome": "ACCEPTED",
            },
            headers=ORIGIN,
        )
    )
    assert sent["command"]["status"] == "PROVIDER_ACCEPTED"
    assert len(sent["command"]["attempts"]) == 1
    worker_replay = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/send-commands/{sent['command']['id']}/process",
            headers=ORIGIN,
        )
    )
    worker_replay_again = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/send-commands/{sent['command']['id']}/process",
            headers=ORIGIN,
        )
    )
    assert worker_replay["command"]["id"] == sent["command"]["id"]
    assert worker_replay_again["command"]["status"] == "PROVIDER_ACCEPTED"
    assert len(worker_replay_again["command"]["attempts"]) == 1
    replay = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send",
            json={"authorization_id": auth_id, "idempotency_key": "pr7b-logical-send"},
            headers=ORIGIN,
        )
    )
    assert replay["command"]["id"] == sent["command"]["id"]
    assert len(replay["command"]["attempts"]) == 1
    different_key_replay = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send",
            json={"authorization_id": auth_id, "idempotency_key": "pr7b-second-ui-click"},
            headers=ORIGIN,
        )
    )
    assert different_key_replay["command"]["id"] == sent["command"]["id"]
    assert len(different_key_replay["command"]["attempts"]) == 1

    detail = _ok(client.get(f"/api/v1/intelligence/engagements/{engagement_id}", headers=ORIGIN))
    assert detail["send_authorization"]["id"] == auth_id
    assert detail["send_command"]["status"] == "PROVIDER_ACCEPTED"

    reconstruction_script = """
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from vayujit_api.identity.models import User
from vayujit_api.intelligence.email_delivery_models import (
    RfqDeliveryAttempt,
    RfqSendAuthorization,
    RfqSendCommand,
    RfqSendOutbox,
)
from vayujit_api.intelligence.email_delivery_service import delivery_projection
from vayujit_api.intelligence.engagement_models import SupplierEngagement

engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
with Session(engine) as db:
    owner = db.scalar(select(User).where(User.email == "pr5b-owner@example.com"))
    assert owner is not None
    command = db.scalar(
        select(RfqSendCommand)
        .where(RfqSendCommand.owner_id == owner.id)
        .order_by(RfqSendCommand.created_at.desc())
    )
    assert command is not None and command.status == "PROVIDER_ACCEPTED"
    authorization = db.get(RfqSendAuthorization, command.authorization_id)
    outbox = db.scalar(
        select(RfqSendOutbox).where(RfqSendOutbox.command_id == command.id)
    )
    attempt = db.scalar(
        select(RfqDeliveryAttempt).where(RfqDeliveryAttempt.command_id == command.id)
    )
    engagement = db.get(SupplierEngagement, command.engagement_id)
    assert authorization is not None
    assert outbox is not None and outbox.state == "PROVIDER_ACCEPTED"
    assert attempt is not None and attempt.outcome == "ACCEPTED"
    assert engagement is not None
    projection = delivery_projection(db, owner, engagement.id)
    assert projection["send_authorization"]["id"] == str(authorization.id)
    assert projection["send_command"]["id"] == str(command.id)
    assert projection["send_command"]["status"] == "PROVIDER_ACCEPTED"
"""
    subprocess.run(
        [sys.executable, "-c", reconstruction_script],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )


def test_pr7b_stale_draft_blocks_without_provider_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_fake(monkeypatch)
    approved = _approved_flow(client, "pr7b-stale")
    engagement_id = approved["id"]
    authorization = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send-authorize",
            json={
                "draft_version": 1,
                "idempotency_key": "pr7b-stale-auth",
                "confirm": True,
                "provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/drafts",
            json={
                "requested_quantity": 250,
                "destination_region": "IN",
                "requested_fields": ["unit_price"],
                "idempotency_key": "pr7b-stale-revision",
                "provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    blocked = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send",
            json={
                "authorization_id": authorization["authorization"]["id"],
                "idempotency_key": "pr7b-stale-command",
            },
            headers=ORIGIN,
        )
    )
    assert blocked["command"]["status"] == "BLOCKED"
    assert blocked["command"]["attempts"] == []


def test_pr7b_failure_states_are_distinct_and_unknown_is_not_retryable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_fake(monkeypatch)
    approved = _approved_flow(client, "pr7b-retry")
    engagement_id = approved["id"]
    authorization = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send-authorize",
            json={"draft_version": 1, "idempotency_key": "pr7b-retry-auth"},
            headers=ORIGIN,
        )
    )
    auth_id = authorization["authorization"]["id"]
    failed = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send",
            json={
                "authorization_id": auth_id,
                "idempotency_key": "pr7b-retry-command",
                "provider_outcome": "RETRYABLE_FAILURE",
            },
            headers=ORIGIN,
        )
    )
    assert failed["command"]["status"] == "FAILED_RETRYABLE"
    retried = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{engagement_id}/send/retry",
            json={"idempotency_key": "pr7b-retry-2", "provider_outcome": "ACCEPTED"},
            headers=ORIGIN,
        )
    )
    assert retried["command"]["status"] == "PROVIDER_ACCEPTED"
    assert len(retried["command"]["attempts"]) == 2

    opportunity_id, supplier_id, contact_id = _second_opportunity(client, "pr7b-unknown")
    approved_unknown = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7b-unknown")
    approved_unknown = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{approved_unknown['id']}/approve",
            json={"idempotency_key": "pr7b-unknown-approve", "reason": "Human reviewed"},
            headers=ORIGIN,
        )
    )
    unknown_auth = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{approved_unknown['id']}/send-authorize",
            json={"draft_version": 1, "idempotency_key": "pr7b-unknown-auth"},
            headers=ORIGIN,
        )
    )
    unknown = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{approved_unknown['id']}/send",
            json={
                "authorization_id": unknown_auth["authorization"]["id"],
                "idempotency_key": "pr7b-unknown-command",
                "provider_outcome": "UNKNOWN_OUTCOME",
            },
            headers=ORIGIN,
        )
    )
    assert unknown["command"]["status"] == "UNKNOWN_OUTCOME"
    blocked_retry = client.post(
        f"/api/v1/intelligence/engagements/{approved_unknown['id']}/send/retry",
        json={"idempotency_key": "pr7b-unknown-retry"},
        headers=ORIGIN,
    )
    assert blocked_retry.status_code == 409
