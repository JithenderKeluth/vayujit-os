from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException

from vayujit_api.intelligence.external_provider import _SafeHTMLParser
from vayujit_api.intelligence.product_research import (
    _classify_live_page,
    _has_product_identity,
    _jsonld_product,
    _live_product_queries,
    _normalize_live_search_failure,
    _target_candidate_count,
    classify_result,
    plan_product_research,
)


def _opportunity() -> SimpleNamespace:
    return SimpleNamespace(
        name="Insulated Lunch Container",
        product_concept="Reusable insulated food container",
        category="Home & Kitchen",
        subcategory="Food Storage",
        target_region="IN",
        intelligence_profile={
            "normalized_product_concept": "reusable insulated food container",
            "research_keywords": ["insulated lunch container"],
        },
    )


def test_product_research_plans_bounded_goal_specific_queries() -> None:
    queries = plan_product_research(_opportunity())
    assert len(queries) == 3
    assert queries[0]["objective"] == "PRODUCT_MARKETPLACE_RESEARCH"
    assert "India" in queries[0]["query"]
    assert queries[1]["objective"] == "COMPETITOR_RESEARCH"
    assert queries[2]["objective"] == "CUSTOMER_RESEARCH"


def test_search_result_classification_does_not_promote_category_snippet() -> None:
    opportunity = _opportunity()
    source, evidence = classify_result(
        title="Best lunch box category guide",
        url="https://example.org/lunch-boxes",
        snippet="A category guide comparing common containers.",
        opportunity=opportunity,
    )
    assert source == "CATEGORY_PAGE"
    assert evidence in {"CATEGORY_LEVEL_EVIDENCE", "POSSIBLE_MATCH"}


def test_safe_parser_extracts_bounded_structured_metadata() -> None:
    parser = _SafeHTMLParser()
    parser.feed(
        '<html><head><meta property="og:image" content="https://cdn.example/image.jpg">'
        '<meta property="product:price:amount" content="999">'
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Lunch Container","image":"https://cdn.example/p.jpg",'
        '"offers":{"price":"999","priceCurrency":"INR"}}'
        "</script></head><body><title>Lunch Container</title></body></html>"
    )
    extracted = parser.extracted(fallback_url="https://example.org/item", max_length=10_000)
    assert extracted["open_graph"] == {"image": "https://cdn.example/image.jpg"}
    metadata = extracted["product_metadata"]
    assert isinstance(metadata, dict)
    assert metadata["price:amount"] == "999"
    assert isinstance(metadata["json_ld"], dict)
    assert metadata["json_ld"]["name"] == "Lunch Container"


def test_product_projection_promotes_bounded_open_graph_product_metadata() -> None:
    from vayujit_api.intelligence.product_research import _bounded_product_projection

    projection, is_product_page = _bounded_product_projection(
        {
            "title": "Retailer product title",
            "meta_description": "Food-grade stainless steel tiffin box.",
            "open_graph": {
                "type": "product",
                "title": "Retailer product title",
                "image": "https://cdn.example/product.jpg",
            },
            "product_metadata": {
                "price:amount": "560",
                "price:currency": "INR",
                "json_ld": {"@type": "BreadcrumbList"},
            },
        }
    )
    assert is_product_page is True
    assert projection["name"] == "Retailer product title"
    assert projection["image"] == "https://cdn.example/product.jpg"
    assert projection["offers"] == {"price": "560", "priceCurrency": "INR"}
    assert projection["description"] == "Food-grade stainless steel tiffin box."


def test_live_page_classification_rejects_editorial_and_shipping_pages() -> None:
    empty: dict[str, object] = {}
    assert (
        _classify_live_page(
            title="How to sell on Amazon India",
            url="https://shipping.amazon.in/blog/low-investment-home-business-ideas",
            snippet="Seller guide",
            extracted=empty,
            projection=empty,
            is_product_page=False,
        )[0]
        == "SHIPPING_POLICY"
    )
    assert (
        _classify_live_page(
            title="Best lunch containers guide",
            url="https://example.org/category/lunch-containers",
            snippet="Category guide",
            extracted=empty,
            projection=empty,
            is_product_page=False,
        )[0]
        == "PRODUCT_LISTING"
    )


def test_live_product_identity_requires_product_page_discriminator() -> None:
    assert not _has_product_identity(
        name="Best lunch containers",
        canonical_url="https://example.org/category/lunch-containers",
        page_type="CATEGORY",
        projection={"name": "Best lunch containers"},
    )
    assert _has_product_identity(
        name="Acme Insulated Tiffin Box",
        canonical_url="https://example.org/product/acme-tiffin",
        page_type="PRODUCT_DETAIL",
        projection={"name": "Acme Insulated Tiffin Box", "brand": "Acme"},
    )


def test_jsonld_product_array_type_establishes_product_evidence() -> None:
    assert _jsonld_product({"@type": ["Thing", "Product"], "name": "Tiffin"})["name"] == "Tiffin"


def test_live_product_queries_are_product_only_and_bounded() -> None:
    queries = _live_product_queries("reusable insulated food container")
    assert len(queries) == 2
    assert queries[0][1] == "PRIMARY_PRODUCT_QUERY"
    assert queries[1][1] == "REFINEMENT_AFTER_NO_PRODUCT_EVIDENCE"
    assert all('"' not in query for query, _reason in queries)
    assert all(
        word in queries[0][0].casefold()
        for word in ("reusable", "insulated", "food", "container", "india", "product")
    )
    assert all(
        word in queries[1][0].casefold()
        for word in ("reusable", "insulated", "food", "container", "india", "product")
    )
    assert all("manufacturer" not in query.casefold() for query, _reason in queries)
    assert all("supplier" not in query.casefold() for query, _reason in queries)


def test_live_search_quota_has_distinct_normalized_state() -> None:
    code, message = _normalize_live_search_failure(HTTPException(429, "Search quota exceeded."))
    assert code == "PROVIDER_QUOTA_EXHAUSTED"
    assert "temporarily unavailable" in message


def test_live_target_candidate_count_is_bounded() -> None:
    assert _target_candidate_count({"target_candidate_count": 9}) == 3
    assert _target_candidate_count({"target_candidate_count": 0}) == 1
    assert _target_candidate_count({"target_candidate_count": "invalid"}) == 1
