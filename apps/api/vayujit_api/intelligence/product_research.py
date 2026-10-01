"""Bounded, read-only ProductOpportunity market research orchestration."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.external_schemas import (
    ExternalFetchRequestBody,
    ExternalSearchRequestBody,
)
from vayujit_api.intelligence.external_service import fetch as approved_fetch
from vayujit_api.intelligence.external_service import search as external_search
from vayujit_api.intelligence.product_discovery import discover_local_product_candidates
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity

STOP_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "india",
    "amazon",
    "product",
    "case",
    "set",
    "container",
    "organizer",
    "storage",
    "travel",
    "portable",
    "reusable",
}


def _tokens(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9]+", value.casefold()) if item not in STOP_WORDS}


def _meaningful(opportunity: ProductOpportunity) -> bool:
    profile = opportunity.intelligence_profile or {}
    return bool(
        profile.get("normalized_product_concept")
        or (opportunity.category and opportunity.description and opportunity.product_concept)
    ) and opportunity.name.casefold() not in {
        "business agent product opportunity",
        "candidate product",
        "product opportunity 1",
        "test product",
        "example product",
    }


def _market_label(value: str) -> str:
    return {"IN": "India", "US": "United States", "GB": "United Kingdom"}.get(value.upper(), value)


def plan_product_research(
    opportunity: ProductOpportunity, *, max_queries: int = 3
) -> list[dict[str, Any]]:
    """Create deterministic, bounded queries from the canonical product identity."""
    profile = opportunity.intelligence_profile or {}
    concept = str(
        profile.get("normalized_product_concept") or opportunity.product_concept or opportunity.name
    )
    market = _market_label(opportunity.target_region or "")
    keywords = profile.get("research_keywords", [])
    first_keyword = str(keywords[0]) if isinstance(keywords, list) and keywords else concept
    queries = [
        {
            "objective": "PRODUCT_MARKETPLACE_RESEARCH",
            "query": f'"{opportunity.name}" {market}'.strip(),
            "source_categories": ["marketplace", "retailer"],
        },
        {
            "objective": "COMPETITOR_RESEARCH",
            "query": f'"{first_keyword}" alternatives {market}'.strip(),
            "source_categories": ["marketplace", "retailer", "editorial"],
        },
        {
            "objective": "CUSTOMER_RESEARCH",
            "query": f'"{concept}" reviews complaints'.strip(),
            "source_categories": ["review", "forum", "editorial"],
        },
    ]
    seen: set[str] = set()
    bounded: list[dict[str, Any]] = []
    for item in queries:
        query = str(item["query"]).strip()
        if query and query.casefold() not in seen:
            seen.add(query.casefold())
            bounded.append(item)
        if len(bounded) >= max(1, min(max_queries, 5)):
            break
    return bounded


def classify_result(
    *, title: str, url: str, snippet: str, opportunity: ProductOpportunity
) -> tuple[str, str]:
    """Classify discovery evidence without promoting snippets to product facts."""
    haystack = f"{title} {url} {snippet}".casefold()
    domain = (urlparse(url).hostname or "").casefold()
    title_tokens = _tokens(f"{title} {url}")
    concept_tokens = _tokens(
        f"{opportunity.name} {opportunity.product_concept} {opportunity.subcategory}"
    )
    overlap = len(title_tokens & concept_tokens)
    if any(host in domain for host in ("amazon.", "flipkart.", "myntra.", "walmart.", "target.")):
        kind = "MARKETPLACE_PRODUCT"
    elif any(term in haystack for term in ("review", "complaint", "rating", "unboxing")):
        kind = "REVIEW_PAGE"
    elif any(term in haystack for term in ("manufacturer", "supplier", "wholesale", "factory")):
        kind = "SUPPLIER_PAGE"
    elif any(term in haystack for term in ("category", "collection", "best ", "guide")):
        kind = "CATEGORY_PAGE"
    else:
        kind = "UNKNOWN"
    if overlap >= 2 or concept_tokens and concept_tokens.issubset(title_tokens):
        match = "DIRECT_PRODUCT_OBSERVATION"
    elif overlap == 1:
        match = "POSSIBLE_MATCH"
    elif kind == "CATEGORY_PAGE":
        match = "CATEGORY_LEVEL_EVIDENCE"
    else:
        match = "SEARCH_DISCOVERY_EVIDENCE"
    return kind, match


def _bounded_result(row: Any, opportunity: ProductOpportunity) -> dict[str, Any]:
    classification, _match = classify_result(
        title=row.title, url=row.url, snippet=row.snippet, opportunity=opportunity
    )
    # Search snippets are discovery evidence only; a verified product observation
    # requires an approved page fetch with structured product metadata.
    evidence_classification = (
        "CATEGORY_LEVEL_EVIDENCE"
        if classification == "CATEGORY_PAGE"
        else "SEARCH_DISCOVERY_EVIDENCE"
    )
    return {
        "id": str(row.id),
        "title": row.title,
        "url": row.url,
        "canonical_url": row.canonical_url,
        "domain": row.domain,
        "snippet": row.snippet,
        "provider": row.provider,
        "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
        "source_classification": classification,
        "evidence_classification": evidence_classification,
        "fetch_status": "NOT_ATTEMPTED",
    }


def _approved_domains() -> set[str]:
    value = get_settings().intelligence_external_approved_domains
    return {item.strip().lower().lstrip(".") for item in value.split(",") if item.strip()}


def _jsonld_product(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        type_value = value.get("@type", "")
        if (isinstance(type_value, str) and type_value.casefold() == "product") or (
            isinstance(type_value, list)
            and any(str(item).casefold() == "product" for item in type_value)
        ):
            return value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                match = _jsonld_product(item)
                if match:
                    return match
    if isinstance(value, list):
        for item in value:
            match = _jsonld_product(item)
            if match:
                return match
    return {}


def _bounded_product_metadata(value: object) -> dict[str, object]:
    product = _jsonld_product(value)
    if not product:
        return {}
    projection: dict[str, object] = {}
    for key in ("name", "sku", "mpn", "gtin", "description"):
        item = product.get(key)
        if isinstance(item, str) and item:
            projection[key] = item[:2_000]
    image = product.get("image")
    if isinstance(image, str) and image:
        projection["image"] = image[:2_000]
    elif isinstance(image, list):
        projection["image"] = [str(item)[:2_000] for item in image[:3]]
    brand = product.get("brand")
    if isinstance(brand, dict) and isinstance(brand.get("name"), str):
        projection["brand"] = {"name": str(brand["name"])[:500]}
    elif isinstance(brand, str) and brand:
        projection["brand"] = brand[:500]
    for key in ("offers", "aggregateRating"):
        item = product.get(key)
        if isinstance(item, dict):
            allowed = {
                name: str(item[name])[:500]
                for name in ("price", "priceCurrency", "availability", "ratingValue", "reviewCount")
                if name in item and item[name] is not None
            }
            if allowed:
                projection[key] = allowed
    return projection


def _bounded_product_projection(extracted: dict[str, object]) -> tuple[dict[str, object], bool]:
    metadata = extracted.get("product_metadata")
    metadata_map = metadata if isinstance(metadata, dict) else {}
    projection = _bounded_product_metadata(metadata_map.get("json_ld"))
    open_graph = extracted.get("open_graph")
    open_graph_map = open_graph if isinstance(open_graph, dict) else {}
    is_product_page = str(open_graph_map.get("type", "")).casefold() == "product"
    if is_product_page:
        title = open_graph_map.get("title") or extracted.get("title")
        if isinstance(title, str) and title:
            projection.setdefault("name", title[:2_000])
        image = open_graph_map.get("image")
        if isinstance(image, str) and image:
            projection.setdefault("image", image[:2_000])
        offers: dict[str, str] = {}
        for source, target in (("price:amount", "price"), ("price:currency", "priceCurrency")):
            value = metadata_map.get(source)
            if isinstance(value, str) and value:
                offers[target] = value[:500]
        if offers:
            projection.setdefault("offers", offers)
        description = extracted.get("meta_description")
        if isinstance(description, str) and description:
            projection.setdefault("description", description[:2_000])
    return projection, is_product_page


def _classify_live_page(
    *,
    title: str,
    url: str,
    snippet: str,
    extracted: dict[str, object],
    projection: dict[str, object],
    is_product_page: bool,
) -> tuple[str, str]:
    """Classify fetched pages before they can become Product Opportunities."""
    haystack = f"{title} {url} {snippet}".casefold()
    parsed = urlparse(url)
    path = parsed.path.casefold()
    if is_product_page or projection.get("name"):
        return "PRODUCT_DETAIL", "Structured product evidence was observed."
    if any(
        term in haystack for term in ("shipping policy", "seller guide", "how to sell", "shipping.")
    ):
        return "SHIPPING_POLICY", "The page is a service, policy, or seller guide."
    if any(term in path for term in ("/search", "/s?")):
        return "SEARCH_PAGE", "The URL indicates a search results surface."
    if any(term in path for term in ("/collections", "/category", "/categories")):
        return "PRODUCT_LISTING", "The URL indicates a listing or category surface."
    if parsed.path in ("", "/") and any(
        host in (parsed.hostname or "") for host in ("amazon.", "flipkart.")
    ):
        return "MARKETPLACE_HOME", "The page is a marketplace home page."
    if any(
        term in haystack
        for term in ("category", "collection", "best ", "guide", "ideas", "top products")
    ):
        return "CATEGORY", "The page is category or editorial discovery evidence."
    if any(term in haystack for term in ("manufacturer", "factory")) and any(
        token in path for token in ("/product", "/p/", "/item/")
    ):
        return "MANUFACTURER_PRODUCT", "A manufacturer product path was observed."
    if any(term in haystack for term in ("supplier", "wholesale")):
        return (
            "SUPPLIER_PRODUCT",
            "The page references a supplier or manufacturer but lacks product proof.",
        )
    if any(term in haystack for term in ("blog", "editorial", "review", "how to")):
        return "EDITORIAL", "The page is editorial or guidance content."
    return "UNKNOWN", "No product-specific page evidence was established."


def _has_product_identity(
    *, name: str, canonical_url: str, page_type: str, projection: dict[str, object]
) -> bool:
    if len(name.strip()) < 4 or page_type not in {
        "PRODUCT_DETAIL",
        "MANUFACTURER_PRODUCT",
        "SUPPLIER_PRODUCT",
    }:
        return False
    discriminator_keys = (
        "brand",
        "sku",
        "mpn",
        "gtin",
        "model",
        "image",
        "description",
        "category",
    )
    if any(projection.get(key) for key in discriminator_keys):
        return True
    path = urlparse(canonical_url).path.casefold()
    return any(token in path for token in ("/product", "/p/", "/dp/", "/item/"))


def _live_hypotheses(raw_goal: str, structured_goal: dict[str, object]) -> list[dict[str, object]]:
    """Reuse bounded deterministic hypotheses as seeds, never as live evidence."""
    definitions = discover_local_product_candidates(raw_goal, structured_goal, limit=3)
    return [
        {
            "name": str(item["name"]),
            "product_concept": str(item["product_concept"]),
            "category": str(item["category"]),
            "subcategory": str(item["subcategory"]),
            "source": "DETERMINISTIC_HYPOTHESIS",
        }
        for item in definitions[:3]
    ]


def _target_candidate_count(structured_goal: dict[str, object]) -> int:
    """Bound the number of validated products needed for one research run."""
    raw = structured_goal.get("target_candidate_count", structured_goal.get("candidate_count", 1))
    try:
        return max(1, min(int(str(raw)), 3))
    except (TypeError, ValueError):
        return 1


def _live_product_queries(concept: str) -> list[tuple[str, str]]:
    """Return product-oriented queries; supplier discovery is a later journey stage."""
    return [
        (f"{concept} India product", "PRIMARY_PRODUCT_QUERY"),
        (f"{concept} product specifications India", "REFINEMENT_AFTER_NO_PRODUCT_EVIDENCE"),
    ]


def _normalize_live_search_failure(exc: HTTPException) -> tuple[str, str]:
    detail = str(exc.detail)
    if exc.status_code == 429 or "quota" in detail.casefold():
        return "PROVIDER_QUOTA_EXHAUSTED", "Live search is temporarily unavailable."
    return "PROVIDER_UNAVAILABLE", detail


def run_live_product_discovery(
    db: Session,
    owner: User,
    *,
    raw_goal: str,
    structured_goal: dict[str, object] | None = None,
    max_results: int = 5,
    correlation_id: str = "",
    run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Run bounded adaptive discovery and materialize only validated product identities."""
    settings = get_settings()
    structured = structured_goal or {}
    market = str(structured.get("country_region") or structured.get("country") or "IN")
    marketplace = str(structured.get("marketplace") or "AMAZON_IN")
    hypotheses = _live_hypotheses(raw_goal, structured)
    configured_budget = max(
        1, min(int(getattr(settings, "intelligence_product_search_max_requests", 3)), 12)
    )
    max_hypotheses = min(len(hypotheses), 3)
    planned_requests = min(max_hypotheses * 2, configured_budget)
    target_candidates = _target_candidate_count(structured)
    empty_budget = {
        "configured": configured_budget,
        "planned": planned_requests,
        "executed": 0,
        "reused": 0,
        "remaining": configured_budget,
        "avoided": planned_requests,
        "target_candidates": target_candidates,
        "stop_reason": "NO_HYPOTHESES",
    }
    if not hypotheses:
        return {
            "mode": settings.intelligence_external_provider_mode,
            "status": "NO_USEFUL_PRODUCT_CANDIDATES",
            "hypotheses": [],
            "queries": [],
            "query_count": 0,
            "result_count": 0,
            "fetch_count": 0,
            "candidate_ids": [],
            "candidates": [],
            "rejected_results": [],
            "failures": ["No bounded product hypotheses were available."],
            "search_budget": empty_budget,
            "observability": {
                "planned_search_requests": planned_requests,
                "executed_search_requests": 0,
                "reused_search_requests": 0,
                "avoided_provider_calls": planned_requests,
                "results_returned": 0,
                "urls_fetched": 0,
                "fetches_reused": 0,
                "candidates_survived": 0,
                "stop_reason": "NO_HYPOTHESES",
            },
        }

    max_search_results = max(1, min(max_results, 3))
    max_fetches = max(1, min(max_results + 3, 8))
    query_reports: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    search_rows: list[tuple[dict[str, object], Any]] = []
    candidates: list[ProductOpportunity] = []
    fetches: list[dict[str, object]] = []
    rejected_results: list[dict[str, object]] = []
    observed_urls: set[str] = set()
    executed_requests = 0
    reused_requests = 0
    reused_fetches = 0
    quota_exhausted = False
    stop_reason = "SEARCH_BUDGET_EXHAUSTED"

    def materialize(hypothesis: dict[str, object], row: Any) -> bool:
        nonlocal reused_fetches
        if len(fetches) >= max_fetches or not hasattr(row, "url"):
            return False
        canonical = str(row.canonical_url or row.url)
        if canonical in observed_urls:
            return False
        observed_urls.add(canonical)
        try:
            fetched = approved_fetch(
                db,
                owner,
                ExternalFetchRequestBody(
                    url=canonical,
                    allowed_domains=[str(row.domain)],
                    search_result_id=uuid.UUID(str(row.id)),
                    correlation_id=f"product-discovery-fetch:{row.id}",
                ),
            )
        except HTTPException as exc:
            fetches.append(
                {
                    "url": canonical,
                    "domain": str(row.domain),
                    "status": "FAILED",
                    "page_type": "UNKNOWN",
                    "eligible": False,
                    "reused": False,
                    "failure": str(exc.detail),
                }
            )
            rejected_results.append(
                {
                    "url": canonical,
                    "domain": str(row.domain),
                    "page_type": "UNKNOWN",
                    "eligible": False,
                    "reason": str(exc.detail),
                }
            )
            return False
        reused = bool(isinstance(fetched, dict) and fetched.get("reuse"))
        if reused:
            reused_fetches += 1
        extracted = fetched.get("extracted", {}) if isinstance(fetched, dict) else {}
        extracted_map = extracted if isinstance(extracted, dict) else {}
        projection, is_product_page = _bounded_product_projection(extracted_map)
        title = str(
            projection.get("name") or extracted_map.get("title") or row.title or ""
        ).strip()[:200]
        page_type, page_reason = _classify_live_page(
            title=title,
            url=canonical,
            snippet=str(row.snippet or ""),
            extracted=extracted_map,
            projection=projection,
            is_product_page=is_product_page,
        )
        eligible = _has_product_identity(
            name=title, canonical_url=canonical, page_type=page_type, projection=projection
        )
        fetch_record: dict[str, object] = {
            "url": canonical,
            "domain": str(row.domain),
            "status": str(fetched.get("status", "COMPLETED")),
            "freshness": fetched.get("freshness", "UNKNOWN"),
            "page_type": page_type,
            "eligible": eligible,
            "reused": reused,
        }
        fetches.append(fetch_record)
        if not eligible:
            rejected_results.append(
                {
                    "url": canonical,
                    "domain": str(row.domain),
                    "title": title,
                    "page_type": page_type,
                    "eligible": False,
                    "reason": page_reason,
                }
            )
            return False
        description = str(
            projection.get("description")
            or extracted_map.get("meta_description")
            or "External product evidence; commercial details require verification."
        ).strip()[:4_000]
        category = str(projection.get("category") or hypothesis["category"])
        subcategory = str(projection.get("subcategory") or hypothesis["subcategory"])
        field_provenance = {
            key: "OBSERVED"
            for key in (
                "name",
                "brand",
                "sku",
                "mpn",
                "gtin",
                "model",
                "image",
                "description",
                "category",
            )
            if projection.get(key)
        }
        if "category" not in field_provenance:
            field_provenance["category"] = "DERIVED_HYPOTHESIS"
        key = hashlib.sha256(canonical.encode()).hexdigest()[:24]
        idempotency_key = (
            f"business-agent:{run_id}:candidate:{key}"
            if run_id is not None
            else f"business-agent:live-product:{key}"
        )
        candidate = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.idempotency_key == idempotency_key,
            )
        )
        if candidate is None:
            candidate = ProductOpportunity(
                owner_id=owner.id,
                name=title,
                description=description,
                product_concept=title,
                category=category,
                subcategory=subcategory,
                target_marketplace=marketplace,
                target_region=market,
                customer_segment="UNKNOWN",
                research_objective="Identify and evaluate products from bounded external evidence.",
                origin="external_research",
                lifecycle_status="researching",
                research_state="researched_with_gaps",
                evidence_state="available",
                tags=["business-agent", "LIVE_READ_ONLY", "EXTERNAL_RESEARCH"],
                notes="External product evidence for evaluation; not Amazon demand or sales data.",
                intelligence_profile={
                    "profile_version": "live-1c-product-discovery-v1",
                    "normalized_product_concept": title,
                    "candidate_source": "EXTERNAL_RESEARCH",
                    "candidate_provenance": {
                        "mode": "LIVE_READ_ONLY",
                        "source": "BRAVE_SEARCH_AND_APPROVED_WEB_FETCH",
                        "authoritative": False,
                    },
                    "research_keywords": [str(hypothesis["product_concept"])],
                    "live_research": {
                        "profile_version": "live-1c-product-discovery-v1",
                        "research_mode": settings.intelligence_external_provider_mode,
                        "status": "RESEARCHED_WITH_GAPS",
                        "queries": query_reports,
                        "search_results": [
                            {
                                "id": str(row.id),
                                "title": row.title,
                                "url": canonical,
                                "domain": row.domain,
                                "provider": row.provider,
                                "page_type": page_type,
                                "evidence_classification": "DIRECT_PRODUCT_OBSERVATION",
                                "fetch_status": str(fetched.get("status", "COMPLETED")),
                            }
                        ],
                        "source_urls": [canonical],
                        "approved_fetches": [fetch_record],
                        "evidence_counts": {
                            "search_discovery": 1,
                            "direct_product_observations": 1,
                            "approved_fetches": 1,
                        },
                        "provenance": (
                            "Brave product-specific search and ApprovedWebFetcher observation."
                        ),
                        "freshness": str(fetched.get("freshness", "UNKNOWN")),
                        "field_provenance": field_provenance,
                        "gaps": [
                            key
                            for key in ("brand", "sku", "model", "image", "offers")
                            if not projection.get(key)
                        ],
                    },
                    "research_sources": [
                        {
                            "url": canonical,
                            "domain": row.domain,
                            "classification": page_type,
                            "provider": row.provider,
                            "field_provenance": field_provenance,
                        }
                    ],
                    "marketplace_observations": {
                        "status": "NOT_AVAILABLE",
                        "message": (
                            "External evidence for a product evaluated for Amazon India; "
                            "not Amazon sales, demand, ranking, or conversion data."
                        ),
                    },
                    "product_metadata": projection,
                    "evidence_gaps": [
                        key
                        for key in ("brand", "sku", "model", "image", "offers")
                        if not projection.get(key)
                    ],
                    "category_provenance": (
                        "OBSERVED" if projection.get("category") else "DERIVED_HYPOTHESIS"
                    ),
                },
                idempotency_key=idempotency_key,
            )
            db.add(candidate)
            db.flush()
        candidates.append(candidate)
        return True

    for hypothesis in hypotheses[:max_hypotheses]:
        useful_for_hypothesis = False
        for query, reason in _live_product_queries(str(hypothesis["product_concept"])):
            if executed_requests >= configured_budget:
                stop_reason = "SEARCH_BUDGET_EXHAUSTED"
                break
            query = re.sub(r"\s+", " ", query).strip()[:240]
            report: dict[str, object] = {
                "stage": "PRODUCT_SPECIFIC_SEARCH",
                "objective": "PRODUCT_DISCOVERY",
                "query": query,
                "reason": reason,
                "market": market,
                "marketplace": marketplace,
                "hypothesis": hypothesis["name"],
                "source": "DETERMINISTIC_HYPOTHESIS",
            }
            executed_requests += 1
            try:
                response = external_search(
                    db,
                    owner,
                    ExternalSearchRequestBody(
                        query=query,
                        market=market,
                        max_results=max_search_results,
                        safe_search=True,
                        source_categories=["marketplace", "retailer", "editorial"],
                        correlation_id=correlation_id or f"product-discovery:{uuid.uuid4()}",
                    ),
                )
            except HTTPException as exc:
                code, message = _normalize_live_search_failure(exc)
                report.update(
                    {"status": "FAILED", "failure": message, "provider_mode": "LIVE_PROVIDER"}
                )
                query_reports.append(report)
                failures.append({"code": code, "message": message})
                if code == "PROVIDER_QUOTA_EXHAUSTED":
                    quota_exhausted = True
                    stop_reason = "PROVIDER_QUOTA_EXHAUSTED"
                    break
                continue
            reused = bool(response.get("reuse"))
            if reused:
                reused_requests += 1
            report.update(
                {
                    "status": response.get("status", "COMPLETED"),
                    "provider_mode": "REUSED_RECENT_SEARCH" if reused else "LIVE_PROVIDER",
                    "freshness": response.get("freshness", "UNKNOWN"),
                }
            )
            result_rows = response.get("results", [])
            rows = result_rows if isinstance(result_rows, list) else []
            report["result_count"] = len(rows)
            query_reports.append(report)
            for row in rows[:max_search_results]:
                search_rows.append((hypothesis, row))
                if materialize(hypothesis, row):
                    useful_for_hypothesis = True
                if len(candidates) >= target_candidates:
                    stop_reason = "EARLY_STOP_TARGET_REACHED"
                    break
            if len(candidates) >= target_candidates:
                break
            if useful_for_hypothesis:
                break
        if len(candidates) >= target_candidates or quota_exhausted:
            break

    if stop_reason == "SEARCH_BUDGET_EXHAUSTED" and executed_requests < configured_budget:
        stop_reason = "SEARCH_EXHAUSTED_WITHOUT_TARGET"
    avoided_provider_calls = max(0, planned_requests - executed_requests)
    search_budget = {
        "configured": configured_budget,
        "planned": planned_requests,
        "executed": executed_requests,
        "reused": reused_requests,
        "remaining": max(0, configured_budget - executed_requests),
        "avoided": avoided_provider_calls,
        "target_candidates": target_candidates,
        "stop_reason": stop_reason,
    }
    observability = {
        "planned_search_requests": planned_requests,
        "executed_search_requests": executed_requests,
        "reused_search_requests": reused_requests,
        "avoided_provider_calls": avoided_provider_calls,
        "results_returned": len(search_rows),
        "urls_fetched": len(fetches),
        "fetches_reused": reused_fetches,
        "candidates_survived": len(candidates),
        "stop_reason": stop_reason,
    }
    for candidate in candidates:
        profile = dict(candidate.intelligence_profile or {})
        live_value = profile.get("live_research")
        live = dict(live_value) if isinstance(live_value, dict) else {}
        live["queries"] = query_reports
        live["search_budget"] = search_budget
        live["observability"] = observability
        live["status"] = (
            "RESEARCHED_WITH_GAPS"
            if quota_exhausted
            else live.get("status", "RESEARCHED_WITH_GAPS")
        )
        profile["live_research"] = live
        candidate.intelligence_profile = profile
    db.commit()
    for candidate in candidates:
        db.refresh(candidate)
    status = (
        "RESEARCHED_WITH_GAPS"
        if candidates
        else ("PROVIDER_QUOTA_EXHAUSTED" if quota_exhausted else "NO_USEFUL_PRODUCT_CANDIDATES")
    )
    return {
        "mode": settings.intelligence_external_provider_mode,
        "status": status,
        "hypotheses": hypotheses[:max_hypotheses],
        "queries": query_reports,
        "query_count": len(query_reports),
        "result_count": len(search_rows),
        "fetch_count": sum(item.get("status") == "COMPLETED" for item in fetches),
        "candidate_ids": [str(item.id) for item in candidates],
        "candidates": [
            {
                "id": str(item.id),
                "name": item.name,
                "research_state": item.research_state,
                "evidence_state": item.evidence_state,
            }
            for item in candidates
        ],
        "fetches": fetches,
        "rejected_results": rejected_results,
        "failures": failures,
        "search_budget": search_budget,
        "observability": observability,
    }


