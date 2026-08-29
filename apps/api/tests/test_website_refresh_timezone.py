from __future__ import annotations

from datetime import UTC, datetime

from vayujit_api.intelligence.website_refresh import next_refresh


def test_refresh_arithmetic_is_timezone_and_month_aware() -> None:
    value = datetime(2026, 3, 8, 6, 30, tzinfo=UTC)
    assert next_refresh(value, "DAILY", "America/New_York") == datetime(
        2026, 3, 9, 5, 30, tzinfo=UTC
    )
    value = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert next_refresh(value, "DAILY", "America/New_York") == datetime(
        2026, 11, 2, 6, 30, tzinfo=UTC
    )
    assert next_refresh(datetime(2026, 1, 31, tzinfo=UTC), "MONTHLY", "UTC") == datetime(
        2026, 2, 28, tzinfo=UTC
    )
    assert next_refresh(datetime(2028, 1, 31, tzinfo=UTC), "MONTHLY", "UTC") == datetime(
        2028, 2, 29, tzinfo=UTC
    )
