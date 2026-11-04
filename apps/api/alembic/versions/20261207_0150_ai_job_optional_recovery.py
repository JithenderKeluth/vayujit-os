"""Align optional AI-job failure/retry metadata with its existing ORM contract.

No rows, defaults, types, identities, failure values or approval state are changed.
Downgrade refuses to invent values or discard records that legitimately use NULL.
"""

import sqlalchemy as sa
from alembic import context, op

revision = "20261207_0150"
down_revision = "20261206_0149"
branch_labels = None
depends_on = None

OPTIONAL = {
    "failure_category": sa.String(80),
    "retry_after_seconds": sa.Integer(),
    "calculated_delay_seconds": sa.Integer(),
    "applied_delay_seconds": sa.Integer(),
    "next_retry_at": sa.DateTime(timezone=True),
    "checkpoint_fingerprint": sa.String(64),
}


def _check(nullable: bool) -> None:
    if context.is_offline_mode() or op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("WP7A_ONLINE_POSTGRESQL_REQUIRED")
    bind = op.get_bind()
    bind.exec_driver_sql("LOCK TABLE ai_studio_jobs IN ACCESS EXCLUSIVE MODE")
    columns = {c["name"]: c for c in sa.inspect(bind).get_columns("ai_studio_jobs")}
    for name, kind in OPTIONAL.items():
        c = columns.get(name)
        if not c or c["nullable"] != nullable or c["default"] is not None:
            raise RuntimeError("WP7A_AI_JOB_SCHEMA_UNSUPPORTED")
        if not isinstance(c["type"], type(kind)):
            raise RuntimeError("WP7A_AI_JOB_TYPE_UNSUPPORTED")
        if isinstance(kind, sa.String) and c["type"].length != kind.length:
            raise RuntimeError("WP7A_AI_JOB_TYPE_UNSUPPORTED")
        if isinstance(kind, sa.DateTime) and not c["type"].timezone:
            raise RuntimeError("WP7A_AI_JOB_TYPE_UNSUPPORTED")


def upgrade() -> None:
    _check(False)
    for name, kind in OPTIONAL.items():
        op.alter_column("ai_studio_jobs", name, existing_type=kind, nullable=True)


def downgrade() -> None:
    _check(True)
    predicate = " OR ".join(f'"{name}" IS NULL' for name in OPTIONAL)
    if op.get_bind().scalar(
        sa.text(f"SELECT EXISTS(SELECT 1 FROM ai_studio_jobs WHERE {predicate})")
    ):
        raise RuntimeError("WP7A_DOWNGRADE_WOULD_INVALIDATE_OPTIONAL_JOB_METADATA")
    for name, kind in OPTIONAL.items():
        op.alter_column("ai_studio_jobs", name, existing_type=kind, nullable=False)
