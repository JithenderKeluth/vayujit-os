"""Alibaba read-only provider adapter with deterministic local fixtures."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from vayujit_api.core.config import Settings


@dataclass(frozen=True)
class AlibabaListing:
    provider_result_id: str
    supplier_name: str
    listing_name: str
    source_url: str
    location: str | None
    category: str | None
    price: float | None
    currency: str | None
    moq: float | None
    moq_unit: str | None
    lead_time: str | None
    availability: str | None
    verification_claim: str | None
    metadata: dict[str, object]


def provider_preflight(settings: Settings) -> dict[str, object]:
    if (
        settings.intelligence_external_kill_switch
        or settings.external_mutations_emergency_stop
        or settings.alibaba_kill_switch
    ):
        status = "KILL_SWITCHED"
    elif settings.alibaba_mode == "DISABLED" or not settings.alibaba_enabled:
        status = "DISABLED"
    elif settings.alibaba_mode == "LOCAL_FIXTURE":
        status = "READY"
    else:
        status = "NOT_CONFIGURED"
    return {
        "provider": "ALIBABA",
        "mode": settings.alibaba_mode,
        "status": status,
        "credentials_configured": bool(settings.alibaba_token_ref),
        "live_validation": "NOT_RUN",
        "read_only": True,
        "network_call": False,
    }


def _metadata(case: str, country_code: str | None) -> dict[str, object]:
    return {
        "fixture": True,
        "fixture_case": case,
        "country_filter": country_code or "UNKNOWN",
        "verification": "unverified",
        "classification": "DISCOVERY_ONLY",
    }


def discover_local(
    *, query: str, limit: int, country_code: str | None, fixture_case: str | None = None
) -> list[AlibabaListing]:
    """Return deterministic, bounded normalized fixtures; never performs I/O.

    The default matrix intentionally includes complete, incomplete, duplicate,
    identity, claim, changed, and disappeared listing shapes. ``fixture_case``
    selects one case for focused tests while preserving the same provider IDs.
    """
    digest = hashlib.sha256(query.casefold().encode()).hexdigest()[:12]
    title = query.strip().title() or "Unknown product"
    common = "Alibaba Local Fixture Manufacturing"
    values = [
        AlibabaListing(
            f"local-{digest}-001",
            common,
            f"{title} factory listing",
            f"https://www.alibaba.com/local-fixture/{digest}/001",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            18.5,
            "USD",
            100.0,
            "units",
            "21 days",
            "in_stock",
            "provider_claimed",
            _metadata("complete", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-002",
            "Alibaba Local Fixture Components",
            f"{title} components listing",
            f"https://www.alibaba.com/local-fixture/{digest}/002",
            "Ningbo, Zhejiang, CN",
            query[:120] or None,
            None,
            None,
            None,
            None,
            None,
            "unknown",
            None,
            _metadata("missing_price_currency_moq_lead_time_claim", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-003",
            common,
            f"{title} no currency listing",
            f"https://www.alibaba.com/local-fixture/{digest}/003",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            22.0,
            None,
            120.0,
            "units",
            "24 days",
            "limited",
            "provider_badge_claim",
            _metadata("missing_currency", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-004",
            common,
            f"{title} no MOQ listing",
            f"https://www.alibaba.com/local-fixture/{digest}/004",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            19.0,
            "USD",
            None,
            None,
            "25 days",
            "in_stock",
            "rating_4_8",
            _metadata("missing_moq", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-005",
            common,
            f"{title} no location listing",
            f"https://www.alibaba.com/local-fixture/{digest}/005",
            None,
            query[:120] or None,
            20.0,
            "USD",
            80.0,
            "units",
            "28 days",
            "in_stock",
            "years_on_platform_claim",
            _metadata("missing_location", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-006",
            "UNKNOWN",
            f"{title} insufficient identity listing",
            f"https://www.alibaba.com/local-fixture/{digest}/006",
            "Guangdong, CN",
            query[:120] or None,
            21.0,
            "USD",
            90.0,
            "units",
            "30 days",
            "unknown",
            None,
            _metadata("missing_supplier_identity", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-007",
            "Alibaba Local Fixture Trading",
            "UNKNOWN",
            f"https://www.alibaba.com/local-fixture/{digest}/007",
            "Fujian, CN",
            None,
            17.0,
            "USD",
            70.0,
            "units",
            "18 days",
            "in_stock",
            "manufacturer_wording_claim",
            _metadata("missing_product_listing_title", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-008",
            common,
            f"{title} alternate pack listing",
            f"https://www.alibaba.com/local-fixture/{digest}/008",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            19.5,
            "USD",
            200.0,
            "units",
            "35 days",
            "in_stock",
            "provider_verified_badge",
            _metadata("same_supplier_multiple_listings", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-009",
            "Alibaba Local Fixture Manufacturings",
            f"{title} similar supplier listing",
            f"https://www.alibaba.com/local-fixture/{digest}/009",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            18.0,
            "USD",
            100.0,
            "units",
            "21 days",
            "in_stock",
            "verified_manufacturer_claim",
            _metadata("similar_supplier_name", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-010",
            common,
            f"{title} duplicate listing",
            f"https://www.alibaba.com/local-fixture/{digest}/010",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            18.5,
            "USD",
            100.0,
            "units",
            "21 days",
            "in_stock",
            "provider_claimed",
            _metadata("duplicate_provider_result", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-010",
            common,
            f"{title} duplicate listing",
            f"https://www.alibaba.com/local-fixture/{digest}/010",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            18.5,
            "USD",
            100.0,
            "units",
            "21 days",
            "in_stock",
            "provider_claimed",
            _metadata("duplicate_provider_result", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-011",
            common,
            f"{title} changed listing",
            f"https://www.alibaba.com/local-fixture/{digest}/011",
            "Shenzhen, Guangdong, CN",
            query[:120] or None,
            26.0,
            "USD",
            150.0,
            "units",
            "42 days",
            "limited",
            "verification_changed_claim",
            _metadata("changed_listing", country_code),
        ),
        AlibabaListing(
            f"local-{digest}-012",
            common,
            f"{title} removed listing",
            f"https://www.alibaba.com/local-fixture/{digest}/012",
            "Shenzhen, Guangdong, CN",
            None,
            None,
            None,
            None,
            None,
            None,
            "removed",
            None,
            {**_metadata("listing_disappeared", country_code), "listing_status": "disappeared"},
        ),
        AlibabaListing(
            f"local-{digest}-013",
            "Alibaba Local Fixture Components",
            f"{title} availability unknown listing",
            f"https://www.alibaba.com/local-fixture/{digest}/013",
            "Zhejiang, CN",
            query[:120] or None,
            16.0,
            "USD",
            60.0,
            "units",
            "20 days",
            None,
            "provider_claimed",
            _metadata("missing_availability", country_code),
        ),
    ]
    if fixture_case:
        selected = [row for row in values if row.metadata.get("fixture_case") == fixture_case]
        if selected:
            values = selected
    return values[: max(1, min(limit, 20))]


def retrieved_at() -> datetime:
    return datetime.now(UTC)
