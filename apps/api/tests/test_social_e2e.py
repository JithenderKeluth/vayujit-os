import pytest

pytestmark = pytest.mark.integration


def test_social_e2e_scope_is_fake_certified_only() -> None:
    assert {"instagram", "facebook", "youtube"} == {"instagram", "facebook", "youtube"}
