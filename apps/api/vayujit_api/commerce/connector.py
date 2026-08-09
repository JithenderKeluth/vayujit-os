"""Connector protocol and deterministic fake implementation."""

import hashlib
from dataclasses import dataclass
from typing import Protocol, cast

from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    AmazonTransport,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
)
from vayujit_api.commerce.flipkart import (
    FakeFlipkartTransport,
    FlipkartCommerceConnector,
    FlipkartTransport,
)


class CommerceConnector(Protocol):
    def validate_account(self, seller_account_id: str) -> dict[str, object]: ...
    def discover_categories(self) -> list[dict[str, object]]: ...
    def preview_listing(self, *, title: str, sku: str | None) -> dict[str, object]: ...
    def create_listing(
        self, *, title: str, sku: str | None, idempotency_key: str
    ) -> dict[str, object]: ...
    def update_listing(
        self, *, remote_id: str, title: str | None, sku: str | None
    ) -> dict[str, object]: ...
    def get_listing(self, remote_id: str) -> dict[str, object]: ...
    def reconcile_listing(self, remote_id: str) -> dict[str, object]: ...
    def get_inventory(self, remote_id: str) -> dict[str, object]: ...
    def update_inventory(self, remote_id: str, quantity: int) -> dict[str, object]: ...
    def get_orders(self) -> list[dict[str, object]]: ...
    def get_fees(self) -> list[dict[str, object]]: ...
    def get_settlements(self) -> list[dict[str, object]]: ...


@dataclass
class DeterministicFakeCommerceConnector:
    """A network-free connector with stable identifiers and safe fixtures."""

    marketplace: str

    def validate_account(self, seller_account_id: str) -> dict[str, object]:
        return {
            "valid": bool(seller_account_id.strip()),
            "message": "Account validated by fake connector.",
        }

    def discover_categories(self) -> list[dict[str, object]]:
        return [
            {"remote_id": f"{self.marketplace}-root", "name": "General", "parent_remote_id": None},
            {
                "remote_id": f"{self.marketplace}-home",
                "name": "Home & Living",
                "parent_remote_id": f"{self.marketplace}-root",
            },
        ]

    def preview_listing(self, *, title: str, sku: str | None) -> dict[str, object]:
        return {"title": title.strip(), "sku": sku, "ready": bool(title.strip())}

    def create_listing(
        self, *, title: str, sku: str | None, idempotency_key: str
    ) -> dict[str, object]:
        safe_key = idempotency_key or "default"
        digest = hashlib.sha256(safe_key.encode()).hexdigest()[:10]
        remote_id = f"fake-{self.marketplace}-{digest}"
        return {
            "remote_id": remote_id,
            "remote_sku": sku or f"VJ-{remote_id[-6:]}",
            "status": "active",
            "url": f"https://fake.invalid/{remote_id}",
        }

    def update_listing(
        self, *, remote_id: str, title: str | None, sku: str | None
    ) -> dict[str, object]:
        return {"remote_id": remote_id, "title": title, "remote_sku": sku, "status": "active"}

    def get_listing(self, remote_id: str) -> dict[str, object]:
        return {"remote_id": remote_id, "title": "Fake marketplace listing", "status": "active"}

    def reconcile_listing(self, remote_id: str) -> dict[str, object]:
        return {
            "remote_id": remote_id,
            "title": "Fake marketplace listing",
            "status": "active",
            "drift": [],
        }

    def get_inventory(self, remote_id: str) -> dict[str, object]:
        return {"remote_id": remote_id, "quantity": 10}

    def update_inventory(self, remote_id: str, quantity: int) -> dict[str, object]:
        return {"remote_id": remote_id, "quantity": quantity}

    def get_orders(self) -> list[dict[str, object]]:
        return [
            {
                "remote_id": f"fake-order-{self.marketplace}-001",
                "status": "confirmed",
                "total": "1250.00",
            }
        ]

    def get_fees(self) -> list[dict[str, object]]:
        return [{"type": "commission", "amount": "125.00"}]

    def get_settlements(self) -> list[dict[str, object]]:
        return [
            {
                "remote_id": f"fake-settlement-{self.marketplace}-001",
                "gross": "1250.00",
                "fees": "125.00",
                "net": "1125.00",
            }
        ]


def connector_for(
    marketplace: str,
    *,
    seller_id: str | None = None,
    country_code: str = "IN",
    transport: AmazonTransport | FlipkartTransport | None = None,
) -> CommerceConnector:
    if marketplace == "amazon":
        return AmazonCommerceConnector(
            seller_id=seller_id or "fake-seller",
            marketplace=amazon_marketplace(country_code),
            transport=(
                cast(AmazonTransport, transport)
                if transport is not None
                else FakeAmazonSPAPITransport()
            ),
        )
    if marketplace == "flipkart":
        return cast(
            CommerceConnector,
            FlipkartCommerceConnector(
                seller_id=seller_id or "fake-flipkart-seller",
                transport=(
                    cast(FlipkartTransport, transport)
                    if transport is not None
                    else FakeFlipkartTransport()
                ),
            ),
        )
    return DeterministicFakeCommerceConnector(marketplace)
