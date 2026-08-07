from typing import get_args

import pytest
from pydantic import ValidationError

from vayujit_api.campaigns.recovery_service import RECOVERY_ACTION_REGISTRY
from vayujit_api.campaigns.schemas import CampaignRecoveryActionKey, CampaignRecoveryActionResult

pytest_plugins = ("test_scheduler_integration",)


def test_recovery_registry_inventory_is_fully_implemented():
    declared = set(get_args(CampaignRecoveryActionKey))
    assert set(RECOVERY_ACTION_REGISTRY) == declared
    unsupported = {
        key
        for key, spec in RECOVERY_ACTION_REGISTRY.items()
        if spec.implementation_status == "unsupported"
    }
    assert unsupported == set()
    assert len(RECOVERY_ACTION_REGISTRY) == 21
    for _key, spec in RECOVERY_ACTION_REGISTRY.items():
        if spec.classification == "mutating":
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


def test_recovery_result_contract_rejects_malformed_executor_output():
    with pytest.raises(ValidationError):
        CampaignRecoveryActionResult.model_validate({"outcome": "not-a-valid-outcome"})


def test_registered_mutating_and_navigation_handlers_are_callable():
    assert callable(RECOVERY_ACTION_REGISTRY["pause_campaign"].executor)
    assert callable(RECOVERY_ACTION_REGISTRY["open_campaign"].navigation_resolver)
