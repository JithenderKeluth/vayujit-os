"""Numeric safety for the Slice 9D descriptive sourcing projection."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from vayujit_api.intelligence.product_opportunity_feasibility_service import _fit, _json, _number


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "-1", None, "invalid"])
def test_invalid_commercial_numbers_remain_unknown(value: object) -> None:
    assert _number(value) is None


@pytest.mark.parametrize(
    ("value", "limit", "expected"),
    [
        ("0", "0", "MEETS"),
        ("20", "20", "MEETS"),
        ("20.0001", "20", "DOES_NOT_MEET"),
        ("29", "30", "MEETS"),
        ("31", "30", "DOES_NOT_MEET"),
        ("-1", "20", "UNKNOWN"),
        ("NaN", "20", "UNKNOWN"),
        ("Infinity", "20", "UNKNOWN"),
    ],
)
def test_constraint_boundaries_preserve_decimal_precision(
    value: str, limit: str, expected: str
) -> None:
    assert _fit(Decimal(value), Decimal(limit)) == expected


def test_nonfinite_json_values_cannot_escape_projection() -> None:
    safe = _json(
        {
            "amount": Decimal("0.123456789"),
            "hhi": Decimal("1234.0000000001"),
            "bad": [Decimal("NaN"), float("inf"), float("nan")],
        }
    )
    assert safe["amount"] == "0.123456789"
    assert safe["hhi"] == "1234.0000000001"
    assert safe["bad"] == [None, None, None]
    json.dumps(safe, allow_nan=False)
