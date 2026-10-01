from types import SimpleNamespace

from vayujit_api.intelligence.business_agent_service import _goal_projection


def test_goal_projection_does_not_treat_requires_as_currency() -> None:
    structured, _assumptions, unresolved = _goal_projection(
        "Find products that do not require complex regulatory approvals.", None
    )
    assert structured["capital"] is None
    assert structured["currency"] is None
    assert "available capital" in unresolved


def test_goal_projection_extracts_currency_with_word_boundary() -> None:
    structured, _assumptions, _unresolved = _goal_projection(
        "Find products within INR 300000 capital.", None
    )
    assert structured["capital"] == 300000
    assert structured["currency"] == "INR"


def test_goal_projection_extracts_supported_inr_and_lakh_forms() -> None:
    for goal in (
        "I have " + chr(0x20B9) + "3 lakh and want to start selling on Amazon India.",
        "I have " + chr(0x20B9) + "3,00,000 and want to start selling on Amazon India.",
        "I have INR 3 lakh and want to start selling on Amazon India.",
        "I have INR 300000 and want to start selling on Amazon India.",
        "I have 3 lakh rupees and want to start selling on Amazon India.",
        "I have 300000 INR and want to start selling on Amazon India.",
    ):
        structured, _assumptions, unresolved = _goal_projection(goal, None)
        assert structured["capital"] == 300000
        assert structured["currency"] == "INR"
        assert "available capital" not in unresolved


def test_goal_projection_preserves_unknown_capital() -> None:
    structured, _assumptions, unresolved = _goal_projection(
        "I want to start selling on Amazon India.", None
    )
    assert structured["capital"] is None
    assert structured["currency"] is None
    assert "available capital" in unresolved


def test_goal_projection_defaults_to_multiple_product_candidates() -> None:
    structured, _assumptions, _unresolved = _goal_projection(
        "I have INR 3 lakh and want to sell a product in kids category on Amazon India.", None
    )
    assert structured["candidate_count"] == 3


def test_goal_projection_is_stable_for_preserved_unicode_input() -> None:
    goal = "I have " + chr(0x20B9) + "3 lakh and want to start selling on Amazon India."
    first = _goal_projection(goal, None)
    second = _goal_projection(goal, None)
    assert first == second


def test_goal_projection_extracts_category_intent_without_inventing_product_evidence() -> None:
    structured, _assumptions, _unresolved = _goal_projection(
        "I have ?3 lakh and want to sell a product in kids category on Amazon India.", None
    )
    assert structured["category"] == "kids"
    assert structured["capital"] == 300000
    assert structured["marketplace"] == "AMAZON_IN"


def test_explicit_raw_category_overrides_stale_structured_category() -> None:
    from vayujit_api.intelligence.product_opportunity_scoring_router import _goal_category

    goal = SimpleNamespace(
        raw_goal="I want to sell a product in kids category on Amazon India.",
        structured_goal={"category": "home & kitchen"},
    )
    assert _goal_category(goal) == "kids"


def test_explicit_raw_category_overrides_supplied_structured_category() -> None:
    structured, _assumptions, _unresolved = _goal_projection(
        "I want to sell a product in kids category on Amazon India.",
        {"marketplace": "AMAZON_IN", "category": "Home & Kitchen"},
    )
    assert structured["category"] == "kids"
