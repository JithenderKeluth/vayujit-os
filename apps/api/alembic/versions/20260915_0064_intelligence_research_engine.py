"""Add deterministic Intelligence research engine persistence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260915_0064"
down_revision = "20260914_0063"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True)


def _owner() -> sa.Column:
    return sa.Column(
        "owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def _json(name: str, default: str = "{}") -> sa.Column:
    return sa.Column(name, JSONB, nullable=False, server_default=default)


def upgrade() -> None:
    op.create_table(
        "intelligence_research_profiles",
        _id(),
        _owner(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("min_selling_price", sa.Numeric(18, 2)),
        sa.Column("max_selling_price", sa.Numeric(18, 2)),
        sa.Column("max_sourcing_estimate", sa.Numeric(18, 2)),
        sa.Column("minimum_margin", sa.Numeric(8, 4)),
        sa.Column("max_weight_kg", sa.Numeric(12, 4)),
        sa.Column("max_length_cm", sa.Numeric(12, 4)),
        sa.Column("max_width_cm", sa.Numeric(12, 4)),
        sa.Column("max_height_cm", sa.Numeric(12, 4)),
        _json("categories", "[]"),
        _json("excluded_categories", "[]"),
        sa.Column(
            "competition_tolerance", sa.String(24), nullable=False, server_default="balanced"
        ),
        sa.Column("risk_tolerance", sa.String(24), nullable=False, server_default="balanced"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_intel_profile_owner_name"),
    )
    op.create_index("ix_intel_profiles_owner", "intelligence_research_profiles", ["owner_id"])

    op.create_table(
        "intelligence_research_missions",
        _id(),
        _owner(),
        sa.Column(
            "project_id",
            UUID,
            sa.ForeignKey("intelligence_research_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            UUID,
            sa.ForeignKey("intelligence_research_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("frequency", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        _json("categories", "[]"),
        sa.Column("ruleset_version", sa.String(120), nullable=False, server_default="default-v1"),
        sa.Column("minimum_score_threshold", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("notification_threshold", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column(
            "last_run_id", UUID, sa.ForeignKey("intelligence_research_runs.id", ondelete="SET NULL")
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_intel_mission_owner_name"),
    )
    op.create_index("ix_intel_missions_owner", "intelligence_research_missions", ["owner_id"])
    op.create_index("ix_intel_missions_status", "intelligence_research_missions", ["status"])

    op.create_table(
        "intelligence_research_candidates",
        _id(),
        _owner(),
        sa.Column(
            "project_id",
            UUID,
            sa.ForeignKey("intelligence_research_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "research_run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            UUID,
            sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_reference", sa.String(300), nullable=False),
        sa.Column("deduplication_key", sa.String(512), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("normalized_title", sa.String(240), nullable=False),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("subcategory", sa.String(120), nullable=False, server_default=""),
        sa.Column("market", sa.String(120), nullable=False, server_default=""),
        sa.Column("observed_brand", sa.String(160)),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="discovered"),
        sa.Column("observed_price", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3)),
        _json("attributes"),
        sa.Column(
            "duplicate_of_id",
            UUID,
            sa.ForeignKey("intelligence_research_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "deduplication_key", name="uq_intel_candidate_owner_dedup"),
    )
    op.create_index("ix_intel_candidates_owner", "intelligence_research_candidates", ["owner_id"])
    op.create_index(
        "ix_intel_candidates_run", "intelligence_research_candidates", ["research_run_id"]
    )
    op.create_index("ix_intel_candidates_status", "intelligence_research_candidates", ["status"])
    op.create_index(
        "ix_intel_candidates_dedup", "intelligence_research_candidates", ["deduplication_key"]
    )
    op.add_column(
        "intelligence_opportunities",
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_research_candidates.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_intelligence_opportunities_candidate", "intelligence_opportunities", ["candidate_id"]
    )

    op.create_table(
        "intelligence_research_signals",
        _id(),
        _owner(),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_type", sa.String(40), nullable=False),
        sa.Column("value", sa.Numeric(18, 6)),
        sa.Column("normalized_score", sa.Numeric(8, 4)),
        sa.Column("unit", sa.String(40)),
        _json("source_evidence_ids", "[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("calculation_method", sa.String(500), nullable=False),
        sa.Column("signal_version", sa.Integer(), nullable=False, server_default="1"),
        _json("details"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "candidate_id",
            "signal_type",
            "signal_version",
            name="uq_intel_signal_candidate_version",
        ),
    )
    op.create_index("ix_intel_signals_candidate", "intelligence_research_signals", ["candidate_id"])

    op.create_table(
        "intelligence_competitor_products",
        _id(),
        _owner(),
        sa.Column(
            "source_id",
            UUID,
            sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_reference", sa.String(300), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("brand", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "source_id",
            "external_reference",
            name="uq_intel_competitor_owner_source_ref",
        ),
    )
    op.create_table(
        "intelligence_competitor_snapshots",
        _id(),
        _owner(),
        sa.Column(
            "competitor_id",
            UUID,
            sa.ForeignKey("intelligence_competitor_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id", UUID, sa.ForeignKey("intelligence_evidence.id", ondelete="SET NULL")
        ),
        sa.Column("price", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("rating", sa.Numeric(4, 2)),
        sa.Column("review_count", sa.Integer()),
        _json("features"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_intel_competitor_snapshots_competitor",
        "intelligence_competitor_snapshots",
        ["competitor_id"],
    )

    for table, columns in (
        (
            "intelligence_review_themes",
            [
                sa.Column(
                    "candidate_id",
                    UUID,
                    sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("theme_type", sa.String(40), nullable=False),
                sa.Column("label", sa.String(160), nullable=False),
                sa.Column("frequency_count", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("frequency_ratio", sa.Numeric(6, 4), nullable=False, server_default="0"),
                _json("evidence_ids", "[]"),
                sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
            ],
        ),
        (
            "intelligence_pain_points",
            [
                sa.Column(
                    "candidate_id",
                    UUID,
                    sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("issue", sa.String(240), nullable=False),
                sa.Column("frequency", sa.Numeric(6, 4), nullable=False),
                sa.Column("frequency_count", sa.Integer(), nullable=False),
                _json("evidence_ids", "[]"),
                sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
            ],
        ),
        (
            "intelligence_differentiations",
            [
                sa.Column(
                    "candidate_id",
                    UUID,
                    sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("idea", sa.String(300), nullable=False),
                sa.Column(
                    "classification", sa.String(24), nullable=False, server_default="hypothesis"
                ),
                sa.Column("rationale", sa.String(500), nullable=False),
                _json("evidence_ids", "[]"),
            ],
        ),
    ):
        op.create_table(
            table,
            _id(),
            _owner(),
            *columns,  # type: ignore[arg-type]
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(f"ix_{table}_candidate", table, ["candidate_id"])

    op.create_table(
        "intelligence_score_evaluations",
        _id(),
        _owner(),
        sa.Column(
            "candidate_id",
            UUID,
            sa.ForeignKey("intelligence_research_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scoring_model_version", sa.String(120), nullable=False),
        _json("weights"),
        _json("inputs"),
        _json("dimension_scores"),
        _json("weighted_contributions"),
        sa.Column("score", sa.Numeric(8, 3), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("recommendation", sa.String(40), nullable=False),
        sa.Column("hard_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        _json("risk_summary"),
        _json("critic_findings", "[]"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        _json("evidence_ids", "[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "candidate_id",
            "scoring_model_version",
            name="uq_intel_score_candidate_version",
        ),
    )
    op.create_index("ix_intel_scores_candidate", "intelligence_score_evaluations", ["candidate_id"])

    op.create_table(
        "intelligence_research_checkpoints",
        _id(),
        _owner(),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(80), nullable=False, server_default="created"),
        _json("payload"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "run_id", name="uq_intel_checkpoint_owner_run"),
    )
    op.create_table(
        "intelligence_research_reports",
        _id(),
        _owner(),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("intelligence_research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _json("provenance_json"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "run_id", "format", name="uq_intel_report_owner_run_format"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_intelligence_opportunities_candidate", table_name="intelligence_opportunities"
    )
    op.drop_column("intelligence_opportunities", "candidate_id")
    for table in (
        "intelligence_research_reports",
        "intelligence_research_checkpoints",
        "intelligence_score_evaluations",
        "intelligence_differentiations",
        "intelligence_pain_points",
        "intelligence_review_themes",
        "intelligence_competitor_snapshots",
        "intelligence_competitor_products",
        "intelligence_research_signals",
        "intelligence_research_candidates",
        "intelligence_research_missions",
        "intelligence_research_profiles",
    ):
        op.drop_table(table)
