import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.brands.models import Brand
from vayujit_api.campaigns.activity_service import add_dependency, create_activity
from vayujit_api.campaigns.calendar_service import calendar_events, progress
from vayujit_api.campaigns.campaign_service import create_campaign, transition
from vayujit_api.campaigns.models import Campaign, CampaignActivity, CampaignActivityDependency
from vayujit_api.campaigns.readiness_service import campaign_readiness
from vayujit_api.campaigns.schedule_service import schedule_activities
from vayujit_api.campaigns.schemas import (
    ActivityCreate,
    CampaignCreate,
    DependencyCreate,
    ScheduleRequest,
)
from vayujit_api.core.database import Base
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User, UserRole, UserStatus
from vayujit_api.identity.service import now
from vayujit_api.main import create_app

URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture
def db() -> Generator[Session, None, None]:
    assert URL and URL.startswith("postgresql")
    create_app()
    engine = create_engine(URL)
    reset_test_schema(engine, Base.metadata, database_url=URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def owner_brand(db: Session) -> tuple[User, Brand]:
    stamp = now()
    owner = User(
        full_name="Campaign Owner",
        email="campaign@example.com",
        normalized_email="campaign@example.com",
        password_hash="test-only",
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        is_active=True,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(owner)
    db.flush()
    brand = Brand(
        owner_id=owner.id,
        name="Campaign Brand",
        normalized_name="campaign brand",
        slug="campaign-brand",
        status="active",
        is_active_context=True,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(brand)
    db.commit()
    return owner, brand


def test_checkpoint_campaign_lifecycle_dependency_schedule_and_calendar(db: Session) -> None:
    owner, brand = owner_brand(db)
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
    campaign = create_campaign(
        db,
        owner,
        CampaignCreate(
            brand_id=brand.id,
            name="Deterministic Campaign",
            timezone_name="UTC",
            local_start_at=start.replace(tzinfo=None),
            local_end_at=(start + timedelta(days=2)).replace(tzinfo=None),
        ),
    )
    first = create_activity(
        db,
        owner,
        campaign.id,
        ActivityCreate(
            activity_type="review_checkpoint",
            name="Review",
            sequence=1,
            scheduled_local_date=start.date(),
            scheduled_local_time=start.time(),
        ),
    )
    second = create_activity(
        db,
        owner,
        campaign.id,
        ActivityCreate(
            activity_type="approval_checkpoint",
            name="Approval",
            sequence=2,
            scheduled_local_date=start.date(),
            scheduled_local_time=(start + timedelta(minutes=30)).time(),
        ),
    )
    dependency = add_dependency(
        db,
        owner,
        campaign.id,
        DependencyCreate(
            predecessor_activity_id=first.id,
            successor_activity_id=second.id,
            dependency_type="success_required",
        ),
    )
    assert dependency.id
    readiness = campaign_readiness(db, campaign, [first, second])
    assert readiness.state == "blocked"
    first.status = "succeeded"
    first.completed_at = now()
    db.commit()
    assert campaign_readiness(db, campaign, [first, second]).state == "ready"
    transition(db, owner, campaign.id, "planning")
    transition(db, owner, campaign.id, "ready")
    result = schedule_activities(
        db,
        owner,
        campaign,
        [first, second],
        ScheduleRequest(confirm=True),
    )
    results = result["results"]
    assert isinstance(results, list)
    assert len(results) == 2
    assert progress([first, second]).completion_percentage == 100
    events = calendar_events(
        db,
        owner.id,
        start - timedelta(hours=1),
        start + timedelta(days=1),
        campaign_id=campaign.id,
    )
    assert len(events) == 2
    assert db.scalar(select(func.count()).select_from(Campaign)) == 1
    assert db.scalar(select(func.count()).select_from(CampaignActivity)) == 2
    assert db.scalar(select(func.count()).select_from(CampaignActivityDependency)) == 1
