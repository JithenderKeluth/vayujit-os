"""Add AI Content and SEO Studio persistence.

Revision ID: 20260814_0027
Revises: 20260813_0026
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260814_0027"
down_revision = "20260813_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_generation_requests",
        sa.Column("channel", sa.String(40), nullable=False, server_default="canonical"),
    )
    op.add_column(
        "ai_generation_requests",
        sa.Column("content_type", sa.String(60), nullable=False, server_default="product_content"),
    )
    op.add_column(
        "ai_generation_requests",
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
    )
    op.add_column("ai_generation_requests", sa.Column("context_fingerprint", sa.String(64)))
    op.add_column(
        "ai_generation_requests", sa.Column("brand_voice_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("ai_generation_requests", sa.Column("preset_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "ai_generation_requests",
        sa.Column("generation_reason", sa.String(80), nullable=False, server_default="initial"),
    )
    op.add_column(
        "ai_generation_requests", sa.Column("user_instruction_fingerprint", sa.String(64))
    )
    op.create_index(
        "ix_ai_generation_requests_context_fingerprint",
        "ai_generation_requests",
        ["context_fingerprint"],
    )
    op.create_index(
        "ix_ai_generation_requests_brand_voice_id", "ai_generation_requests", ["brand_voice_id"]
    )
    op.create_index("ix_ai_generation_requests_preset_id", "ai_generation_requests", ["preset_id"])

    op.add_column(
        "generated_artifacts",
        sa.Column("channel", sa.String(40), nullable=False, server_default="canonical"),
    )
    op.add_column(
        "generated_artifacts",
        sa.Column("content_type", sa.String(60), nullable=False, server_default="product_content"),
    )
    op.add_column(
        "generated_artifacts",
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
    )
    op.add_column("generated_artifacts", sa.Column("context_fingerprint", sa.String(64)))
    op.add_column("generated_artifacts", sa.Column("brand_voice_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "generated_artifacts", sa.Column("parent_artifact_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column(
        "generated_artifacts",
        sa.Column("generation_reason", sa.String(80), nullable=False, server_default="initial"),
    )
    op.add_column(
        "generated_artifacts",
        sa.Column("source", sa.String(30), nullable=False, server_default="ai_generated"),
    )
    op.add_column("generated_artifacts", sa.Column("user_instructions", sa.Text()))
    op.add_column("generated_artifacts", sa.Column("input_context_json", postgresql.JSONB()))
    op.add_column("generated_artifacts", sa.Column("edited_at", sa.DateTime(timezone=True)))
    op.add_column("generated_artifacts", sa.Column("edited_by", postgresql.UUID(as_uuid=True)))
    for column in (
        "channel",
        "content_type",
        "context_fingerprint",
        "brand_voice_id",
        "parent_artifact_id",
    ):
        op.create_index(f"ix_generated_artifacts_{column}", "generated_artifacts", [column])

    op.create_table(
        "ai_brand_voices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("tone", sa.String(80), nullable=False),
        sa.Column("personality", sa.String(500)),
        sa.Column("terminology_json", postgresql.JSONB(), nullable=False),
        sa.Column("target_audience", sa.String(500)),
        sa.Column("preferred_phrases_json", postgresql.JSONB(), nullable=False),
        sa.Column("prohibited_phrases_json", postgresql.JSONB(), nullable=False),
        sa.Column("spelling_conventions", sa.String(200)),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("formatting_preferences_json", postgresql.JSONB(), nullable=False),
        sa.Column("compliance_notes", sa.String(1000)),
        sa.Column("custom_instructions", sa.String(2000)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", "version", name="uq_ai_brand_voice_version"),
    )
    op.create_index("ix_ai_brand_voices_owner_id", "ai_brand_voices", ["owner_id"])
    op.create_index("ix_ai_brand_voices_brand_id", "ai_brand_voices", ["brand_id"])
    op.create_index("ix_ai_brand_voices_is_default", "ai_brand_voices", ["is_default"])

    op.create_table(
        "ai_generation_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("output_types_json", postgresql.JSONB(), nullable=False),
        sa.Column("channels_json", postgresql.JSONB(), nullable=False),
        sa.Column("tone", sa.String(80)),
        sa.Column("length", sa.String(40)),
        sa.Column("required_context_json", postgresql.JSONB(), nullable=False),
        sa.Column("validation_rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_ai_generation_preset_name"),
    )
    op.create_index("ix_ai_generation_presets_owner_id", "ai_generation_presets", ["owner_id"])

    op.create_table(
        "ai_keyword_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("primary_keywords_json", postgresql.JSONB(), nullable=False),
        sa.Column("secondary_keywords_json", postgresql.JSONB(), nullable=False),
        sa.Column("marketplace_keywords_json", postgresql.JSONB(), nullable=False),
        sa.Column("website_keywords_json", postgresql.JSONB(), nullable=False),
        sa.Column("campaign_keywords_json", postgresql.JSONB(), nullable=False),
        sa.Column("negative_keywords_json", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("owner_id", "brand_id", "product_id"):
        op.create_index(f"ix_ai_keyword_sets_{column}", "ai_keyword_sets", [column])

    op.create_table(
        "ai_studio_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_ids_json", postgresql.JSONB(), nullable=False),
        sa.Column("channels_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_types_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "brand_voice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_brand_voices.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "preset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_generation_presets.id", ondelete="SET NULL"),
        ),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("user_instructions", sa.String(2000)),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_outputs", sa.Integer(), nullable=False),
        sa.Column("completed_outputs", sa.Integer(), nullable=False),
        sa.Column("failed_outputs", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_ai_studio_generation_idempotency"
        ),
    )
    op.create_index("ix_ai_studio_generations_owner_id", "ai_studio_generations", ["owner_id"])
    op.create_index(
        "ix_ai_studio_generations_context_fingerprint",
        "ai_studio_generations",
        ["context_fingerprint"],
    )
    op.create_index("ix_ai_studio_generations_status", "ai_studio_generations", ["status"])

    op.create_table(
        "ai_studio_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_studio_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="SET NULL"),
        ),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "generation_id",
            "product_id",
            "channel",
            "content_type",
            name="uq_ai_studio_output_target",
        ),
    )
    for column in ("generation_id", "product_id", "artifact_id"):
        op.create_index(f"ix_ai_studio_outputs_{column}", "ai_studio_outputs", [column])


def downgrade() -> None:
    op.drop_table("ai_studio_outputs")
    op.drop_table("ai_studio_generations")
    op.drop_table("ai_keyword_sets")
    op.drop_table("ai_generation_presets")
    op.drop_table("ai_brand_voices")
    for column in (
        "channel",
        "content_type",
        "locale",
        "context_fingerprint",
        "brand_voice_id",
        "parent_artifact_id",
        "generation_reason",
        "source",
        "user_instructions",
        "input_context_json",
        "edited_at",
        "edited_by",
    ):
        op.drop_column("generated_artifacts", column)
    for column in (
        "channel",
        "content_type",
        "locale",
        "context_fingerprint",
        "brand_voice_id",
        "preset_id",
        "generation_reason",
        "user_instruction_fingerprint",
    ):
        op.drop_column("ai_generation_requests", column)
