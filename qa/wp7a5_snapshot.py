"""Read-only owned projections for signed synthetic certification; no row creation."""

import json

from sqlalchemy import select


def snapshot(db, owner):
    from vayujit_api.ai.seo_models import SEOAnalysis, TagSet
    from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt, KeywordSet
    from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceListing
    from vayujit_api.video.bulk_models import VideoBulkChild, VideoBulkOperation
    from vayujit_api.video.channels import VideoChannelHandoff
    from vayujit_api.video.models import VideoGeneration, VideoOutput

    fields = {
        VideoBulkOperation: ["id", "status", "total_children", "completed_count"],
        VideoBulkChild: [
            "id",
            "bulk_id",
            "generation_id",
            "job_id",
            "output_id",
            "status",
            "retry_count",
            "failure_code",
        ],
        VideoGeneration: ["id", "product_id", "status", "provider_key", "failure_code"],
        VideoOutput: ["id", "generation_id", "media_id", "status"],
        VideoChannelHandoff: [
            "id",
            "video_generation_id",
            "video_output_id",
            "social_post_id",
            "state",
            "handoff_fingerprint",
        ],
        SEOAnalysis: [
            "id",
            "product_id",
            "artifact_id",
            "artifact_version",
            "keyword_set_id",
            "keyword_set_version",
            "fingerprint",
            "status",
        ],
        KeywordSet: ["id", "product_id", "version", "archived"],
        TagSet: ["id", "product_id", "archived"],
        MarketplaceAccount: [
            "id",
            "marketplace",
            "environment",
            "enabled",
            "validation_status",
        ],
        MarketplaceListing: [
            "id",
            "product_id",
            "account_id",
            "marketplace",
            "status",
            "content_artifact_id",
        ],
    }
    result = {}
    for model, names in fields.items():
        result[model.__tablename__] = [
            {
                name: json.loads(json.dumps(getattr(row, name, None), default=str))
                for name in names
            }
            for row in db.scalars(
                select(model).where(model.owner_id == owner.id).order_by(model.id)
            )
        ]
    result[AIStudioJobAttempt.__tablename__] = [
        {
            name: json.loads(json.dumps(getattr(row, name), default=str))
            for name in ("id", "job_id", "attempt_number", "state", "error_code")
        }
        for row in db.scalars(
            select(AIStudioJobAttempt)
            .join(AIStudioJob, AIStudioJob.id == AIStudioJobAttempt.job_id)
            .where(AIStudioJob.owner_id == owner.id)
        )
    ]
    return result
