from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from test_marketing_plan_slice4_acceptance import (
    _confirm_plan,
    _enable_six_channel_accounts,
    _six_channel_payload,
)

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_unified_calendar_matrix_and_replacement_safety(client: Any) -> None:
    context = integration_fixture.setup_context(client)
    start = datetime.now(UTC).replace(microsecond=0)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": context["brand"]["id"],
            "name": "Final calendar certification",
            "timezone_name": "UTC",
            "local_start_at": start.replace(tzinfo=None).isoformat(),
            "local_end_at": (start + timedelta(days=1)).replace(tzinfo=None).isoformat(),
        },
        headers=ORIGIN,
    )
    assert campaign.status_code == 201, campaign.text

    _enable_six_channel_accounts(client, context)
    plan = _confirm_plan(client, _six_channel_payload(context, "final-calendar"))
    assert plan["status"] in {"queued", "ready", "running", "succeeded", "partially_completed"}

    queries = {
        "campaign": client.get(
            "/api/v1/campaigns/calendar",
            params={
                "start": (start - timedelta(hours=1)).isoformat(),
                "end": (start + timedelta(days=1)).isoformat(),
                "view": "agenda",
                "timezone_name": "UTC",
            },
            headers=ORIGIN,
        ),
        "social": client.get("/api/v1/social/calendar", headers=ORIGIN),
        "ads": client.get("/api/v1/ads/calendar", headers=ORIGIN),
        "marketing": client.get("/api/v1/ads/marketing/calendar", headers=ORIGIN),
    }
    for name, response in queries.items():
        assert response.status_code == 200, f"{name}: {response.text}"
        lowered = response.text.lower()
        assert all(marker not in lowered for marker in ("traceback", "postgresql://", "file://"))

    campaign_body = queries["campaign"].json()
    assert campaign_body["view"] == "agenda"
    assert isinstance(campaign_body["days"], list)
    assert queries["social"].json() == []
    assert isinstance(queries["ads"].json(), list)
    marketing_events = queries["marketing"].json()
    assert isinstance(marketing_events, list)
    assert any(str(item["plan_id"]) == str(plan["id"]) for item in marketing_events)

    event_ids: list[str] = []
    for response in queries.values():
        body = response.json()
        rows = body.get("days", []) if isinstance(body, dict) else body
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    source_id = row.get("id") or row.get("activity_id") or row.get("plan_id")
                    if source_id is not None:
                        event_ids.append(str(source_id))
    assert len(event_ids) == len(set(event_ids))
