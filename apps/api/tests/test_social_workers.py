import pytest

from vayujit_api.social.connectors import FakeSocialConnector

pytestmark = pytest.mark.integration


def test_social_worker_connector_is_idempotent_after_remote_success() -> None:
    connector = FakeSocialConnector("youtube")
    first = connector.publish_post(
        {"remote_account_id": "youtube-local"}, {"title": "One"}, "same-key"
    )
    second = connector.publish_post(
        {"remote_account_id": "youtube-local"}, {"title": "One"}, "same-key"
    )
    assert first["remote_publication_id"] == second["remote_publication_id"]
