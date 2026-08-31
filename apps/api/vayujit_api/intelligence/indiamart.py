"""Provider-neutral IndiaMART read-only adapter.

No official IndiaMART endpoint is configured in this repository.  The local
fixture is deterministic and deliberately exposes only normalized fields.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from vayujit_api.core.config import Settings


@dataclass(frozen=True)
class IndiaMartListing:
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
        or settings.indiamart_kill_switch
    ):
        status = "KILL_SWITCHED"
    elif settings.indiamart_mode == "DISABLED" or not settings.indiamart_enabled:
        status = "DISABLED"
    elif settings.indiamart_mode == "LOCAL_FIXTURE":
        status = "READY"
    else:
        status = "NOT_CONFIGURED"
    return {
        "provider": "INDIAMART",
        "mode": settings.indiamart_mode,
        "status": status,
        "credentials_configured": bool(settings.indiamart_token_ref),
        "live_validation": "NOT_RUN",
        "read_only": True,
        "network_call": False,
    }


def discover_local(*, query: str, limit: int, country_code: str | None) -> list[IndiaMartListing]:
    digest = hashlib.sha256(query.casefold().encode()).hexdigest()[:12]
    fixtures = [
        IndiaMartListing(
            provider_result_id=f"local-{digest}-001",
            supplier_name="IndiaMART Local Fixture Industries",
            listing_name=f"{query.title()} supplier listing",
            source_url=f"https://www.indiamart.com/local-fixture/{digest}/001",
            location="Pune, Maharashtra, IN",
            category=query[:120] or None,
            price=420.0,
            currency="INR",
            moq=50.0,
            moq_unit="units",
            lead_time="14 days",
            availability="in_stock",
            verification_claim="provider_claimed",
            metadata={"fixture": True, "country_filter": country_code or "UNKNOWN"},
        ),
        IndiaMartListing(
            provider_result_id=f"local-{digest}-002",
            supplier_name="IndiaMART Local Fixture Components",
            listing_name=f"{query.title()} components listing",
            source_url=f"https://www.indiamart.com/local-fixture/{digest}/002",
            location="Ahmedabad, Gujarat, IN",
            category=query[:120] or None,
            price=None,
            currency=None,
            moq=None,
            moq_unit=None,
            lead_time=None,
            availability="unknown",
            verification_claim=None,
            metadata={"fixture": True, "country_filter": country_code or "UNKNOWN"},
        ),
    ]
    return fixtures[: max(1, min(limit, 20))]


def retrieved_at() -> datetime:
    return datetime.now(UTC)
