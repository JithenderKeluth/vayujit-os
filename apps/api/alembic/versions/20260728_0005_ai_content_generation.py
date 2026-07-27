"""Add AI content generation.

Revision ID: 20260728_0005
Revises: 20260727_0004
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260728_0005"
down_revision = "20260727_0004"
branch_labels = None
depends_on = None

DEFAULT_TEMPLATE_ID = uuid.UUID("a1000000-0000-4000-8000-000000000001")


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", "version", name="uq_prompt_template_key_version"),
        sa.CheckConstraint("status IN ('enabled', 'disabled')", name="ck_prompt_templates_status"),
    )
    op.create_index("ix_prompt_templates_key", "prompt_templates", ["key"])
    op.create_index("ix_prompt_templates_template_type", "prompt_templates", ["template_type"])
    op.create_index("ix_prompt_templates_status", "prompt_templates", ["status"])

    op.create_table(
        "ai_generation_requests",
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
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prompt_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("additional_instructions", sa.String(2000)),
        sa.Column("normalized_input_hash", sa.String(64)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_generation_requests_status",
        ),
    )
    for column in ("owner_id", "brand_id", "product_id", "status", "normalized_input_hash"):
        op.create_index(f"ix_ai_generation_requests_{column}", "ai_generation_requests", [column])

    op.create_table(
        "generated_artifacts",
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
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "generation_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_generation_requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prompt_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("validation_result", postgresql.JSONB(), nullable=False),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column(
            "rejected_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("rejection_reason", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "version_number", name="uq_artifact_product_version"),
        sa.UniqueConstraint("generation_request_id", name="uq_artifact_generation_request"),
        sa.CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected', 'superseded')",
            name="ck_generated_artifacts_status",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_generated_artifacts_version"),
    )
    for column in ("owner_id", "brand_id", "product_id", "status"):
        op.create_index(f"ix_generated_artifacts_{column}", "generated_artifacts", [column])

    timestamp = datetime.now(UTC)
    prompt_templates = sa.table(
        "prompt_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("template_type", sa.String()),
        sa.column("system_instructions", sa.Text()),
        sa.column("user_template", sa.Text()),
        sa.column("output_schema", postgresql.JSONB()),
        sa.column("status", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        prompt_templates,
        [
            {
                "id": DEFAULT_TEMPLATE_ID,
                "key": "product-content",
                "name": "Product content",
                "description": "Generates reviewable product marketing content.",
                "version": 1,
                "template_type": "product_content",
                "system_instructions": "Return structured product content only.",
                "user_template": "Generate content for the supplied brand and product context.",
                "output_schema": {
                    "title": "string",
                    "short_description": "string",
                    "long_description": "string",
                    "seo_title": "string",
                    "seo_description": "string",
                    "keywords": ["string"],
                },
                "status": "enabled",
                "is_default": True,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("generated_artifacts")
    op.drop_table("ai_generation_requests")
    op.drop_table("prompt_templates")
