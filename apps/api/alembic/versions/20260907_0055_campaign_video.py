"""Add exact Video lineage fields to Campaign Activities."""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260907_0055"
down_revision: str | None = "20260906_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = [
        (
            "video_generation_id",
            UUID(as_uuid=True),
            ForeignKey("video_generations.id", ondelete="RESTRICT"),
        ),
        (
            "video_output_id",
            UUID(as_uuid=True),
            ForeignKey("video_outputs.id", ondelete="RESTRICT"),
        ),
        ("video_media_id", UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT")),
        ("video_version", Integer(), None),
        ("video_channel", String(40), None),
        (
            "video_thumbnail_output_id",
            UUID(as_uuid=True),
            ForeignKey("ai_image_outputs.id", ondelete="SET NULL"),
        ),
        (
            "video_thumbnail_media_id",
            UUID(as_uuid=True),
            ForeignKey("media_assets.id", ondelete="SET NULL"),
        ),
        ("video_thumbnail_version", Integer(), None),
        (
            "video_caption_track_id",
            UUID(as_uuid=True),
            ForeignKey("video_caption_tracks.id", ondelete="SET NULL"),
        ),
        ("video_caption_version", Integer(), None),
        ("video_metadata_json", JSONB(), None),
        ("video_preview_fingerprint", String(64), None),
        ("video_target_account_id", UUID(as_uuid=True), None),
        ("video_target_listing_id", UUID(as_uuid=True), None),
        ("video_mapping_id", UUID(as_uuid=True), None),
        ("video_marketplace_job_id", UUID(as_uuid=True), None),
        ("video_remote_id", String(200), None),
        ("video_downstream_state", String(40), None),
        ("video_job_payload_version", Integer(), None),
        ("dependency_state", String(30), None),
        ("video_replacement_state", String(30), None),
    ]
    for name, type_, foreign_key in columns:
        args = [name, type_]
        if foreign_key is not None:
            args.append(foreign_key)
        op.add_column("campaign_activities", Column(*cast(Any, args), nullable=True))
    for name in (
        "video_generation_id",
        "video_output_id",
        "video_media_id",
        "video_channel",
        "video_thumbnail_output_id",
        "video_thumbnail_media_id",
        "video_caption_track_id",
        "video_preview_fingerprint",
        "video_target_account_id",
        "video_target_listing_id",
        "video_mapping_id",
        "video_marketplace_job_id",
        "video_remote_id",
        "video_downstream_state",
        "dependency_state",
    ):
        op.create_index(f"ix_campaign_activities_{name}", "campaign_activities", [name])


def downgrade() -> None:
    for name in (
        "video_downstream_state",
        "video_remote_id",
        "video_marketplace_job_id",
        "video_mapping_id",
        "video_target_listing_id",
        "video_target_account_id",
        "video_preview_fingerprint",
        "video_caption_track_id",
        "video_thumbnail_media_id",
        "video_thumbnail_output_id",
        "video_channel",
        "video_media_id",
        "video_output_id",
        "video_generation_id",
        "dependency_state",
    ):
        op.drop_index(f"ix_campaign_activities_{name}", table_name="campaign_activities")
    for name in (
        "video_replacement_state",
        "dependency_state",
        "video_job_payload_version",
        "video_downstream_state",
        "video_remote_id",
        "video_marketplace_job_id",
        "video_mapping_id",
        "video_target_listing_id",
        "video_target_account_id",
        "video_preview_fingerprint",
        "video_metadata_json",
        "video_caption_version",
        "video_caption_track_id",
        "video_thumbnail_version",
        "video_thumbnail_media_id",
        "video_thumbnail_output_id",
        "video_channel",
        "video_version",
        "video_media_id",
        "video_output_id",
        "video_generation_id",
    ):
        op.drop_column("campaign_activities", name)
