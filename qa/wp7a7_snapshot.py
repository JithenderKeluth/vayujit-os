"""Read-only exact lineage evidence; never credentials, content bodies or tokens."""

import json

from sqlalchemy import select


def snapshot(db, owner):
    from vayujit_api.ads.models import AdCampaign, AdCreative, AdJob
    from vayujit_api.campaigns.models import (
        CampaignActivity,
        CampaignActivityDependency,
    )
    from vayujit_api.commerce.models import (
        MarketplaceListingExecutionAuthorization,
        MarketplaceListingReview,
        MarketplaceMediaMapping,
        MarketplacePrice,
        MarketplaceVariant,
    )

    fields = {
        CampaignActivity: [
            "id",
            "campaign_id",
            "product_id",
            "artifact_id",
            "artifact_version",
            "row_version",
            "status",
            "schedule_id",
            "job_id",
            "released_at",
        ],
        MarketplaceListingReview: [
            "id",
            "listing_id",
            "account_id",
            "marketplace",
            "artifact_id",
            "artifact_version",
            "payload_fingerprint",
            "status",
        ],
        MarketplaceListingExecutionAuthorization: [
            "id",
            "listing_id",
            "review_id",
            "marketplace",
            "status",
            "expires_at",
            "payload_fingerprint",
            "consumed_at",
        ],
        MarketplaceVariant: [
            "id",
            "listing_id",
            "product_id",
            "stable_variant_key",
            "sku",
            "price_amount",
            "currency",
            "listing_state",
            "remote_variant_id",
        ],
        MarketplacePrice: ["id", "listing_id", "amount", "mrp_amount", "currency"],
        MarketplaceMediaMapping: [
            "id",
            "listing_id",
            "media_id",
            "image_output_id",
            "position",
            "remote_media_id",
        ],
        CampaignActivityDependency: [
            "id",
            "campaign_id",
            "predecessor_activity_id",
            "successor_activity_id",
            "dependency_type",
            "released_at",
        ],
        AdCampaign: [
            "id",
            "product_id",
            "brand_id",
            "account_id",
            "state",
            "preview_fingerprint",
            "remote_campaign_id",
            "sync_state",
            "failure_code",
        ],
        AdCreative: [
            "id",
            "campaign_id",
            "product_id",
            "creative_type",
            "artifact_id",
            "artifact_version",
            "image_output_id",
            "image_media_id",
            "image_version",
            "approval_status",
            "fingerprint",
            "exact_lineage_json",
        ],
        AdJob: [
            "id",
            "campaign_id",
            "status",
            "operation",
            "remote_checkpoint_json",
            "failure_code",
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
