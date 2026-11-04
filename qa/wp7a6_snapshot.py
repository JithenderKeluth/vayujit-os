"""Read-only, owner-scoped allowlisted persisted evidence. Never expose credentials."""

import json

from sqlalchemy import select


def snapshot(db, owner):
    from vayujit_api.campaigns.models import Campaign, CampaignActivity
    from vayujit_api.commerce.models import (
        AmazonListingExecutionAuthorization,
        AmazonListingReview,
    )
    from vayujit_api.social.models import SocialPost

    fields = {
        SocialPost: [
            "id",
            "product_id",
            "brand_id",
            "account_id",
            "content_artifact_id",
            "content_artifact_version",
            "media_ids",
            "video_generation_id",
            "lifecycle_status",
            "preview_fingerprint",
            "remote_publication_id",
            "schedule_id",
        ],
        AmazonListingReview: [
            "id",
            "listing_id",
            "account_id",
            "artifact_id",
            "artifact_version",
            "payload_fingerprint",
            "status",
        ],
        AmazonListingExecutionAuthorization: [
            "id",
            "listing_id",
            "review_id",
            "status",
            "expires_at",
            "payload_fingerprint",
        ],
        Campaign: ["id", "brand_id", "row_version", "status"],
        CampaignActivity: [
            "id",
            "campaign_id",
            "product_id",
            "artifact_id",
            "artifact_version",
            "row_version",
            "status",
        ],
    }
    return {
        model.__tablename__: [
            {
                name: json.loads(json.dumps(getattr(row, name, None), default=str))
                for name in names
            }
            for row in db.scalars(select(model).where(model.owner_id == owner.id))
        ]
        for model, names in fields.items()
    }
