import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from vayujit_api.campaigns.calendar_service import calendar_projection
from vayujit_api.campaigns.completion_service import terminal_state
from vayujit_api.campaigns.schemas import AgendaCalendar, CalendarEvent


def activity(status: str, *, required: bool = True, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(status=status, required=required, enabled=enabled)


def event(at: datetime, *, conflict: bool = False) -> CalendarEvent:
    return CalendarEvent(
        campaign_id=uuid.uuid4(),
        campaign_name="Launch",
        activity_id=uuid.uuid4(),
        activity_name="Publish",
        brand_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        destination_id=uuid.uuid4(),
        connector_key="wordpress",
        requested_action="publish",
        status="scheduled",
        readiness_status="ready",
        scheduled_at_utc=at,
        timezone_name="UTC",
        has_conflict=conflict,
    )


def test_terminal_projection_distinguishes_optional_failure() -> None:
    assert terminal_state([activity("succeeded")]) == "completed"
    assert (
        terminal_state([activity("succeeded"), activity("failed", required=False)])
        == "partially_completed"
    )
    assert terminal_state([activity("dead_letter")]) == "failed"
    assert terminal_state([activity("reconciliation_required")]) == "blocked"


def test_calendar_views_have_distinct_shapes() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    events = [event(start + timedelta(hours=9)), event(start + timedelta(hours=9), conflict=True)]
    month = calendar_projection(events, "month", start, start + timedelta(days=1), "UTC")
    week = calendar_projection(events, "week", start, start + timedelta(days=1), "UTC")
    agenda = calendar_projection(events, "agenda", start, start + timedelta(days=1), "UTC")
    assert month.view == "month" and month.days[0].activity_count == 2
    assert week.view == "week" and week.slots[0].overlap_count == 1
    assert agenda.view == "agenda" and len(agenda.days[0].events) == 2


def test_agenda_pagination_is_bounded() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    values = [event(start + timedelta(minutes=index)) for index in range(3)]
    first = cast(
        AgendaCalendar,
        calendar_projection(values, "agenda", start, start + timedelta(days=1), "UTC", limit=2),
    )
    assert first.next_offset == 2
    assert sum(len(day.events) for day in first.days) == 2
