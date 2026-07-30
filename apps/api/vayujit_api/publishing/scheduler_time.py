"""Timezone-safe recurrence calculations for durable publishing schedules."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def timezone_for(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown IANA timezone: {name}") from error


def local_to_utc(value: datetime, timezone_name: str, fold: int = 0) -> datetime:
    """Convert wall time while rejecting DST gaps and supporting explicit overlap folds."""
    if value.tzinfo is not None:
        raise ValueError("Local scheduled time must not include a timezone offset.")
    zone = timezone_for(timezone_name)
    candidate = value.replace(tzinfo=zone, fold=fold)
    utc_value = candidate.astimezone(UTC)
    if utc_value.astimezone(zone).replace(tzinfo=None) != value:
        raise ValueError("The selected local time does not exist because of a DST transition.")
    return utc_value


def next_local_occurrence(current: datetime, recurrence: dict[str, object]) -> datetime:
    frequency = str(recurrence.get("frequency", "daily"))
    interval = int(cast(Any, recurrence.get("interval", 1)))
    if interval < 1 or interval > 366:
        raise ValueError("Recurrence interval must be between 1 and 366.")
    if frequency == "daily":
        return current + timedelta(days=interval)
    if frequency == "weekly":
        raw_weekdays = cast(list[object], recurrence.get("weekdays", []))
        weekdays = sorted({int(cast(Any, day)) for day in raw_weekdays})
        if not weekdays:
            return current + timedelta(weeks=interval)
        if any(day < 0 or day > 6 for day in weekdays):
            raise ValueError("Weekdays must be integers from 0 (Monday) to 6 (Sunday).")
        for offset in range(1, interval * 7 + 1):
            candidate = current + timedelta(days=offset)
            if candidate.weekday() in weekdays and (
                offset < 7 or ((offset - 1) // 7) % interval == 0
            ):
                return candidate
        return current + timedelta(weeks=interval)
    if frequency == "monthly":
        month = current.month - 1 + interval
        year = current.year + month // 12
        month = month % 12 + 1
        requested_day = int(cast(Any, recurrence.get("day_of_month", current.day)))
        day = min(requested_day, monthrange(year, month)[1])
        return current.replace(year=year, month=month, day=day)
    raise ValueError("Recurrence frequency must be daily, weekly, or monthly.")


def next_utc_occurrence(
    current_local: datetime,
    timezone_name: str,
    recurrence: dict[str, object],
    *,
    fold: int = 0,
) -> tuple[datetime, datetime]:
    candidate = next_local_occurrence(current_local, recurrence)
    # DST gaps are advanced minute-by-minute to the first real wall-clock instant.
    for _ in range(181):
        try:
            return candidate, local_to_utc(candidate, timezone_name, fold)
        except ValueError as error:
            if "DST transition" not in str(error):
                raise
            candidate += timedelta(minutes=1)
    raise ValueError("Unable to resolve the next local occurrence.")


def occurrence_key(schedule_id: object, scheduled_at: datetime) -> str:
    normalized = scheduled_at.astimezone(UTC).replace(microsecond=0).isoformat()
    return f"schedule:{schedule_id}:{normalized}"


def utcnow() -> datetime:
    return datetime.now(UTC)


def start_of_local_day(value: date, timezone_name: str) -> datetime:
    return local_to_utc(datetime.combine(value, datetime.min.time()), timezone_name)
