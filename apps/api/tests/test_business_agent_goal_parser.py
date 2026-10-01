from vayujit_api.intelligence.business_agent_service import _goal_projection


def test_goal_projection_does_not_treat_requires_as_currency() -> None:
    structured, _assumptions, unresolved = _goal_projection(
        "Find products that do not require complex regulatory approvals.", None
    )
    assert structured["capital"] is None
    assert "available capital" in unresolved


def test_goal_projection_extracts_currency_with_word_boundary() -> None:
    structured, _assumptions, _unresolved = _goal_projection(
        "Find products within INR 300000 capital.", None
    )
    assert structured["capital"] == 300000
