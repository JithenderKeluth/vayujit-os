from typing import get_args
from uuid import uuid4

import pytest
from pydantic import ValidationError

from vayujit_api.campaigns.recovery_service import RECOVERY_ACTION_REGISTRY
from vayujit_api.campaigns.schemas import CampaignRecoveryActionKey, CampaignRecoveryActionResult

pytest_plugins = ("test_scheduler_integration",)


def test_recovery_registry_inventory_is_callable_or_explicitly_unsupported():
    declared = set(get_args(CampaignRecoveryActionKey))
    assert set(RECOVERY_ACTION_REGISTRY) == declared
    unsupported = {
        key
        for key, spec in RECOVERY_ACTION_REGISTRY.items()
        if spec.implementation_status == "unsupported"
    }
    assert unsupported == {"create_one_catch_up", "reschedule_activity"}
    for key, spec in RECOVERY_ACTION_REGISTRY.items():
        if key in unsupported:
            assert spec.executor is None
        elif spec.classification == "mutating":
            assert callable(spec.executor)
        else:
            assert callable(spec.navigation_resolver)


def test_recovery_router_uses_registry_dispatch_path():
    from pathlib import Path

    source = Path(__file__).parents[1].joinpath("vayujit_api", "campaigns", "router.py").read_text()
    route = source[
        source.index("def execute_recovery_action") : source.index('@router.get("/calendar"')
    ]
    assert "legacy_dispatch" not in route
    assert "fallback_dispatch" not in route
    assert "implementation_status" in route
    assert "RECOVERY_ACTION_REGISTRY" in route
    assert "typed_result" in route


@pytest.mark.parametrize(
    ("action", "message"),
    [
        ("create_one_catch_up", "Catch-up creation is not implemented yet."),
        ("reschedule_activity", "Durable Activity rescheduling is not implemented yet."),
    ],
)
def test_unsupported_recovery_actions_are_safe_and_non_mutating(harness, action, message):
    client, _sessions = harness
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": action,
            "campaign_id": str(uuid4()),
            "reason": "Unsupported action characterization.",
            "confirm": True,
        },
        headers={"Origin": "http://localhost:4200"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["outcome"] == "unsupported"
    assert payload["safe_message"] == message
    assert payload.get("correlation_id")


def test_recovery_result_contract_rejects_malformed_executor_output():
    with pytest.raises(ValidationError):
        CampaignRecoveryActionResult.model_validate({"outcome": "not-a-valid-outcome"})


def test_registered_mutating_and_navigation_handlers_are_callable():
    assert callable(RECOVERY_ACTION_REGISTRY["pause_campaign"].executor)
    assert callable(RECOVERY_ACTION_REGISTRY["open_campaign"].navigation_resolver)
