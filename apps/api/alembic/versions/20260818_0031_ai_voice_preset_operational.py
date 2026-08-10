"""Complete operational Brand Voice and Generation Preset metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260818_0031"
down_revision: str | None = "20260817_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_brand_voices", sa.Column("description", sa.String(500)))
    for name, column in (
        ("brand_voice_id", postgresql.UUID(as_uuid=True)),
        ("locale", sa.String(16)),
        ("guidance", sa.String(2000)),
        ("preferred_provider", sa.String(100)),
        ("preferred_model", sa.String(120)),
        ("version", sa.Integer()),
    ):
        op.add_column("ai_generation_presets", sa.Column(name, column))
    op.create_foreign_key(
        "fk_ai_generation_presets_brand_voice_id",
        "ai_generation_presets",
        "ai_brand_voices",
        ["brand_voice_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE ai_generation_presets SET version = 1 WHERE version IS NULL")
    op.execute("UPDATE ai_generation_presets SET locale = 'en-IN' WHERE locale IS NULL")
    op.alter_column("ai_generation_presets", "version", nullable=False, server_default="1")
    op.alter_column("ai_generation_presets", "locale", nullable=False, server_default="en-IN")
    op.drop_constraint("uq_ai_generation_preset_name", "ai_generation_presets", type_="unique")
    op.create_unique_constraint(
        "uq_ai_generation_preset_name", "ai_generation_presets", ["owner_id", "name", "version"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_ai_generation_preset_name", "ai_generation_presets", type_="unique")
    op.create_unique_constraint(
        "uq_ai_generation_preset_name", "ai_generation_presets", ["owner_id", "name"]
    )
    op.drop_constraint(
        "fk_ai_generation_presets_brand_voice_id", "ai_generation_presets", type_="foreignkey"
    )
    for name in (
        "version",
        "preferred_model",
        "preferred_provider",
        "guidance",
        "locale",
        "brand_voice_id",
    ):
        op.drop_column("ai_generation_presets", name)
    op.drop_column("ai_brand_voices", "description")
