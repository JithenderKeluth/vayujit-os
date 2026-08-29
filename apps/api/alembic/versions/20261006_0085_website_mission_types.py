# ruff: noqa: E501
"""Allow bounded manufacturer and supplier website research missions."""

from alembic import op

revision = "20261006_0085"
down_revision = "20261005_0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_autonomous_mission_type", "intelligence_autonomous_missions", type_="check"
    )
    op.create_check_constraint(
        "ck_autonomous_mission_type",
        "intelligence_autonomous_missions",
        "mission_type IN ('PRODUCT_DISCOVERY','PRODUCT_VALIDATION','TREND_RESEARCH','COMPETITOR_RESEARCH','REVIEW_RESEARCH','SUPPLIER_DISCOVERY','SUPPLIER_VERIFICATION','PRICING_RESEARCH','ECONOMICS_RESEARCH','RISK_RESEARCH','SOURCE_REFRESH','FULL_OPPORTUNITY_RESEARCH','MANUFACTURER_RESEARCH','SUPPLIER_WEBSITE_RESEARCH')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_autonomous_mission_type", "intelligence_autonomous_missions", type_="check"
    )
    op.create_check_constraint(
        "ck_autonomous_mission_type",
        "intelligence_autonomous_missions",
        "mission_type IN ('PRODUCT_DISCOVERY','PRODUCT_VALIDATION','TREND_RESEARCH','COMPETITOR_RESEARCH','REVIEW_RESEARCH','SUPPLIER_DISCOVERY','SUPPLIER_VERIFICATION','PRICING_RESEARCH','ECONOMICS_RESEARCH','RISK_RESEARCH','SOURCE_REFRESH','FULL_OPPORTUNITY_RESEARCH')",
    )
