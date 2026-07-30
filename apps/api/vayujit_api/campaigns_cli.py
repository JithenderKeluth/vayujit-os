"""Safe Campaign diagnostics with explicitly confirmed mutations."""

import argparse
import uuid

from sqlalchemy import func, select

from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignMissedActivityResolution,
    CampaignWorkflowWait,
)
from vayujit_api.campaigns.readiness_service import campaign_readiness
from vayujit_api.campaigns.workflow_service import restore_campaign_waits
from vayujit_api.core.database import SessionFactory
from vayujit_api.publishing.scheduler_time import utcnow


def summary() -> dict[str, object]:
    with SessionFactory() as db:
        return {
            "campaigns": db.scalar(select(func.count()).select_from(Campaign)) or 0,
            "active": db.scalar(
                select(func.count())
                .select_from(Campaign)
                .where(Campaign.status.notin_(["completed", "cancelled", "archived"]))
            )
            or 0,
            "activities": db.scalar(select(func.count()).select_from(CampaignActivity)) or 0,
            "blocked": db.scalar(
                select(func.count())
                .select_from(CampaignActivity)
                .where(CampaignActivity.readiness_status.in_(["blocked", "invalid"]))
            )
            or 0,
            "upcoming": db.scalar(
                select(func.count())
                .select_from(CampaignActivity)
                .where(CampaignActivity.scheduled_at_utc >= utcnow())
            )
            or 0,
            "active_waits": db.scalar(
                select(func.count())
                .select_from(CampaignWorkflowWait)
                .where(CampaignWorkflowWait.completed_at.is_(None))
            )
            or 0,
            "missed": db.scalar(
                select(func.count())
                .select_from(CampaignActivity)
                .where(CampaignActivity.status == "missed")
            )
            or 0,
            "unresolved_missed": db.scalar(
                select(func.count())
                .select_from(CampaignMissedActivityResolution)
                .where(CampaignMissedActivityResolution.resolution_status == "unresolved")
            )
            or 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="VAYUJIT Campaign diagnostics")
    parser.add_argument(
        "command",
        choices=[
            "list",
            "status",
            "activities",
            "readiness",
            "conflicts",
            "upcoming",
            "waits",
            "missed",
            "recovery",
            "restore-waits",
            "validate",
        ],
    )
    parser.add_argument("--campaign-id", type=uuid.UUID)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command == "restore-waits":
        if not args.confirm:
            parser.error("Wait restoration requires --confirm.")
        with SessionFactory() as db:
            print({"restored": restore_campaign_waits(db)})
        return
    if args.command == "validate":
        if not args.confirm or not args.campaign_id:
            parser.error("Validation requires --campaign-id and --confirm.")
        with SessionFactory() as db:
            campaign = db.get(Campaign, args.campaign_id)
            if not campaign:
                parser.error("Campaign not found.")
            activities = list(
                db.scalars(
                    select(CampaignActivity).where(CampaignActivity.campaign_id == campaign.id)
                )
            )
            result = campaign_readiness(db, campaign, activities)
            db.commit()
            print(result.model_dump(mode="json"))
        return
    print(summary())


if __name__ == "__main__":
    main()
