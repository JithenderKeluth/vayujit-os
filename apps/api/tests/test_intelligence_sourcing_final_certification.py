from __future__ import annotations

import uuid
from typing import Any

import pytest
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence.sourcing_closure import safe_report
from vayujit_api.intelligence.sourcing_service import SOURCING_RECOVERY_ACTIONS

pytest_plugins = ["test_ai_integration"]
pytestmark = pytest.mark.integration


def test_recovery_taxonomy_actions_are_advertised_and_executable(client: Any) -> None:
    setup_context(client)
    job = client.post(
        "/api/v1/intelligence/sourcing/worker/jobs",
        json={"task": "cost_recalculation", "idempotency_key": "taxonomy-job"},
        headers=ORIGIN,
    )
    assert job.status_code == 201, job.text
    entity_id = job.json()["id"]
    assert set(SOURCING_RECOVERY_ACTIONS) == {
        "invalid_requirement",
        "invalid_supplier_state",
        "quote_expired",
        "quote_invalid",
        "currency_mismatch",
        "cost_calculation_failed",
        "missing_assumption",
        "sample_failed",
        "inspection_failed",
        "checkpoint_invalid",
    }
    index = 0
    for failure_code, actions in SOURCING_RECOVERY_ACTIONS.items():
        for action in actions:
            response = client.post(
                "/api/v1/intelligence/sourcing/recovery",
                json={
                    "entity_type": "sourcing_worker_job",
                    "entity_id": entity_id,
                    "action": action,
                    "failure_code": failure_code,
                    "idempotency_key": f"taxonomy-{index}",
                    "reason": "Bounded local certification recovery.",
                },
                headers=ORIGIN,
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["failure_code"] == failure_code
            assert result["allowed_actions"] == list(actions)
            assert result["action"] == action
            assert result["safe_message"]
            assert result["correlation_id"]
            assert result["status"] == "recovered"
            index += 1


def test_product_channel_calendar_history_and_report_boundaries(client: Any) -> None:
    context = setup_context(client)
    product_id = context["product"]["id"]
    requirement = client.post(
        "/api/v1/intelligence/sourcing/requirements",
        json={
            "product_id": product_id,
            "idempotency_key": "projection-requirement",
            "payload": {"category": "disposable", "target_quantity": 1},
        },
        headers=ORIGIN,
    )
    assert requirement.status_code == 201, requirement.text
    projection = client.get(
        f"/api/v1/intelligence/sourcing/product-channel/{product_id}", headers=ORIGIN
    )
    assert projection.status_code == 200, projection.text
    assert {
        "research_status",
        "supplier_status",
        "rfq_status",
        "quote_status",
        "sample_status",
        "inspection_status",
        "economics_status",
        "sourcing_decision",
    } <= projection.json().keys()

    calendar = client.post(
        "/api/v1/intelligence/sourcing/calendar",
        json={
            "idempotency_key": "calendar-follow-up",
            "kind": "rfq_follow_up",
            "title": "RFQ follow-up",
            "due_at": "2030-01-01T00:00:00Z",
            "entity_type": "requirement",
            "entity_id": requirement.json()["requirement"]["id"],
            "payload": {"informational": True},
        },
        headers=ORIGIN,
    )
    assert calendar.status_code == 201, calendar.text
    assert client.get("/api/v1/intelligence/sourcing/calendar", headers=ORIGIN).json()["items"]
    history = client.get("/api/v1/intelligence/sourcing/history/unified", headers=ORIGIN)
    assert history.status_code == 200, history.text
    assert any(item["kind"] == "requirement" for item in history.json()["items"])
    for format_name in ("json", "markdown", "html"):
        report = client.get(f"/api/v1/intelligence/sourcing/report/{format_name}", headers=ORIGIN)
        assert report.status_code == 200, report.text
        assert "postgresql://" not in report.text.lower()
        assert "traceback" not in report.text.lower()

    foreign = str(uuid.uuid4())
    for path in (
        f"/api/v1/intelligence/sourcing/requirements/{foreign}",
        f"/api/v1/intelligence/sourcing/rfqs/{foreign}",
        f"/api/v1/intelligence/sourcing/quotes/{foreign}",
        f"/api/v1/intelligence/sourcing/samples/{foreign}",
        f"/api/v1/intelligence/sourcing/scenarios/{foreign}",
        f"/api/v1/intelligence/sourcing/decisions/{foreign}",
        f"/api/v1/intelligence/sourcing/product-channel/{foreign}",
    ):
        response = client.get(path, headers=ORIGIN)
        assert response.status_code == 404
        assert all(
            secret not in response.text.lower()
            for secret in ("postgresql://", "traceback", "c:\\\\users\\", "/home/", "token")
        )


def test_sourcing_report_escapes_xss_and_private_payloads() -> None:
    payload = {
        "rfq_text": '<script>alert("x")</script>',
        "quote_notes": "<img src=x onerror=alert(1)>",
        "decision_notes": "postgresql://user:secret@db/local",
    }
    markdown = safe_report(payload, "markdown")
    html = safe_report(payload, "html")
    assert isinstance(markdown, str)
    assert isinstance(html, str)
    assert "<script>" not in markdown and "<script>" not in html
    assert "<img" not in markdown and "<img" not in html
    assert "postgresql://" not in markdown
    assert "secret@db" not in markdown
    assert "python traceback" not in markdown.lower()
