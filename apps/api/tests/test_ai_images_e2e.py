import pytest

from vayujit_api.ai.image_provider import image_provider

pytestmark = pytest.mark.integration


def test_image_e2e_provider_contract_is_network_free() -> None:
    value, metadata = image_provider.generate(
        operation="marketplace_main_image", width=128, height=128, seed="e2e", scenario="success"
    )
    assert value.startswith(b"\x89PNG")
    assert metadata["deterministic"] is True
