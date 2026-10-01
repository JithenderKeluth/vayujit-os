from __future__ import annotations

import pytest

from vayujit_api.core.config import get_settings
from vayujit_api.intelligence.business_agent_service import _supplier_source_policy


@pytest.mark.parametrize("mode", ["LIVE_READ_ONLY", "LOCAL_FIXTURE", "DISABLED"])
def test_business_agent_supplier_policy_reuses_configured_mode(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "intelligence_external_provider_mode", mode)
    assert _supplier_source_policy() == {
        "mode": mode,
        "external_connectors": "disabled",
    }


def test_business_agent_supplier_policy_does_not_enable_external_connectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "intelligence_external_provider_mode", "LIVE_READ_ONLY")
    policy = _supplier_source_policy()
    assert policy["mode"] == "LIVE_READ_ONLY"
    assert policy["external_connectors"] == "disabled"


def test_supplier_continuation_requires_human_product_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from vayujit_api.intelligence import business_agent_service

    opportunity_id = uuid4()
    monkeypatch.setattr(
        business_agent_service,
        "_candidate_opportunity_ids",
        lambda _db, _owner, _goal_id: [opportunity_id],
    )

    class EmptyDecisionDb:
        def scalar(self, _statement: object) -> None:
            return None

    class SelectedDecisionDb:
        def scalar(self, _statement: object) -> object:
            return opportunity_id

    run = SimpleNamespace(goal_id=uuid4())
    owner = SimpleNamespace(id=uuid4())
    assert (
        business_agent_service._run_has_human_product_selection(EmptyDecisionDb(), owner, run)
        is False
    )
    assert (
        business_agent_service._run_has_human_product_selection(SelectedDecisionDb(), owner, run)
        is True
    )
