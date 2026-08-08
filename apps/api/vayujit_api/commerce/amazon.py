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
    def product_type_attributes(
        self, *, marketplace_id: str, product_type: str
    ) -> list[dict[str, Any]]: ...
    def listing_by_sku(
        self, *, seller_id: str, marketplace_id: str, sku: str
    ) -> AmazonOperationResult: ...
    def submit_media(
        self, *, remote_id: str, media: list[dict[str, Any]], idempotency_key: str
    ) -> AmazonOperationResult: ...
    def submit_variants(
        self, *, remote_id: str, variants: list[dict[str, Any]], idempotency_key: str
    ) -> AmazonOperationResult: ...
    def price(self, *, remote_id: str) -> AmazonOperationResult: ...
    def update_price(
        self, *, remote_id: str, price: dict[str, Any], idempotency_key: str
    ) -> AmazonOperationResult: ...
    def returns(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]: ...
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


class AmazonMediaPolicy:
    ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
    MIN_DIMENSION = 500
    MAX_BYTES = 10 * 1024 * 1024

    @classmethod
    def validate(cls, media: list[dict[str, Any]]) -> list[AmazonIssue]:
        issues: list[AmazonIssue] = []
        if not media:
            return [
                AmazonIssue(
                    AmazonIssueCode.MISSING_ATTRIBUTE,
                    "At least one main image is required.",
                    field="main_image",
                )
            ]
        ordered = sorted(media, key=lambda item: int(item.get("position", 0)))
        if int(ordered[0].get("position", 0)) != 0:
            issues.append(
                AmazonIssue(
                    AmazonIssueCode.INVALID_ATTRIBUTE,
                    "The main image must be first.",
                    field="media",
                )
            )
        for item in ordered:
            if str(item.get("mime_type", "")) not in cls.ALLOWED_MIME_TYPES:
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.INVALID_ATTRIBUTE,
                        "Image MIME type is not supported.",
                        field="media",
                    )
                )
            if (
                int(item.get("width", 0)) < cls.MIN_DIMENSION
                or int(item.get("height", 0)) < cls.MIN_DIMENSION
            ):
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.INVALID_ATTRIBUTE,
                        "Image dimensions are below the Amazon minimum.",
                        field="media",
                    )
                )
            if int(item.get("size_bytes", 0)) > cls.MAX_BYTES:
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.INVALID_ATTRIBUTE,
                        "Image exceeds the Amazon size limit.",
                        field="media",
                    )
                )
            if not item.get("checksum_sha256"):
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.INVALID_ATTRIBUTE,
                        "Image checksum is required.",
                        field="media",
                    )
                )
        return issues


class AmazonVariantPolicy:
    @staticmethod
    def validate(variants: list[dict[str, Any]]) -> list[AmazonIssue]:
        issues: list[AmazonIssue] = []
        if not variants:
            return issues
        keys = [str(item.get("stable_variant_key", "")) for item in variants]
        skus = [str(item.get("sku", "")) for item in variants]
        combinations = [
            str(item.get("combination_key", item.get("stable_variant_key", "")))
            for item in variants
        ]
        if any(not key for key in keys):
            issues.append(
                AmazonIssue(
                    AmazonIssueCode.INVALID_ATTRIBUTE,
                    "Every variant needs a stable local key.",
                    field="variants",
                )
            )
        if len(keys) != len(set(keys)) or len(combinations) != len(set(combinations)):
            issues.append(
                AmazonIssue(
                    AmazonIssueCode.INVALID_ATTRIBUTE,
                    "Variant combinations must be unique.",
                    field="variants",
                )
            )
        if len(skus) != len(set(skus)) or any(not sku for sku in skus):
            issues.append(
                AmazonIssue(
                    AmazonIssueCode.SKU_CONFLICT,
                    "Seller SKUs must be unique and non-empty.",
                    field="sku",
                )
            )
        for item in variants:
            if not item.get("variation_theme"):
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.MISSING_ATTRIBUTE,
                        "Variation theme is required.",
                        field="variation_theme",
                    )
                )
            if item.get("price") is None and item.get("selling_price") is None:
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.MISSING_ATTRIBUTE,
                        "Variant price is required.",
                        field="price",
                    )
                )
            barcode = item.get("barcode")
            if (
                barcode is not None
                and barcode != ""
                and (not str(barcode).isdigit() or len(str(barcode)) not in {8, 12, 13, 14})
            ):
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.IDENTIFIER_ERROR,
                        "Variant barcode must be a valid GTIN.",
                        field="barcode",
                    )
                )
        return issues


