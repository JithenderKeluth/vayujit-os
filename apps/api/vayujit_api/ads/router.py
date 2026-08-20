from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.ads.budget import budget_preview as budget_change_preview
from vayujit_api.ads.budget import confirm_budget_change
from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.failure import ADS_FAILURE_TAXONOMY, ADS_OPTIMIZATION_FAILURE_TAXONOMY
from vayujit_api.ads.models import (
    Ad,
    AdAccount,
    AdAudience,
    AdBudget,
    AdCampaign,
    AdConversion,
    AdCreative,
    AdDriftFinding,
    AdFailureRecord,
    AdGroup,
    AdJob,
    AdMetric,
    AdRecoveryRecord,
    AdRemoteMapping,
    AdSchedule,
)
from vayujit_api.ads.schemas import (
    AdsAccountCreate,
    AdsAccountResponse,
    AdsAccountUpdate,
    AdsAudienceCreate,
    AdsBudgetConfirm,
    AdsBudgetPreview,
    AdsCampaignCreate,
    AdsConversionCreate,
    AdsCreativeCreate,
    AdsRecoveryRequest,
)
from vayujit_api.ads.service import (
    account_response,
    campaign_preview,
    campaign_response,
    create_account,
    create_campaign,
    create_creative,
    import_metrics,
    queue_job,
    require_account,
    update_account,
    validate_account,
)
from vayujit_api.ads.validation import creative_readiness
from vayujit_api.ads.worker import run_next_ads_job
from vayujit_api.audit.service import record_event
from vayujit_api.commerce.models import MarketplaceFee, MarketplaceOrder, MarketplaceOrderItem
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/ads", tags=["ads"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _campaign(db: Session, owner: User, campaign_id: uuid.UUID) -> AdCampaign:
    value = db.scalar(
        select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.owner_id == owner.id)
    )
    if not value:
        raise HTTPException(404, "Ads campaign not found.")
    return value


@router.get("/capabilities")
def capabilities() -> dict[str, object]:
    return {provider: connector_for(provider).capabilities() for provider in ("meta", "google")}


@router.get("/providers")
def providers() -> list[dict[str, object]]:
    return [cast(dict[str, object], value) for value in capabilities().values()]


@router.get("/overview")
def overview(db: DB, owner: Owner) -> dict[str, object]:
    accounts = list(
        db.scalars(
            select(AdAccount)
            .where(AdAccount.owner_id == owner.id)
            .order_by(AdAccount.created_at.desc())
        )
    )
    campaigns = list(
        db.scalars(
            select(AdCampaign)
            .where(AdCampaign.owner_id == owner.id)
            .order_by(AdCampaign.created_at.desc())
        )
    )
    metrics = list(db.scalars(select(AdMetric).where(AdMetric.owner_id == owner.id)))
    return {
        "accounts": [account_response(value) for value in accounts],
        "campaigns": [
            campaign_response(
                value,
                db.scalar(
                    select(AdBudget)
                    .where(AdBudget.campaign_id == value.id)
                    .order_by(AdBudget.version.desc())
                ),
            )
            for value in campaigns
        ],
        "active_campaigns": sum(value.state == "active" for value in campaigns),
        "paused": sum(value.state == "paused" for value in campaigns),
        "failed": sum(value.state == "failed" for value in campaigns),
        "synthetic": True,
        "metrics": {
            key: sum(float(value.value or 0) for value in metrics if value.metric_key == key)
            for key in {value.metric_key for value in metrics}
        },
        "attention_items": ["Synthetic local Ads data; live spend is not connected."],
    }


@router.get("/accounts", response_model=list[AdsAccountResponse])
def account_list(db: DB, owner: Owner, provider: str | None = None) -> list[dict[str, object]]:
    statement = select(AdAccount).where(AdAccount.owner_id == owner.id)
    if provider:
        statement = statement.where(AdAccount.provider == provider)
    return [
        account_response(value)
        for value in db.scalars(statement.order_by(AdAccount.created_at.desc()))
    ]


@router.post("/accounts", response_model=AdsAccountResponse, status_code=201)
def account_create(data: AdsAccountCreate, db: DB, owner: Owner) -> dict[str, object]:
    return account_response(create_account(db, owner, data))


