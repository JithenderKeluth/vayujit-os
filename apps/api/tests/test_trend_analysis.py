"""Focused deterministic Trend 12C analysis regressions."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from vayujit_api.intelligence.trend_analysis_service import _series_payload

pytestmark = pytest.mark.integration


def _row(
    value: Decimal | None,
    observed_at: datetime,
    *,
    measurement_type: str = "INDEX",
    granularity: str = "DAILY",
    freshness_state: str = "CURRENT",
    text: str | None = None,
    boolean: bool | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        value_numeric=value,
        value_text=text,
        value_boolean=boolean,
        measurement_type=measurement_type,
        granularity=granularity,
        observed_at=observed_at,
        period_start=observed_at,
        period_end=observed_at,
        freshness_state=freshness_state,
        provider_observation_id=str(uuid4()),
    )


def test_numeric_statistics_change_direction_and_persistence_are_decimal_safe() -> None:
    rows = [
        _row(Decimal(value), datetime(2026, 1, day, tzinfo=UTC))
        for day, value in enumerate(("10", "12", "15"), 1)
    ]
    result = _series_payload(rows)
    assert result["readiness"] == "AVAILABLE"
    assert result["direction"] == "INCREASING"
    assert result["persistence"] == "PERSISTENT_INCREASE"
    assert Decimal(result["statistics"]["mean"]) == Decimal(37) / Decimal(3)
    assert result["change"]["absolute"] == "5"
    assert Decimal(result["change"]["relative_percent"]) == Decimal(50)


def test_zero_baseline_has_no_relative_change() -> None:
    result = _series_payload(
        [
            _row(Decimal("0"), datetime(2026, 1, 1, tzinfo=UTC)),
            _row(Decimal("4"), datetime(2026, 1, 2, tzinfo=UTC)),
        ]
    )
    assert result["change"]["absolute"] == "4"
    assert result["change"]["relative_percent"] is None
    assert result["change"]["relative_reason"] == "ZERO_DENOMINATOR"


def test_missing_daily_period_is_exposed_without_interpolation() -> None:
    result = _series_payload(
        [
            _row(Decimal("1"), datetime(2026, 1, 1, tzinfo=UTC)),
            _row(Decimal("3"), datetime(2026, 1, 3, tzinfo=UTC)),
        ]
    )
    assert result["expected_period_count"] == 3
    assert result["observed_period_count"] == 2
    assert result["missing_period_count"] == 1
    assert result["missing_periods"] == ["2026-01-02"]


def test_single_observation_cannot_claim_direction_or_persistence() -> None:
    result = _series_payload([_row(Decimal("8"), datetime(2026, 1, 1, tzinfo=UTC))])
    assert result["readiness"] == "PARTIAL"
    assert result["direction"] == "INSUFFICIENT_EVIDENCE"
    assert result["persistence"] == "INSUFFICIENT_EVIDENCE"


def test_boolean_series_remains_descriptive_and_non_numeric() -> None:
    result = _series_payload(
        [
            _row(None, datetime(2026, 1, 1, tzinfo=UTC), measurement_type="BOOLEAN", boolean=False),
            _row(None, datetime(2026, 1, 2, tzinfo=UTC), measurement_type="BOOLEAN", boolean=True),
        ]
    )
    assert result["statistics"]["first"] is False
    assert result["statistics"]["latest"] is True
    assert result["statistics"].get("mean") is None
    assert result["persistence"] == "INSUFFICIENT_EVIDENCE"
