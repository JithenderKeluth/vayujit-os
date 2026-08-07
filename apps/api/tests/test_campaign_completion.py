import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast, get_args

from vayujit_api.campaigns.calendar_service import calendar_projection
from vayujit_api.campaigns.completion_service import terminal_state
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.campaigns.recovery_service import RECOVERY_ACTION_REGISTRY
from vayujit_api.campaigns.router import recovery_actions
from vayujit_api.campaigns.schemas import (
    AgendaCalendar,
    CalendarEvent,
    CampaignRecoveryActionKey,
    ValidateCampaignAction,
)


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


def test_campaign_workflow_action_is_typed_and_closed() -> None:
    action = ValidateCampaignAction(
        action="validate_campaign",
        campaign_id=uuid.uuid4(),
        correlation_id="correlation-123",
    )
    assert action.action == "validate_campaign"


def test_recovery_action_eligibility_suppresses_unsafe_actions() -> None:
    required = SimpleNamespace(
        product_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        destination_id=uuid.uuid4(),
        job_id=None,
        publishing_execution_id=None,
        required=True,
        status="missed",
    )
    optional = SimpleNamespace(**{**required.__dict__, "required": False})
    assert "skip_optional_activity" not in recovery_actions(cast(CampaignActivity, required))
    assert "skip_missed_activity" not in recovery_actions(cast(CampaignActivity, required))
    assert "skip_missed_activity" in recovery_actions(cast(CampaignActivity, optional))


def test_recovery_action_registry_is_complete_and_classified() -> None:
    declared = set(get_args(CampaignRecoveryActionKey))
    assert set(RECOVERY_ACTION_REGISTRY) == declared
    for key, spec in RECOVERY_ACTION_REGISTRY.items():
        assert spec.key == key
        assert spec.permission
        assert spec.request_contract
        assert spec.result_contract
        assert callable(spec.eligibility_evaluator)
        assert spec.idempotency
        assert spec.audit_event
        assert spec.safe_success_message
        assert spec.safe_failure_behavior
        assert spec.implementation_status == "implemented"
        if spec.classification == "mutating":
            assert callable(spec.executor)
            assert spec.navigation_resolver is None
            assert spec.confirmation_required
        else:
            assert spec.classification == "navigation_only"
            assert spec.executor is None
            assert callable(spec.navigation_resolver)
            assert not spec.confirmation_required
