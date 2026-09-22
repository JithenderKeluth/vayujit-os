"""Focused deterministic Trend 12D momentum and change regressions."""

from types import SimpleNamespace
from uuid import uuid4

from vayujit_api.intelligence.trend_change_service import (
    _comparable,
    _delta,
    _materiality,
    _momentum,
)


def _series(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "sample_size": 4,
        "readiness": "AVAILABLE",
        "direction": "INCREASING",
        "persistence": "PERSISTENT_INCREASE",
        "missing_period_count": 0,
        "freshness_state": "CURRENT",
        "measurement_type": "INDEX",
        "unit": "index",
        "scale": None,
        "geography_scope": "GLOBAL",
        "granularity": "DAILY",
        "id": uuid4(),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_momentum_states_are_deterministic_and_not_forecast() -> None:
    assert _momentum(_series(), None, True) == "SUSTAINED_INCREASE"
    assert _momentum(_series(sample_size=2), None, True) == "EMERGING_INCREASE"
    assert _momentum(_series(persistence="INTERMITTENT"), _series(), True) == "WEAKENING_INCREASE"
    assert (
        _momentum(
            _series(direction="DECREASING", persistence="PERSISTENT_DECREASE"), _series(), True
        )
        == "REVERSING"
    )
    assert _momentum(_series(direction="MIXED"), None, True) == "MIXED"
    assert _momentum(_series(), None, False) == "NOT_COMPARABLE"


def test_decimal_delta_handles_zero_denominator() -> None:
    absolute, relative, reason = _delta(0, 4)
    assert absolute == 4
    assert relative is None
    assert reason == "ZERO_DENOMINATOR"


def test_materiality_is_bounded_and_descriptive() -> None:
    assert _materiality(1, 2, "STABLE", False, True, 4) == "LOW"
    assert _materiality(50, 50, "REVERSING", True, True, 4) == "HIGH"
    assert _materiality(50, 50, "SUSTAINED_INCREASE", True, False, 4) == "UNKNOWN"


def test_incompatible_series_are_not_comparable() -> None:
    assert not _comparable(_series(unit="index"), _series(unit="percent"))
    assert not _comparable(_series(geography_scope="IN"), _series(geography_scope="US"))
    assert not _comparable(_series(granularity="DAILY"), _series(granularity="WEEKLY"))
