import uuid
from datetime import UTC, datetime, timedelta

from vayujit_api.campaigns.activity_service import dependency_would_cycle
from vayujit_api.campaigns.conflict_service import detect_conflicts
from vayujit_api.campaigns.constants import ACTIVITY_ACTIONS, LEGAL_TRANSITIONS
from vayujit_api.campaigns.models import Campaign, CampaignActivity


def campaign() -> Campaign:
    stamp = datetime.now(UTC)
    return Campaign(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        name="Launch",
        slug="launch",
        description="",
        objective="",
        status="planning",
        priority=0,
        timezone_name="UTC",
        start_at_utc=stamp,
        end_at_utc=stamp + timedelta(days=2),
        local_start_at=stamp.replace(tzinfo=None),
        local_end_at=(stamp + timedelta(days=2)).replace(tzinfo=None),
        approval_policy="approve_before_scheduling",
        scheduling_policy="strict_window",
        conflict_policy="block",
        created_by=uuid.uuid4(),
        created_at=stamp,
        updated_at=stamp,
        row_version=1,
    )


def activity(value: Campaign, sequence: int, when: datetime) -> CampaignActivity:
    activity_id = uuid.uuid4()
    return CampaignActivity(
        id=activity_id,
        owner_id=value.owner_id,
        campaign_id=value.id,
        product_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        artifact_version=1,
        destination_id=uuid.uuid4(),
        connector_key="wordpress",
        requested_action="publish",
        activity_type="wordpress_publish",
        name=f"Activity {sequence}",
        description="",
        sequence=sequence,
        dependency_policy="success_required",
        scheduled_local_date=when.date(),
        scheduled_local_time=when.time(),
        timezone_name="UTC",
        scheduled_at_utc=when,
        status="draft",
        readiness_status="incomplete",
        required=True,
        enabled=True,
        created_by=value.owner_id,
        created_at=when,
        updated_at=when,
        correlation_id=None,
        idempotency_key=f"activity:{activity_id}",
        row_version=1,
    )


def test_activity_actions_are_bounded_and_draft_first() -> None:
    assert ACTIVITY_ACTIONS["wordpress_create_draft"] == ("wordpress", "create_draft")
    assert ACTIVITY_ACTIONS["shopify_create_draft"] == ("shopify", "create_draft")
    assert "social_publish" not in ACTIVITY_ACTIONS


def test_campaign_lifecycle_is_explicit() -> None:
    assert "planning" in LEGAL_TRANSITIONS["draft"]
    assert "archived" not in LEGAL_TRANSITIONS["draft"]
    assert LEGAL_TRANSITIONS["archived"] == set()


def test_dependency_cycle_detection_is_deterministic() -> None:
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    edges = [(first, second), (second, third)]
    assert dependency_would_cycle(edges, third, first)
    assert not dependency_would_cycle(edges, first, third)


def test_duplicate_and_outside_window_conflicts() -> None:
    value = campaign()
    stamp = value.start_at_utc + timedelta(hours=1)
    first = activity(value, 1, stamp)
    second = activity(value, 2, stamp)
    second.product_id = first.product_id
    second.artifact_id = first.artifact_id
    second.destination_id = first.destination_id
    outside = activity(value, 3, value.end_at_utc + timedelta(hours=1))
    conflicts = detect_conflicts(value, [first, second, outside], [])
    types = {conflict.conflict_type for conflict in conflicts}
    assert "duplicate_destination_action" in types
    assert "outside_campaign_window" in types
