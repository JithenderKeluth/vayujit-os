from datetime import UTC, datetime

import pytest

from vayujit_api.publishing.scheduler_time import (
    local_to_utc,
    next_local_occurrence,
    occurrence_key,
)


def test_local_to_utc_uses_iana_timezone() -> None:
    value = local_to_utc(datetime(2026, 7, 30, 12), "Asia/Kolkata")
    assert value == datetime(2026, 7, 30, 6, 30, tzinfo=UTC)


def test_dst_gap_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        local_to_utc(datetime(2026, 3, 8, 2, 30), "America/New_York")


def test_dst_overlap_fold_is_explicit() -> None:
    first = local_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York", 0)
    second = local_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York", 1)
    assert second - first == __import__("datetime").timedelta(hours=1)


def test_monthly_recurrence_clamps_to_last_day() -> None:
    value = next_local_occurrence(datetime(2026, 1, 31, 9), {"frequency": "monthly", "interval": 1})
    assert value == datetime(2026, 2, 28, 9)


def test_occurrence_key_is_stable_across_offsets() -> None:
    first = datetime.fromisoformat("2026-07-30T12:00:00+05:30")
    second = datetime.fromisoformat("2026-07-30T06:30:00+00:00")
    assert occurrence_key("abc", first) == occurrence_key("abc", second)
