from __future__ import annotations

from typing import cast

import pytest

from vayujit_api.ads.connectors import (
    AdsConnectorError,
    FakeAdsState,
    FakeGoogleAdsConnector,
    FakeMetaAdsConnector,
)
from vayujit_api.ads.failure import ADS_FAILURE_TAXONOMY, failure_spec

pytest_plugins = ("test_ai_integration",)


def test_failure_taxonomy_has_all_sixteen_safe_contracts() -> None:
    assert len(ADS_FAILURE_TAXONOMY) == 16
    for code, spec in ADS_FAILURE_TAXONOMY.items():
        assert code.startswith("ads.")
        assert spec["safe_message"]
        assert isinstance(spec["retryable"], bool)
        assert spec["recovery_actions"]
        rendered = f"{code} {spec['safe_message']}"
        assert all(
            secret not in rendered.lower()
            for secret in ("token", "cookie", "password", "dsn", "traceback")
        )


@pytest.mark.parametrize("code", sorted(ADS_FAILURE_TAXONOMY))
def test_each_failure_code_resolves_to_a_safe_projection(code: str) -> None:
    spec = failure_spec(code)
    assert spec["safe_message"] == ADS_FAILURE_TAXONOMY[code]["safe_message"]
    assert isinstance(spec["retryable"], bool)
    assert isinstance(spec["recovery_actions"], list)


def test_meta_and_google_throttling_are_retry_after_safe() -> None:
    for connector in (FakeMetaAdsConnector(), FakeGoogleAdsConnector()):
        connector.state.failures["create_campaign"] = "throttled"
        with pytest.raises(AdsConnectorError) as raised:
            connector.create_campaign("local", {"objective": "traffic"})
        assert raised.value.code == "ads.throttled"
        assert raised.value.retryable is True
        assert raised.value.retry_after_seconds == 15
        assert len(connector.state.entities["campaign"]) == 0


def test_ambiguous_mutation_is_reconciled_without_replay() -> None:
    for connector_type in (FakeMetaAdsConnector, FakeGoogleAdsConnector):
        state = FakeAdsState()
        connector = connector_type(state)
        state.failures["create_campaign"] = "ambiguous"
        with pytest.raises(AdsConnectorError) as raised:
            connector.create_campaign("same-local-id", {"objective": "traffic"})
        assert raised.value.ambiguous is True
        remote_ids = list(state.entities["campaign"])
        assert len(remote_ids) == 1
        assert connector.lookup("campaign", remote_ids[0]) is not None
        state.failures.pop("create_campaign")
        assert (
            connector.create_campaign("same-local-id", {"objective": "traffic"})["remote_id"]
            == remote_ids[0]
        )


@pytest.mark.integration
def test_recovery_projection_and_action_matrix_is_complete(client) -> None:
    from helpers.ads_acceptance import create_campaign, setup_ads_context
    from test_ai_integration import ORIGIN

    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="recovery-matrix")
    projection = client.get("/api/v1/ads/recovery", headers=ORIGIN)
    assert projection.status_code == 200, projection.text
    assert len(projection.json()) == 16
    for index, item in enumerate(projection.json()):
        assert item["failure_code"] in ADS_FAILURE_TAXONOMY
        assert item["safe_message"]
        assert isinstance(item["retryable"], bool)
        spec = cast(dict[str, object], ADS_FAILURE_TAXONOMY[item["failure_code"]])
        action = str(cast(list[object], spec["recovery_actions"])[0])
        response = client.post(
            "/api/v1/ads/recovery",
            json={
                "action": action,
                "entity_type": "campaign",
                "entity_id": campaign["id"],
                "failure_code": item["failure_code"],
                "confirm": True,
                "idempotency_key": f"recovery-matrix-{index}",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["failure_code"] == item["failure_code"]
        assert body["correlation_id"]
        assert body["provider"] == "meta"
        assert all(
            marker not in response.text.lower()
            for marker in ("token", "cookie", "password", "traceback", "postgresql://")
        )
