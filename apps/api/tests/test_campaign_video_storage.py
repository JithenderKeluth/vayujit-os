from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as ai_fixture
from sqlalchemy import select
from test_campaign_video_cross_channel import (
    test_six_channel_campaign_executes_independently_and_projects_exact_usage as _run_six_channel,
)
from test_campaign_video_execution import _factory

from vayujit_api.campaigns.models import CampaignActivity, CampaignActivityDependency
from vayujit_api.commerce.marketplace_video import MarketplaceVideoJob, MarketplaceVideoMapping
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.social.models import SocialPost
from vayujit_api.video.models import VideoGeneration, VideoOutput

client = ai_fixture.client
pytestmark = pytest.mark.integration


def test_campaign_video_e2e_storage_integrity_counts_are_zero(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_six_channel(client, monkeypatch)
    with _factory() as db:
        activities = list(db.scalars(select(CampaignActivity)))
        schedules = list(db.scalars(select(PublishingSchedule)))
        jobs = list(db.scalars(select(PublishingJob)))
        dependencies = list(db.scalars(select(CampaignActivityDependency)))
        social_posts = list(db.scalars(select(SocialPost)))
        marketplace_jobs = list(db.scalars(select(MarketplaceVideoJob)))
        mappings = list(db.scalars(select(MarketplaceVideoMapping)))
        owner_ids = {activity.owner_id for activity in activities}
        counts = {
            "duplicate_campaign_activities": len(activities)
            - len({(activity.owner_id, activity.idempotency_key) for activity in activities}),
            "duplicate_active_schedules": len(
                [schedule for schedule in schedules if schedule.enabled and not schedule.archived]
            )
            - len(
                {
                    schedule.id
                    for schedule in schedules
                    if schedule.enabled and not schedule.archived
                }
            ),
            "duplicate_logical_jobs": len(jobs) - len({job.id for job in jobs}),
            "duplicate_downstream_mutations": len(
                [activity.video_remote_id for activity in activities if activity.video_remote_id]
            )
            - len(
                {activity.video_remote_id for activity in activities if activity.video_remote_id}
            ),
            "orphan_activity_video_refs": sum(
                db.get(VideoGeneration, activity.video_generation_id) is None
                or db.get(VideoOutput, activity.video_output_id) is None
                for activity in activities
            ),
            "broken_dependency_refs": sum(
                db.get(CampaignActivity, dependency.predecessor_activity_id) is None
                or db.get(CampaignActivity, dependency.successor_activity_id) is None
                for dependency in dependencies
            ),
            "broken_downstream_refs": sum(
                (
                    activity.video_channel in {"youtube_video", "instagram_reel", "facebook_reel"}
                    and (
                        activity.social_post_id is None
                        or db.get(SocialPost, activity.social_post_id) is None
                    )
                )
                or (
                    activity.video_channel in {"amazon", "flipkart", "meesho"}
                    and (
                        activity.video_marketplace_job_id is None
                        or db.get(MarketplaceVideoJob, activity.video_marketplace_job_id) is None
                        or activity.video_mapping_id is None
                        or db.get(MarketplaceVideoMapping, activity.video_mapping_id) is None
                    )
                )
                for activity in activities
            ),
            "broken_replacement_history": sum(
                (
                    activity.replaces_activity_id is not None
                    and db.get(CampaignActivity, activity.replaces_activity_id) is None
                )
                or (
                    activity.replaced_by_activity_id is not None
                    and db.get(CampaignActivity, activity.replaced_by_activity_id) is None
                )
                for activity in activities
            ),
            "cross_channel_leakage": (
                sum(value.owner_id not in owner_ids for value in social_posts)
                + sum(value.owner_id not in owner_ids for value in marketplace_jobs)
                + sum(value.owner_id not in owner_ids for value in mappings)
            ),
        }
    print(f"Campaign Video storage integrity counts: {counts}")
    assert len(activities) == 6
    assert all(value == 0 for value in counts.values())
