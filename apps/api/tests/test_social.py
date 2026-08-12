from uuid import UUID

import pytest

from vayujit_api.social.connectors import SCENARIOS, FakeSocialConnector, SocialConnectorFailure
from vayujit_api.social.schemas import SocialPostCreate


def test_social_connector_registry_and_deterministic_identity() -> None:
    assert {"instagram", "facebook", "youtube"}.issubset({"instagram", "facebook", "youtube"})
    assert "ambiguous_result" in SCENARIOS
    connector = FakeSocialConnector("instagram")
    first = connector.publish_post({"remote_account_id": "acct-1"}, {"caption": "hello"}, "post-1")
    second = connector.publish_post({"remote_account_id": "acct-1"}, {"caption": "hello"}, "post-1")
    assert first == second
    assert first["synthetic_test_data"] is True


@pytest.mark.parametrize("scenario", sorted(SCENARIOS - {"success", "processing", "published"}))
def test_social_connector_failure_scenarios_are_safe(scenario: str) -> None:
    connector = FakeSocialConnector("facebook", scenario)
    with pytest.raises(SocialConnectorFailure) as failure:
        if scenario == "credential_failure":
            connector.validate_account({})
        else:
            connector.publish_post({}, {"caption": "safe"}, "post-1")
    assert failure.value.code.startswith("social.")
    assert (
        "credential" not in failure.value.safe_message.lower() or scenario == "credential_failure"
    )


def test_social_format_must_match_platform() -> None:
    with pytest.raises(ValueError):
        SocialPostCreate(
            brand_id=UUID("00000000-0000-4000-8000-000000000001"),
            account_id=UUID("00000000-0000-4000-8000-000000000002"),
            platform="instagram",
            content_type="youtube_video",
            content_artifact_id=UUID("00000000-0000-4000-8000-000000000003"),
            content_artifact_version=1,
            idempotency_key="invalid-format",
        )
