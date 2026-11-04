"""Permit existing storyboard-only scene authority without a rendered generation."""

import sqlalchemy as sa
from alembic import context, op

revision = "20261206_0149"
down_revision = "20261205_0148"
branch_labels = None
depends_on = None


def _check(*, nullable: bool) -> None:
    if context.is_offline_mode() or op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("WP6A_ONLINE_POSTGRESQL_REQUIRED")
    op.get_bind().exec_driver_sql("LOCK TABLE video_scenes IN ACCESS EXCLUSIVE MODE")
    columns = {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns("video_scenes")}
    generation = columns.get("generation_id")
    board = columns.get("storyboard_id")
    if (
        not generation
        or not board
        or not isinstance(generation["type"], sa.UUID)
        or generation["nullable"] != nullable
        or generation["default"] is not None
    ):
        raise RuntimeError("WP6A_SCENE_GENERATION_SCHEMA_UNSUPPORTED")


def upgrade() -> None:
    _check(nullable=False)
    op.alter_column("video_scenes", "generation_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    _check(nullable=True)
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM video_scenes WHERE generation_id IS NULL)")
    ):
        raise RuntimeError("WP6A_DOWNGRADE_WOULD_ORPHAN_STORYBOARD_SCENES")
    op.alter_column("video_scenes", "generation_id", existing_type=sa.UUID(), nullable=False)
