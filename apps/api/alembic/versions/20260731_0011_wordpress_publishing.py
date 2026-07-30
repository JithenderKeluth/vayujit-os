"""Add WordPress connector configuration and remote publishing state."""

from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260731_0011"
down_revision = "20260730_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execution_columns = [
        sa.Column("requested_action", sa.String(30), nullable=False, server_default="publish"),
        sa.Column("remote_entity_type", sa.String(30)),
        sa.Column("remote_entity_id", sa.String(100)),
        sa.Column("remote_edit_url", sa.String(500)),
        sa.Column("remote_status", sa.String(30)),
        sa.Column("remote_slug", sa.String(200)),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("reconciliation_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("correlation_id", sa.String(64)),
    ]
    for column in execution_columns:
        op.add_column("publishing_executions", cast(sa.Column[Any], column))

    attempt_columns = [
        sa.Column("operation", sa.String(40), nullable=False, server_default="publish"),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("request_method", sa.String(10)),
        sa.Column("safe_endpoint_label", sa.String(80)),
        sa.Column("response_status", sa.Integer()),
        sa.Column("remote_request_id", sa.String(160)),
        sa.Column("retry_after_seconds", sa.Integer()),
        sa.Column("ambiguous_result", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("correlation_id", sa.String(64)),
    ]
    for column in attempt_columns:
        op.add_column("publishing_execution_attempts", cast(sa.Column[Any], column))

    op.create_table(
        "wordpress_connector_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_url", sa.String(500), nullable=False),
        sa.Column("username", sa.String(160), nullable=False),
        sa.Column("encrypted_application_password", sa.Text()),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("authentication_type", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("default_post_status", sa.String(20), nullable=False),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retry_attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("safe_validation_message", sa.String(500)),
        sa.Column("last_validation_latency_ms", sa.Integer()),
        sa.Column(
            "capabilities_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            "request_timeout_seconds BETWEEN 10 AND 120", name="ck_wordpress_timeout"
        ),
        sa.CheckConstraint("max_retry_attempts BETWEEN 1 AND 5", name="ck_wordpress_retries"),
        sa.UniqueConstraint("owner_id", name="uq_wordpress_configuration_owner"),
    )
    op.create_index(
        "ix_wordpress_connector_configurations_owner_id",
        "wordpress_connector_configurations",
        ["owner_id"],
    )


def downgrade() -> None:
    op.drop_table("wordpress_connector_configurations")
    for column in [
        "correlation_id",
        "ambiguous_result",
        "retry_after_seconds",
        "remote_request_id",
        "response_status",
        "safe_endpoint_label",
        "request_method",
        "latency_ms",
        "operation",
    ]:
        op.drop_column("publishing_execution_attempts", column)
    for column in [
        "correlation_id",
        "reconciliation_status",
        "last_reconciled_at",
        "cancelled_at",
        "cancellation_requested_at",
        "remote_slug",
        "remote_status",
        "remote_edit_url",
        "remote_entity_id",
        "remote_entity_type",
        "requested_action",
    ]:
        op.drop_column("publishing_executions", column)
