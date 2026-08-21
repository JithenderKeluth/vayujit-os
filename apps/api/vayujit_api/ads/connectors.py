"""Transport-injected deterministic Ads connectors.

The local adapters intentionally never perform network I/O.  Their state is
kept in memory so tests can exercise retries, ambiguity, throttling and
reconciliation without credentials or spend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AdsConnectorError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        ambiguous: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.ambiguous = ambiguous
        self.retry_after_seconds = retry_after_seconds


@dataclass
class FakeAdsState:
    entities: dict[str, dict[str, dict[str, Any]]] = field(
        default_factory=lambda: {
            "campaign": {},
            "group": {},
            "creative": {},
            "ad": {},
            "keyword": {},
            "product_target": {},
        }
    )
    calls: list[dict[str, Any]] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)


class AdsConnector:
    provider = "base"

    def __init__(self, state: FakeAdsState | None = None) -> None:
        self.state = state or FakeAdsState()

    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    def _remote_id(self, entity_type: str, local_key: str) -> str:
        prefix = {"meta": "meta", "google": "google", "amazon": "amz", "flipkart": "fk"}.get(
            self.provider, self.provider
        )
        return f"{prefix}_{entity_type}_{local_key.replace('-', '')[:18]}"

    def _check_failure(self, operation: str) -> None:
        code = self.state.failures.get(operation)
        if code == "throttled":
            raise AdsConnectorError(
                "ads.throttled",
                "The Ads connector is throttled; retry later.",
                retryable=True,
                retry_after_seconds=15,
            )
        if code == "ambiguous":
            raise AdsConnectorError(
                "ads.ambiguous_result",
                "The Ads result is ambiguous; reconcile before retrying.",
                ambiguous=True,
            )
        if code == "unavailable":
            raise AdsConnectorError(
                "ads.connector_unavailable", "The Ads connector is unavailable.", retryable=True
            )

    def _create(self, entity_type: str, local_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        ambiguous = self.state.failures.get(f"create_{entity_type}") == "ambiguous"
        if not ambiguous:
            self._check_failure(f"create_{entity_type}")
        remote_id = self._remote_id(entity_type, local_key)
        existing = self.state.entities[entity_type].get(remote_id)
        if existing:
            return existing
        result = {"remote_id": remote_id, "entity_type": entity_type, **payload, "state": "active"}
        self.state.entities[entity_type][remote_id] = result
        self.state.calls.append(
            {
                "operation": f"create_{entity_type}",
                "provider": self.provider,
                "remote_id": remote_id,
                "payload": payload,
            }
        )
        if ambiguous:
            raise AdsConnectorError(
                "ads.ambiguous_result",
                "The Ads result is ambiguous; reconcile before retrying.",
                ambiguous=True,
            )
        return result

    def create_campaign(self, local_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create("campaign", local_key, payload)

    def update_campaign(self, remote_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._update("campaign", remote_id, payload)

    def pause_campaign(self, remote_id: str) -> dict[str, Any]:
        return self._update("campaign", remote_id, {"state": "paused"})

    def resume_campaign(self, remote_id: str) -> dict[str, Any]:
        return self._update("campaign", remote_id, {"state": "active"})

    def archive_campaign(self, remote_id: str) -> dict[str, Any]:
        return self._update("campaign", remote_id, {"state": "archived"})

    def create_group(self, local_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create("group", local_key, payload)

    def attach_creative(self, local_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create("creative", local_key, payload)

    def create_ad(self, local_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create("ad", local_key, payload)

    def update_ad(self, remote_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._update("ad", remote_id, payload)

    def _update(self, entity_type: str, remote_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ambiguous = self.state.failures.get(f"update_{entity_type}") == "ambiguous"
        if not ambiguous:
            self._check_failure(f"update_{entity_type}")
        entity = self.state.entities[entity_type].get(remote_id)
        if entity is None:
            raise AdsConnectorError("ads.remote_not_found", "The remote Ads entity was not found.")
        entity.update(payload)
        self.state.calls.append(
            {
                "operation": f"update_{entity_type}",
                "provider": self.provider,
                "remote_id": remote_id,
                "payload": payload,
            }
        )
        if ambiguous:
            raise AdsConnectorError(
                "ads.ambiguous_result",
                "The Ads result is ambiguous; reconcile before retrying.",
                ambiguous=True,
            )
        return entity

    def lookup(self, entity_type: str, remote_id: str) -> dict[str, Any] | None:
        return self.state.entities.get(entity_type, {}).get(remote_id)

    def metrics(self, remote_campaign_id: str) -> dict[str, float]:
        return {
            "impressions": 1200.0,
            "reach": 980.0,
            "clicks": 48.0,
            "spend": 125.0,
            "conversions": 6.0,
            "sales": 4.0,
            "revenue": 1000.0,
            "video_views": 300.0,
        }


class FakeMetaAdsConnector(AdsConnector):
    provider = "meta"

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": "meta",
            "status": "fake_certified",
            "platforms": ["facebook", "instagram"],
            "placements": ["feed", "story", "reel", "video"],
            "objectives": [
                "awareness",
                "traffic",
                "engagement",
                "leads",
                "conversions",
                "sales",
                "video_views",
                "remarketing",
            ],
            "media_types": ["text", "image", "video"],
            "bidding_strategies": [
                "lowest_cost",
                "maximize_conversions",
                "target_cpa",
                "target_roas",
            ],
            "cta_types": ["learn_more", "shop_now", "sign_up"],
            "audience_types": [
                "geography",
                "language",
                "interest",
                "demographic",
                "custom_reference",
            ],
            "budget_modes": ["daily", "lifetime"],
            "currencies": ["INR", "USD"],
            "text_limits": {"headline": 200, "primary_text": 2200},
        }


class FakeGoogleAdsConnector(AdsConnector):
    provider = "google"

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": "google",
            "status": "fake_certified",
            "campaign_types": ["search", "display", "video"],
            "placements": ["search", "display", "youtube"],
            "objectives": ["awareness", "traffic", "leads", "conversions", "sales", "video_views"],
            "media_types": ["text", "image", "video"],
            "targeting": ["keywords", "negative_keywords", "audience"],
            "bidding_strategies": ["manual_cpc", "maximize_clicks", "maximize_conversions"],
            "budget_modes": ["daily", "lifetime"],
            "currencies": ["INR", "USD"],
            "text_limits": {"headline": 30, "description": 90},
        }


class FakeAmazonAdsConnector(AdsConnector):
    provider = "amazon"

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": "amazon",
            "marketplace": "amazon",
            "status": "fake_certified",
            "campaign_types": ["sponsored_products", "sponsored_brands", "display"],
            "placements": ["search", "detail_page", "rest_of_search"],
            "objectives": ["sales", "traffic", "awareness"],
            "media_types": ["text", "image"],
            "creative_types": ["content", "image"],
            "targeting": [
                "keywords",
                "negative_keywords",
                "product",
                "listing",
                "category",
                "audience",
            ],
            "bidding_strategies": ["dynamic_down_only", "dynamic_up_down", "fixed_bid"],
            "budget_modes": ["daily"],
            "currencies": ["INR", "USD"],
            "video_support": False,
            "listing_required": True,
            "keyword_match_types": ["exact", "phrase", "broad"],
            "destination_constraints": ["marketplace_listing"],
        }


class FakeFlipkartAdsConnector(AdsConnector):
    provider = "flipkart"

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": "flipkart",
            "marketplace": "flipkart",
            "status": "fake_certified",
            "campaign_types": ["product", "display"],
            "placements": ["search", "product_page"],
            "objectives": ["sales", "traffic"],
            "media_types": ["text", "image"],
            "creative_types": ["content", "image"],
            "targeting": ["product", "listing", "category", "audience"],
            "bidding_strategies": ["manual_cpc", "maximize_sales"],
            "budget_modes": ["daily"],
            "currencies": ["INR"],
            "video_support": False,
            "listing_required": True,
            "keyword_match_types": [],
            "destination_constraints": ["marketplace_listing"],
        }


MARKETPLACE_CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "amazon": FakeAmazonAdsConnector().capabilities(),
    "flipkart": FakeFlipkartAdsConnector().capabilities(),
    "meesho": {
        "provider": "meesho",
        "marketplace": "meesho",
        "status": "not_supported",
        "reason": "Marketplace Ads capability is not modeled in the local contract.",
        "listing_required": True,
        "synthetic": True,
    },
}

CONNECTORS: dict[str, AdsConnector] = {
    "meta": FakeMetaAdsConnector(),
    "google": FakeGoogleAdsConnector(),
    "amazon": FakeAmazonAdsConnector(),
    "flipkart": FakeFlipkartAdsConnector(),
}


def connector_for(provider: str) -> AdsConnector:
    try:
        return CONNECTORS[provider]
    except KeyError as error:
        raise AdsConnectorError(
            "ads.connector_unavailable", "The requested Ads provider is unavailable."
        ) from error
