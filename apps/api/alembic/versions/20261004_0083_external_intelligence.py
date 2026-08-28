# ruff: noqa: E501
"""Persist external evidence intelligence and idempotent handoff metadata."""
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "20261004_0083"
down_revision = "20261003_0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    additions: dict[str, list[tuple[str, Any]]] = {
        "intelligence_autonomous_evidence": [
            ("fresh_until", sa.DateTime(timezone=True)),
            ("stale_at", sa.DateTime(timezone=True)),
            ("expires_at", sa.DateTime(timezone=True)),
            ("freshness_at_verification", sa.String(32)),
            ("verification_reason", sa.String(500)),
            ("verification_method", sa.String(120)),
            ("verified_at", sa.DateTime(timezone=True)),
            ("source_profile", sa.String(120)),
            ("provider", sa.String(120)),
            ("canonical_url", sa.String(1000)),
            ("domain", sa.String(255)),
            ("lineage", sa.JSON()),
        ],
        "intelligence_autonomous_contradictions": [
            ("task_id", sa.UUID()),
            ("claim_key", sa.String(120)),
            ("evidence_a_value", sa.JSON()),
            ("evidence_b_value", sa.JSON()),
            ("source_a", sa.String(1000)),
            ("source_b", sa.String(1000)),
            ("freshness_a", sa.String(32)),
            ("freshness_b", sa.String(32)),
            ("verification_a", sa.String(32)),
            ("verification_b", sa.String(32)),
            ("confidence_a", sa.Numeric(6, 4)),
            ("confidence_b", sa.Numeric(6, 4)),
            ("correlation_id", sa.String(80)),
        ],
        "intelligence_autonomous_changes": [
            ("entity_type", sa.String(80)),
            ("entity_id", sa.String(120)),
            ("field_key", sa.String(120)),
        ],
        "intelligence_autonomous_alerts": [("identity_key", sa.String(300))],
    }
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in additions.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, type_ in columns:
            if name not in existing:
                op.add_column(table, sa.Column(name, type_, nullable=True))
    op.create_unique_constraint(
        "uq_autonomous_alert_identity",
        "intelligence_autonomous_alerts",
        ["owner_id", "mission_id", "identity_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_autonomous_alert_identity", "intelligence_autonomous_alerts", type_="unique"
    )
    for table, names in {
        "intelligence_autonomous_alerts": ["identity_key"],
        "intelligence_autonomous_changes": ["field_key", "entity_id", "entity_type"],
        "intelligence_autonomous_contradictions": [
            "correlation_id",
            "confidence_b",
            "confidence_a",
            "verification_b",
            "verification_a",
            "freshness_b",
            "freshness_a",
            "source_b",
            "source_a",
            "evidence_b_value",
            "evidence_a_value",
            "claim_key",
            "task_id",
        ],
        "intelligence_autonomous_evidence": [
            "lineage",
            "domain",
            "canonical_url",
            "provider",
            "source_profile",
            "verified_at",
            "verification_method",
            "verification_reason",
            "freshness_at_verification",
            "expires_at",
            "stale_at",
            "fresh_until",
        ],
    }.items():
        for name in names:
            op.drop_column(table, name)
