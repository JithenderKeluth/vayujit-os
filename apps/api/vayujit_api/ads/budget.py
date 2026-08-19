from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ads.models import AdBudget, AdCampaign, AdJob
from vayujit_api.ads.schemas import AdsBudgetConfirm, AdsBudgetPreview
from vayujit_api.ads.service import fingerprint, now, queue_job
from vayujit_api.identity.models import User


def budget_preview(
    db: Session, owner: User, campaign: AdCampaign, data: AdsBudgetPreview
) -> dict[str, Any]:
    current = db.scalar(
        select(AdBudget)
        .where(AdBudget.campaign_id == campaign.id)
        .order_by(AdBudget.version.desc())
    )
    if current is None or current.version != data.expected_version:
        raise HTTPException(409, "The Ads budget version is stale; refresh before previewing.")
    if data.proposed.currency.upper() != current.currency:
        raise HTTPException(422, "Budget currency cannot change after campaign creation.")
    payload = data.model_dump(mode="json")
    return {
        "campaign_id": campaign.id,
        "current": {
            "version": current.version,
            "currency": current.currency,
            "daily_amount": current.daily_amount,
            "lifetime_amount": current.lifetime_amount,
        },
        "proposed": payload["proposed"],
        "old_budget_version": current.version,
        "proposed_budget_version": current.version + 1,
        "mutates": False,
        "fingerprint": fingerprint(payload),
        "warnings": ["Synthetic local Ads preview; no remote mutation occurs."],
    }


def confirm_budget_change(
    db: Session, owner: User, campaign: AdCampaign, data: AdsBudgetConfirm
) -> tuple[AdBudget, AdJob]:
    if not data.confirm:
        raise HTTPException(422, "Explicit confirmation is required before a budget mutation.")
    preview = budget_preview(
        db,
        owner,
        campaign,
        AdsBudgetPreview(proposed=data.proposed, expected_version=data.expected_version),
    )
    if data.preview_fingerprint != preview["fingerprint"]:
        raise HTTPException(409, "The Ads budget preview is stale; generate a new preview.")
    existing = db.scalar(
        select(AdBudget).where(
            AdBudget.owner_id == owner.id,
            AdBudget.campaign_id == campaign.id,
            AdBudget.confirmation_fingerprint == data.preview_fingerprint,
        )
    )
    if existing is None:
        timestamp = now()
        existing = AdBudget(
            owner_id=owner.id,
            campaign_id=campaign.id,
            version=data.expected_version + 1,
            daily_amount=data.proposed.daily_amount,
            lifetime_amount=data.proposed.lifetime_amount,
            currency=data.proposed.currency.upper(),
            effective_from=data.proposed.effective_from,
            effective_until=data.proposed.effective_until,
            confirmed=False,
            budget_type=data.proposed.budget_type
            or ("daily" if data.proposed.daily_amount is not None else "lifetime"),
            proposed_from_version=data.expected_version,
            confirmation_fingerprint=data.preview_fingerprint,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(existing)
        db.flush()
    job = queue_job(
        db,
        owner,
        campaign,
        "update_budget",
        data.idempotency_key,
        {
            "campaign_id": str(campaign.id),
            "budget_id": str(existing.id),
            "budget_version": existing.version,
        },
    )
    return existing, job
