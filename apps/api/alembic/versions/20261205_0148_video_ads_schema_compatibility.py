"""Repair legacy Video version names and missing Ads campaign recovery columns.

Only the known pre-repair schema is accepted. No historical rows are rewritten.
Downgrade refuses to discard non-NULL recovery metadata written after upgrade.
"""

from typing import Any

import sqlalchemy as sa
from alembic import context, op

revision = "20261205_0148"
down_revision = "20261204_0147"
branch_labels = None
depends_on = None

VERSION_NAMES = (("storyboardversion", "storyboard_version"), ("styleversion", "style_version"))
RECOVERY_NAMES = ("failure_category", "retry_after_seconds", "next_retry_at", "correlation_id")
INDEX_NAME = "ix_ad_campaigns_correlation_id"


def _locked_columns() -> tuple[dict[str, Any], dict[str, Any]]:
    if context.is_offline_mode():
        raise RuntimeError("WP6A_ONLINE_SCHEMA_VERIFICATION_REQUIRED")
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("WP6A_POSTGRESQL_REQUIRED")
    inspector = sa.inspect(bind)
    if not all(inspector.has_table(t) for t in ("ad_campaigns", "video_generations")):
        raise RuntimeError("WP6A_REQUIRED_TABLE_MISSING")
    # Locks span checks and transactional DDL, including rollback data-loss guard.
    bind.exec_driver_sql("LOCK TABLE ad_campaigns, video_generations IN ACCESS EXCLUSIVE MODE")
    return (
        {c["name"]: c for c in sa.inspect(bind).get_columns("video_generations")},
        {c["name"]: c for c in sa.inspect(bind).get_columns("ad_campaigns")},
    )


def _version_contract(columns: dict[str, Any], *, repaired: bool) -> None:
    for legacy, canonical in VERSION_NAMES:
        source, absent = (canonical, legacy) if repaired else (legacy, canonical)
        column = columns.get(source)
        if (
            not column
            or absent in columns
            or not isinstance(column["type"], sa.Integer)
            or not column["nullable"]
            or column["default"] is not None
        ):
            raise RuntimeError("WP6A_VIDEO_VERSION_SCHEMA_UNSUPPORTED")


def upgrade() -> None:
    video, campaigns = _locked_columns()
    _version_contract(video, repaired=False)
    if any(name in campaigns for name in RECOVERY_NAMES):
        raise RuntimeError("WP6A_ADS_RECOVERY_SCHEMA_AMBIGUOUS")
    if any(i["name"] == INDEX_NAME for i in sa.inspect(op.get_bind()).get_indexes("ad_campaigns")):
        raise RuntimeError("WP6A_ADS_INDEX_AMBIGUOUS")
    for legacy, canonical in VERSION_NAMES:
        op.alter_column("video_generations", legacy, new_column_name=canonical)
    op.add_column("ad_campaigns", sa.Column("failure_category", sa.String(80), nullable=True))
    op.add_column("ad_campaigns", sa.Column("retry_after_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "ad_campaigns", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("ad_campaigns", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.create_index(INDEX_NAME, "ad_campaigns", ["correlation_id"], unique=False)


def downgrade() -> None:
    video, campaigns = _locked_columns()
    _version_contract(video, repaired=True)
    expected: dict[str, sa.types.TypeEngine[Any]] = {
        "failure_category": sa.String(80),
        "retry_after_seconds": sa.Integer(),
        "next_retry_at": sa.DateTime(timezone=True),
        "correlation_id": sa.String(64),
    }
    for name, kind in expected.items():
        column = campaigns.get(name)
        if (
            not column
            or not column["nullable"]
            or column["default"] is not None
            or column["type"].compile(dialect=op.get_bind().dialect)
            != kind.compile(dialect=op.get_bind().dialect)
        ):
            raise RuntimeError("WP6A_DOWNGRADE_SCHEMA_UNSUPPORTED")
    index = next(
        (
            i
            for i in sa.inspect(op.get_bind()).get_indexes("ad_campaigns")
            if i["name"] == INDEX_NAME
        ),
        None,
    )
    if not index or index["column_names"] != ["correlation_id"] or index["unique"]:
        raise RuntimeError("WP6A_DOWNGRADE_INDEX_UNSUPPORTED")
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM ad_campaigns WHERE failure_category IS NOT NULL "
            "OR retry_after_seconds IS NOT NULL OR next_retry_at IS NOT NULL "
            "OR correlation_id IS NOT NULL)"
        )
    ):
        raise RuntimeError("WP6A_DOWNGRADE_WOULD_LOSE_RECOVERY_DATA")
    op.drop_index(INDEX_NAME, table_name="ad_campaigns")
    for name in RECOVERY_NAMES:
        op.drop_column("ad_campaigns", name)
    for legacy, canonical in VERSION_NAMES:
        op.alter_column("video_generations", canonical, new_column_name=legacy)
