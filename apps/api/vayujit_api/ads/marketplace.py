"""Normalized local Marketplace Ads orchestration."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ads.connectors import MARKETPLACE_CAPABILITY_REGISTRY, connector_for
from vayujit_api.ads.models import (
    Ad,
    AdBudget,
    AdCampaign,
    AdConversion,
    AdGroup,
    AdMarketplaceListing,
    AdMetric,
    AdRemoteMapping,
)
from vayujit_api.ads.schemas import AdsCampaignCreate, AdsConversionCreate
from vayujit_api.ads.service import (
    campaign_response,
    create_campaign,
    import_metrics,
    now,
    queue_job,
    require_account,
)
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/ads/marketplace", tags=["marketplace-ads"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]
Marketplace = Literal["amazon", "flipkart"]


class ListingCreate(BaseModel):
    account_id: uuid.UUID
    product_id: uuid.UUID
    marketplace: Marketplace
    listing_id: str = Field(min_length=1, max_length=180)
    version: int = Field(default=1, ge=1)
    state: Literal["active", "inactive", "suppressed"] = "active"
    title: str = Field(min_length=1, max_length=240)
    sku: str | None = Field(default=None, max_length=120)
    metadata: dict[str, object] = Field(default_factory=dict)


class MarketplaceReadinessRequest(AdsCampaignCreate):
    provider: Marketplace
    marketplace: Marketplace

    @model_validator(mode="after")
    def provider_matches(self) -> MarketplaceReadinessRequest:
        if self.provider != self.marketplace:
            raise ValueError("marketplace must match provider")
        return self


class FailureSimulationRequest(BaseModel):
    operation: str = Field(min_length=1, max_length=80)
    mode: Literal["throttled", "ambiguous", "unavailable", "clear"]


def _listing(db: Session, owner: User, listing_uuid: uuid.UUID) -> AdMarketplaceListing:
    value = db.scalar(
        select(AdMarketplaceListing).where(
            AdMarketplaceListing.id == listing_uuid, AdMarketplaceListing.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Marketplace listing not found.")
    return value


def _campaign(db: Session, owner: User, campaign_id: uuid.UUID) -> AdCampaign:
    value = db.scalar(
        select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.owner_id == owner.id)
    )
    if value is None:
        raise HTTPException(404, "Marketplace Ads campaign not found.")
    if value.provider not in {"amazon", "flipkart"}:
        raise HTTPException(422, "The campaign is not a marketplace Ads campaign.")
    return value


def _listing_response(value: AdMarketplaceListing) -> dict[str, object]:
    return {
        "id": value.id,
        "account_id": value.account_id,
        "product_id": value.product_id,
        "marketplace": value.marketplace,
        "listing_id": value.listing_id,
        "version": value.version,
        "state": value.state,
        "title": value.title,
        "sku": value.sku,
        "metadata": value.metadata_json,
        "synthetic": True,
    }


@router.get("/capabilities")
def marketplace_capabilities() -> dict[str, object]:
    return {key: value for key, value in MARKETPLACE_CAPABILITY_REGISTRY.items()}


@router.get("/providers")
def marketplace_providers() -> list[dict[str, object]]:
    return [cast(dict[str, object], value) for value in MARKETPLACE_CAPABILITY_REGISTRY.values()]


@router.post("/listings", status_code=201)
def listing_create(data: ListingCreate, db: DB, owner: Owner) -> dict[str, object]:
    account = require_account(db, owner, data.account_id)
    if account.provider != data.marketplace:
        raise HTTPException(422, "Listing marketplace does not match the Ads account.")
    if data.marketplace not in MARKETPLACE_CAPABILITY_REGISTRY:
        raise HTTPException(422, "The marketplace capability is not supported locally.")
    product = db.scalar(
        select(Product).where(Product.id == data.product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    existing = db.scalar(
        select(AdMarketplaceListing).where(
            AdMarketplaceListing.owner_id == owner.id,
            AdMarketplaceListing.marketplace == data.marketplace,
            AdMarketplaceListing.listing_id == data.listing_id,
            AdMarketplaceListing.version == data.version,
        )
    )
    if existing is not None:
        return _listing_response(existing)
    stamp = now()
    value = AdMarketplaceListing(
        owner_id=owner.id,
        account_id=account.id,
        product_id=product.id,
        marketplace=data.marketplace,
        listing_id=data.listing_id.strip(),
        version=data.version,
        state=data.state,
        title=data.title.strip(),
        sku=data.sku,
        metadata_json=data.metadata,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.marketplace_listing_created",
        entity_type="marketplace_listing",
        entity_id=value.id,
        metadata={
            "marketplace": value.marketplace,
            "listing_id": value.listing_id,
            "version": value.version,
        },
    )
    db.commit()
    db.refresh(value)
    return _listing_response(value)


@router.get("/listings")
def listing_list(
    db: DB, owner: Owner, marketplace: str | None = None, product_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    statement = select(AdMarketplaceListing).where(AdMarketplaceListing.owner_id == owner.id)
    if marketplace:
        statement = statement.where(AdMarketplaceListing.marketplace == marketplace)
    if product_id:
        statement = statement.where(AdMarketplaceListing.product_id == product_id)
    return [
        _listing_response(value)
        for value in db.scalars(statement.order_by(AdMarketplaceListing.created_at.desc()))
    ]


@router.get("/listings/{listing_uuid}")
def listing_detail(listing_uuid: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _listing_response(_listing(db, owner, listing_uuid))


def _validate_listing_request(
    data: MarketplaceReadinessRequest, db: Session, owner: User
) -> AdMarketplaceListing:
    account = require_account(db, owner, data.account_id)
    if account.provider != data.provider or not account.validated or not account.enabled:
        raise HTTPException(422, "The marketplace Ads account must be validated and enabled.")
    if not data.product_id or not data.listing_id or not data.listing_version:
        raise HTTPException(422, "An exact marketplace listing and version are required.")
    listing = db.scalar(
        select(AdMarketplaceListing).where(
            AdMarketplaceListing.owner_id == owner.id,
            AdMarketplaceListing.account_id == account.id,
            AdMarketplaceListing.product_id == data.product_id,
            AdMarketplaceListing.marketplace == data.marketplace,
            AdMarketplaceListing.listing_id == data.listing_id,
            AdMarketplaceListing.version == data.listing_version,
            AdMarketplaceListing.state == "active",
        )
    )
    if listing is None:
        raise HTTPException(422, "The exact active marketplace listing version is unavailable.")
    return listing


@router.post("/campaigns/readiness")
def campaign_readiness(
    data: MarketplaceReadinessRequest, db: DB, owner: Owner
) -> dict[str, object]:
    listing = _validate_listing_request(data, db, owner)
    from vayujit_api.ads.service import campaign_preview

    try:
        preview = campaign_preview(db, owner, data)
    except HTTPException as error:
        return {
            "ready": False,
            "blockers": [str(error.detail)],
            "warnings": [],
            "information": {"listing": _listing_response(listing), "synthetic": True},
        }
    return {
        "ready": True,
        "blockers": [],
        "warnings": [str(value) for value in cast(list[object], preview.get("warnings", []))],
        "information": {
            "provider": data.provider,
            "account_id": data.account_id,
            "product_id": data.product_id,
            "listing": _listing_response(listing),
            "objective": data.objective,
            "targeting": data.targeting_summary,
            "creative": "exact approved creative required at ad creation",
            "synthetic": True,
        },
        "fingerprint": preview["fingerprint"],
    }


@router.post("/campaigns/preview")
def campaign_preview_route(
    data: MarketplaceReadinessRequest, db: DB, owner: Owner
) -> dict[str, object]:
    listing = _validate_listing_request(data, db, owner)
    from vayujit_api.ads.service import campaign_preview

    result = campaign_preview(db, owner, data)
    return {**result, "listing": _listing_response(listing), "synthetic": True}


@router.post("/campaigns/confirm")
def campaign_confirm(payload: dict[str, Any], db: DB, owner: Owner) -> dict[str, object]:
    if not payload.get("confirm"):
        raise HTTPException(
            422, "Explicit confirmation is required before a marketplace Ads mutation."
        )
    raw = payload.get("campaign", payload)
    data = MarketplaceReadinessRequest.model_validate(raw)
    listing = _validate_listing_request(data, db, owner)
    value = create_campaign(db, owner, data, str(payload.get("preview_fingerprint") or ""))
    key = str(payload.get("idempotency_key") or f"marketplace-campaign:{value.id}")
    job = queue_job(
        db,
        owner,
        value,
        "create_campaign",
        key,
        {
            "campaign_id": str(value.id),
            "budget": raw.get("budget", {}),
            "listing_id": listing.listing_id,
            "listing_version": listing.version,
        },
    )
    return {
        "campaign": campaign_response(value),
        "job": {"id": job.id, "status": job.status, "idempotent": job.attempt_count > 0},
        "listing": _listing_response(listing),
        "synthetic": True,
    }


@router.get("/campaigns")
def campaign_list(db: DB, owner: Owner, marketplace: str | None = None) -> list[dict[str, object]]:
    statement = select(AdCampaign).where(
        AdCampaign.owner_id == owner.id, AdCampaign.provider.in_(["amazon", "flipkart"])
    )
    if marketplace:
        statement = statement.where(AdCampaign.marketplace == marketplace)
    return [
        campaign_response(value)
        for value in db.scalars(statement.order_by(AdCampaign.created_at.desc()))
    ]


@router.get("/campaigns/{campaign_id}")
def campaign_detail(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    listing = db.scalar(
        select(AdMarketplaceListing).where(
            AdMarketplaceListing.owner_id == owner.id,
            AdMarketplaceListing.marketplace == campaign.marketplace,
            AdMarketplaceListing.listing_id == campaign.listing_id,
            AdMarketplaceListing.version == campaign.listing_version,
        )
    )
    groups = list(
        db.scalars(
            select(AdGroup).where(AdGroup.owner_id == owner.id, AdGroup.campaign_id == campaign.id)
        )
    )
    ads = list(db.scalars(select(Ad).where(Ad.owner_id == owner.id, Ad.campaign_id == campaign.id)))
    return {
        "campaign": campaign_response(campaign),
        "listing": _listing_response(listing) if listing else None,
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "state": group.state,
                "remote_id": group.remote_group_id,
                "targeting": group.targeting_json,
            }
            for group in groups
        ],
        "ads": [
            {
                "id": ad.id,
                "state": ad.state,
                "remote_id": ad.remote_ad_id,
                "creative_id": ad.creative_id,
            }
            for ad in ads
        ],
        "synthetic": True,
    }


@router.post("/campaigns/{campaign_id}/reconcile")
def campaign_reconcile(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    connector = connector_for(campaign.provider)
    remote_id = campaign.remote_campaign_id or connector._remote_id("campaign", str(campaign.id))
    remote = connector.lookup("campaign", remote_id)
    if remote is None:
        mapping = db.scalar(
            select(AdRemoteMapping).where(
                AdRemoteMapping.owner_id == owner.id,
                AdRemoteMapping.local_entity_id == campaign.id,
                AdRemoteMapping.entity_type == "campaign",
            )
        )
        remote = mapping.remote_state_json if mapping is not None else None
    drift: list[dict[str, object]] = []
    if remote is None:
        campaign.reconciliation_state = "missing_remote"
        drift.append({"field": "campaign", "state": "missing_remote"})
    else:
        campaign.reconciliation_state = "matched"
        if remote.get("state") != campaign.state and campaign.state not in {"approved", "draft"}:
            drift.append({"field": "state", "local": campaign.state, "remote": remote.get("state")})
    campaign.updated_at = now()
    db.commit()
    return {
        "campaign_id": campaign.id,
        "remote_id": remote_id,
        "reconciliation_state": campaign.reconciliation_state,
        "drift": drift,
        "synthetic": True,
    }


@router.post("/campaigns/{campaign_id}/metrics/import")
def campaign_metrics_import(
    campaign_id: uuid.UUID, db: DB, owner: Owner
) -> list[dict[str, object]]:
    campaign = _campaign(db, owner, campaign_id)
    return [
        {
            "metric_key": metric.metric_key,
            "value": float(metric.value or 0),
            "availability": metric.availability,
            "source": metric.source,
            "observed_at": metric.observed_at,
        }
        for metric in import_metrics(db, owner, campaign)
    ]


@router.get("/campaigns/{campaign_id}/metrics")
def campaign_metrics(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    _campaign(db, owner, campaign_id)
    return [
        {
            "metric_key": metric.metric_key,
            "value": float(metric.value or 0),
            "availability": metric.availability,
            "source": metric.source,
            "observed_at": metric.observed_at,
        }
        for metric in db.scalars(
            select(AdMetric)
            .where(AdMetric.owner_id == owner.id, AdMetric.campaign_id == campaign_id)
            .order_by(AdMetric.observed_at.desc())
        )
    ]


@router.post("/campaigns/{campaign_id}/conversions", status_code=201)
def campaign_conversion(
    campaign_id: uuid.UUID, data: AdsConversionCreate, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    existing = db.scalar(
        select(AdConversion).where(
            AdConversion.owner_id == owner.id,
            AdConversion.provider_event_id == data.provider_event_id,
        )
    )
    if existing is None:
        existing = AdConversion(
            owner_id=owner.id,
            provider=campaign.provider,
            provider_event_id=data.provider_event_id,
            campaign_id=campaign.id,
            product_id=campaign.product_id,
            conversion_type=data.conversion_type,
            occurred_at=data.occurred_at,
            value=data.value,
            currency=data.currency,
            source="fake_connector",
            attribution_json={"type": data.attribution_type, "window": data.attribution_window},
            attribution_type=data.attribution_type,
            attribution_window=data.attribution_window,
            created_at=now(),
            updated_at=now(),
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return {
        "id": existing.id,
        "campaign_id": existing.campaign_id,
        "value": existing.value,
        "currency": existing.currency,
        "synthetic": True,
    }


@router.get("/campaigns/{campaign_id}/analytics")
def campaign_analytics(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    metrics = list(
        db.scalars(
            select(AdMetric).where(
                AdMetric.owner_id == owner.id, AdMetric.campaign_id == campaign.id
            )
        )
    )
    spend = sum(float(metric.value or 0) for metric in metrics if metric.metric_key == "spend")
    revenue = sum(
        float(metric.value or 0) for metric in metrics if metric.metric_key in {"sales", "revenue"}
    )
    conversions = sum(
        float(metric.value or 0) for metric in metrics if metric.metric_key == "conversions"
    )
    currency = db.scalar(
        select(AdBudget.currency)
        .where(AdBudget.campaign_id == campaign.id)
        .order_by(AdBudget.version.desc())
    )
    return {
        "provider": campaign.provider,
        "campaign_id": campaign.id,
        "product_id": campaign.product_id,
        "spend": spend,
        "revenue": revenue,
        "conversions": conversions,
        "roas": revenue / spend if spend > 0 else None,
        "profitability": "Unavailable",
        "profit_status": "unavailable",
        "currency": currency,
        "synthetic": True,
    }


@router.get("/overview")
def marketplace_overview(db: DB, owner: Owner) -> dict[str, object]:
    campaigns = list(
        db.scalars(
            select(AdCampaign).where(
                AdCampaign.owner_id == owner.id, AdCampaign.provider.in_(["amazon", "flipkart"])
            )
        )
    )
    listings = list(
        db.scalars(select(AdMarketplaceListing).where(AdMarketplaceListing.owner_id == owner.id))
    )
    return {
        "providers": marketplace_capabilities(),
        "campaigns": [campaign_response(value) for value in campaigns],
        "listings": [_listing_response(value) for value in listings],
        "synthetic": True,
        "live_provider_calls": False,
    }


@router.get("/product-channel/{product_id}")
def product_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaigns = list(
        db.scalars(
            select(AdCampaign).where(
                AdCampaign.owner_id == owner.id,
                AdCampaign.product_id == product_id,
                AdCampaign.provider.in_(["amazon", "flipkart"]),
            )
        )
    )
    return {
        "product_id": product_id,
        "providers": {
            key: {"status": value["status"], "reason": value.get("reason"), "synthetic": True}
            for key, value in MARKETPLACE_CAPABILITY_REGISTRY.items()
        },
        "campaigns": [campaign_response(value) for value in campaigns],
        "actions": [
            "create_ad",
            "open_campaign",
            "preview_ad",
            "pause",
            "resume",
            "preview_budget_change",
            "preview_bid_change",
            "preview_creative_replacement",
            "reconcile",
            "open_recovery",
            "open_recommendation",
        ],
        "synthetic": True,
    }


@router.get("/comparison/{product_id}")
def marketplace_comparison(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaigns = list(
        db.scalars(
            select(AdCampaign).where(
                AdCampaign.owner_id == owner.id,
                AdCampaign.product_id == product_id,
                AdCampaign.provider.in_(["amazon", "flipkart"]),
            )
        )
    )
    rows: list[dict[str, object]] = []
    currencies: set[str] = set()
    for campaign in campaigns:
        currency = db.scalar(
            select(AdBudget.currency)
            .where(AdBudget.campaign_id == campaign.id)
            .order_by(AdBudget.version.desc())
        )
        if currency:
            currencies.add(currency)
        rows.append(
            {
                "provider": campaign.provider,
                "campaign_id": campaign.id,
                "currency": currency,
                "analytics": {"synthetic": True},
            }
        )
    compatible = len(currencies) <= 1
    return {
        "product_id": product_id,
        "rows": rows,
        "compatible": compatible,
        "status": "available" if compatible else "unavailable",
        "warning": (
            None
            if compatible
            else "Currencies differ; cross-marketplace aggregation is unavailable."
        ),
        "synthetic": True,
    }


@router.post("/failures/simulate")
def failure_simulate(
    data: FailureSimulationRequest, db: DB, owner: Owner, provider: Marketplace = "amazon"
) -> dict[str, object]:
    connector = connector_for(provider)
    if data.mode == "clear":
        connector.state.failures.pop(data.operation, None)
    else:
        connector.state.failures[data.operation] = data.mode
    return {"provider": provider, "operation": data.operation, "mode": data.mode, "synthetic": True}


@router.get("/history")
def marketplace_history(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "created_at": event.occurred_at,
            "metadata": event.metadata_json,
        }
        for event in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.actor_id == owner.id, AuditEvent.action.like("ads.%"))
            .order_by(AuditEvent.occurred_at.desc())
        )
    ]
