"""Typed Flipkart marketplace boundary.

The live Flipkart contract is intentionally not assumed here.  The adapter is
transport-injected and local development uses the deterministic fake transport.
All vendor-specific details stay behind this module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlsplit


class FlipkartMarketplace(StrEnum):
    INDIA = "flipkart-IN"


@dataclass(frozen=True)
class FlipkartMarket:
    marketplace_id: str
    country_code: str
    currency: str
    locale: str
    endpoint_host: str


FLIPKART_MARKETPLACE = FlipkartMarket(
    marketplace_id=FlipkartMarketplace.INDIA,
    country_code="IN",
    currency="INR",
    locale="en-IN",
    endpoint_host="seller.flipkart.com",
)


class FlipkartIssueCode(StrEnum):
    INVALID_ATTRIBUTE = "invalid_attribute"
    MISSING_ATTRIBUTE = "missing_attribute"
    SKU_CONFLICT = "sku_conflict"
    AUTHORIZATION = "authorization"
    THROTTLED = "throttled"
    IDENTIFIER_ERROR = "product_identifier_error"
    POLICY_REJECTION = "policy_rejection"
    TRANSIENT = "transient_service"
    AMBIGUOUS = "ambiguous_result"


@dataclass(frozen=True)
class FlipkartIssue:
    code: FlipkartIssueCode
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    field: str | None = None


@dataclass(frozen=True)
class FlipkartOperationResult:
    status: str
    remote_id: str | None = None
    remote_status: str | None = None
    issues: tuple[FlipkartIssue, ...] = ()
    retryable: bool = False
    retry_after_seconds: int | None = None
    ambiguous: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FlipkartAuthState:
    """Request-scoped auth state; credentials never cross this boundary."""

    seller_id: str
    access_token: str
    expires_at: int | None = None


class FlipkartAuthStrategy(Protocol):
    def resolve(self, seller_id: str) -> FlipkartAuthState: ...


class FakeFlipkartAuthStrategy:
    def resolve(self, seller_id: str) -> FlipkartAuthState:
        return FlipkartAuthState(seller_id=seller_id, access_token="fake-request-token")


class FlipkartTransport(Protocol):
    def validate_account(
        self, *, seller_id: str, marketplace_id: str
    ) -> FlipkartOperationResult: ...
    def categories(
        self, *, search: str | None, offset: int, limit: int
    ) -> list[dict[str, Any]]: ...
    def attributes(self, *, category_id: str) -> list[dict[str, Any]]: ...
    def submit_listing(
        self,
        *,
        seller_id: str,
        marketplace_id: str,
        sku: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> FlipkartOperationResult: ...
    def update_listing(
        self, *, remote_id: str, title: str | None, sku: str | None, idempotency_key: str
    ) -> FlipkartOperationResult: ...
    def update_price(
        self, *, remote_id: str, payload: dict[str, Any], idempotency_key: str
    ) -> FlipkartOperationResult: ...
    def listing(self, remote_id: str) -> FlipkartOperationResult: ...
    def reconcile_listing(self, remote_id: str) -> FlipkartOperationResult: ...
    def inventory(self, *, seller_id: str, sku: str) -> FlipkartOperationResult: ...
    def update_inventory(
        self, *, seller_id: str, sku: str, quantity: int, idempotency_key: str
    ) -> FlipkartOperationResult: ...
    def orders(self, *, seller_id: str) -> list[dict[str, Any]]: ...
    def financial_events(self, *, seller_id: str) -> list[dict[str, Any]]: ...
    def returns(self, *, seller_id: str) -> list[dict[str, Any]]: ...
    def cancellations(self, *, seller_id: str) -> list[dict[str, Any]]: ...
    def refunds(self, *, seller_id: str) -> list[dict[str, Any]]: ...
    def lookup_by_sku(self, *, seller_id: str, sku: str) -> FlipkartOperationResult: ...


_REMOTE_LISTINGS: dict[str, dict[str, Any]] = {}
_IDEMPOTENCY: dict[str, str] = {}
_INVENTORY: dict[str, int] = {}
_THROTTLE_ATTEMPTS: dict[str, int] = {}


def fake_flipkart_listing_count() -> int:
    return len(_REMOTE_LISTINGS)


def reset_fake_flipkart_state() -> None:
    _REMOTE_LISTINGS.clear()
    _IDEMPOTENCY.clear()
    _INVENTORY.clear()
    _THROTTLE_ATTEMPTS.clear()


class FlipkartEndpointPolicy:
    ALLOWED_HOSTS = frozenset({"seller.flipkart.com", "api.flipkart.com"})

    @classmethod
    def validate(cls, url: str, *, expected_host: str | None = None) -> str:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Flipkart endpoint must use HTTPS without URL credentials.")
        if parsed.hostname not in cls.ALLOWED_HOSTS:
            raise ValueError("Flipkart endpoint host is not allowlisted.")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Flipkart endpoint paths are connector-managed.")
        if expected_host and parsed.hostname != expected_host:
            raise ValueError("Flipkart endpoint does not match the configured host.")
        return parsed.hostname


class FlipkartMediaPolicy:
    ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
    MIN_DIMENSION = 500
    MAX_BYTES = 10 * 1024 * 1024

    @classmethod
    def validate(cls, media: list[dict[str, Any]]) -> list[FlipkartIssue]:
        if not media:
            return [
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE,
                    "At least one main image is required.",
                    field="main_image",
                )
            ]
        issues: list[FlipkartIssue] = []
        ordered = sorted(media, key=lambda value: int(value.get("position", 0)))
        if int(ordered[0].get("position", 0)) != 0:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.INVALID_ATTRIBUTE,
                    "The main image must be first.",
                    field="media",
                )
            )
        for item in ordered:
            if str(item.get("mime_type", "")) not in cls.ALLOWED_MIME_TYPES:
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.INVALID_ATTRIBUTE,
                        "Image MIME type is not supported.",
                        field="media",
                    )
                )
            if (
                int(item.get("width", 0)) < cls.MIN_DIMENSION
                or int(item.get("height", 0)) < cls.MIN_DIMENSION
            ):
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.INVALID_ATTRIBUTE,
                        "Image dimensions are below the Flipkart minimum.",
                        field="media",
                    )
                )
            if int(item.get("size_bytes", 0)) > cls.MAX_BYTES:
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.INVALID_ATTRIBUTE,
                        "Image exceeds the Flipkart size limit.",
                        field="media",
                    )
                )
            if not item.get("checksum_sha256"):
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.INVALID_ATTRIBUTE,
                        "Image checksum is required.",
                        field="media",
                    )
                )
        return issues


class FlipkartVariantPolicy:
    @classmethod
    def validate(cls, variants: list[dict[str, Any]]) -> list[FlipkartIssue]:
        if not variants:
            return [
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE,
                    "At least one variant is required.",
                    field="variants",
                )
            ]
        issues: list[FlipkartIssue] = []
        keys: set[str] = set()
        skus: set[str] = set()
        for item in variants:
            key = str(item.get("stable_variant_key", "")).strip()
            sku = str(item.get("sku", "")).strip()
            if not key or key in keys:
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.INVALID_ATTRIBUTE,
                        "Variant combinations must be unique.",
                        field="variants",
                    )
                )
            if not sku or sku in skus:
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.SKU_CONFLICT,
                        "Variant seller SKUs must be unique.",
                        field="sku",
                    )
                )
            if item.get("price") is None or float(item.get("price", 0)) < 0:
                issues.append(
                    FlipkartIssue(
                        FlipkartIssueCode.INVALID_ATTRIBUTE,
                        "Variant selling price is required.",
                        field="price",
                    )
                )
            keys.add(key)
            skus.add(sku)
        return issues


class FlipkartPricingPolicy:
    @classmethod
    def validate(cls, price: dict[str, Any], currency: str) -> list[FlipkartIssue]:
        issues: list[FlipkartIssue] = []
        selling = price.get("selling_price")
        if selling is None or float(selling) < 0:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.INVALID_ATTRIBUTE,
                    "Selling price is required.",
                    field="selling_price",
                )
            )
        if str(price.get("currency", "")) != currency:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.INVALID_ATTRIBUTE,
                    f"Price currency must be {currency}.",
                    field="currency",
                )
            )
        if (
            price.get("list_price") is not None
            and selling is not None
            and float(price["list_price"]) < float(selling)
        ):
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.INVALID_ATTRIBUTE,
                    "MRP cannot be lower than selling price.",
                    field="list_price",
                )
            )
        return issues


class FakeFlipkartTransport:
    """Network-free deterministic fake; no live Flipkart calls are possible."""

    def validate_account(self, *, seller_id: str, marketplace_id: str) -> FlipkartOperationResult:
        if seller_id.strip().startswith("invalid"):
            return FlipkartOperationResult(
                "rejected",
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.AUTHORIZATION, "Flipkart seller validation failed."
                    ),
                ),
            )
        return FlipkartOperationResult(
            "succeeded", remote_status="VALID", payload={"marketplace_id": marketplace_id}
        )

    def categories(self, *, search: str | None, offset: int, limit: int) -> list[dict[str, Any]]:
        values = [
            {"id": "fk-home", "name": "Home & Living", "parent_id": None},
            {"id": "fk-apparel", "name": "Apparel", "parent_id": None},
            {"id": "fk-electronics", "name": "Electronics", "parent_id": None},
        ]
        if search:
            values = [item for item in values if search.casefold() in str(item["name"]).casefold()]
        return values[offset : offset + min(limit, 100)]

    def attributes(self, *, category_id: str) -> list[dict[str, Any]]:
        return [
            {"key": "brand", "label": "Brand", "type": "string", "required": True},
            {
                "key": "color",
                "label": "Color",
                "type": "enum",
                "required": False,
                "options": ["Black", "White", "Blue"],
            },
            {
                "key": "country_of_origin",
                "label": "Country of origin",
                "type": "string",
                "required": True,
            },
        ]

    def submit_listing(
        self,
        *,
        seller_id: str,
        marketplace_id: str,
        sku: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> FlipkartOperationResult:
        if (
            idempotency_key.startswith("throttle-")
            and _THROTTLE_ATTEMPTS.get(idempotency_key, 0) == 0
        ):
            _THROTTLE_ATTEMPTS[idempotency_key] = 1
            return FlipkartOperationResult(
                "throttled",
                retryable=True,
                retry_after_seconds=2,
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.THROTTLED,
                        "Flipkart fake throttled this request.",
                        retryable=True,
                        retry_after_seconds=2,
                    ),
                ),
            )
        if sku in {str(value.get("sku")) for value in _REMOTE_LISTINGS.values()}:
            existing = next(value for value in _REMOTE_LISTINGS.values() if value.get("sku") == sku)
            return FlipkartOperationResult(
                "rejected",
                remote_id=str(existing["id"]),
                remote_status="REJECTED",
                issues=(
                    FlipkartIssue(FlipkartIssueCode.SKU_CONFLICT, "Seller SKU already exists."),
                ),
            )
        if idempotency_key in _IDEMPOTENCY:
            remote_id = _IDEMPOTENCY[idempotency_key]
            return FlipkartOperationResult(
                "accepted", remote_id=remote_id, remote_status="PROCESSING"
            )
        digest = hashlib.sha256(f"flipkart:{seller_id}:{idempotency_key}".encode()).hexdigest()[:12]
        remote_id = f"FK-LISTING-{digest}"
        _IDEMPOTENCY[idempotency_key] = remote_id
        _REMOTE_LISTINGS[remote_id] = {
            "id": remote_id,
            "sku": sku,
            "title": payload.get("title", ""),
            "status": "PROCESSING",
            "payload": payload,
            "seller_id": seller_id,
        }
        if idempotency_key.startswith("ambiguous-"):
            return FlipkartOperationResult(
                "unknown",
                remote_id=remote_id,
                remote_status="PROCESSING",
                ambiguous=True,
                retryable=True,
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.AMBIGUOUS,
                        "The remote result is unresolved.",
                        retryable=True,
                    ),
                ),
            )
        return FlipkartOperationResult("accepted", remote_id=remote_id, remote_status="PROCESSING")

    def update_listing(
        self, *, remote_id: str, title: str | None, sku: str | None, idempotency_key: str
    ) -> FlipkartOperationResult:
        value = _REMOTE_LISTINGS.get(remote_id)
        if value is None:
            return FlipkartOperationResult(
                "rejected",
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.IDENTIFIER_ERROR, "Flipkart listing was not found."
                    ),
                ),
            )
        if (
            idempotency_key.startswith("throttle-")
            and _THROTTLE_ATTEMPTS.get(idempotency_key, 0) == 0
        ):
            _THROTTLE_ATTEMPTS[idempotency_key] = 1
            return FlipkartOperationResult("throttled", retryable=True, retry_after_seconds=2)
        if title is not None:
            value["title"] = title
        if sku is not None:
            value["sku"] = sku
        if idempotency_key.startswith("ambiguous-"):
            return FlipkartOperationResult(
                "unknown", remote_id=remote_id, remote_status=str(value["status"]), ambiguous=True
            )
        return FlipkartOperationResult(
            "succeeded",
            remote_id=remote_id,
            remote_status=str(value["status"]),
            payload=dict(value),
        )

    def update_price(
        self, *, remote_id: str, payload: dict[str, Any], idempotency_key: str
    ) -> FlipkartOperationResult:
        if (
            idempotency_key.startswith("throttle-")
            and _THROTTLE_ATTEMPTS.get(idempotency_key, 0) == 0
        ):
            _THROTTLE_ATTEMPTS[idempotency_key] = 1
            return FlipkartOperationResult("throttled", retryable=True, retry_after_seconds=2)
        value = _REMOTE_LISTINGS.get(remote_id)
        if value is None:
            return FlipkartOperationResult(
                "rejected",
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.IDENTIFIER_ERROR, "Flipkart listing was not found."
                    ),
                ),
            )
        value["price"] = dict(payload)
        if idempotency_key.startswith("ambiguous-"):
            return FlipkartOperationResult(
                "unknown",
                remote_id=remote_id,
                remote_status=str(value["status"]),
                ambiguous=True,
                retryable=True,
                payload=dict(value),
            )
        return FlipkartOperationResult(
            "succeeded",
            remote_id=remote_id,
            remote_status=str(value["status"]),
            payload=dict(value),
        )

    def listing(self, remote_id: str) -> FlipkartOperationResult:
        value = _REMOTE_LISTINGS.get(remote_id)
        if value is None:
            return FlipkartOperationResult(
                "rejected",
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.IDENTIFIER_ERROR, "Flipkart listing was not found."
                    ),
                ),
            )
        return FlipkartOperationResult(
            "succeeded",
            remote_id=remote_id,
            remote_status=str(value["status"]),
            payload=dict(value),
        )

    def reconcile_listing(self, remote_id: str) -> FlipkartOperationResult:
        value = _REMOTE_LISTINGS.get(remote_id)
        if value is None:
            return FlipkartOperationResult(
                "rejected",
                issues=(
                    FlipkartIssue(
                        FlipkartIssueCode.IDENTIFIER_ERROR, "Flipkart listing was not found."
                    ),
                ),
            )
        if value["status"] == "PROCESSING":
            value["status"] = "ACTIVE"
        return FlipkartOperationResult(
            "succeeded",
            remote_id=remote_id,
            remote_status=str(value["status"]),
            payload=dict(value),
        )

    def lookup_by_sku(self, *, seller_id: str, sku: str) -> FlipkartOperationResult:
        for remote_id, value in _REMOTE_LISTINGS.items():
            if value.get("seller_id") == seller_id and value.get("sku") == sku:
                return self.listing(remote_id)
        return FlipkartOperationResult(
            "rejected",
            issues=(
                FlipkartIssue(
                    FlipkartIssueCode.IDENTIFIER_ERROR, "Flipkart listing was not found."
                ),
            ),
        )

    def inventory(self, *, seller_id: str, sku: str) -> FlipkartOperationResult:
        return FlipkartOperationResult(
            "succeeded", payload={"sku": sku, "quantity": _INVENTORY.get(sku, 10)}
        )

    def update_inventory(
        self, *, seller_id: str, sku: str, quantity: int, idempotency_key: str
    ) -> FlipkartOperationResult:
        if (
            idempotency_key.startswith("throttle-")
            and _THROTTLE_ATTEMPTS.get(idempotency_key, 0) == 0
        ):
            _THROTTLE_ATTEMPTS[idempotency_key] = 1
            return FlipkartOperationResult("throttled", retryable=True, retry_after_seconds=2)
        _INVENTORY[sku] = quantity
        if idempotency_key.startswith("ambiguous-"):
            return FlipkartOperationResult(
                "unknown",
                ambiguous=True,
                retryable=True,
                payload={"sku": sku, "quantity": quantity},
            )
        return FlipkartOperationResult("succeeded", payload={"sku": sku, "quantity": quantity})

    def orders(self, *, seller_id: str) -> list[dict[str, Any]]:
        return [
            {
                "remote_id": "FK-ORDER-001",
                "status": "CONFIRMED",
                "payment_status": "PAID",
                "fulfilment_status": "PENDING",
                "fulfilment_id": "FK-FULFILMENT-001",
                "carrier": "FakeExpress",
                "tracking_reference": "FK-TRACK-001",
                "currency": "INR",
                "total": "1250.00",
                "items": [{"sku": "FK-DEMO-SKU", "quantity": 1, "unit_price": "1250.00"}],
            }
        ]

    def financial_events(self, *, seller_id: str) -> list[dict[str, Any]]:
        return [
            {
                "settlement_id": "FK-SETTLEMENT-001",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "gross": "1250.00",
                "fees": [{"type": "commission", "amount": "125.00"}],
                "refunds": "0.00",
                "withholding": "0.00",
                "adjustments": "0.00",
                "net": "1125.00",
                "currency": "INR",
            }
        ]

    def returns(self, *, seller_id: str) -> list[dict[str, Any]]:
        return [
            {
                "reference": "FK-RETURN-001",
                "order_id": "FK-ORDER-001",
                "status": "REQUESTED",
                "reason": "customer_return",
                "quantity": 1,
                "requested_at": "2026-01-15T00:00:00Z",
                "refund_amount": "0.00",
            }
        ]

    def cancellations(self, *, seller_id: str) -> list[dict[str, Any]]:
        return [
            {
                "reference": "FK-CANCEL-001",
                "order_id": "FK-ORDER-001",
                "status": "REQUESTED",
                "reason": "buyer_request",
                "quantity": 1,
            }
        ]

    def refunds(self, *, seller_id: str) -> list[dict[str, Any]]:
        return [
            {
                "reference": "FK-REFUND-001",
                "order_id": "FK-ORDER-001",
                "reason": "customer_return",
                "status": "REPORTED",
                "amount": "0.00",
                "currency": "INR",
            }
        ]


@dataclass
class FlipkartCommerceConnector:
    seller_id: str
    marketplace: FlipkartMarket = FLIPKART_MARKETPLACE
    transport: FlipkartTransport = field(default_factory=FakeFlipkartTransport)
    auth: FlipkartAuthStrategy = field(default_factory=FakeFlipkartAuthStrategy)

    def validate_account(self, seller_account_id: str) -> dict[str, object]:
        result = self.transport.validate_account(
            seller_id=seller_account_id, marketplace_id=self.marketplace.marketplace_id
        )
        return {
            "valid": result.status == "succeeded",
            "message": (
                result.issues[0].message
                if result.issues
                else "Flipkart account validated by fake transport."
            ),
        }

    def discover_categories(
        self, *, search: str | None = None, offset: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self.transport.categories(search=search, offset=offset, limit=limit)

    def category_attributes(self, category_id: str) -> list[dict[str, Any]]:
        return self.transport.attributes(category_id=category_id)

    def preview(
        self,
        *,
        title: str,
        sku: str | None,
        category_id: str | None,
        attributes: dict[str, Any],
        approved: bool,
        media: list[dict[str, Any]] | None = None,
        variants: list[dict[str, Any]] | None = None,
        price: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        issues: list[FlipkartIssue] = []
        if not approved:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.POLICY_REJECTION,
                    "An approved Flipkart content Artifact is required.",
                    field="artifact",
                )
            )
        if not category_id:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE,
                    "Select a Flipkart category.",
                    field="category",
                )
            )
        if not sku:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE,
                    "Seller SKU is required.",
                    field="seller_sku",
                )
            )
        if not media:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE,
                    "At least one main image is required.",
                    field="media",
                )
            )
        else:
            issues.extend(FlipkartMediaPolicy.validate(media))
        if not variants:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE,
                    "At least one variant is required.",
                    field="variants",
                )
            )
        else:
            issues.extend(FlipkartVariantPolicy.validate(variants))
        if not price:
            issues.append(
                FlipkartIssue(
                    FlipkartIssueCode.MISSING_ATTRIBUTE, "Selling price is required.", field="price"
                )
            )
        else:
            issues.extend(FlipkartPricingPolicy.validate(price, self.marketplace.currency))
        return {
            "ready": not issues,
            "blocking_issues": [
                {"code": item.code, "message": item.message, "field": item.field} for item in issues
            ],
            "warnings": [],
            "informational": [
                {
                    "code": "inventory_policy",
                    "message": (
                        "Inventory changes are explicit and are not continuously synchronized."
                    ),
                }
            ],
            "category_id": category_id,
            "title": title,
            "sku": sku,
            "attributes": attributes,
            "currency": self.marketplace.currency,
        }

    def submit(
        self, *, sku: str, payload: dict[str, Any], idempotency_key: str
    ) -> FlipkartOperationResult:
        return self.transport.submit_listing(
            seller_id=self.seller_id,
            marketplace_id=self.marketplace.marketplace_id,
            sku=sku,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    def preview_listing(self, *, title: str, sku: str | None) -> dict[str, object]:
        return {"title": title.strip(), "sku": sku, "ready": bool(title.strip() and sku)}

    def create_listing(
        self, *, title: str, sku: str | None, idempotency_key: str
    ) -> dict[str, object]:
        result = self.submit(
            sku=sku or "UNASSIGNED", payload={"title": title}, idempotency_key=idempotency_key
        )
        return {
            "remote_id": result.remote_id,
            "remote_sku": sku or "UNASSIGNED",
            "status": result.remote_status or result.status,
            "url": None,
        }

    def update_listing(
        self,
        *,
        remote_id: str,
        title: str | None,
        sku: str | None,
        idempotency_key: str = "compat-listing-update",
    ) -> dict[str, object]:
        result = self.transport.update_listing(
            remote_id=remote_id, title=title, sku=sku, idempotency_key=idempotency_key
        )
        return {
            "remote_id": remote_id,
            "title": title or result.payload.get("title"),
            "remote_sku": sku or result.payload.get("sku"),
            "status": result.remote_status or result.status,
        }

    def update_price(
        self, *, remote_id: str, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, object]:
        result = self.transport.update_price(
            remote_id=remote_id, payload=payload, idempotency_key=idempotency_key
        )
        return {
            "remote_id": remote_id,
            "status": result.remote_status or result.status,
            "operation_status": result.status,
            "retryable": result.retryable,
            "retry_after_seconds": result.retry_after_seconds,
            "ambiguous": result.ambiguous,
            "message": result.issues[0].message if result.issues else None,
            **result.payload,
        }

    def get_listing(self, remote_id: str) -> dict[str, object]:
        result = self.transport.listing(remote_id)
        return {
            "remote_id": remote_id,
            "status": result.remote_status or "UNKNOWN",
            **result.payload,
        }

    def reconcile_listing(self, remote_id: str) -> dict[str, Any]:
        result = self.transport.reconcile_listing(remote_id)
        return {
            "status": result.remote_status or "UNKNOWN",
            "remote_id": result.remote_id,
            "payload": result.payload,
        }

    def get_inventory(self, sku: str) -> dict[str, Any]:
        result = self.transport.inventory(seller_id=self.seller_id, sku=sku)
        return dict(result.payload)

    def update_inventory(
        self, sku: str, quantity: int, idempotency_key: str = "compat-inventory"
    ) -> dict[str, Any]:
        result = self.transport.update_inventory(
            seller_id=self.seller_id, sku=sku, quantity=quantity, idempotency_key=idempotency_key
        )
        return {
            **result.payload,
            "operation_status": result.status,
            "retryable": result.retryable,
            "retry_after_seconds": result.retry_after_seconds,
            "ambiguous": result.ambiguous,
            "message": result.issues[0].message if result.issues else None,
        }

    def get_orders(self) -> list[dict[str, Any]]:
        return self.transport.orders(seller_id=self.seller_id)

    def get_fees(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "commission",
                "amount": item["fees"][0]["amount"],
                "currency": item["currency"],
            }
            for item in self.transport.financial_events(seller_id=self.seller_id)
        ]

    def get_settlements(self) -> list[dict[str, Any]]:
        return self.transport.financial_events(seller_id=self.seller_id)

    def get_financial_events(self) -> list[dict[str, Any]]:
        return self.transport.financial_events(seller_id=self.seller_id)

    def get_returns(self) -> list[dict[str, Any]]:
        return self.transport.returns(seller_id=self.seller_id)

    def get_cancellations(self) -> list[dict[str, Any]]:
        return self.transport.cancellations(seller_id=self.seller_id)

    def get_refunds(self) -> list[dict[str, Any]]:
        return self.transport.refunds(seller_id=self.seller_id)