class AmazonPricingPolicy:
    @staticmethod
    def validate(price: dict[str, Any], currency: str) -> list[AmazonIssue]:
        issues: list[AmazonIssue] = []
        selling = price.get("selling_price")
        try:
            selling_value = float(str(selling))
        except (TypeError, ValueError):
            selling_value = -1
        if selling_value < 0:
            issues.append(
                AmazonIssue(
                    AmazonIssueCode.INVALID_ATTRIBUTE,
                    "Selling price must be non-negative.",
                    field="selling_price",
                )
            )
        if price.get("list_price") is not None:
            try:
                if float(price["list_price"]) < selling_value:
                    issues.append(
                        AmazonIssue(
                            AmazonIssueCode.INVALID_ATTRIBUTE,
                            "List price cannot be below selling price.",
                            field="list_price",
                        )
                    )
            except (TypeError, ValueError):
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.INVALID_ATTRIBUTE,
                        "List price must be numeric.",
                        field="list_price",
                    )
                )
        if price.get("sale_price") is not None:
            try:
                if float(price["sale_price"]) > selling_value:
                    issues.append(
                        AmazonIssue(
                            AmazonIssueCode.INVALID_ATTRIBUTE,
                            "Sale price cannot exceed selling price.",
                            field="sale_price",
                        )
                    )
            except (TypeError, ValueError):
                issues.append(
                    AmazonIssue(
                        AmazonIssueCode.INVALID_ATTRIBUTE,
                        "Sale price must be numeric.",
                        field="sale_price",
                    )
                )
        if currency != str(price.get("currency", currency)):
            issues.append(
                AmazonIssue(
                    AmazonIssueCode.INVALID_ATTRIBUTE,
                    "Price currency must match the marketplace.",
                    field="currency",
                )
            )
        return issues


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
_FAKE_MEDIA: dict[str, list[dict[str, Any]]] = {}
_FAKE_VARIANTS: dict[str, list[dict[str, Any]]] = {}
_FAKE_PRICES: dict[str, dict[str, Any]] = {}


def reset_fake_amazon_state() -> None:
    _FAKE_LISTINGS.clear()
    _FAKE_IDEMPOTENCY.clear()
    _FAKE_MEDIA.clear()
    _FAKE_VARIANTS.clear()
    _FAKE_PRICES.clear()