def run_product_research(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    *,
    max_queries: int = 3,
    max_results: int = 5,
    fetch_sources: bool = True,
) -> dict[str, Any]:
    if not _meaningful(opportunity):
        raise HTTPException(422, "Product research requires a meaningful product identity.")
    settings = get_settings()
    opportunity.research_state = "researching"
    opportunity.lifecycle_status = "researching"
    db.flush()
    queries = plan_product_research(opportunity, max_queries=max_queries)
    query_reports: list[dict[str, Any]] = []
    search_results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, item in enumerate(queries, start=1):
        query = str(item["query"])
        try:
            response = external_search(
                db,
                owner,
                ExternalSearchRequestBody(
                    query=query,
                    market=opportunity.target_region or "",
                    max_results=max(1, min(max_results, 10)),
                    safe_search=True,
                    source_categories=list(item["source_categories"]),
                    correlation_id=f"product-research:{opportunity.id}:{index}",
                ),
            )
            raw_rows = response.get("results", [])
            rows = raw_rows if isinstance(raw_rows, list) else []
            bounded = [_bounded_result(row, opportunity) for row in rows if hasattr(row, "url")]
            search_results.extend(bounded)
            query_reports.append(
                {
                    "objective": item["objective"],
                    "query": query,
                    "status": response.get("status"),
                    "result_count": len(bounded),
                }
            )
        except HTTPException as exc:
            failures.append({"objective": str(item["objective"]), "code": str(exc.detail)})
            query_reports.append(
                {
                    "objective": item["objective"],
                    "query": query,
                    "status": "FAILED",
                    "result_count": 0,
                    "failure": str(exc.detail),
                }
            )
    unique_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for result in search_results:
        url = str(result["canonical_url"])
        if url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    approved = _approved_domains()
    fetch_reports: list[dict[str, Any]] = []
    if fetch_sources:
        for result in unique_results[:10]:
            domain = str(result["domain"]).lower()
            if not any(domain == item or domain.endswith("." + item) for item in approved):
                result["fetch_status"] = "BLOCKED_UNAPPROVED_DOMAIN"
                continue
            try:
                fetched = approved_fetch(
                    db,
                    owner,
                    ExternalFetchRequestBody(
                        url=str(result["canonical_url"]),
                        allowed_domains=[domain],
                        search_result_id=uuid.UUID(str(result["id"])),
                        correlation_id=f"product-research-fetch:{result['id']}",
                    ),
                )
                extracted = fetched.get("extracted", {}) if isinstance(fetched, dict) else {}
                extracted_map = extracted if isinstance(extracted, dict) else {}
                product_projection, is_product_page = _bounded_product_projection(extracted_map)
                if product_projection:
                    result["source_classification"] = (
                        "RETAILER_PRODUCT" if is_product_page else result["source_classification"]
                    )
                    result["evidence_classification"] = "DIRECT_PRODUCT_OBSERVATION"
                result["fetch_status"] = (
                    str(fetched.get("status", "COMPLETED"))
                    if isinstance(fetched, dict)
                    else "COMPLETED"
                )
                fetch_reports.append(
                    {
                        "url": result["canonical_url"],
                        "domain": domain,
                        "status": result["fetch_status"],
                        "freshness": fetched.get("freshness", "UNKNOWN"),
                        "extracted": {
                            "title": extracted_map.get("title"),
                            "canonical_url": extracted_map.get("canonical_url"),
                            "open_graph": extracted_map.get("open_graph", {}),
                            "product_metadata": product_projection,
                        },
                    }
                )
            except HTTPException as exc:
                result["fetch_status"] = "FETCH_FAILED"
                fetch_reports.append(
                    {
                        "url": result["canonical_url"],
                        "domain": domain,
                        "status": "FETCH_FAILED",
                        "failure": str(exc.detail),
                    }
                )
    now = datetime.now(UTC)
    direct_count = sum(
        item["evidence_classification"] == "DIRECT_PRODUCT_OBSERVATION" for item in unique_results
    )
    possible_count = sum(
        item["evidence_classification"] == "POSSIBLE_MATCH" for item in unique_results
    )
    live = {
        "profile_version": "gp7.6-live-product-research-v1",
        "research_mode": settings.intelligence_external_provider_mode,
        "status": (
            "RESEARCHED_WITH_GAPS"
            if query_reports and any(item.get("status") == "COMPLETED" for item in query_reports)
            else "PROVIDER_UNAVAILABLE"
        ),
        "started_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "queries": query_reports,
        "search_results": unique_results[:30],
        "source_urls": [str(item["canonical_url"]) for item in unique_results[:30]],
        "approved_fetches": fetch_reports[:10],
        "evidence_counts": {
            "search_discovery": len(unique_results),
            "direct_product_observations": direct_count,
            "possible_matches": possible_count,
            "approved_fetches": len(fetch_reports),
        },
        "provenance": "Brave search discovery and approved web fetch where permitted.",
        "freshness": "FRESH" if unique_results else "UNKNOWN",
        "failures": failures,
        "gaps": (
            [
                "Approved domain fetch is unavailable for unapproved domains.",
                "Marketplace, price, review, competitor, trend, and demand facts "
                "require approved fetched evidence.",
            ]
            if unique_results
            else ["No authoritative market evidence was returned."]
        ),
    }
    profile = dict(opportunity.intelligence_profile or {})
    profile["live_research"] = live
    profile["research_sources"] = [
        {
            "url": item["canonical_url"],
            "domain": item["domain"],
            "classification": item["source_classification"],
            "evidence_classification": item["evidence_classification"],
            "observed_at": item["retrieved_at"],
            "provider": item["provider"],
        }
        for item in unique_results[:30]
    ]
    if fetch_reports:
        profile["approved_fetch_evidence"] = fetch_reports[:10]
    if direct_count:
        profile["marketplace_observations"] = {
            "status": "AVAILABLE",
            "count": direct_count,
            "source": "EXTERNAL_RESEARCH",
        }
    opportunity.intelligence_profile = profile
    opportunity.evidence_state = (
        "available" if direct_count else ("partial" if unique_results else "unknown")
    )
    opportunity.research_state = (
        "researched_with_gaps" if unique_results else "provider_unavailable"
    )
    opportunity.updated_at = now
    db.commit()
    db.refresh(opportunity)
    return {
        "opportunity_id": str(opportunity.id),
        "research_state": opportunity.research_state,
        "evidence_state": opportunity.evidence_state,
        "mode": settings.intelligence_external_provider_mode,
        "query_count": len(query_reports),
        "result_count": len(unique_results),
        "fetch_count": len(fetch_reports),
        "queries": query_reports,
        "results": unique_results[:30],
        "fetches": fetch_reports[:10],
        "failures": failures,
        "gaps": live["gaps"],
    }
