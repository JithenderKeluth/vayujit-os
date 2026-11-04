"""Canonical reschedule review must bind the current dependency graph."""

import uuid
from datetime import datetime
from types import SimpleNamespace

from vayujit_api.campaigns.recovery_service import reschedule_fingerprint


def test_dependency_change_invalidates_reschedule_impact_review():
    owner_id, campaign_id, activity_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    campaign = SimpleNamespace(id=campaign_id, status="draft")
    activity = SimpleNamespace(
        id=activity_id,
        row_version=1,
        schedule_id=None,
        job_id=None,
        artifact_id=None,
        artifact_version=None,
        destination_id=None,
    )
    edges = []
    db = SimpleNamespace(get=lambda *args: None, scalars=lambda *args: edges)

    def fingerprint():
        return reschedule_fingerprint(
            db,
            owner_id,
            campaign,
            activity,
            datetime(2026, 11, 14, 9),
            "Asia/Kolkata",
            "Review dependencies",
            None,
        )

    before = fingerprint()
    assert before == fingerprint()
    edges.append(
        SimpleNamespace(
            id=uuid.uuid4(),
            predecessor_activity_id=uuid.uuid4(),
            successor_activity_id=activity_id,
            dependency_type="success_required",
            released_at=None,
        )
    )
    assert fingerprint() != before
