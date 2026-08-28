# ruff: noqa: E501,I001
# mypy: ignore-errors
"""Controlled external research ledgers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261003_0082"
down_revision = "20261002_0081"
branch_labels = None
depends_on = None


def _common(name: str, *extra: sa.Column[object]) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *extra,
    )


def upgrade() -> None:
    _common(
        "intelligence_external_search_requests",
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("language", sa.String(32), nullable=False, server_default="en"),
        sa.Column("max_results", sa.Integer, nullable=False, server_default="10"),
        sa.Column("safe_search", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("source_categories", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("allowed_domains", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("excluded_domains", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("identity_key", sa.String(300), nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_unique_constraint(
        "uq_external_search_identity",
        "intelligence_external_search_requests",
        ["owner_id", "identity_key"],
    )
    _common(
        "intelligence_external_search_results",
        sa.Column(
            "search_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_external_search_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("canonical_url", sa.Text, nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("snippet", sa.Text, nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_result_id", sa.String(300), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("raw_payload_reference", sa.Text, nullable=True),
        sa.Column(
            "source_classification",
            sa.String(64),
            nullable=False,
            server_default="SEARCH_DISCOVERY_RESULT",
        ),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("identity_key", sa.String(300), nullable=False),
    )
    op.create_unique_constraint(
        "uq_external_search_result_identity",
        "intelligence_external_search_results",
        ["owner_id", "identity_key"],
    )
    _common(
        "intelligence_external_fetches",
        sa.Column("mission_id", postgresql.UUID(as_uuid=True)),
        sa.Column("task_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "search_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_external_search_results.id", ondelete="SET NULL"),
        ),
        sa.Column("requested_url", sa.Text, nullable=False),
        sa.Column("final_url", sa.Text),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("http_status", sa.Integer),
        sa.Column("content_type", sa.String(120)),
        sa.Column("content_length", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(128)),
        sa.Column("source_profile", sa.String(120), nullable=False, server_default="default"),
        sa.Column("provider_mode", sa.String(32), nullable=False),
        sa.Column("redirect_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("identity_key", sa.String(300), nullable=False),
        sa.Column("freshness", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("extracted", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
    )
    op.create_unique_constraint(
        "uq_external_fetch_identity", "intelligence_external_fetches", ["owner_id", "identity_key"]
    )
    _common(
        "intelligence_external_source_profiles",
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("approved_domains", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("blocked_domains", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("robots_policy", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("terms_status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("access_classification", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_unique_constraint(
        "uq_external_source_profile", "intelligence_external_source_profiles", ["owner_id", "name"]
    )
    _common(
        "intelligence_external_provider_states",
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DISABLED"),
        sa.Column("requests_minute", sa.Integer, nullable=False, server_default="0"),
        sa.Column("requests_hour", sa.Integer, nullable=False, server_default="0"),
        sa.Column("requests_day", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_failure", sa.String(80)),
        sa.Column("disabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_external_provider_state",
        "intelligence_external_provider_states",
        ["owner_id", "provider"],
    )


def downgrade() -> None:
    for name in (
        "intelligence_external_provider_states",
        "intelligence_external_source_profiles",
        "intelligence_external_fetches",
        "intelligence_external_search_results",
        "intelligence_external_search_requests",
    ):
        op.drop_table(name)
