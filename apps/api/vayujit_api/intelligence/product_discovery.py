"""Bounded local product discovery for the guided commerce journey.

This module provides realistic, deterministic candidate identity only. It does
not claim live marketplace, demand, price, review, trend, or supplier facts.
Those remain owned by their existing intelligence services.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductCandidateDefinition:
    name: str
    product_concept: str
    description: str
    detailed_description: str
    category: str
    subcategory: str
    customer_segment: str
    customer_problem: str
    key_characteristics: tuple[str, ...]
    research_keywords: tuple[str, ...]
    alternative_terms: tuple[str, ...]
    shipping_characteristics: dict[str, str]
    regulatory_note: str

    @property
    def normalized_concept(self) -> str:
        return _normalize(self.product_concept)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            f"{self.normalized_concept}|{_normalize(self.category)}".encode()
        ).hexdigest()[:24]


LOCAL_PRODUCT_CANDIDATES: tuple[ProductCandidateDefinition, ...] = (
    ProductCandidateDefinition(
        name="Insulated Lunch Container",
        product_concept="Reusable insulated food container",
        description=(
            "A reusable insulated food container intended to keep meals organized during "
            "work, school, or travel."
        ),
        detailed_description=(
            "A portable meal-storage concept with an insulated body and a secure closure. "
            "Exact capacity, materials, dimensions, and thermal performance require supplier "
            "and marketplace verification."
        ),
        category="Home & Kitchen",
        subcategory="Food Storage",
        customer_segment="Office commuters, students, and travelers",
        customer_problem="Keeps prepared meals contained and easier to carry away from home.",
        key_characteristics=(
            "physical product",
            "portable",
            "lightweight concept",
            "non-fragile concept",
            "reusable",
            "easy-to-ship concept",
        ),
        research_keywords=(
            "insulated lunch container",
            "thermal lunch box",
            "reusable meal container",
        ),
        alternative_terms=("insulated tiffin", "food flask container"),
        shipping_characteristics={
            "size_class": "small-to-medium",
            "weight_class": "lightweight concept",
            "fragility": "low concept risk",
            "complexity": "simple parcel handling expected; verify",
        },
        regulatory_note=(
            "Electrical safety applies to included accessories only; "
            + "product scope needs verification."
        ),
    ),
    ProductCandidateDefinition(
        name="Foldable Wardrobe Organizer",
        product_concept="Collapsible fabric wardrobe storage organizer",
        description=(
            "A collapsible organizer for storing folded clothing and household textiles in "
            "wardrobes, shelves, or under-bed spaces."
        ),
        detailed_description=(
            "A foldable soft-storage concept designed to improve household organization. "
            "Fabric composition, load capacity, dimensions, and durability remain unverified."
        ),
        category="Home & Kitchen",
        subcategory="Storage & Organization",
        customer_segment="Renters, families, and small-space households",
        customer_problem="Reduces clutter and makes stored textiles easier to find and move.",
        key_characteristics=(
            "physical product",
            "foldable",
            "lightweight concept",
            "non-fragile concept",
            "non-perishable",
            "space-saving",
        ),
        research_keywords=(
            "foldable wardrobe organizer",
            "collapsible fabric storage box",
            "closet organizer",
        ),
        alternative_terms=("folding storage cube", "wardrobe storage bin"),
        shipping_characteristics={
            "size_class": "medium but collapsible",
            "weight_class": "lightweight concept",
            "fragility": "low concept risk",
            "complexity": "simple parcel handling expected; verify",
        },
        regulatory_note=(
            "Electrical safety applies to included accessories only; "
            + "product scope needs verification."
        ),
    ),
    ProductCandidateDefinition(
        name="Cable Management Travel Case",
        product_concept="Portable electronics cable and accessory organizer case",
        description=(
            "A compact case that keeps charging cables, adapters, and small electronics "
            "accessories organized during travel or daily commuting."
        ),
        detailed_description=(
            "A portable accessory-organizer concept with compartments or elastic retention. "
            "Exact materials, connector compatibility, and protective performance require "
            "evidence."
        ),
        category="Electronics Accessories",
        subcategory="Cable & Accessory Organization",
        customer_segment="Remote workers, students, and frequent travelers",
        customer_problem="Prevents cables and small accessories from becoming tangled or lost.",
        key_characteristics=(
            "physical product",
            "compact",
            "lightweight concept",
            "non-fragile concept",
            "non-perishable",
            "portable",
        ),
        research_keywords=(
            "cable organizer travel case",
            "electronics accessory pouch",
            "charger storage case",
        ),
        alternative_terms=("tech pouch", "cord organizer bag"),
        shipping_characteristics={
            "size_class": "small",
            "weight_class": "lightweight concept",
            "fragility": "low concept risk",
            "complexity": "simple parcel handling expected; verify",
        },
        regulatory_note=(
            "Electrical safety applies to included accessories only; "
            + "product scope needs verification."
        ),
    ),
    ProductCandidateDefinition(
        name="Reusable Food Storage Set",
        product_concept="Reusable household food storage container set",
        description=(
            "A reusable set of household containers intended to organize leftovers, pantry "
            "items, or packed meals."
        ),
        detailed_description=(
            "A household food-storage concept that may include multiple container sizes and "
            "closures. Exact materials, seal performance, and food-contact compliance require "
            "verification."
        ),
        category="Home & Kitchen",
        subcategory="Food Storage",
        customer_segment="Households preparing meals or storing leftovers",
        customer_problem=(
            "Makes food storage more organized while reducing reliance on "
            + "disposable packaging."
        ),
        key_characteristics=(
            "physical product",
            "reusable",
            "variant complexity possible",
            "non-perishable",
            "shipping complexity needs verification",
        ),
        research_keywords=(
            "reusable food storage containers",
            "meal prep container set",
            "airtight storage box set",
        ),
        alternative_terms=("kitchen storage set", "leftover containers"),
        shipping_characteristics={
            "size_class": "medium",
            "weight_class": "light-to-medium concept",
            "fragility": "material-dependent; verify",
            "complexity": "closure and breakage handling need verification",
        },
        regulatory_note=(
            "Electrical safety applies to included accessories only; "
            + "product scope needs verification."
        ),
    ),
    ProductCandidateDefinition(
        name="Travel Toiletry Organizer",
        product_concept="Portable travel toiletry and personal-care organizer",
        description=(
            "A portable organizer for carrying personal-care bottles and accessories during "
            "travel or everyday commutes."
        ),
        detailed_description=(
            "A soft-sided or structured toiletry-organizer concept with compartments for "
            "personal-care items. Exact capacity, leak resistance, and materials remain unknown."
        ),
        category="Travel Accessories",
        subcategory="Toiletry & Personal Organization",
        customer_segment="Travelers, gym users, and commuters",
        customer_problem="Keeps personal-care items contained and easier to pack or access.",
        key_characteristics=(
            "physical product",
            "compact",
            "lightweight concept",
            "non-fragile concept",
            "non-perishable",
            "portable",
        ),
        research_keywords=(
            "travel toiletry organizer",
            "hanging wash bag",
            "cosmetic travel pouch",
        ),
        alternative_terms=("travel wash bag", "toiletry case"),
        shipping_characteristics={
            "size_class": "small-to-medium",
            "weight_class": "lightweight concept",
            "fragility": "low concept risk",
            "complexity": "simple parcel handling expected; verify",
        },
        regulatory_note=(
            "Electrical safety applies to included accessories only; "
            + "product scope needs verification."
        ),
    ),
)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _goal_fit(raw_goal: str, structured_goal: dict[str, Any]) -> list[str]:
    text = f"{raw_goal} {structured_goal}".casefold()
    matches: list[str] = []
    if "amazon" in text:
        matches.append("Target marketplace recorded as Amazon India.")
    if any(token in text for token in ("lightweight", "easy to ship", "ship")):
        matches.append("Lightweight and shipping simplicity are confirmed goal preferences.")
    if "non-fragile" in text:
        matches.append("Non-fragile products are a confirmed goal preference.")
    if "non-perishable" in text:
        matches.append("Non-perishable products are a confirmed goal preference.")
    if "regulatory" in text:
        matches.append(
            "Simple regulatory profile is a confirmed goal preference; "
            + "requirements remain unverified."
        )
    matches.append("Candidate identity is supplied by the local deterministic research fixture.")
    return matches


def discover_local_product_candidates(
    raw_goal: str,
    structured_goal: dict[str, Any] | None = None,
    *,
    limit: int = 5,
) -> list[dict[str, object]]:
    """Return bounded candidate concepts for local deterministic mode."""
    goal = structured_goal or {}
    bounded = max(1, min(limit, len(LOCAL_PRODUCT_CANDIDATES)))
    marketplace = str(goal.get("marketplace") or "AMAZON_IN")
    region = str(goal.get("country_region") or goal.get("country") or "IN")
    results: list[dict[str, object]] = []
    for candidate in LOCAL_PRODUCT_CANDIDATES[:bounded]:
        fit = _goal_fit(raw_goal, goal)
        profile: dict[str, object] = {
            "profile_version": "gp7.5-local-product-intelligence-v1",
            "normalized_product_concept": candidate.normalized_concept,
            "product_type": "physical",
            "detailed_description": candidate.detailed_description,
            "customer_problem": candidate.customer_problem,
            "customer_problem_provenance": "DERIVED_FROM_PRODUCT_CONCEPT",
            "key_characteristics": list(candidate.key_characteristics),
            "research_keywords": list(candidate.research_keywords),
            "alternative_terms": list(candidate.alternative_terms),
            "candidate_source": "LOCAL_DETERMINISTIC_RESEARCH_FIXTURE",
            "candidate_provenance": {
                "source": "LOCAL_DETERMINISTIC_RESEARCH_FIXTURE",
                "mode": "LOCAL_DETERMINISTIC",
                "authoritative": False,
            },
            "goal_fit": fit,
            "why_this_surfaced": fit,
            "image": {
                "available": False,
                "source": "NOT_AVAILABLE",
                "message": "No verified product image available yet.",
            },
            "marketplace_observations": {
                "status": "NOT_AVAILABLE",
                "message": "No authoritative marketplace observation is configured in local mode.",
            },
            "price_evidence": {
                "status": "NOT_AVAILABLE",
                "message": "Observed marketplace prices are not available in local mode.",
            },
            "customer_evidence": {
                "status": "NOT_AVAILABLE",
                "message": "No authoritative customer-review evidence is configured in local mode.",
            },
            "competitor_evidence": {
                "status": "NOT_AVAILABLE",
                "message": "No authoritative competitor observations are configured in local mode.",
            },
            "trend_evidence": {
                "status": "NOT_AVAILABLE",
                "message": "No authoritative trend observations are configured in local mode.",
            },
            "demand_proxy_evidence": {
                "status": "NOT_AVAILABLE",
                "message": "Direct sales and demand data are not available; proxies need research.",
            },
            "shipping_characteristics": candidate.shipping_characteristics,
            "regulatory_evidence": {
                "status": "NEEDS_VERIFICATION",
                "message": candidate.regulatory_note,
            },
            "potential_differentiation": {
                "status": "NEEDS_EVIDENCE",
                "items": [],
            },
            "risk": {
                "status": "UNKNOWN",
                "message": "Product-level risk requires authoritative assessment evidence.",
            },
            "confidence": "PARTIAL",
            "evidence_completeness": {
                "overall": "PARTIAL",
                "identity": "COMPLETE",
                "category": "COMPLETE",
                "description": "COMPLETE",
                "customer": "MISSING",
                "competition": "MISSING",
                "trend": "MISSING",
                "marketplace": "MISSING",
                "supplier": "NOT_STARTED",
            },
            "missing_information": [
                "Authoritative marketplace observations",
                "Observed prices, ratings, and review counts",
                "Customer-review themes",
                "Competitor evidence",
                "Trend or interest evidence",
                "Supplier specifications and regulatory verification",
            ],
            "sourcing_readiness": {
                "identity": "READY",
                "category": "READY",
                "research_keywords": "READY",
                "supplier_search_context": "READY",
                "specifications": "PARTIAL",
                "regulatory_requirements": "NEEDS_VERIFICATION",
            },
            "candidate_readiness": "NEEDS_MORE_RESEARCH",
            "freshness": "FIXTURE_DEFINED",
        }
        results.append(
            {
                "name": candidate.name,
                "product_concept": candidate.product_concept,
                "description": candidate.description,
                "category": candidate.category,
                "subcategory": candidate.subcategory,
                "customer_segment": candidate.customer_segment,
                "target_marketplace": marketplace,
                "target_region": region,
                "research_keywords": list(candidate.research_keywords),
                "profile": profile,
                "fingerprint": candidate.fingerprint,
            }
        )
    return results


__all__ = [
    "ProductCandidateDefinition",
    "LOCAL_PRODUCT_CANDIDATES",
    "discover_local_product_candidates",
]