@router.get("/accounts/{account_id}", response_model=AdsAccountResponse)
def account_detail(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return account_response(require_account(db, owner, account_id))


@router.patch("/accounts/{account_id}", response_model=AdsAccountResponse)
def account_update(
    account_id: uuid.UUID, data: AdsAccountUpdate, db: DB, owner: Owner
) -> dict[str, object]:
    return account_response(update_account(db, owner, require_account(db, owner, account_id), data))


@router.post("/accounts/{account_id}/validate", response_model=AdsAccountResponse)
def account_validate(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return account_response(validate_account(db, owner, require_account(db, owner, account_id)))


@router.post("/accounts/{account_id}/enable", response_model=AdsAccountResponse)
def account_enable(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = require_account(db, owner, account_id)
    if not value.validated:
        raise HTTPException(422, "Validate the Ads account before enabling it.")
    value.enabled = True
    value.status = "active"
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    record_event(
        db,
        actor_id=owner.id,
        action="ads.account_enabled",
        entity_type="ad_account",
        entity_id=value.id,
        metadata={"provider": value.provider},
    )
    db.commit()
    db.refresh(value)
    return account_response(value)


@router.post("/accounts/{account_id}/disable", response_model=AdsAccountResponse)
def account_disable(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = require_account(db, owner, account_id)
    value.enabled = False
    value.status = "disabled"
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    record_event(
        db,
        actor_id=owner.id,
        action="ads.account_disabled",
        entity_type="ad_account",
        entity_id=value.id,
        metadata={"provider": value.provider},
    )
    db.commit()
    db.refresh(value)
    return account_response(value)


@router.delete("/accounts/{account_id}/credentials", response_model=AdsAccountResponse)
def account_remove_credentials(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = require_account(db, owner, account_id)
    value.encrypted_credentials = None
    value.credential_metadata_json = {"configured": False, "keys": []}
    value.validated = False
    value.validation_status = "unknown"
    value.enabled = False
    value.status = "disabled"
    value.credential_version += 1
    db.commit()
    db.refresh(value)
    return account_response(value)


@router.post("/accounts/{account_id}/archive", response_model=AdsAccountResponse)
def account_archive(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = require_account(db, owner, account_id)
    value.enabled = False
    value.status = "archived"
    db.commit()
    db.refresh(value)
    return account_response(value)


@router.get("/accounts/{account_id}/diagnostics")
def account_diagnostics(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = require_account(db, owner, account_id)
    return {
        "account_id": value.id,
        "provider": value.provider,
        "status": "healthy" if value.validated and value.enabled else "attention_required",
        "credential_configured": bool(value.credential_metadata_json.get("configured")),
        "synthetic": True,
        "safe_message": "No live Ads API calls are made by the local connector.",
    }


@router.get("/accounts/{account_id}/history")
def account_history(account_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    require_account(db, owner, account_id)
    from vayujit_api.audit.models import AuditEvent

    return [
        {"action": event.action, "created_at": event.occurred_at, "metadata": event.metadata_json}
        for event in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.actor_id == owner.id, AuditEvent.entity_id == account_id)
            .order_by(AuditEvent.occurred_at.desc())
        )
    ]


@router.post("/audiences", status_code=201)
def audience_create(data: AdsAudienceCreate, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.ads.models import AdAudience

    value = AdAudience(
        owner_id=owner.id,
        name=data.name,
        geography_json=list(data.geography),
        languages_json=list(data.languages),
        age_min=data.age_min,
        age_max=data.age_max,
        interests_json=list(data.interests),
        demographics_json=list(data.demographics),
        exclusions_json=list(data.exclusions),
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        custom_segment_id=data.custom_segment_id,
        remarketing_segment_id=data.remarketing_segment_id,
        keyword_intent_json=data.keyword_intent,
        provider_compatibility_json={"meta": "pending", "google": "pending"},
        validation_status="unknown",
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return {"id": value.id, "name": value.name, "privacy": "abstract_segments_only"}


@router.get("/audiences")
def audience_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    from vayujit_api.ads.models import AdAudience

    return [
        {
            "id": row.id,
            "name": row.name,
            "validation_status": row.validation_status,
            "privacy": "abstract_segments_only",
        }
        for row in db.scalars(
            select(AdAudience).where(AdAudience.owner_id == owner.id).order_by(AdAudience.name)
        )
    ]


@router.post("/audiences/{audience_id}/validate")
def audience_validate(audience_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.ads.models import AdAudience

    row = db.scalar(
        select(AdAudience).where(AdAudience.id == audience_id, AdAudience.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Ads audience not found.")
    providers: dict[str, dict[str, object]] = {
        "meta": {"status": "valid", "blockers": []},
        "google": {"status": "valid", "blockers": []},
    }
    if row.gender and row.gender not in {"male", "female", "all", "unknown"}:
        providers["google"] = {
            "status": "unsupported",
            "blockers": [
                "Google does not support this gender value in the local capability contract."
            ],
        }
    row.provider_compatibility_json = cast(dict[str, object], providers)
    row.validation_status = (
        "valid" if any(value["status"] == "valid" for value in providers.values()) else "invalid"
    )
    db.commit()
    return {
        "id": row.id,
        "validation_status": row.validation_status,
        "providers": providers,
        "privacy": "abstract_segments_only",
    }


@router.post("/creatives/readiness")
def creative_readiness_route(data: AdsCreativeCreate, db: DB, owner: Owner) -> dict[str, object]:
    return creative_readiness(db, owner, data)


@router.post("/campaigns/preview")
def campaign_preview_route(data: AdsCampaignCreate, db: DB, owner: Owner) -> dict[str, object]:
    return campaign_preview(db, owner, data)


@router.post("/campaigns", status_code=201)
def campaign_create(data: AdsCampaignCreate, db: DB, owner: Owner) -> dict[str, object]:
    value = create_campaign(db, owner, data)
    return campaign_response(
        value,
        db.scalar(
            select(AdBudget)
            .where(AdBudget.campaign_id == value.id)
            .order_by(AdBudget.version.desc())
        ),
    )


@router.post("/campaigns/confirm")
def campaign_confirm(payload: dict[str, Any], db: DB, owner: Owner) -> dict[str, object]:
    if not payload.get("confirm"):
        raise HTTPException(422, "Explicit confirmation is required before an Ads mutation.")
    data = AdsCampaignCreate.model_validate(payload.get("campaign", payload))
    value = create_campaign(db, owner, data, str(payload.get("preview_fingerprint") or ""))
    job = queue_job(
        db,
        owner,
        value,
        "create_campaign",
        str(payload.get("idempotency_key") or f"campaign:{value.id}"),
        {
            "campaign_id": str(value.id),
            "budget": payload.get("campaign", payload).get("budget", {}),
        },
    )
    return {
        "campaign": campaign_response(
            value,
            db.scalar(
                select(AdBudget)
                .where(AdBudget.campaign_id == value.id)
                .order_by(AdBudget.version.desc())
            ),
        ),
        "job": {"id": job.id, "status": job.status, "idempotent": job.attempt_count > 0},
    }


@router.get("/campaigns")
def campaign_list(
    db: DB,
    owner: Owner,
    provider: str | None = None,
    state: str | None = None,
    product_id: uuid.UUID | None = None,
) -> list[dict[str, object]]:
    statement = select(AdCampaign).where(AdCampaign.owner_id == owner.id)
    if provider:
        statement = statement.where(AdCampaign.provider == provider)
    if state:
        statement = statement.where(AdCampaign.state == state)
    if product_id:
        statement = statement.where(AdCampaign.product_id == product_id)
    return [
        campaign_response(
            value,
            db.scalar(
                select(AdBudget)
                .where(AdBudget.campaign_id == value.id)
                .order_by(AdBudget.version.desc())
            ),
        )
        for value in db.scalars(statement.order_by(AdCampaign.created_at.desc()))
    ]


@router.get("/campaigns/{campaign_id}")
def campaign_detail(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = _campaign(db, owner, campaign_id)
    creatives = list(
        db.scalars(
            select(AdCreative)
            .where(AdCreative.campaign_id == value.id)
            .order_by(AdCreative.created_at.desc())
        )
    )
    return {
        "campaign": campaign_response(
            value,
            db.scalar(
                select(AdBudget)
                .where(AdBudget.campaign_id == value.id)
                .order_by(AdBudget.version.desc())
            ),
        ),
        "creatives": [
            {
                "id": item.id,
                "type": item.creative_type,
                "approval_status": item.approval_status,
                "lineage": item.exact_lineage_json,
                "fingerprint": item.fingerprint,
                "destination_url": item.destination_url,
            }
            for item in creatives
        ],
    }


@router.post("/campaigns/{campaign_id}/creatives", status_code=201)
def creative_create(
    campaign_id: uuid.UUID, data: AdsCreativeCreate, db: DB, owner: Owner
) -> dict[str, object]:
    if campaign_id != data.campaign_id:
        raise HTTPException(422, "Creative campaign does not match the route.")
    value = create_creative(db, owner, data)
    return {
        "id": value.id,
        "campaign_id": value.campaign_id,
        "creative_type": value.creative_type,
        "approval_status": value.approval_status,
        "exact_lineage": value.exact_lineage_json,
        "fingerprint": value.fingerprint,
        "destination_url": value.destination_url,
        "readiness": value.readiness_json,
    }


@router.post("/campaigns/{campaign_id}/budget/preview")
def budget_preview(
    campaign_id: uuid.UUID, data: AdsBudgetPreview, db: DB, owner: Owner
) -> dict[str, object]:
    return budget_change_preview(db, owner, _campaign(db, owner, campaign_id), data)


@router.post("/campaigns/{campaign_id}/budget/confirm")
def budget_confirm(
    campaign_id: uuid.UUID, data: AdsBudgetConfirm, db: DB, owner: Owner
) -> dict[str, object]:
    budget, job = confirm_budget_change(db, owner, _campaign(db, owner, campaign_id), data)
    db.commit()
    return {
        "budget": {"id": budget.id, "version": budget.version, "confirmed": budget.confirmed},
        "job": {"id": job.id, "status": job.status},
    }


@router.post("/jobs/{job_id}/run")
def job_run(job_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    job = db.scalar(select(AdJob).where(AdJob.id == job_id, AdJob.owner_id == owner.id))
    if not job:
        raise HTTPException(404, "Ads job not found.")
    result = (
        run_next_ads_job(db, owner_id=owner.id) if job.status in {"queued", "retry_wait"} else job
    )
    if result is None:
        result = job
    return {
        "id": result.id,
        "status": result.status,
        "result": result.result_json,
        "failure_code": result.failure_code,
        "safe_failure_message": result.safe_failure_message,
    }


@router.get("/jobs")
def job_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "id": job.id,
            "operation": job.operation,
            "provider": job.provider,
            "status": job.status,
            "attempt_count": job.attempt_count,
            "result": job.result_json,
            "failure_code": job.failure_code,
            "safe_failure_message": job.safe_failure_message,
        }
        for job in db.scalars(
            select(AdJob).where(AdJob.owner_id == owner.id).order_by(AdJob.created_at.desc())
        )
    ]


@router.post("/campaigns/{campaign_id}/metrics/import")
def metrics_import(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "metric_key": value.metric_key,
            "value": float(value.value or 0),
            "availability": value.availability,
            "source": value.source,
            "observed_at": value.observed_at,
        }
        for value in import_metrics(db, owner, _campaign(db, owner, campaign_id))
    ]


@router.get("/campaigns/{campaign_id}/metrics")
def metrics_list(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    _campaign(db, owner, campaign_id)
    return [
        {
            "metric_key": value.metric_key,
            "value": float(value.value or 0),
            "availability": value.availability,
            "source": value.source,
            "observed_at": value.observed_at,
        }
        for value in db.scalars(
            select(AdMetric)
            .where(AdMetric.owner_id == owner.id, AdMetric.campaign_id == campaign_id)
            .order_by(AdMetric.observed_at.desc())
        )
    ]


@router.post("/campaigns/{campaign_id}/conversions", status_code=201)
def conversion_create(
    campaign_id: uuid.UUID, data: AdsConversionCreate, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    value = db.scalar(
        select(AdConversion).where(
            AdConversion.owner_id == owner.id,
            AdConversion.provider_event_id == data.provider_event_id,
        )
    )
    if value is None:
        value = AdConversion(
            owner_id=owner.id,
            provider=campaign.provider,
            provider_event_id=data.provider_event_id,
            campaign_id=campaign.id,
            product_id=campaign.product_id,
            conversion_type=data.conversion_type,
            occurred_at=data.occurred_at,
            value=data.value,
            currency=data.currency.upper() if data.currency else None,
            source=data.source,
            attribution_json={"type": data.attribution_type, "window": data.attribution_window},
            attribution_type=data.attribution_type,
            attribution_window=data.attribution_window,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(value)
        db.commit()
        db.refresh(value)
    return {
        "id": value.id,
        "campaign_id": value.campaign_id,
        "value": value.value,
        "currency": value.currency,
        "attribution_type": value.attribution_type,
        "attribution_window": value.attribution_window,
    }


@router.get("/campaigns/{campaign_id}/analytics")
def campaign_analytics(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    spend = db.scalar(
        select(func.sum(AdMetric.value)).where(
            AdMetric.owner_id == owner.id,
            AdMetric.campaign_id == campaign.id,
            AdMetric.metric_key == "spend",
        )
    )
    revenue = db.scalar(
        select(func.sum(AdConversion.value)).where(
            AdConversion.owner_id == owner.id, AdConversion.campaign_id == campaign.id
        )
    )
    spend_value = float(spend) if spend is not None else None
    revenue_value = float(revenue) if revenue is not None else None
    currency = db.scalar(
        select(AdBudget.currency)
        .where(AdBudget.campaign_id == campaign.id)
        .order_by(AdBudget.version.desc())
    )
    conversion_currencies = {
        value
        for value in db.scalars(
            select(AdConversion.currency).where(
                AdConversion.owner_id == owner.id, AdConversion.campaign_id == campaign.id
            )
        )
        if value
    }
    currency_compatible = (
        not currency or not conversion_currencies or conversion_currencies == {currency}
    )
    product = (
        db.scalar(
            select(Product).where(Product.id == campaign.product_id, Product.owner_id == owner.id)
        )
        if campaign.product_id
        else None
    )
    cogs_value: float | None = None
    commerce_revenue: float | None = None
    commerce_currency: str | None = None
    if product is not None and product.cost_amount is not None:
        item_rows = list(
            db.execute(
                select(MarketplaceOrderItem, MarketplaceOrder)
                .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceOrderItem.order_id)
                .where(
                    MarketplaceOrderItem.owner_id == owner.id,
                    MarketplaceOrderItem.product_id == product.id,
                    MarketplaceOrder.owner_id == owner.id,
                )
            )
        )
        if item_rows:
            quantity = sum(int(item.quantity or 0) for item, _order in item_rows)
            cogs_value = float(product.cost_amount) * quantity
            commerce_revenue = sum(float(item.total_price or 0) for item, _order in item_rows)
            currencies = {
                str((order.totals_json or {}).get("currency"))
                for _item, order in item_rows
                if isinstance(order.totals_json, dict) and order.totals_json.get("currency")
            }
            if len(currencies) == 1:
                commerce_currency = next(iter(currencies))
    fee_value: float | None = None
    fee_currency: str | None = None
    fee_rows = list(db.scalars(select(MarketplaceFee).where(MarketplaceFee.owner_id == owner.id)))
    if fee_rows:
        fee_currencies = {row.currency for row in fee_rows if row.currency}
        if len(fee_currencies) == 1:
            fee_currency = next(iter(fee_currencies))
            fee_value = sum(float(row.amount or 0) for row in fee_rows)
    same_currency = (not currency or not commerce_currency or commerce_currency == currency) and (
        not currency or not fee_currency or fee_currency == currency
    )
    profitability: float | str = "Unavailable"
    if (
        commerce_revenue is not None
        and cogs_value is not None
        and fee_value is not None
        and spend_value is not None
        and same_currency
    ):
        profitability = commerce_revenue - cogs_value - fee_value - spend_value
    roas = (
        (revenue_value / spend_value)
        if currency_compatible and revenue_value is not None and spend_value and spend_value > 0
        else None
    )
    return {
        "campaign_id": campaign.id,
        "spend": spend_value,
        "revenue": revenue_value,
        "currency": currency,
        "roas": roas,
        "currency_compatible": currency_compatible and same_currency,
        "cogs": cogs_value,
        "marketplace_fees": fee_value,
        "profitability": profitability,
        "profit_status": "available" if isinstance(profitability, float) else "unavailable",
        "attribution": "deterministic local fixtures only",
    }


@router.get("/failures/catalog")
def failure_catalog() -> dict[str, dict[str, object]]:
    # Preserve the Slice 1 public catalog; optimization-specific codes are
    # exposed by the optimization catalog below without changing that contract.
    return {
        key: value
        for key, value in ADS_FAILURE_TAXONOMY.items()
        if not key.startswith("ads.optimization_")
        and key
        not in {
            "ads.rule_invalid",
            "ads.guardrail_blocked",
            "ads.insufficient_data",
            "ads.experiment_invalid",
            "ads.rollback_conflict",
        }
    }


@router.get("/optimization/failures/catalog")
def optimization_failure_catalog() -> dict[str, dict[str, object]]:
    return ADS_OPTIMIZATION_FAILURE_TAXONOMY


@router.get("/recovery")
def recovery_projection(db: DB, owner: Owner) -> list[dict[str, object]]:
    """Return a safe, complete projection for every normalized failure code."""
    records = list(
        db.scalars(
            select(AdFailureRecord)
            .where(AdFailureRecord.owner_id == owner.id)
            .order_by(AdFailureRecord.created_at.desc())
        )
    )
    latest = {record.code: record for record in records}
    projection: list[dict[str, object]] = []
    for code, spec in ADS_FAILURE_TAXONOMY.items():
        record = latest.get(code)
        projection.append(
            {
                "failure_code": code,
                "safe_message": spec["safe_message"],
                "retryable": bool(spec["retryable"]),
                "recovery_actions": list(cast(list[object], spec["recovery_actions"])),
                "provider": record.provider if record else None,
                "entity_type": record.entity_type if record else None,
                "entity_id": record.entity_id if record else None,
                "correlation_id": record.correlation_id if record else None,
                "observed": record is not None,
            }
        )
    return projection


@router.post("/recovery")
def recovery(data: AdsRecoveryRequest, db: DB, owner: Owner) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required for Ads recovery.")
    if data.failure_code:
        spec = ADS_FAILURE_TAXONOMY.get(data.failure_code)
        if spec is None:
            raise HTTPException(422, "The Ads failure code is not recognized.")
        actions = cast(list[object], spec["recovery_actions"])
        if data.action not in actions:
            raise HTTPException(
                422, "The requested recovery action is not allowed for this failure."
            )
    key = data.idempotency_key or f"{data.action}:{data.entity_type}:{data.entity_id}"
    correlation_id = data.correlation_id or uuid.uuid4().hex
    existing = db.scalar(
        select(AdRecoveryRecord).where(
            AdRecoveryRecord.owner_id == owner.id, AdRecoveryRecord.idempotency_key == key
        )
    )
    if existing is not None:
        return {**existing.result_json, "idempotent_reuse": True, "recovery_id": existing.id}

    campaign: AdCampaign | None = None
    if data.entity_type == "campaign":
        campaign = _campaign(db, owner, data.entity_id)
    elif data.entity_type == "group":
        group = db.scalar(
            select(AdGroup).where(AdGroup.id == data.entity_id, AdGroup.owner_id == owner.id)
        )
        if group is None:
            raise HTTPException(404, "Ads group not found.")
        campaign = _campaign(db, owner, group.campaign_id)
    elif data.entity_type == "ad":
        ad = db.scalar(select(Ad).where(Ad.id == data.entity_id, Ad.owner_id == owner.id))
        if ad is None:
            raise HTTPException(404, "Ads ad not found.")
        campaign = _campaign(db, owner, ad.campaign_id)
    else:
        creative = db.scalar(
            select(AdCreative).where(
                AdCreative.id == data.entity_id, AdCreative.owner_id == owner.id
            )
        )
        if creative is None:
            raise HTTPException(404, "Ads creative not found.")
        campaign = _campaign(db, owner, creative.campaign_id)

    status = "accepted"
    job_id: uuid.UUID | None = None
    if data.action == "reconcile" and campaign is not None:
        remote = connector_for(campaign.provider).lookup(
            "campaign",
            campaign.remote_campaign_id
            or connector_for(campaign.provider)._remote_id("campaign", str(campaign.id)),
        )
        campaign.reconciliation_state = "matched" if remote else "review_required"
        campaign.updated_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        status = "succeeded"
    elif data.action in {"retry", "pause", "resume", "change_budget"} and campaign is not None:
        operation: str = data.action
        if operation == "retry":
            prior = db.scalar(
                select(AdJob)
                .where(
                    AdJob.owner_id == owner.id,
                    AdJob.entity_id == data.entity_id,
                    AdJob.status.in_(["failed", "retry_wait"]),
                )
                .order_by(AdJob.created_at.desc())
            )
            operation = prior.operation if prior else "create_campaign"
        job = queue_job(
            db,
            owner,
            campaign,
            operation,
            f"recovery:{key}",
            {"recovery_key": key, "action": data.action},
            entity_type=data.entity_type,
            entity_id=data.entity_id,
        )
        job_id = job.id
        status = "queued"

    result = {
        "status": status,
        "action": data.action,
        "entity_type": data.entity_type,
        "entity_id": str(data.entity_id),
        "provider": campaign.provider if campaign else None,
        "safe_message": "Ads recovery action recorded safely.",
        "failure_code": data.failure_code,
        "correlation_id": correlation_id,
        "job_id": str(job_id) if job_id is not None else None,
    }
    record = AdRecoveryRecord(
        owner_id=owner.id,
        action=data.action,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        status=status,
        idempotency_key=key,
        result_json=result,
        correlation_id=correlation_id,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    db.add(record)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.recovery_recorded",
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        metadata={"action": data.action, "correlation_id": correlation_id, "status": status},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AdRecoveryRecord).where(
                AdRecoveryRecord.owner_id == owner.id,
                AdRecoveryRecord.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        return {**existing.result_json, "recovery_id": existing.id, "idempotent_reuse": True}
    return {**result, "recovery_id": record.id, "idempotent_reuse": False}


@router.get("/product-channel/{product_id}")
def product_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaigns = list(
        db.scalars(
            select(AdCampaign)
            .where(AdCampaign.owner_id == owner.id, AdCampaign.product_id == product_id)
            .order_by(AdCampaign.created_at.desc())
        )
    )
    result = []
    for campaign in campaigns:
        groups = list(
            db.scalars(
                select(AdGroup).where(
                    AdGroup.owner_id == owner.id, AdGroup.campaign_id == campaign.id
                )
            )
        )
        ads = list(
            db.scalars(select(Ad).where(Ad.owner_id == owner.id, Ad.campaign_id == campaign.id))
        )
        creatives = list(
            db.scalars(
                select(AdCreative).where(
                    AdCreative.owner_id == owner.id, AdCreative.campaign_id == campaign.id
                )
            )
        )
        account = db.get(AdAccount, campaign.account_id)
        budget = db.scalar(
            select(AdBudget)
            .where(AdBudget.campaign_id == campaign.id)
            .order_by(AdBudget.version.desc())
        )
        latest_metric_rows = list(
            db.scalars(
                select(AdMetric).where(
                    AdMetric.owner_id == owner.id, AdMetric.campaign_id == campaign.id
                )
            )
        )
        latest_metrics = {row.metric_key: row.value for row in latest_metric_rows}
        failure = db.scalar(
            select(AdFailureRecord)
            .where(AdFailureRecord.owner_id == owner.id, AdFailureRecord.entity_id == campaign.id)
            .order_by(AdFailureRecord.created_at.desc())
        )
        actions: list[str] = []
        if not ads:
            actions.extend(["create_ad", "open_campaign", "preview_ad"])
        elif campaign.state == "active":
            actions.extend(["pause", "preview_budget_change", "preview_creative_replacement"])
        elif campaign.state == "paused":
            actions.append("resume")
        elif campaign.state == "failed":
            actions.append("open_recovery")
        if campaign.reconciliation_state == "review_required":
            actions.append("reconcile")
        current_creative_ids = {ad.creative_id for ad in ads}
        update_available = any(creative.id not in current_creative_ids for creative in creatives)
        result.append(
            {
                "campaign": campaign_response(campaign),
                "account": account_response(account) if account else None,
                "budget": (
                    {
                        "version": budget.version,
                        "daily_amount": budget.daily_amount,
                        "lifetime_amount": budget.lifetime_amount,
                        "currency": budget.currency,
                        "confirmed": budget.confirmed,
                        "remote_version": budget.remote_version,
                    }
                    if budget
                    else None
                ),
                "metrics": latest_metrics,
                "actions": actions,
                "groups": [
                    {
                        "id": group.id,
                        "name": group.name,
                        "state": group.state,
                        "remote_id": group.remote_group_id,
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
                "creatives": [
                    {
                        "id": creative.id,
                        "type": creative.creative_type,
                        "version": creative.artifact_version
                        or creative.image_version
                        or creative.video_version,
                        "readiness": creative.readiness_json,
                    }
                    for creative in creatives
                ],
                "update_available": update_available,
                "drift": campaign.reconciliation_state == "review_required",
                "failure": (
                    {
                        "code": failure.code,
                        "safe_message": failure.safe_message,
                        "correlation_id": failure.correlation_id,
                    }
                    if failure
                    else None
                ),
                "recovery": {"available": bool(failure) or campaign.state == "failed"},
            }
        )
    return {"product_id": product_id, "providers": result, "synthetic": True}


@router.post("/campaigns/{campaign_id}/schedule", status_code=201)
def schedule_create(
    campaign_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    raw_start = payload.get("start_at")
    if not raw_start:
        raise HTTPException(422, "An exact Ads schedule start is required.")
    try:
        start_at = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
        end_at = (
            datetime.fromisoformat(str(payload["end_at"]).replace("Z", "+00:00"))
            if payload.get("end_at")
            else None
        )
    except ValueError:
        raise HTTPException(422, "The Ads schedule timestamp is invalid.") from None
    if end_at is not None and end_at <= start_at:
        raise HTTPException(422, "The Ads schedule end must be after its start.")
    timezone_name = str(payload.get("timezone") or campaign.timezone_name)
    row = db.scalar(
        select(AdSchedule).where(
            AdSchedule.owner_id == owner.id,
            AdSchedule.campaign_id == campaign.id,
            AdSchedule.start_at == start_at,
        )
    )
    if row is None:
        row = AdSchedule(
            owner_id=owner.id,
            campaign_id=campaign.id,
            start_at=start_at,
            end_at=end_at,
            timezone_name=timezone_name,
            state=str(payload.get("state") or "scheduled"),
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "provider": campaign.provider,
        "product_id": campaign.product_id,
        "start_at": row.start_at,
        "end_at": row.end_at,
        "timezone": row.timezone_name,
        "state": row.state,
    }


@router.get("/calendar")
def ads_calendar(db: DB, owner: Owner) -> list[dict[str, object]]:
    schedules = list(
        db.scalars(
            select(AdSchedule).where(AdSchedule.owner_id == owner.id).order_by(AdSchedule.start_at)
        )
    )
    campaigns: dict[uuid.UUID, AdCampaign] = {
        campaign.id: campaign
        for campaign in db.scalars(select(AdCampaign).where(AdCampaign.owner_id == owner.id))
    }
    budgets: dict[uuid.UUID, AdBudget] = {}
    for budget in db.scalars(
        select(AdBudget).where(AdBudget.owner_id == owner.id).order_by(AdBudget.version.desc())
    ):
        budgets.setdefault(budget.campaign_id, budget)
    result: list[dict[str, object]] = []
    for row in schedules:
        campaign = campaigns.get(row.campaign_id)
        current_budget = budgets.get(row.campaign_id)
        groups = (
            list(
                db.scalars(
                    select(AdGroup).where(
                        AdGroup.owner_id == owner.id, AdGroup.campaign_id == row.campaign_id
                    )
                )
            )
            if campaign
            else []
        )
        ads = (
            list(
                db.scalars(
                    select(Ad).where(Ad.owner_id == owner.id, Ad.campaign_id == row.campaign_id)
                )
            )
            if campaign
            else []
        )
        creatives = {
            creative.id: creative
            for creative in db.scalars(
                select(AdCreative).where(
                    AdCreative.owner_id == owner.id, AdCreative.campaign_id == row.campaign_id
                )
            )
        }
        result.append(
            {
                "id": row.id,
                "campaign_id": row.campaign_id,
                "campaign": campaign.name if campaign else None,
                "provider": campaign.provider if campaign else None,
                "product_id": campaign.product_id if campaign else None,
                "group_ids": [group.id for group in groups],
                "ad_ids": [ad.id for ad in ads],
                "creative_ids": [ad.creative_id for ad in ads],
                "creative_versions": [
                    (
                        creatives[ad.creative_id].artifact_version
                        or creatives[ad.creative_id].image_version
                        or creatives[ad.creative_id].video_version
                    )
                    for ad in ads
                    if ad.creative_id in creatives
                ],
                "budget_version": current_budget.version if current_budget else None,
                "start_at": row.start_at,
                "end_at": row.end_at,
                "timezone": row.timezone_name,
                "budget": current_budget.daily_amount if current_budget else None,
                "currency": current_budget.currency if current_budget else None,
                "state": row.state,
                "failure": campaign.safe_failure_message if campaign else None,
                "recovery": {"available": campaign.state == "failed"} if campaign else None,
            }
        )
    return result


@router.get("/storage/integrity")
def storage_integrity(db: DB, owner: Owner) -> dict[str, object]:
    """Return exact owner-scoped duplicate, orphan, and lineage counters."""

    def count(model: Any) -> int:
        statement = select(func.count()).select_from(model).where(model.owner_id == owner.id)
        return int(db.execute(statement).scalar_one() or 0)

    def duplicate_count(model: Any, *columns: Any) -> int:
        rows = db.execute(
            select(*columns, func.count())
            .where(model.owner_id == owner.id)
            .group_by(*columns)
            .having(func.count() > 1)
        ).all()
        return len(rows)

    accounts = list(db.scalars(select(AdAccount).where(AdAccount.owner_id == owner.id)))
    campaigns = list(db.scalars(select(AdCampaign).where(AdCampaign.owner_id == owner.id)))
    groups = list(db.scalars(select(AdGroup).where(AdGroup.owner_id == owner.id)))
    ads = list(db.scalars(select(Ad).where(Ad.owner_id == owner.id)))
    creatives = list(db.scalars(select(AdCreative).where(AdCreative.owner_id == owner.id)))
    mappings = list(db.scalars(select(AdRemoteMapping).where(AdRemoteMapping.owner_id == owner.id)))
    jobs = list(db.scalars(select(AdJob).where(AdJob.owner_id == owner.id)))
    schedules = list(db.scalars(select(AdSchedule).where(AdSchedule.owner_id == owner.id)))
    account_ids = {value.id for value in accounts}
    campaign_ids = {value.id for value in campaigns}
    group_ids = {value.id for value in groups}
    ad_ids = {value.id for value in ads}
    creative_ids = {value.id for value in creatives}
    broken_group = sum(value.campaign_id not in campaign_ids for value in groups)
    broken_ad = sum(
        value.campaign_id not in campaign_ids or value.group_id not in group_ids for value in ads
    )
    broken_creative = sum(value.campaign_id not in campaign_ids for value in creatives)
    broken_mapping = sum(
        (value.entity_type == "campaign" and value.local_entity_id not in campaign_ids)
        or (value.entity_type == "group" and value.local_entity_id not in group_ids)
        or (value.entity_type == "ad" and value.local_entity_id not in ad_ids)
        or (value.entity_type == "creative" and value.local_entity_id not in creative_ids)
        for value in mappings
    )
    broken_job = sum(
        (value.entity_type == "campaign" and value.entity_id not in campaign_ids)
        or (value.entity_type == "group" and value.entity_id not in group_ids)
        or (value.entity_type == "ad" and value.entity_id not in ad_ids)
        for value in jobs
    )
    broken_calendar = sum(value.campaign_id not in campaign_ids for value in schedules)
    broken_product = sum(value.product_id is None for value in campaigns + creatives + ads)
    broken_provider = sum(
        value.provider
        != next(
            (campaign.provider for campaign in campaigns if campaign.id == value.campaign_id),
            value.provider,
        )
        for value in ads
    )
    duplicate_jobs = duplicate_count(AdJob, AdJob.owner_id, AdJob.idempotency_key)
    return {
        "counts": {
            "ad_accounts": len(accounts),
            "ad_campaigns": len(campaigns),
            "ad_groups": len(groups),
            "ads": len(ads),
            "ad_creatives": len(creatives),
            "remote_mappings": len(mappings),
            "jobs": len(jobs),
        },
        "duplicates": {
            "ad_account": duplicate_count(
                AdAccount, AdAccount.owner_id, AdAccount.provider, AdAccount.external_account_id
            ),
            "ad_campaign": duplicate_count(
                AdCampaign, AdCampaign.owner_id, AdCampaign.idempotency_key
            ),
            "ad_group": duplicate_count(
                AdGroup, AdGroup.owner_id, AdGroup.campaign_id, AdGroup.idempotency_key
            ),
            "ad": duplicate_count(Ad, Ad.owner_id, Ad.idempotency_key),
            "creative_mapping": duplicate_count(
                AdCreative, AdCreative.owner_id, AdCreative.idempotency_key
            ),
            "remote_mapping": duplicate_count(
                AdRemoteMapping,
                AdRemoteMapping.owner_id,
                AdRemoteMapping.provider,
                AdRemoteMapping.entity_type,
                AdRemoteMapping.local_entity_id,
            ),
            "logical_job": duplicate_jobs,
        },
        "orphans": {
            "campaign": sum(value.account_id not in account_ids for value in campaigns),
            "group": broken_group,
            "ad": broken_ad,
            "creative": broken_creative,
            "remote_mapping": broken_mapping,
            "job": broken_job,
        },
        "lineage": {
            "broken_product": broken_product,
            "broken_creative": broken_creative,
            "broken_campaign": broken_ad,
            "broken_calendar": broken_calendar,
        },
        "isolation": {"cross_owner": 0, "cross_provider": broken_provider},
        "safe": not any(
            (
                duplicate_jobs,
                broken_group,
                broken_ad,
                broken_creative,
                broken_mapping,
                broken_job,
                broken_calendar,
                broken_product,
                broken_provider,
            )
        ),
    }


@router.get("/history")
def history(
    db: DB, owner: Owner, limit: int = Query(default=100, ge=1, le=500)
) -> list[dict[str, object]]:
    from vayujit_api.audit.models import AuditEvent

    return [
        {
            "action": value.action,
            "entity_type": value.entity_type,
            "entity_id": value.entity_id,
            "created_at": value.occurred_at,
            "metadata": value.metadata_json,
        }
        for value in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.actor_id == owner.id, AuditEvent.action.like("ads.%"))
            .order_by(AuditEvent.occurred_at.desc())
            .limit(limit)
        )
    ]


@router.post("/campaigns/{campaign_id}/groups", status_code=201)
def group_create(
    campaign_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    key = str(
        payload.get("idempotency_key") or f"group:{campaign_id}:{payload.get('name', 'default')}"
    )
    value = db.scalar(
        select(AdGroup).where(
            AdGroup.owner_id == owner.id,
            AdGroup.campaign_id == campaign.id,
            AdGroup.idempotency_key == key,
        )
    )
    audience_id: uuid.UUID | None = None
    if payload.get("audience_id"):
        try:
            audience_id = uuid.UUID(str(payload["audience_id"]))
        except (TypeError, ValueError):
            raise HTTPException(422, "Audience reference is invalid.") from None
        audience = db.scalar(
            select(AdAudience).where(AdAudience.id == audience_id, AdAudience.owner_id == owner.id)
        )
        if audience is None or audience.validation_status != "valid":
            raise HTTPException(422, "Validate the exact Ads audience before using it.")
        provider_status = cast(dict[str, object], audience.provider_compatibility_json).get(
            campaign.provider
        )
        if not isinstance(provider_status, dict) or provider_status.get("status") != "valid":
            raise HTTPException(422, "The Ads audience is not compatible with this provider.")
    if value is None:
        value = AdGroup(
            owner_id=owner.id,
            campaign_id=campaign.id,
            provider_group_type="ad_set" if campaign.provider == "meta" else "ad_group",
            name=str(payload.get("name") or "Default group"),
            state="approved",
            audience_id=audience_id,
            placements_json=list(payload.get("placements") or []),
            targeting_json=dict(payload.get("targeting") or {}),
            idempotency_key=key,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(value)
        db.commit()
        db.refresh(value)
    job = queue_job(
        db,
        owner,
        campaign,
        "create_group",
        key,
        {"group_id": str(value.id)},
        entity_type="group",
        entity_id=value.id,
    )
    return {
        "id": value.id,
        "campaign_id": value.campaign_id,
        "provider_group_type": value.provider_group_type,
        "name": value.name,
        "state": value.state,
        "remote_group_id": value.remote_group_id,
        "targeting": value.targeting_json,
        "job_id": job.id,
    }


@router.post("/groups/{group_id}/ads", status_code=201)
def ad_create(
    group_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    group = db.scalar(select(AdGroup).where(AdGroup.id == group_id, AdGroup.owner_id == owner.id))
    if group is None:
        raise HTTPException(404, "Ads group not found.")
    campaign = _campaign(db, owner, group.campaign_id)
    creative_id = uuid.UUID(str(payload.get("creative_id"))) if payload.get("creative_id") else None
    creative = (
        db.scalar(
            select(AdCreative).where(AdCreative.id == creative_id, AdCreative.owner_id == owner.id)
        )
        if creative_id
        else None
    )
    if creative is None:
        raise HTTPException(422, "An approved exact creative is required.")
    if creative.campaign_id != campaign.id or creative.product_id != campaign.product_id:
        raise HTTPException(422, "Creative lineage does not match the Ads campaign.")
    if creative.approval_status != "approved":
        raise HTTPException(422, "An approved exact creative is required.")
    provider = str(payload.get("provider") or campaign.provider)
    if provider != campaign.provider:
        raise HTTPException(422, "Ad provider must match the Campaign provider.")
    placement = str(payload.get("placement") or "feed")
    if placement not in connector_for(campaign.provider).capabilities().get("placements", []):
        raise HTTPException(422, "The selected placement is unsupported by this provider.")
    key = str(payload.get("idempotency_key") or f"ad:{group.id}:{creative.id}")
    value = db.scalar(select(Ad).where(Ad.owner_id == owner.id, Ad.idempotency_key == key))
    if value is None:
        value = Ad(
            owner_id=owner.id,
            campaign_id=group.campaign_id,
            group_id=group.id,
            creative_id=creative.id,
            product_id=creative.product_id,
            provider=provider,
            placement=placement,
            state="approved",
            idempotency_key=key,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(value)
        db.commit()
        db.refresh(value)
    job = queue_job(
        db,
        owner,
        campaign,
        "create_ad",
        key,
        {"ad_id": str(value.id)},
        entity_type="ad",
        entity_id=value.id,
    )
    return {
        "id": value.id,
        "campaign_id": value.campaign_id,
        "group_id": value.group_id,
        "creative_id": value.creative_id,
        "provider": value.provider,
        "placement": value.placement,
        "state": value.state,
        "remote_ad_id": value.remote_ad_id,
        "job_id": job.id,
    }


@router.post("/campaigns/{campaign_id}/ads/{ad_id}/creative/preview")
@router.post("/campaigns/{campaign_id}/creative-replacement/preview")
def creative_replacement_preview(
    campaign_id: uuid.UUID, ad_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    ad = db.scalar(
        select(Ad).where(Ad.id == ad_id, Ad.owner_id == owner.id, Ad.campaign_id == campaign.id)
    )
    if ad is None:
        raise HTTPException(404, "Ads ad not found.")
    raw_id = payload.get("creative_id") or payload.get("replacement_creative_id")
    try:
        creative_id = uuid.UUID(str(raw_id))
    except (TypeError, ValueError):
        raise HTTPException(422, "An exact replacement creative is required.") from None
    creative = db.scalar(
        select(AdCreative).where(
            AdCreative.id == creative_id,
            AdCreative.owner_id == owner.id,
            AdCreative.campaign_id == campaign.id,
            AdCreative.approval_status == "approved",
        )
    )
    if creative is None or creative.product_id != campaign.product_id:
        raise HTTPException(422, "The exact approved replacement creative is unavailable.")
    if creative.id == ad.creative_id:
        raise HTTPException(422, "The replacement creative must differ from the active creative.")
    request = {
        "campaign_id": str(campaign.id),
        "ad_id": str(ad.id),
        "current_creative_id": str(ad.creative_id),
        "replacement_creative_id": str(creative.id),
        "replacement_fingerprint": creative.fingerprint,
    }
    return {
        "mutates": False,
        "fingerprint": __import__("hashlib")
        .sha256(__import__("json").dumps(request, sort_keys=True, default=str).encode())
        .hexdigest(),
        "current_creative_id": ad.creative_id,
        "replacement_creative_id": creative.id,
        "warnings": ["Synthetic local Ads preview; no connector mutation."],
    }


@router.post("/campaigns/{campaign_id}/ads/{ad_id}/creative/confirm")
@router.post("/campaigns/{campaign_id}/creative-replacement/confirm")
def creative_replacement_confirm(
    campaign_id: uuid.UUID, ad_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    if not payload.get("confirm"):
        raise HTTPException(422, "Explicit confirmation is required for creative replacement.")
    key = str(payload.get("idempotency_key") or "")
    if key:
        existing = db.scalar(
            select(AdJob).where(AdJob.owner_id == owner.id, AdJob.idempotency_key == key)
        )
        if existing is not None:
            return {
                "status": existing.status,
                "job_id": existing.id,
                "ad_id": ad_id,
                "idempotent_reuse": True,
            }
    preview = creative_replacement_preview(campaign_id, ad_id, payload, db, owner)
    supplied = str(payload.get("preview_fingerprint") or "")
    if supplied != preview["fingerprint"]:
        raise HTTPException(
            409, "The creative replacement preview is stale; generate a new preview."
        )
    key = str(
        payload.get("idempotency_key")
        or f"replace_creative:{ad_id}:{preview['replacement_creative_id']}"
    )
    campaign = _campaign(db, owner, campaign_id)
    job = queue_job(
        db,
        owner,
        campaign,
        "replace_creative",
        key,
        {
            "creative_id": str(preview["replacement_creative_id"]),
            "current_creative_id": str(preview["current_creative_id"]),
            "preview_fingerprint": supplied,
        },
        entity_type="ad",
        entity_id=ad_id,
    )
    return {
        "status": job.status,
        "job_id": job.id,
        "ad_id": ad_id,
        "current_creative_id": preview["current_creative_id"],
        "replacement_creative_id": preview["replacement_creative_id"],
        "idempotent_reuse": job.idempotency_key == key and job.attempt_count > 0,
    }


@router.post("/campaigns/{campaign_id}/reconcile")
def campaign_reconcile(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    connector = connector_for(campaign.provider)
    remote_key = campaign.remote_campaign_id or connector._remote_id("campaign", str(campaign.id))
    remote = connector.lookup("campaign", remote_key)
    findings: list[dict[str, object]] = []
    if remote is not None and campaign.remote_campaign_id is None:
        campaign.remote_campaign_id = str(remote["remote_id"])
        campaign.sync_state = "synchronized"
        mapping = db.scalar(
            select(AdRemoteMapping).where(
                AdRemoteMapping.owner_id == owner.id,
                AdRemoteMapping.provider == campaign.provider,
                AdRemoteMapping.entity_type == "campaign",
                AdRemoteMapping.local_entity_id == campaign.id,
            )
        )
        if mapping is None:
            db.add(
                AdRemoteMapping(
                    owner_id=owner.id,
                    provider=campaign.provider,
                    entity_type="campaign",
                    local_entity_id=campaign.id,
                    remote_id=str(remote["remote_id"]),
                    remote_state_json=remote,
                    last_reconciled_at=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                    created_at=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                    updated_at=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                )
            )
    if remote is None:
        findings.append(
            {
                "entity_type": "campaign",
                "entity_id": campaign.id,
                "field": "existence",
                "local": True,
                "remote": False,
            }
        )
    else:
        if remote.get("state") != campaign.state and campaign.state not in {"approved", "draft"}:
            findings.append(
                {
                    "entity_type": "campaign",
                    "entity_id": campaign.id,
                    "field": "state",
                    "local": campaign.state,
                    "remote": remote.get("state"),
                }
            )
    for finding in findings:
        db.add(
            AdDriftFinding(
                owner_id=owner.id,
                campaign_id=campaign.id,
                entity_type=str(finding["entity_type"]),
                entity_id=campaign.id,
                field_name=str(finding["field"]),
                local_value_json=finding["local"],
                remote_value_json=finding["remote"],
                state="open",
                created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        )
    campaign.reconciliation_state = "matched" if not findings else "review_required"
    campaign.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
    return {
        "campaign_id": campaign.id,
        "state": campaign.reconciliation_state,
        "findings": findings,
        "drift": findings,
        "synthetic": True,
    }


@router.post("/campaigns/{campaign_id}/drift/{finding_id}/action")
def drift_action(
    campaign_id: uuid.UUID, finding_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    finding = db.scalar(
        select(AdDriftFinding).where(
            AdDriftFinding.id == finding_id,
            AdDriftFinding.owner_id == owner.id,
            AdDriftFinding.campaign_id == campaign.id,
        )
    )
    if finding is None:
        raise HTTPException(404, "Ads drift finding not found.")
    action = str(payload.get("action") or "review")
    if action == "overwrite_remote" and not payload.get("confirm"):
        raise HTTPException(
            422, "Explicit confirmation is required before overwriting remote Ads state."
        )
    if action not in {"refresh_remote", "keep_remote", "overwrite_remote", "review"}:
        raise HTTPException(422, "Unsupported Ads drift action.")
    finding.state = "resolved" if action != "review" else "open"
    finding.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
    return {
        "finding_id": finding.id,
        "action": action,
        "state": finding.state,
        "safe_message": "Ads drift action recorded safely.",
    }


@router.post("/campaigns/{campaign_id}/action")
def campaign_action(
    campaign_id: uuid.UUID, payload: dict[str, Any], db: DB, owner: Owner
) -> dict[str, object]:
    campaign = _campaign(db, owner, campaign_id)
    if not payload.get("confirm"):
        raise HTTPException(422, "Explicit confirmation is required for Ads mutations.")
    action = str(payload.get("action") or "")
    if action not in {"pause", "resume", "archive"}:
        raise HTTPException(422, "Unsupported Ads campaign action.")
    job = queue_job(
        db,
        owner,
        campaign,
        action,
        str(payload.get("idempotency_key") or f"{action}:{campaign.id}"),
        {"action": action},
    )
    return {"job_id": job.id, "status": job.status, "action": action}
