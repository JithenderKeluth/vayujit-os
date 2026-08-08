"""Amazon Selling Partner API boundary.

The production adapter is deliberately transport-injected.  Local development
and tests use :class:`FakeAmazonSPAPITransport`; no network call is possible
unless an operator explicitly supplies a transport implementation.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, cast
from urllib.parse import urlsplit


class AmazonMarketplaceId(StrEnum):
    INDIA = "A21TJRUUN4KGV"
    UNITED_STATES = "ATVPDKIKX0DER"
    UNITED_KINGDOM = "A1F83G8C2ARO7P"


@dataclass(frozen=True)
class AmazonMarketplace:
    marketplace_id: str
    country_code: str
    currency: str
    locale: str
    endpoint_region: str
    endpoint_host: str


AMAZON_MARKETPLACES: dict[str, AmazonMarketplace] = {
    "IN": AmazonMarketplace(
        marketplace_id=AmazonMarketplaceId.INDIA,
        country_code="IN",
        currency="INR",
        locale="en-IN",
        endpoint_region="eu-west-1",
        endpoint_host="sellingpartnerapi-eu.amazon.com",
    ),
    "US": AmazonMarketplace(
        marketplace_id=AmazonMarketplaceId.UNITED_STATES,
        country_code="US",
        currency="USD",
        locale="en-US",
        endpoint_region="us-east-1",
        endpoint_host="sellingpartnerapi-na.amazon.com",
    ),
    "GB": AmazonMarketplace(
        marketplace_id=AmazonMarketplaceId.UNITED_KINGDOM,
        country_code="GB",
        currency="GBP",
        locale="en-GB",
        endpoint_region="eu-west-1",
        endpoint_host="sellingpartnerapi-eu.amazon.com",
    ),
}


class AmazonIssueCode(StrEnum):
    INVALID_ATTRIBUTE = "invalid_attribute"
    MISSING_ATTRIBUTE = "missing_attribute"
    SKU_CONFLICT = "sku_conflict"
    AUTHORIZATION = "authorization"
    THROTTLED = "throttled"
    IDENTIFIER_ERROR = "product_identifier_error"
    RESTRICTED_CATEGORY = "restricted_category"
    POLICY_REJECTION = "policy_rejection"
    TRANSIENT = "transient_service"
    AMBIGUOUS = "ambiguous_result"


@dataclass(frozen=True)
class AmazonIssue:
    code: AmazonIssueCode
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    field: str | None = None


@dataclass(frozen=True)
class AmazonOperationResult:
    status: str
    remote_id: str | None = None
    remote_status: str | None = None
    issues: tuple[AmazonIssue, ...] = ()
    retryable: bool = False
    retry_after_seconds: int | None = None
    ambiguous: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


class AmazonTransport(Protocol):
    def validate_account(self, *, seller_id: str, marketplace_id: str) -> AmazonOperationResult: ...
    def marketplaces(self) -> list[AmazonMarketplace]: ...
    def product_types(
        self, *, marketplace_id: str, search: str | None, offset: int, limit: int
    ) -> list[dict[str, Any]]: ...
    def submit_listing(
        self,
        *,
        seller_id: str,
        marketplace_id: str,
        sku: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> AmazonOperationResult: ...
    def listing(self, remote_id: str) -> AmazonOperationResult: ...
    def reconcile_listing(self, remote_id: str) -> AmazonOperationResult: ...
    def inventory(
        self, *, seller_id: str, marketplace_id: str, sku: str
    ) -> AmazonOperationResult: ...
    def update_inventory(
        self, *, seller_id: str, marketplace_id: str, sku: str, quantity: int, idempotency_key: str
    ) -> AmazonOperationResult: ...
    def orders(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]: ...
    def financial_events(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]: ...
    def process(self, remote_id: str) -> AmazonOperationResult: ...


class AmazonEndpointPolicy:
    """Allowlist and validate outbound SP-API endpoints."""

    ALLOWED_HOSTS = frozenset(
        {
            "sellingpartnerapi-eu.amazon.com",
            "sellingpartnerapi-na.amazon.com",
            "sellingpartnerapi-fe.amazon.com",
        }
    )

    @classmethod
    def validate(cls, url: str, *, expected_host: str | None = None) -> str:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Amazon endpoint must use HTTPS without URL credentials.")
        if parsed.hostname not in cls.ALLOWED_HOSTS:
            raise ValueError("Amazon endpoint host is not allowlisted.")
        if expected_host and parsed.hostname != expected_host:
            raise ValueError("Amazon endpoint does not match the configured region.")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Amazon endpoint paths are connector-managed.")
        return parsed.hostname


class AmazonRateLimiter:
    def __init__(self, *, min_interval_seconds: float = 0.0) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last: dict[str, float] = {}

    def delay_for(self, operation: str) -> float:
        remaining = self.min_interval_seconds - (time.monotonic() - self._last.get(operation, 0.0))
        if remaining > 0:
            return remaining
        self._last[operation] = time.monotonic()
        return 0.0


_FAKE_LISTINGS: dict[str, dict[str, Any]] = {}
_FAKE_IDEMPOTENCY: dict[str, str] = {}


class FakeAmazonSPAPITransport:
    """Deterministic fake boundary with processing, throttling, and failures."""

    def __init__(self, *, scenario: str = "success") -> None:
        self.scenario = scenario

    def validate_account(self, *, seller_id: str, marketplace_id: str) -> AmazonOperationResult:
        if not seller_id or not marketplace_id:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(
                        AmazonIssueCode.AUTHORIZATION, "Amazon seller configuration is incomplete."
                    ),
                ),
            )
        return AmazonOperationResult(
            "succeeded",
            remote_status="valid",
            payload={"seller_id": seller_id, "marketplace_id": marketplace_id},
        )

    def marketplaces(self) -> list[AmazonMarketplace]:
        return list(AMAZON_MARKETPLACES.values())

    def product_types(
        self, *, marketplace_id: str, search: str | None, offset: int, limit: int
    ) -> list[dict[str, Any]]:
        values = [
            {"id": "PRODUCT", "name": "General Product", "marketplace_ids": [marketplace_id]},
            {"id": "HOME", "name": "Home & Living", "marketplace_ids": [marketplace_id]},
            {"id": "APPAREL", "name": "Apparel", "marketplace_ids": [marketplace_id]},
        ]
        if search:
            values = [
                value
                for value in values
                if search.casefold() in cast(str, value["name"]).casefold()
            ]
        return values[offset : offset + limit]

    def submit_listing(
        self,
        *,
        seller_id: str,
        marketplace_id: str,
        sku: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> AmazonOperationResult:
        if self.scenario == "throttle":
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(
                        AmazonIssueCode.THROTTLED,
                        "Amazon temporarily throttled this operation.",
                        True,
                        2,
                    ),
                ),
                retryable=True,
                retry_after_seconds=2,
            )
        if self.scenario == "ambiguous":
            return AmazonOperationResult(
                "ambiguous",
                ambiguous=True,
                issues=(
                    AmazonIssue(
                        AmazonIssueCode.AMBIGUOUS,
                        "Amazon accepted an indeterminate request result.",
                        True,
                    ),
                ),
                retryable=True,
            )
        if self.scenario == "reject":
            return AmazonOperationResult(
                "rejected",
                remote_status="REJECTED",
                issues=(
                    AmazonIssue(
                        AmazonIssueCode.POLICY_REJECTION,
                        "Amazon rejected the listing for policy review.",
                    ),
                ),
            )
        if not payload.get("product_type"):
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(
                        AmazonIssueCode.MISSING_ATTRIBUTE,
                        "Amazon product type is required.",
                        field="product_type",
                    ),
                ),
            )
        existing = _FAKE_IDEMPOTENCY.get(idempotency_key)
        if existing:
            return AmazonOperationResult("accepted", remote_id=existing, remote_status="PROCESSING")
        digest = hashlib.sha256(f"{seller_id}:{marketplace_id}:{sku}".encode()).hexdigest()[:12]
        remote_id = f"FAKE-AMZ-{digest.upper()}"
        _FAKE_IDEMPOTENCY[idempotency_key] = remote_id
        _FAKE_LISTINGS[remote_id] = {
            "sku": sku,
            "status": "PROCESSING",
            "payload": payload,
            "quantity": 0,
            "polls": 0,
        }
        return AmazonOperationResult("accepted", remote_id=remote_id, remote_status="PROCESSING")

    def listing(self, remote_id: str) -> AmazonOperationResult:
        value = _FAKE_LISTINGS.get(remote_id)
        if value is None:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        return AmazonOperationResult(
            "succeeded",
            remote_id=remote_id,
            remote_status=value["status"],
            payload={"sku": value["sku"], "title": value["payload"].get("title", "")},
        )

    def reconcile_listing(self, remote_id: str) -> AmazonOperationResult:
        value = _FAKE_LISTINGS.get(remote_id)
        if value is None:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        value["polls"] += 1
        if value["status"] == "PROCESSING" and value["polls"] >= 1:
            value["status"] = "ACTIVE"
        return self.listing(remote_id)

    def process(self, remote_id: str) -> AmazonOperationResult:
        return self.reconcile_listing(remote_id)

    def inventory(self, *, seller_id: str, marketplace_id: str, sku: str) -> AmazonOperationResult:
        for value in _FAKE_LISTINGS.values():
            if value["sku"] == sku:
                return AmazonOperationResult(
                    "succeeded", payload={"sku": sku, "quantity": value["quantity"]}
                )
        return AmazonOperationResult("succeeded", payload={"sku": sku, "quantity": None})

    def update_inventory(
        self, *, seller_id: str, marketplace_id: str, sku: str, quantity: int, idempotency_key: str
    ) -> AmazonOperationResult:
        for value in _FAKE_LISTINGS.values():
            if value["sku"] == sku:
                value["quantity"] = quantity
        return AmazonOperationResult("succeeded", payload={"sku": sku, "quantity": quantity})

    def orders(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]:
        return [
            {
                "order_id": f"FAKE-AMZ-ORDER-{marketplace_id[-4:]}",
                "status": "Unshipped",
                "fulfilment_channel": "MFN",
                "total": "1250.00",
                "currency": "INR",
            }
        ]

    def financial_events(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]:
        return [
            {
                "event_id": f"FAKE-AMZ-FIN-{marketplace_id[-4:]}",
                "type": "Commission",
                "amount": "125.00",
                "currency": "INR",
            }
        ]


@dataclass
class AmazonCommerceConnector:
    seller_id: str
    marketplace: AmazonMarketplace
    transport: AmazonTransport = field(default_factory=FakeAmazonSPAPITransport)
    limiter: AmazonRateLimiter = field(default_factory=AmazonRateLimiter)

    def validate_account(self, seller_account_id: str) -> dict[str, object]:
        result = self.transport.validate_account(
            seller_id=seller_account_id, marketplace_id=self.marketplace.marketplace_id
        )
        return {
            "valid": result.status == "succeeded",
            "message": (
                result.issues[0].message
                if result.issues
                else "Amazon account validated by the configured transport."
            ),
        }

    def discover_marketplaces(self) -> list[AmazonMarketplace]:
        return self.transport.marketplaces()

    def discover_categories(self) -> list[dict[str, object]]:
        return [
            {
                "remote_id": str(item["id"]),
                "name": str(item["name"]),
                "parent_remote_id": None,
            }
            for item in self.discover_product_types()
        ]

    def preview_listing(self, *, title: str, sku: str | None) -> dict[str, object]:
        return {
            "title": title.strip(),
            "sku": sku,
            "ready": bool(title.strip() and sku),
        }

    def discover_product_types(
        self, *, search: str | None = None, offset: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self.transport.product_types(
            marketplace_id=self.marketplace.marketplace_id,
            search=search,
            offset=offset,
            limit=min(limit, 100),
        )

    def preview(
        self,
        *,
        title: str,
        sku: str | None,
        product_type: str | None,
        attributes: dict[str, Any],
        approved: bool,
        media_count: int = 0,
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        if not approved:
            issues.append(
                {
                    "code": "approval_required",
                    "message": "An approved Amazon content Artifact is required.",
                }
            )
        if not product_type:
            issues.append(
                {
                    "code": "missing_attribute",
                    "field": "product_type",
                    "message": "Select an Amazon product type.",
                }
            )
        if not sku:
            issues.append(
                {
                    "code": "missing_attribute",
                    "field": "seller_sku",
                    "message": "Seller SKU is required.",
                }
            )
        if media_count < 1:
            issues.append(
                {
                    "code": "missing_media",
                    "message": "At least one Amazon-compatible image is required.",
                }
            )
        return {
            "ready": not issues,
            "blocking_issues": issues,
            "warnings": [],
            "marketplace_id": self.marketplace.marketplace_id,
            "product_type": product_type,
            "title": title,
            "sku": sku,
            "attributes": attributes,
        }

    def submit(
        self, *, sku: str, payload: dict[str, Any], idempotency_key: str
    ) -> AmazonOperationResult:
        self.limiter.delay_for("listing_submit")
        return self.transport.submit_listing(
            seller_id=self.seller_id,
            marketplace_id=self.marketplace.marketplace_id,
            sku=sku,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    def create_listing(
        self, *, title: str, sku: str | None, idempotency_key: str
    ) -> dict[str, object]:
        result = self.submit(
            sku=sku or "UNASSIGNED",
            payload={"title": title, "product_type": "PRODUCT"},
            idempotency_key=idempotency_key,
        )
        return {
            "remote_id": result.remote_id,
            "remote_sku": sku or "UNASSIGNED",
            "status": "submitting",
            "url": None,
        }

    def update_listing(
        self, *, remote_id: str, title: str | None, sku: str | None
    ) -> dict[str, object]:
        result = self.transport.listing(remote_id)
        return {
            "remote_id": remote_id,
            "title": title,
            "remote_sku": sku,
            "status": result.remote_status or "unknown",
        }

    def get_listing(self, remote_id: str) -> dict[str, object]:
        result = self.transport.listing(remote_id)
        return {
            "remote_id": remote_id,
            "status": result.remote_status or "unknown",
            **result.payload,
        }

    def reconcile_listing(self, remote_id: str) -> dict[str, object]:
        result = self.transport.reconcile_listing(remote_id)
        return {
            "remote_id": remote_id,
            "status": result.remote_status or "unknown",
            **result.payload,
        }

    def get_inventory(self, remote_id: str) -> dict[str, object]:
        return self.transport.inventory(
            seller_id=self.seller_id, marketplace_id=self.marketplace.marketplace_id, sku=remote_id
        ).payload

    def update_inventory(self, remote_id: str, quantity: int) -> dict[str, object]:
        return self.transport.update_inventory(
            seller_id=self.seller_id,
            marketplace_id=self.marketplace.marketplace_id,
            sku=remote_id,
            quantity=quantity,
            idempotency_key=f"inventory:{self.seller_id}:{remote_id}:{quantity}",
        ).payload

    def get_orders(self) -> list[dict[str, object]]:
        return [
            {
                "remote_id": str(item["order_id"]),
                "status": {"unshipped": "confirmed", "shipped": "shipped"}.get(
                    str(item["status"]).lower(), "processing"
                ),
                "total": str(item["total"]),
            }
            for item in self.transport.orders(
                seller_id=self.seller_id, marketplace_id=self.marketplace.marketplace_id
            )
        ]

    def get_fees(self) -> list[dict[str, object]]:
        return [
            {
                "type": str(item["type"]).lower(),
                "amount": str(item["amount"]),
            }
            for item in self.transport.financial_events(
                seller_id=self.seller_id, marketplace_id=self.marketplace.marketplace_id
            )
        ]

    def get_settlements(self) -> list[dict[str, object]]:
        return [
            {
                "remote_id": f"fake-settlement-{self.marketplace.country_code.lower()}-001",
                "gross": "1250.00",
                "fees": "125.00",
                "net": "1125.00",
            }
        ]

    def process(self, remote_id: str) -> AmazonOperationResult:
        return self.transport.process(remote_id)


def amazon_marketplace(country_code: str) -> AmazonMarketplace:
    try:
        return AMAZON_MARKETPLACES[country_code.upper()]
    except KeyError as error:
        raise ValueError("Amazon marketplace region is unsupported.") from error
