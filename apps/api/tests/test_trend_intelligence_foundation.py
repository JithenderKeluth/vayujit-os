"""Focused 12A contract and safety regressions."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from vayujit_api.intelligence.trend_schemas import TrendObservationCreate
from vayujit_api.intelligence.trend_service import _safe_metadata

pytestmark = pytest.mark.integration


def test_observation_contract_requires_exactly_one_value() -> None:
    with pytest.raises(ValidationError):
        TrendObservationCreate(
            source_id="00000000-0000-0000-0000-000000000001",
            signal_type="CUSTOM_INDEX",
            observed_at=datetime.now(UTC),
        )
    value = TrendObservationCreate(
        source_id="00000000-0000-0000-0000-000000000001",
        signal_type="CUSTOM_INDEX",
        observed_at=datetime.now(UTC),
        value_numeric=Decimal("1.25"),
        raw_metadata={"authorization": "secret", "safe": "ok"},
    )
    assert value.value_numeric == Decimal("1.25")


def test_metadata_redacts_credentials_and_bounds_nesting() -> None:
    result = _safe_metadata({"token": "hidden", "nested": {"api_key": "hidden", "label": "ok"}})
    assert result == {"token": "[REDACTED]", "nested": {"api_key": "[REDACTED]", "label": "ok"}}
    with pytest.raises(HTTPException):
        _safe_metadata({"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}})
