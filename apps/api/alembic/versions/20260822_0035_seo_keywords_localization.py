"""Add explainable SEO analysis and tag sets."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0035"
down_revision: str | None = "20260821_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_keyword_sets", sa.Column("description", sa.String(500)))
    op.add_column(
        "ai_keyword_sets",
        sa.Column(
            "excluded_keywords_json", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "ai_keyword_sets",
        sa.Column(
            "competitor_references_json", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "ai_keyword_sets",
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
    )
    op.add_column(
        "ai_keyword_sets", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "ai_keyword_sets",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_keyword_sets",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_ai_keyword_sets_locale", "ai_keyword_sets", ["locale"])
    op.create_index("ix_ai_keyword_sets_archived", "ai_keyword_sets", ["archived"])
    op.create_table(
        "ai_seo_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_artifacts.id", ondelete="CASCADE"),
        ),
        sa.Column("artifact_version", sa.Integer()),
        sa.Column(
            "keyword_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_keyword_sets.id", ondelete="SET NULL"),
        ),
        sa.Column("keyword_set_version", sa.Integer()),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("intent", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("seo_type", sa.String(32), nullable=False, server_default="website"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False, server_default="seo-rules-v1"),
        sa.Column("status", sa.String(24), nullable=False, server_default="current"),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("dimensions_json", postgresql.JSONB(), nullable=False),
        sa.Column("findings_json", postgresql.JSONB(), nullable=False),
        sa.Column("recommendations_json", postgresql.JSONB(), nullable=False),
        sa.Column("keyword_coverage_json", postgresql.JSONB(), nullable=False),
        sa.Column("metrics_json", postgresql.JSONB(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "artifact_id",
            "artifact_version",
            "channel",
            "locale",
            "fingerprint",
            name="uq_ai_seo_analysis_context",
        ),
    )
    for column in (
        "owner_id",
        "product_id",
        "artifact_id",
        "keyword_set_id",
        "channel",
        "locale",
        "fingerprint",
    ):
        op.create_index(f"ix_ai_seo_analyses_{column}", "ai_seo_analyses", [column])
    op.create_table(
        "ai_tag_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="product"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
        sa.Column("tags_json", postgresql.JSONB(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", "scope", "locale", name="uq_ai_tag_set_identity"),
    )
    for column in ("owner_id", "product_id", "archived"):
        op.create_index(f"ix_ai_tag_sets_{column}", "ai_tag_sets", [column])


def downgrade() -> None:
    op.drop_table("ai_tag_sets")
    op.drop_table("ai_seo_analyses")
    op.drop_index("ix_ai_keyword_sets_archived", table_name="ai_keyword_sets")
    op.drop_index("ix_ai_keyword_sets_locale", table_name="ai_keyword_sets")
    for column in (
        "is_default",
        "archived",
        "version",
        "locale",
        "competitor_references_json",
        "excluded_keywords_json",
        "description",
    ):
        op.drop_column("ai_keyword_sets", column)
