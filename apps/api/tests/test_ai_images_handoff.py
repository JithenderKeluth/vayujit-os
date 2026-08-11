from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from vayujit_api.ai.image_schemas import (
    ImageGenerateRequest,
    ImageHandoffRequest,
    ImageRegenerateRequest,
)

pytestmark = pytest.mark.integration


def test_regeneration_reasons_and_exact_identity_are_typed() -> None:
    request = ImageRegenerateRequest(
        reason="rejected_feedback", feedback="Use the approved composition."
    )
    assert request.reason == "rejected_feedback"
    handoff = ImageHandoffRequest(
        marketplace="amazon", listing_id=uuid4(), idempotency_key="handoff-1"
    )
    assert handoff.role == "gallery"
    with pytest.raises(ValidationError):
        ImageGenerateRequest(brand_id=uuid4(), product_id=uuid4(), operation=cast(Any, "unknown"))


def test_image_handoff_rejects_invalid_marketplace() -> None:
    with pytest.raises(ValidationError):
        ImageHandoffRequest(
            marketplace=cast(Any, "ebay"),
            listing_id=uuid4(),
            idempotency_key="handoff-2",
        )
