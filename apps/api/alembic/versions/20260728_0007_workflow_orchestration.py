"""Add constrained workflow orchestration."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260728_0007"
down_revision = "20260728_0006"
branch_labels = None
depends_on = None
DEFAULT_TEMPLATE_ID = uuid.UUID("b1000000-0000-4000-8000-000000000001")


def upgrade() -> None:
    op.create_table(
        "workflow_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("workflow_type", sa.String(80), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", "version", name="uq_workflow_template_key_version"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_workflow_template_status"),
    )
    for column in ("key", "workflow_type", "status"):
        op.create_index(f"ix_workflow_templates_{column}", "workflow_templates", [column])
    op.create_table(
        "workflow_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column(
            "workflow_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id"),
            nullable=False,
        ),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publishing_destinations.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_step_key", sa.String(80)),
        sa.Column("input_json", postgresql.JSONB(), nullable=False),
        sa.Column("context_json", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','running','waiting_for_approval','completed','failed','cancelled')",
            name="ck_workflow_instance_status",
        ),
    )
    for column in (
        "owner_id",
        "brand_id",
        "product_id",
        "destination_id",
        "status",
        "current_step_key",
    ):
        op.create_index(f"ix_workflow_instances_{column}", "workflow_instances", [column])
    op.create_table(
        "workflow_step_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_instances.id"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(80), nullable=False),
        sa.Column("step_type", sa.String(40), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_reference_json", postgresql.JSONB(), nullable=False),
        sa.Column("output_reference_json", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workflow_instance_id", "step_key", "attempt_number", name="uq_workflow_step_attempt"
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','waiting','succeeded','failed','skipped','cancelled')",
            name="ck_workflow_step_status",
        ),
        sa.CheckConstraint("sequence_number BETWEEN 1 AND 3", name="ck_workflow_step_sequence"),
        sa.CheckConstraint("attempt_number > 0", name="ck_workflow_step_attempt_positive"),
    )
    for column in ("workflow_instance_id", "step_key", "status"):
        op.create_index(
            f"ix_workflow_step_executions_{column}", "workflow_step_executions", [column]
        )
    stamp = datetime.now(UTC)
    table = sa.table(
        "workflow_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("workflow_type", sa.String()),
        sa.column("definition_json", postgresql.JSONB()),
        sa.column("status", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": DEFAULT_TEMPLATE_ID,
                "key": "product-content-publish",
                "name": "Product content and publish",
                "description": (
                    "Generate product content, pause for owner approval, "
                    "then publish to a destination."
                ),
                "version": 1,
                "workflow_type": "product_content_publish",
                "definition_json": {
                    "schema_version": 1,
                    "steps": [
                        {"key": "generate_content", "type": "ai_generate"},
                        {
                            "key": "wait_for_approval",
                            "type": "human_approval",
                            "depends_on": ["generate_content"],
                        },
                        {
                            "key": "publish_content",
                            "type": "publish",
                            "depends_on": ["wait_for_approval"],
                        },
                    ],
                },
                "status": "enabled",
                "is_default": True,
                "created_at": stamp,
                "updated_at": stamp,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("workflow_step_executions")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_templates")
