"""Exact disposable clock fixture; never imported by the application runtime."""

import os
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def install(app, token, engine):
    if (
        os.environ.get("QA_BROWSER_PHASE") != "WP7A7"
        or engine.url.database != f"vayujit_qa{token}_test"
    ):
        raise ValueError("EXACT_WP7A7_REQUIRED")
    from vayujit_api.commerce.models import (
        AmazonListingExecutionAuthorization,
        MarketplaceAccount,
        MarketplaceListing,
        MarketplaceListingExecutionAuthorization,
    )
    from vayujit_api.core.database import get_session
    from vayujit_api.core.test_database import assert_safe_test_database
    from vayujit_api.identity.models import User
    from vayujit_api.identity.router import current_user
    from vayujit_api.identity.service import now

    @app.post("/__qa/wp7a7/expire-authorization", include_in_schema=False)
    def expire(
        data: dict,
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if (
            x_qa_token != token
            or set(data) != {"channel", "authorization_id"}
            or data["channel"] not in {"amazon", "flipkart"}
        ):
            raise HTTPException(403, "Exact QA clock scope required")
        with engine.connect() as connection:
            assert_safe_test_database(
                connection, database_url=str(engine.url), environment="test"
            )
        model = (
            AmazonListingExecutionAuthorization
            if data["channel"] == "amazon"
            else MarketplaceListingExecutionAuthorization
        )
        try:
            authorization_id = uuid.UUID(str(data["authorization_id"]))
        except (ValueError, TypeError):
            raise HTTPException(422, "Exact authorization identity required") from None
        row = db.scalar(
            select(model).where(
                model.id == authorization_id,
                model.owner_id == owner.id,
            )
        )
        listing = db.get(MarketplaceListing, row.listing_id) if row else None
        account = db.get(MarketplaceAccount, row.account_id) if row else None
        if (
            not row
            or row.status != "issued"
            or not listing
            or listing.owner_id != owner.id
            or listing.marketplace != data["channel"]
            or listing.remote_listing_id
            or not listing.title.startswith("[QA SYNTHETIC] QA7 ")
            or not account
            or account.owner_id != owner.id
            or account.environment != "sandbox"
            or not account.seller_account_id.startswith("qa6-")
        ):
            raise HTTPException(
                403, "Exact unpublished synthetic authorization required"
            )
        row.expires_at = now() - timedelta(seconds=1)
        db.commit()
        return {
            "synthetic": True,
            "authorization_id": str(row.id),
            "expires_at": row.expires_at,
            "external_writes": False,
        }

    @app.post("/__qa/wp7a7/interrupted-activity", include_in_schema=False)
    def interrupted_activity(
        data: dict,
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        # Seed an explicitly synthetic missed local intent, not a claimed worker
        # execution. Subsequent preview/confirmation uses the normal authority.
        if x_qa_token != token or set(data) != {"activity_id"}:
            raise HTTPException(403, "Exact QA fixture scope required")
        from vayujit_api.ai.models import GeneratedArtifact
        from vayujit_api.audit.service import record_event
        from vayujit_api.campaigns.models import CampaignActivity
        from vayujit_api.publishing.models import PublishingDestination

        with engine.connect() as connection:
            assert_safe_test_database(
                connection, database_url=str(engine.url), environment="test"
            )
        try:
            activity_id = uuid.UUID(str(data["activity_id"]))
        except (ValueError, TypeError):
            raise HTTPException(422, "Exact activity identity required") from None
        activity = db.scalar(
            select(CampaignActivity)
            .where(
                CampaignActivity.id == activity_id,
                CampaignActivity.owner_id == owner.id,
            )
            .with_for_update()
        )
        destination = (
            db.get(PublishingDestination, activity.destination_id) if activity else None
        )
        artifact = db.get(GeneratedArtifact, activity.artifact_id) if activity else None
        if (
            not activity
            or activity.status != "draft"
            or not activity.name.startswith("[QA SYNTHETIC] QA7 ")
            or activity.schedule_id
            or activity.job_id
            or activity.publishing_execution_id
            or activity.scheduled_at_utc >= now()
            or not destination
            or destination.owner_id != owner.id
            or destination.connector_key != "mock_publisher_v1"
            or destination.status != "active"
            or not artifact
            or artifact.owner_id != owner.id
            or artifact.status != "approved"
            or artifact.version_number != activity.artifact_version
        ):
            raise HTTPException(
                403, "Exact unpublished approved local-mock activity required"
            )
        activity.status = "missed"
        activity.failure_code = "qa.synthetic_interruption"
        activity.safe_failure_message = "Synthetic missed local intent; no provider or publishing worker was executed."
        activity.updated_at = now()
        activity.row_version += 1
        record_event(
            db,
            actor_id=owner.id,
            action="qa.wp7a7.synthetic_interruption",
            entity_type="campaign_activity",
            entity_id=activity.id,
            metadata={"synthetic": True, "worker_executed": False},
        )
        db.commit()
        return {
            "synthetic": True,
            "activity_id": str(activity.id),
            "row_version": activity.row_version,
            "worker_executed": False,
        }
