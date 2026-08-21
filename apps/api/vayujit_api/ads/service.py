from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.ads.connectors import AdsConnectorError, connector_for
from vayujit_api.ads.failure import failure_spec
from vayujit_api.ads.models import (
    Ad,
    AdAccount,
    AdAudience,
    AdBudget,
    AdCampaign,
    AdCreative,
    AdFailureRecord,
    AdGroup,
    AdJob,
    AdMarketplaceListing,
    AdMetric,
    AdOptimizationExecution,
    AdRemoteMapping,
)
from vayujit_api.ads.schemas import (
    AdsAccountCreate,
    AdsAccountUpdate,
    AdsCampaignCreate,
    AdsCreativeCreate,
)
from vayujit_api.ads.validation import require_creative_readiness
from vayujit_api.ai.credentials import encrypt_credential
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.studio_models import KeywordSet
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User


def now() -> datetime:
    return datetime.now(UTC)


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def safe_destination(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise HTTPException(422, "Destination URL must be a safe HTTPS URL.")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise HTTPException(422, "Local destination URLs are not allowed.")
    return value


def account_response(value: AdAccount) -> dict[str, object]:
    return {
        "id": value.id,
        "provider": value.provider,
        "external_account_id": value.external_account_id,
        "display_name": value.display_name,
        "environment": value.environment,
        "status": value.status,
        "enabled": value.enabled,
        "validated": value.validated,
        "validation_status": value.validation_status,
        "credential_version": value.credential_version,
        "credential_metadata": value.credential_metadata_json,
        "timezone_name": value.timezone_name,
        "currency": value.currency,
        "capabilities": value.capabilities_json,
        "last_validated_at": value.last_validated_at,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def campaign_response(value: AdCampaign, budget: AdBudget | None = None) -> dict[str, object]:
    return {
        "id": value.id,
        "provider": value.provider,
        "account_id": value.account_id,
        "brand_id": value.brand_id,
        "product_id": value.product_id,
        "marketplace": value.marketplace,
        "listing_id": value.listing_id,
        "listing_version": value.listing_version,
        "listing_state": value.listing_state,
        "name": value.name,
        "objective": value.objective,
        "state": value.state,
        "start_at": value.start_at,
        "end_at": value.end_at,
        "timezone_name": value.timezone_name,
        "bidding_strategy": value.bidding_strategy,
        "targeting_summary": value.targeting_summary_json,
        "remote_campaign_id": value.remote_campaign_id,
        "sync_state": value.sync_state,
        "reconciliation_state": value.reconciliation_state,
        "preview_fingerprint": value.preview_fingerprint,
        "failure_code": value.failure_code,
        "safe_failure_message": value.safe_failure_message,
        "budget": (
            None
            if budget is None
            else {
                "version": budget.version,
                "daily_amount": budget.daily_amount,
                "lifetime_amount": budget.lifetime_amount,
                "currency": budget.currency,
                "confirmed": budget.confirmed,
            }
        ),
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def create_account(db: Session, owner: User, data: AdsAccountCreate) -> AdAccount:
    connector = connector_for(data.provider)
    timestamp = now()
    encrypted: str | None = None
    if data.credentials:
        raw = json.dumps(data.credentials, sort_keys=True)
        try:
            encrypted = encrypt_credential(raw, get_settings().credential_encryption_key)
        except Exception:
            encrypted = "local-hash:" + hashlib.sha256(raw.encode()).hexdigest()
    value = AdAccount(
        owner_id=owner.id,
        provider=data.provider,
        external_account_id=data.external_account_id.strip(),
        display_name=data.display_name.strip(),
        environment=data.environment,
        status="disabled",
        enabled=False,
        validated=False,
        validation_status="unknown",
        credential_version=1,
        credential_metadata_json={
            "configured": bool(data.credentials),
            "keys": sorted(data.credentials),
        },
        encrypted_credentials=encrypted,
        timezone_name=data.timezone_name,
        currency=data.currency.upper(),
        capabilities_json=connector.capabilities(),
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.account_created",
        entity_type="ad_account",
        entity_id=value.id,
        metadata={"provider": value.provider},
    )
    db.commit()
    db.refresh(value)
    return value


def update_account(db: Session, owner: User, value: AdAccount, data: AdsAccountUpdate) -> AdAccount:
    if data.display_name is not None:
        value.display_name = data.display_name.strip()
    if data.currency is not None:
        value.currency = data.currency.upper()
    if data.credentials is not None:
        raw = json.dumps(data.credentials, sort_keys=True)
        try:
            value.encrypted_credentials = encrypt_credential(
                raw, get_settings().credential_encryption_key
            )
        except Exception:
            value.encrypted_credentials = "local-hash:" + hashlib.sha256(raw.encode()).hexdigest()
        value.credential_metadata_json = {"configured": True, "keys": sorted(data.credentials)}
        value.credential_version += 1
        value.validated = False
        value.validation_status = "unknown"
    value.updated_at = now()
    db.commit()
    db.refresh(value)
    return value


def validate_account(db: Session, owner: User, value: AdAccount) -> AdAccount:
    if not value.credential_metadata_json.get("configured"):
        value.validated = False
        value.validation_status = "invalid"
        db.commit()
        raise HTTPException(422, "Ads account credentials are not configured.")
    value.validated = True
    value.validation_status = "valid"
    value.last_validated_at = now()
    value.updated_at = now()
    value.capabilities_json = connector_for(value.provider).capabilities()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.account_validated",
        entity_type="ad_account",
        entity_id=value.id,
        metadata={"provider": value.provider},
    )
    db.commit()
    db.refresh(value)
    return value


def require_account(db: Session, owner: User, account_id: uuid.UUID) -> AdAccount:
    value = db.scalar(
        select(AdAccount).where(AdAccount.id == account_id, AdAccount.owner_id == owner.id)
    )
    if not value:
        raise HTTPException(404, "Ads account not found.")
    return value


def campaign_preview(db: Session, owner: User, data: AdsCampaignCreate) -> dict[str, object]:
    account = require_account(db, owner, data.account_id)
    if account.provider != data.provider:
        raise HTTPException(422, "Ads account provider does not match the campaign provider.")
    if not account.enabled or not account.validated:
        raise HTTPException(
            422, "Ads account must be validated and enabled before campaign creation."
        )
    if data.provider in {"amazon", "flipkart"}:
        if data.marketplace != data.provider:
            raise HTTPException(422, "Marketplace must match the Ads provider.")
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
    capabilities = connector_for(data.provider).capabilities()
    target_type = data.targeting_summary.get("target_type")
    supported_targeting = set(capabilities.get("targeting", []))
    if target_type and target_type not in supported_targeting:
        raise HTTPException(422, "The selected targeting type is unsupported by this provider.")
    if data.provider in {"amazon", "flipkart"} and target_type in {
        "product",
        "category",
        "listing",
    }:
        target_listing_id = data.targeting_summary.get("listing_id")
        if target_listing_id is not None and str(target_listing_id) != str(data.listing_id):
            raise HTTPException(422, "The targeting listing must match the campaign listing.")
    if data.bidding_strategy and data.bidding_strategy not in capabilities.get(
        "bidding_strategies", []
    ):
        raise HTTPException(422, "The selected bidding strategy is unsupported by this provider.")
    if data.provider == "google" and data.keyword_set_id is not None:
        keyword_set = db.scalar(
            select(KeywordSet).where(
                KeywordSet.id == data.keyword_set_id,
                KeywordSet.owner_id == owner.id,
                KeywordSet.archived.is_(False),
            )
        )
        if keyword_set is None:
            raise HTTPException(422, "The exact Google Keyword Set is unavailable.")
        if keyword_set.locale != data.targeting_summary.get("locale", keyword_set.locale):
            raise HTTPException(422, "Keyword Set locale does not match the campaign locale.")
        if not keyword_set.primary_keywords_json and not keyword_set.secondary_keywords_json:
            raise HTTPException(
                422, "Google Search requires positive keywords from the exact Keyword Set."
            )
    audience_id = data.targeting_summary.get("audience_id")
    if audience_id:
        try:
            parsed_audience_id = uuid.UUID(str(audience_id))
        except ValueError:
            raise HTTPException(422, "Audience reference is invalid.") from None
        audience = db.scalar(
            select(AdAudience).where(
                AdAudience.id == parsed_audience_id, AdAudience.owner_id == owner.id
            )
        )
        if audience is None:
            raise HTTPException(422, "The exact Ads audience is unavailable.")
        if audience.validation_status != "valid":
            raise HTTPException(422, "Validate the Ads audience before using it.")

    if data.objective not in capabilities["objectives"]:
        raise HTTPException(422, "The selected Ads objective is unsupported by this provider.")
    if data.budget.currency.upper() not in capabilities["currencies"]:
        raise HTTPException(422, "The selected budget currency is unsupported by this provider.")
    if data.budget.daily_amount is not None and data.budget.daily_amount < 10:
        raise HTTPException(422, "The daily budget is below the local fake-provider minimum.")
    payload = data.model_dump(mode="json")
    return {
        "provider": data.provider,
        "account_id": data.account_id,
        "objective": data.objective,
        "budget": payload["budget"],
        "fingerprint": fingerprint(payload),
        "mutates": False,
        "warnings": ["Synthetic local Ads preview; no live spend."],
        "blockers": [],
    }


def create_campaign(
    db: Session, owner: User, data: AdsCampaignCreate, preview_fingerprint: str | None = None
) -> AdCampaign:
    preview = campaign_preview(db, owner, data)
    if preview_fingerprint is not None and preview_fingerprint != preview["fingerprint"]:
        raise HTTPException(409, "The Ads preview is stale; generate a new preview.")
    timestamp = now()
    campaign = db.scalar(
        select(AdCampaign).where(
            AdCampaign.owner_id == owner.id, AdCampaign.idempotency_key == data.idempotency_key
        )
    )
    if campaign:
        return campaign
    campaign = AdCampaign(
        owner_id=owner.id,
        provider=data.provider,
        account_id=data.account_id,
        brand_id=data.brand_id,
        product_id=data.product_id,
        marketplace=data.marketplace,
        listing_id=data.listing_id,
        listing_version=data.listing_version,
        listing_state=data.listing_state,
        name=data.name,
        objective=data.objective,
        state="approved",
        start_at=data.start_at,
        end_at=data.end_at,
        timezone_name=data.timezone_name,
        bidding_strategy=data.bidding_strategy,
        targeting_summary_json={
            **data.targeting_summary,
            **({"keyword_set_id": str(data.keyword_set_id)} if data.keyword_set_id else {}),
        },
        keyword_set_id=data.keyword_set_id,
        idempotency_key=data.idempotency_key,
        preview_fingerprint=str(preview["fingerprint"]),
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(campaign)
    db.flush()
    budget = AdBudget(
        owner_id=owner.id,
        campaign_id=campaign.id,
        version=1,
        daily_amount=data.budget.daily_amount,
        lifetime_amount=data.budget.lifetime_amount,
        currency=data.budget.currency.upper(),
        effective_from=data.budget.effective_from,
        effective_until=data.budget.effective_until,
        confirmed=True,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(budget)
    record_event(
        db,
        actor_id=owner.id,
        action="ads.campaign_approved",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"provider": campaign.provider},
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def create_creative(db: Session, owner: User, data: AdsCreativeCreate) -> AdCreative:
    campaign = db.scalar(
        select(AdCampaign).where(AdCampaign.id == data.campaign_id, AdCampaign.owner_id == owner.id)
    )
    if not campaign:
        raise HTTPException(404, "Ads campaign not found.")
    destination = safe_destination(data.destination_url)
    readiness = require_creative_readiness(db, owner, data, campaign)
    if data.creative_type == "content" and (
        data.artifact_id is None or data.artifact_version is None
    ):
        raise HTTPException(422, "An exact approved Content Artifact version is required.")
    if data.artifact_id is not None:
        artifact = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == data.artifact_id,
                GeneratedArtifact.owner_id == owner.id,
                GeneratedArtifact.version_number == data.artifact_version,
            )
        )
        if not artifact or artifact.status != "approved":
            raise HTTPException(422, "The exact Content Artifact version must be approved.")
    timestamp = now()
    value = db.scalar(
        select(AdCreative).where(
            AdCreative.owner_id == owner.id, AdCreative.idempotency_key == data.idempotency_key
        )
    )
    if value:
        return value
    lineage = {
        "artifact_id": str(data.artifact_id) if data.artifact_id else None,
        "artifact_version": data.artifact_version,
        "image_output_id": str(data.image_output_id) if data.image_output_id else None,
        "image_version": data.image_version,
        "video_output_id": str(data.video_output_id) if data.video_output_id else None,
        "video_version": data.video_version,
    }
    value = AdCreative(
        owner_id=owner.id,
        campaign_id=campaign.id,
        product_id=data.product_id,
        creative_type=data.creative_type,
        artifact_id=data.artifact_id,
        artifact_version=data.artifact_version,
        image_output_id=data.image_output_id,
        image_media_id=data.image_media_id,
        image_version=data.image_version,
        video_generation_id=data.video_generation_id,
        video_output_id=data.video_output_id,
        video_media_id=data.video_media_id,
        video_version=data.video_version,
        locale=data.locale,
        headline=data.headline,
        primary_text=data.primary_text,
        description=data.description,
        cta=data.cta,
        destination_url=destination,
        exact_lineage_json=lineage,
        approval_status="approved",
        readiness_json=readiness,
        provider_compatibility_json={"provider": campaign.provider},
        objective_compatibility_json=[campaign.objective],
        placements_json=data.placements,
        idempotency_key=data.idempotency_key,
        fingerprint=fingerprint(lineage),
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def queue_job(
    db: Session,
    owner: User,
    campaign: AdCampaign,
    operation: str,
    idempotency_key: str,
    request: dict[str, object],
    entity_type: str = "campaign",
    entity_id: uuid.UUID | None = None,
) -> AdJob:
    job = db.scalar(
        select(AdJob).where(AdJob.owner_id == owner.id, AdJob.idempotency_key == idempotency_key)
    )
    if job:
        return job
    job = AdJob(
        owner_id=owner.id,
        operation=operation,
        entity_type=entity_type,
        entity_id=entity_id or campaign.id,
        provider=campaign.provider,
        status="queued",
        attempt_count=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        request_json=request,
        created_at=now(),
        updated_at=now(),
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AdJob).where(
                AdJob.owner_id == owner.id, AdJob.idempotency_key == idempotency_key
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(job)
    return job


def _sync_optimization_execution(db: Session, job: AdJob) -> None:
    execution = db.scalar(
        select(AdOptimizationExecution).where(AdOptimizationExecution.job_id == job.id)
    )
    if execution is None:
        return
    execution.status = {
        "succeeded": "succeeded",
        "retry_wait": "retry_wait",
        "failed": "failed",
    }.get(job.status, job.status)
    execution.result_json = {
        "job_status": job.status,
        "result": job.result_json,
        "failure_code": job.failure_code,
        "safe_failure_message": job.safe_failure_message,
        "synthetic": True,
    }
    execution.updated_at = now()


def _record_failure(db: Session, job: AdJob) -> None:
    if not job.failure_code:
        return
    spec = failure_spec(job.failure_code)
    correlation_id = job.correlation_id or f"ads-{job.id.hex}"
    job.correlation_id = correlation_id
    existing = db.scalar(
        select(AdFailureRecord).where(
            AdFailureRecord.owner_id == job.owner_id,
            AdFailureRecord.correlation_id == correlation_id,
        )
    )
    if existing is not None:
        return
    db.add(
        AdFailureRecord(
            owner_id=job.owner_id,
            provider=job.provider,
            code=job.failure_code,
            safe_message=job.safe_failure_message or spec["safe_message"],
            retryable=bool(spec["retryable"]),
            recovery_actions_json=list(cast(list[object], spec["recovery_actions"])),
            entity_type=job.entity_type,
            entity_id=job.entity_id,
            correlation_id=correlation_id,
            created_at=now(),
            updated_at=now(),
        )
    )


def run_job(db: Session, job: AdJob, *, worker_id: str | None = None) -> AdJob:
    if job.status == "succeeded":
        return job
    target_group = (
        db.scalar(
            select(AdGroup).where(AdGroup.id == job.entity_id, AdGroup.owner_id == job.owner_id)
        )
        if job.entity_type == "group"
        else None
    )
    target_ad = (
        db.scalar(select(Ad).where(Ad.id == job.entity_id, Ad.owner_id == job.owner_id))
        if job.entity_type == "ad"
        else None
    )
    campaign_id = (
        target_group.campaign_id
        if target_group
        else target_ad.campaign_id if target_ad else job.entity_id
    )
    campaign = db.scalar(
        select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.owner_id == job.owner_id)
    )
    if not campaign:
        job.status = "failed"
        job.failure_code = "ads.remote_not_found"
        job.safe_failure_message = "The local Ads campaign no longer exists."
        job.lease_expires_at = None
        _record_failure(db, job)
        _sync_optimization_execution(db, job)
        db.commit()
        return job
    account = db.scalar(
        select(AdAccount).where(
            AdAccount.id == campaign.account_id, AdAccount.owner_id == job.owner_id
        )
    )
    if not account or not account.enabled:
        job.status = "failed"
        job.failure_code = "ads.account_disabled"
        job.safe_failure_message = "The Ads account is disabled."
        job.lease_expires_at = None
        _record_failure(db, job)
        _sync_optimization_execution(db, job)
        db.commit()
        return job
    budget = None
    if job.operation in {"update_budget", "rollback_budget"}:
        raw_budget_id = job.request_json.get("budget_id")
        budget = (
            db.get(AdBudget, uuid.UUID(str(raw_budget_id)))
            if raw_budget_id
            else db.scalar(
                select(AdBudget)
                .where(
                    AdBudget.owner_id == job.owner_id,
                    AdBudget.campaign_id == campaign.id,
                )
                .order_by(AdBudget.version.desc())
            )
        )
        if budget is None or budget.owner_id != job.owner_id:
            raise HTTPException(404, "Ads budget not found.")
        if not campaign.remote_campaign_id:
            raise HTTPException(422, "Publish the campaign before changing its remote budget.")
    job.status = "running"
    job.attempt_count += 1
    job.lease_expires_at = now() + timedelta(seconds=300)
    job.updated_at = now()
    db.commit()
    try:
        connector = connector_for(campaign.provider)
        checkpoint = (
            job.result_json.get("remote_checkpoint") if isinstance(job.result_json, dict) else None
        )
        if isinstance(checkpoint, dict) and checkpoint.get("remote_id"):
            remote = checkpoint
        elif job.operation == "pause":
            remote = connector.pause_campaign(campaign.remote_campaign_id or "")
        elif job.operation == "resume":
            remote = connector.resume_campaign(campaign.remote_campaign_id or "")
        elif job.operation == "archive":
            remote = connector.archive_campaign(campaign.remote_campaign_id or "")
        elif job.operation in {"update_budget", "rollback_budget"}:
            remote = connector.update_campaign(
                campaign.remote_campaign_id or "",
                {"budget": job.request_json, "budget_version": budget.version if budget else None},
            )
        elif job.operation == "create_group":
            if target_group is None:
                raise HTTPException(422, "The Ads group no longer exists.")
            remote = connector.create_group(
                str(target_group.id),
                {"name": target_group.name, "targeting": target_group.targeting_json},
            )
        elif job.operation == "create_ad":
            if target_ad is None:
                raise HTTPException(422, "The Ads ad no longer exists.")
            remote = connector.create_ad(
                str(target_ad.id),
                {"creative_id": str(target_ad.creative_id), "placement": target_ad.placement},
            )
        elif job.operation in {"replace_creative", "rollback_creative", "adopt_experiment_winner"}:
            if target_ad is None:
                target_ad = db.scalar(
                    select(Ad)
                    .where(
                        Ad.owner_id == job.owner_id,
                        Ad.campaign_id == campaign.id,
                    )
                    .order_by(Ad.created_at.desc())
                )
            if target_ad is None:
                raise HTTPException(422, "The Ads ad no longer exists.")
            raw_creative_id = job.request_json.get("creative_id")
            if not raw_creative_id or not target_ad.remote_ad_id:
                raise HTTPException(422, "The Ads ad is not ready for creative replacement.")
            replacement = db.scalar(
                select(AdCreative).where(
                    AdCreative.id == uuid.UUID(str(raw_creative_id)),
                    AdCreative.owner_id == job.owner_id,
                    AdCreative.campaign_id == campaign.id,
                    AdCreative.approval_status == "approved",
                )
            )
            if replacement is None:
                raise HTTPException(422, "The exact approved replacement creative is unavailable.")
            remote = connector.update_ad(
                target_ad.remote_ad_id,
                {"creative_id": str(replacement.id)},
            )
        else:
            remote = connector.create_campaign(
                str(campaign.id),
                {
                    "name": campaign.name,
                    "objective": campaign.objective,
                    "budget": job.request_json.get("budget"),
                },
            )
    except AdsConnectorError as error:
        resolved_ambiguous = False
        if error.ambiguous:
            # The provider may have committed the mutation before the response
            # was lost. Resolve its deterministic remote identity before retry.
            resolver = connector_for(campaign.provider)
            remote_type = "campaign"
            remote_key = campaign.remote_campaign_id or str(campaign.id)
            if job.operation == "create_group" and target_group is not None:
                remote_type = "group"
                remote_key = str(target_group.id)
            elif (
                job.operation in {"create_ad", "replace_creative", "adopt_experiment_winner"}
                and target_ad is not None
            ):
                remote_type = "ad"
                remote_key = target_ad.remote_ad_id or str(target_ad.id)
            lookup_key = (
                remote_key
                if (remote_type == "ad" and target_ad is not None and target_ad.remote_ad_id)
                else resolver._remote_id(remote_type, remote_key)
            )
            candidate = resolver.lookup(remote_type, lookup_key)
            if candidate is not None:
                remote = candidate
                resolved_ambiguous = True
            else:
                error = AdsConnectorError(error.code, error.safe_message)
        if resolved_ambiguous:
            # A deterministic remote checkpoint was found; continue through
            # the normal local projection path below.
            pass
        elif error.ambiguous:
            job.status = "failed"
            job.failure_code = error.code
            job.safe_failure_message = error.safe_message
            job.failure_category = error.code
            job.lease_expires_at = None
            _record_failure(db, job)
            db.commit()
            return job
        else:
            job.status = (
                "retry_wait"
                if error.retryable and job.attempt_count < job.max_attempts
                else "failed"
            )
            job.failure_code = error.code
            job.safe_failure_message = error.safe_message
            job.retry_after_seconds = error.retry_after_seconds
            job.failure_category = error.code
            if job.status == "retry_wait":
                delay = error.retry_after_seconds or min(300, 2 ** max(job.attempt_count - 1, 0))
                job.next_retry_at = now() + timedelta(seconds=delay)
            else:
                job.next_retry_at = None
            job.lease_expires_at = None
            _record_failure(db, job)
            _sync_optimization_execution(db, job)
            db.commit()
            return job
    except Exception:
        # Preserve the leased job for deterministic recovery after a process crash.
        job.updated_at = now()
        db.commit()
        raise
    # Commit the remote checkpoint before projecting local completion state.
    job.result_json = {"remote_checkpoint": remote, "synthetic": True}
    db.commit()
    campaign.remote_campaign_id = remote["remote_id"]
    campaign.state = {"pause": "paused", "resume": "active", "archive": "archived"}.get(
        job.operation, "active"
    )
    campaign.sync_state = "synchronized"
    campaign.reconciliation_state = "matched"
    campaign.updated_at = now()
    mapping_type = (
        "campaign"
        if job.operation in {"create_campaign", "pause", "resume", "archive", "update_budget"}
        else (
            "group"
            if job.operation == "create_group"
            else (
                "ad"
                if job.operation in {"create_ad", "replace_creative", "adopt_experiment_winner"}
                else None
            )
        )
    )
    mapping_entity_id = (
        campaign.id
        if mapping_type == "campaign"
        else (
            target_group.id
            if mapping_type == "group" and target_group
            else target_ad.id if mapping_type == "ad" and target_ad else None
        )
    )
    if mapping_type and mapping_entity_id is not None and remote.get("remote_id"):
        mapping = db.scalar(
            select(AdRemoteMapping).where(
                AdRemoteMapping.owner_id == job.owner_id,
                AdRemoteMapping.provider == campaign.provider,
                AdRemoteMapping.entity_type == mapping_type,
                AdRemoteMapping.local_entity_id == mapping_entity_id,
            )
        )
        if mapping is None:
            db.add(
                AdRemoteMapping(
                    owner_id=job.owner_id,
                    provider=campaign.provider,
                    entity_type=mapping_type,
                    local_entity_id=mapping_entity_id,
                    remote_id=str(remote["remote_id"]),
                    remote_state_json=remote,
                    last_reconciled_at=now(),
                    created_at=now(),
                    updated_at=now(),
                )
            )
    if target_group is not None and job.operation == "create_group":
        target_group.remote_group_id = remote.get("remote_id")
        target_group.state = "active"
        target_group.updated_at = now()
    if target_ad is not None and job.operation in {
        "create_ad",
        "replace_creative",
        "adopt_experiment_winner",
    }:
        target_ad.remote_ad_id = remote.get("remote_id")
        if job.operation in {"replace_creative", "rollback_creative", "adopt_experiment_winner"}:
            target_ad.creative_id = uuid.UUID(str(job.request_json["creative_id"]))
        target_ad.state = "active"
        target_ad.sync_state = "synchronized"
        target_ad.updated_at = now()
    if budget is not None:
        if job.operation == "rollback_budget" and job.request_json.get("daily_amount") is not None:
            budget.daily_amount = Decimal(str(job.request_json["daily_amount"]))
        budget.confirmed = True
        budget.remote_version = budget.version
        budget.remote_checkpoint_json = {
            "remote_id": remote.get("remote_id"),
            "budget_version": budget.version,
        }
        budget.updated_at = now()
    job.status = "succeeded"
    job.lease_expires_at = None
    job.next_retry_at = None
    job.result_json = {
        "remote_id": remote["remote_id"],
        "remote_campaign_id": remote["remote_id"],
        "remote_checkpoint": remote,
        "synthetic": True,
    }
    job.completed_at = now()
    job.updated_at = now()
    record_event(
        db,
        actor_id=job.owner_id,
        action=(
            "ads.ad_campaign_created"
            if job.operation == "create_campaign"
            else f"ads.campaign_{job.operation}"
        ),
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"provider": campaign.provider, "synthetic": True},
    )
    db.commit()
    db.refresh(job)
    return job


def import_metrics(db: Session, owner: User, campaign: AdCampaign) -> list[AdMetric]:
    if not campaign.remote_campaign_id:
        raise HTTPException(422, "The Ads campaign has not been published to a fake connector yet.")
    existing_rows = list(
        db.scalars(
            select(AdMetric).where(
                AdMetric.owner_id == owner.id, AdMetric.campaign_id == campaign.id
            )
        )
    )
    if existing_rows:
        return existing_rows
    timestamp = now()
    values = connector_for(campaign.provider).metrics(campaign.remote_campaign_id)
    rows: list[AdMetric] = []
    for key, metric in values.items():
        existing = db.scalar(
            select(AdMetric).where(
                AdMetric.owner_id == owner.id,
                AdMetric.campaign_id == campaign.id,
                AdMetric.observed_at == timestamp,
                AdMetric.metric_key == key,
            )
        )
        if existing:
            rows.append(existing)
            continue
        row = AdMetric(
            owner_id=owner.id,
            campaign_id=campaign.id,
            metric_key=key,
            value=metric,
            currency="INR" if key == "spend" else None,
            availability="synthetic",
            source="fake_connector",
            observed_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(row)
        rows.append(row)
    record_event(
        db,
        actor_id=owner.id,
        action="ads.metrics_imported",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"synthetic": True, "count": len(rows)},
    )
    db.commit()
    return rows
