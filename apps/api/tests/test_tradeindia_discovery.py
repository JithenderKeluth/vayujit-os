from vayujit_api.core.config import Settings
from vayujit_api.intelligence.tradeindia import discover_local, provider_preflight


def test_tradeindia_provider_defaults_disabled_and_fixture_is_deterministic() -> None:
    settings = Settings()
    readiness = provider_preflight(settings)
    assert readiness["provider"] == "TRADEINDIA"
    assert readiness["status"] == "DISABLED"
    assert readiness["read_only"] is True
    first = discover_local(query="cotton shirt", limit=2, country_code="IN")
    second = discover_local(query="cotton shirt", limit=2, country_code="IN")
    assert [row.provider_result_id for row in first] == [row.provider_result_id for row in second]
    assert all(row.metadata["fixture"] is True for row in first)


def test_tradeindia_live_mode_is_fail_closed() -> None:
    settings = Settings(
        tradeindia_enabled=True, tradeindia_mode="LIVE_READ_ONLY", tradeindia_token_ref="configured"
    )
    readiness = provider_preflight(settings)
    assert readiness["status"] == "NOT_CONFIGURED"
    assert readiness["network_call"] is False


def test_tradeindia_normalization_matrix_is_null_safe_and_deduplicated_by_runtime() -> None:
    cases = (
        "complete",
        "missing_price_currency_moq_lead_time_claim",
        "missing_currency",
        "missing_moq",
        "missing_location",
        "missing_supplier_identity",
        "missing_product_listing_title",
        "same_supplier_multiple_listings",
        "similar_supplier_name",
        "duplicate_provider_result",
        "changed_listing",
        "listing_disappeared",
        "missing_availability",
        "commercial_disagreement",
        "stale_commercial_observation",
    )
    for case in cases:
        rows = discover_local(query="cotton shirt", limit=20, country_code="IN", fixture_case=case)
        expected_count = 2 if case == "duplicate_provider_result" else 1
        assert len(rows) == expected_count
        row = rows[0]
        assert row.metadata["fixture_case"] == case
        assert row.metadata["classification"] == "DISCOVERY_ONLY"
        assert row.source_url.startswith("https://www.tradeindia.com/")
        assert row.supplier_name
        assert row.listing_name
    rows = discover_local(query="cotton shirt", limit=20, country_code="IN")
    assert len(rows) == 16
    assert len({row.provider_result_id for row in rows}) == 15
    assert all(row.metadata["fixture"] is True for row in rows)