def fake_amazon_listing_count() -> int:
    return len(_FAKE_LISTINGS)


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
            payload={
                "sku": value["sku"],
                "title": value["payload"].get("title", ""),
                "product_type": value["payload"].get("product_type"),
                "attributes": value["payload"].get("attributes", {}),
                "variants": _FAKE_VARIANTS.get(remote_id, []),
                "media": _FAKE_MEDIA.get(remote_id, []),
                "price": _FAKE_PRICES.get(remote_id),
                "quantity": value.get("quantity", 0),
            },
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
                "payment_status": "paid",
                "item_subtotal": "1000.00",
                "tax": "200.00",
                "shipping": "50.00",
                "discount": "0.00",
                "seller_sku": "E2E-SKU",
                "asin": "B0FAKE1234",
                "quantity": 1,
                "unit_price": "1250.00",
                "title": "Fake Amazon Product",
                "fulfilment_id": "FAKE-FULFILMENT-1",
                "carrier": "FakeCarrier",
                "tracking_reference": "FAKE-TRACK-1",
            }
        ]

    def financial_events(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]:
        categories = (
            ("Commission", "125.00"),
            ("Referral_Commission", "12.00"),
            ("Fulfilment_Fee", "50.00"),
            ("Shipping_Fee", "20.00"),
            ("Storage_Fee", "5.00"),
            ("Closing_Fee", "3.00"),
            ("Refund", "-30.00"),
            ("Refund_Fee", "-2.00"),
            ("Promotion", "-4.00"),
            ("Advertising", "6.00"),
            ("Tax", "15.00"),
            ("Withholding", "10.00"),
            ("Chargeback", "-8.00"),
            ("Adjustment", "-1.00"),
            ("Unknown_Remote_Category", "0.50"),
        )
        return [
            {
                "event_id": f"FAKE-AMZ-FIN-{marketplace_id[-4:]}-{index:02d}",
                "type": category,
                "amount": amount,
                "currency": "INR",
            }
            for index, (category, amount) in enumerate(categories, start=1)
        ]

    def product_type_attributes(
        self, *, marketplace_id: str, product_type: str
    ) -> list[dict[str, Any]]:
        return [
            {"name": "item_name", "required": True, "type": "string"},
            {"name": "brand", "required": False, "type": "string"},
            {"name": "variation_theme", "required": False, "type": "string"},
        ]

    def listing_by_sku(
        self, *, seller_id: str, marketplace_id: str, sku: str
    ) -> AmazonOperationResult:
        for remote_id, value in _FAKE_LISTINGS.items():
            if value["sku"] == sku:
                return self.listing(remote_id)
        return AmazonOperationResult(
            "failed",
            issues=(
                AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
            ),
        )

    def submit_media(
        self, *, remote_id: str, media: list[dict[str, Any]], idempotency_key: str
    ) -> AmazonOperationResult:
        if remote_id not in _FAKE_LISTINGS:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        _FAKE_MEDIA[remote_id] = [dict(item) for item in media]
        return AmazonOperationResult(
            "succeeded", remote_id=remote_id, payload={"count": len(media)}
        )

    def submit_variants(
        self, *, remote_id: str, variants: list[dict[str, Any]], idempotency_key: str
    ) -> AmazonOperationResult:
        if remote_id not in _FAKE_LISTINGS:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        _FAKE_VARIANTS[remote_id] = [dict(item) for item in variants]
        return AmazonOperationResult(
            "succeeded", remote_id=remote_id, payload={"count": len(variants)}
        )

    def price(self, *, remote_id: str) -> AmazonOperationResult:
        if remote_id not in _FAKE_LISTINGS:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        return AmazonOperationResult(
            "succeeded", remote_id=remote_id, payload=_FAKE_PRICES.get(remote_id, {})
        )

    def update_price(
        self, *, remote_id: str, price: dict[str, Any], idempotency_key: str
    ) -> AmazonOperationResult:
        if remote_id not in _FAKE_LISTINGS:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        _FAKE_PRICES[remote_id] = dict(price)
        return AmazonOperationResult("succeeded", remote_id=remote_id, payload=dict(price))

    def returns(self, *, seller_id: str, marketplace_id: str) -> list[dict[str, Any]]:
        return [
            {
                "return_id": "FAKE-AMZ-RETURN-1",
                "order_id": f"FAKE-AMZ-ORDER-{marketplace_id[-4:]}",
                "status": "requested",
                "reason": "Customer changed mind",
                "quantity": 1,
                "refund_amount": "1250.00",
                "amount": "1250.00",
                "currency": "INR",
            }
        ]

    def remote_drift(self, remote_id: str, *, changes: dict[str, Any]) -> AmazonOperationResult:
        value = _FAKE_LISTINGS.get(remote_id)
        if value is None:
            return AmazonOperationResult(
                "failed",
                issues=(
                    AmazonIssue(AmazonIssueCode.IDENTIFIER_ERROR, "Amazon listing was not found."),
                ),
            )
        for key, changed in changes.items():
            if key in {"title", "product_type", "attributes"}:
                value["payload"][key] = changed
            elif key == "quantity":
                value["quantity"] = changed
            elif key == "variants":
                _FAKE_VARIANTS[remote_id] = list(changed)
            elif key == "media":
                _FAKE_MEDIA[remote_id] = list(changed)
            elif key == "price":
                _FAKE_PRICES[remote_id] = dict(changed)
        return self.listing(remote_id)


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
        media: list[dict[str, Any]] | None = None,
        variants: list[dict[str, Any]] | None = None,
        price: dict[str, Any] | None = None,
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
        if media_count < 1 and not media:
            issues.append(
                {
                    "code": "missing_media",
                    "message": "At least one Amazon-compatible image is required.",
                }
            )
        if media:
            issues.extend(
                {"code": issue.code, "message": issue.message, "field": issue.field}
                for issue in AmazonMediaPolicy.validate(media)
            )
        if variants:
            issues.extend(
                {"code": issue.code, "message": issue.message, "field": issue.field}
                for issue in AmazonVariantPolicy.validate(variants)
            )
        if price:
            issues.extend(
                {"code": issue.code, "message": issue.message, "field": issue.field}
                for issue in AmazonPricingPolicy.validate(price, self.marketplace.currency)
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
        if isinstance(self.transport, FakeAmazonSPAPITransport):
            value = _FAKE_LISTINGS.get(remote_id)
            if value is not None:
                if title is not None:
                    value["payload"]["title"] = title
                if sku is not None:
                    value["sku"] = sku
                result = self.transport.listing(remote_id)
        return {
            "remote_id": remote_id,
            "title": result.payload.get("title", title),
            "remote_sku": result.payload.get("sku", sku),
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
        normalized: list[dict[str, object]] = []
        for item in self.transport.orders(
            seller_id=self.seller_id, marketplace_id=self.marketplace.marketplace_id
        ):
            normalized.append(
                {
                    "remote_id": str(item["order_id"]),
                    "status": {"unshipped": "confirmed", "shipped": "shipped"}.get(
                        str(item.get("status", "")).lower(), "processing"
                    ),
                    "raw_status": str(item.get("status", "unknown")),
                    "total": str(item.get("total", "0")),
                    "currency": str(item.get("currency", self.marketplace.currency)),
                    "fulfilment_channel": str(item.get("fulfilment_channel", "MFN")),
                    "payment_status": str(item.get("payment_status", "paid")),
                    "item_subtotal": str(item.get("item_subtotal", item.get("total", "0"))),
                    "tax": str(item.get("tax", "0")),
                    "shipping": str(item.get("shipping", "0")),
                    "discount": str(item.get("discount", "0")),
                    "seller_sku": item.get("seller_sku"),
                    "asin": item.get("asin"),
                    "quantity": item.get("quantity", 1),
                    "unit_price": str(item.get("unit_price", item.get("total", "0"))),
                    "title": item.get("title"),
                    "fulfilment_id": item.get("fulfilment_id"),
                    "carrier": item.get("carrier"),
                    "tracking_reference": item.get("tracking_reference"),
                    "last_update": item.get("last_update"),
                }
            )
        return normalized

    def get_fees(self) -> list[dict[str, object]]:
        return [
            {
                "type": str(item["type"]).lower(),
                "amount": str(item["amount"]),
                "currency": str(item.get("currency", self.marketplace.currency)),
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

    def product_type_attributes(self, product_type: str) -> list[dict[str, Any]]:
        return self.transport.product_type_attributes(
            marketplace_id=self.marketplace.marketplace_id, product_type=product_type
        )

    def find_by_sku(self, sku: str) -> AmazonOperationResult:
        return self.transport.listing_by_sku(
            seller_id=self.seller_id, marketplace_id=self.marketplace.marketplace_id, sku=sku
        )

    def submit_media(
        self, remote_id: str, media: list[dict[str, Any]], idempotency_key: str
    ) -> AmazonOperationResult:
        return self.transport.submit_media(
            remote_id=remote_id, media=media, idempotency_key=idempotency_key
        )

    def submit_variants(
        self, remote_id: str, variants: list[dict[str, Any]], idempotency_key: str
    ) -> AmazonOperationResult:
        return self.transport.submit_variants(
            remote_id=remote_id, variants=variants, idempotency_key=idempotency_key
        )

    def get_price(self, remote_id: str) -> AmazonOperationResult:
        return self.transport.price(remote_id=remote_id)

    def update_price(
        self, remote_id: str, price: dict[str, Any], idempotency_key: str
    ) -> AmazonOperationResult:
        return self.transport.update_price(
            remote_id=remote_id, price=price, idempotency_key=idempotency_key
        )

    def get_returns(self) -> list[dict[str, Any]]:
        return self.transport.returns(
            seller_id=self.seller_id, marketplace_id=self.marketplace.marketplace_id
        )

    def process(self, remote_id: str) -> AmazonOperationResult:
        return self.transport.process(remote_id)


def amazon_marketplace(country_code: str) -> AmazonMarketplace:
    try:
        return AMAZON_MARKETPLACES[country_code.upper()]
    except KeyError as error:
        raise ValueError("Amazon marketplace region is unsupported.") from error
