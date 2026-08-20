"""Bounded deterministic Ads optimization and marketing intelligence services."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ads.connectors import connector_for
from vayujit_api.ads.models import (
    Ad,
    AdAccount,
    AdBidRecommendation,
    AdBudget,
    AdBudgetRecommendation,
    AdCampaign,
    AdCreative,
    AdCreativeFatigueSignal,
    AdExperiment,
    AdExperimentResult,
    AdExperimentVariant,
    AdFailureRecord,
    AdJob,
    AdMetric,
    AdOptimizationDecision,
    AdOptimizationExecution,
    AdOptimizationRecommendation,
    AdOptimizationRule,
    AdPerformanceAnomaly,
)
from vayujit_api.ads.service import queue_job
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User

SUPPORTED_METRICS = {
    "impressions",
    "reach",
    "clicks",
    "spend",
    "conversions",
    "conversion_value",
    "ctr",
    "cpc",
    "cpa",
    "roas",
    "frequency",
    "video_views",
    "budget_utilization",
}
SUPPORTED_ACTIONS = {
    "increase_budget",
    "decrease_budget",
    "pause_campaign",
    "resume_campaign",
    "pause_ad",
    "resume_ad",
    "replace_creative",
    "rotate_creative",
    "change_bid_strategy",
    "adjust_bid_target",
    "narrow_audience",
    "broaden_audience",
    "exclude_underperforming_segment",
    "add_negative_keyword",
    "remove_keyword",
    "increase_keyword_bid",
    "decrease_keyword_bid",
    "schedule_shift",
    "review_destination",
    "review_policy",
    "investigate_tracking",
    "investigate_anomaly",
}
LOW_RISK_AUTO_ACTIONS = {"pause_campaign", "resume_campaign", "decrease_budget", "pause_ad"}


def now() -> datetime:
    return datetime.now(UTC)


def _json(value: object) -> object:
    if isinstance(value, (Decimal, uuid.UUID, datetime)):
        return float(value) if isinstance(value, Decimal) else str(value)
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    return value


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_json(value), sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def metric_snapshot(db: Session, owner_id: uuid.UUID, campaign_id: uuid.UUID) -> dict[str, float]:
    rows = list(
        db.scalars(
            select(AdMetric)
            .where(AdMetric.owner_id == owner_id, AdMetric.campaign_id == campaign_id)
            .order_by(AdMetric.observed_at.desc())
        )
    )
    result: dict[str, float] = {}
    for row in rows:
        if row.metric_key not in result and row.value is not None:
            result[row.metric_key] = float(row.value)
    impressions, clicks, spend, conversions = (
        result.get(k, 0.0) for k in ("impressions", "clicks", "spend", "conversions")
    )
    if impressions and "ctr" not in result:
        result["ctr"] = clicks / impressions
    if clicks and "cpc" not in result:
        result["cpc"] = spend / clicks
    if conversions and "cpa" not in result:
        result["cpa"] = spend / conversions
    if result.get("conversion_value") is not None and spend and "roas" not in result:
        result["roas"] = result["conversion_value"] / spend
    budget = db.scalar(
        select(AdBudget)
        .where(AdBudget.owner_id == owner_id, AdBudget.campaign_id == campaign_id)
        .order_by(AdBudget.version.desc())
    )
    if budget and budget.daily_amount and float(budget.daily_amount) > 0:
        result["budget_utilization"] = min(1.0, spend / float(budget.daily_amount))
    return result


def campaign_state(db: Session, owner_id: uuid.UUID, campaign: AdCampaign) -> dict[str, object]:
    budget = db.scalar(
        select(AdBudget)
        .where(AdBudget.owner_id == owner_id, AdBudget.campaign_id == campaign.id)
        .order_by(AdBudget.version.desc())
    )
    creative = db.scalar(
        select(AdCreative)
        .where(AdCreative.owner_id == owner_id, AdCreative.campaign_id == campaign.id)
        .order_by(AdCreative.created_at.desc())
    )
    return {
        "campaign_state": campaign.state,
        "budget_version": budget.version if budget else None,
        "daily_budget": float(budget.daily_amount) if budget and budget.daily_amount else None,
        "lifetime_budget": (
            float(budget.lifetime_amount) if budget and budget.lifetime_amount else None
        ),
        "currency": budget.currency if budget else None,
        "bidding_strategy": campaign.bidding_strategy,
        "creative_id": str(creative.id) if creative else None,
        "creative_version": creative.artifact_version if creative else None,
    }


def live_fingerprint(
    db: Session, owner_id: uuid.UUID, campaign: AdCampaign, action: str, rule_version: int = 1
) -> str:
    return fingerprint(
        {
            "owner": str(owner_id),
            "provider": campaign.provider,
            "campaign": str(campaign.id),
            "action": action,
            "metrics": metric_snapshot(db, owner_id, campaign.id),
            "state": campaign_state(db, owner_id, campaign),
            "rule_version": rule_version,
        }
    )


def campaign_or_404(db: Session, owner: User, campaign_id: uuid.UUID) -> AdCampaign:
    row = db.scalar(
        select(AdCampaign).where(AdCampaign.owner_id == owner.id, AdCampaign.id == campaign_id)
    )
    if row is None:
        raise HTTPException(404, "Ads campaign not found.")
    return row


def validate_rule_payload(payload: dict[str, object], provider: str | None = None) -> None:
    metric, action, operator = (
        str(payload.get("metric") or ""),
        str(payload.get("action") or ""),
        str(payload.get("operator") or ""),
    )
    if metric not in SUPPORTED_METRICS:
        raise HTTPException(422, "The optimization metric is unsupported.")
    if action not in SUPPORTED_ACTIONS:
        raise HTTPException(422, "The optimization action is unsupported.")
    if operator not in {"<", "<=", ">", ">=", "=="}:
        raise HTTPException(422, "The optimization operator is unsupported.")
    try:
        Decimal(str(payload.get("threshold")))
    except (TypeError, ValueError):
        raise HTTPException(422, "The optimization threshold is invalid.") from None
    if not 1 <= int(str(payload.get("window_days") or 0)) <= 90:
        raise HTTPException(422, "The optimization metric window is outside the safe bounds.")
    if (
        provider
        and action
        in {
            "add_negative_keyword",
            "remove_keyword",
            "increase_keyword_bid",
            "decrease_keyword_bid",
        }
        and provider != "google"
    ):
        raise HTTPException(422, "Keyword optimization is available only for Google Search.")
    if provider and provider not in {"meta", "google"}:
        raise HTTPException(422, "The optimization provider is unsupported.")
    if provider and action in {  # noqa: SIM102
        "change_bid_strategy",
        "adjust_bid_target",
        "increase_keyword_bid",
        "decrease_keyword_bid",
    }:
        if not connector_for(provider).capabilities().get("bidding_strategies"):
            raise HTTPException(422, "The provider has no compatible bidding strategy capability.")
    if provider and action in {  # noqa: SIM102
        "narrow_audience",
        "broaden_audience",
        "exclude_underperforming_segment",
    }:
        if not connector_for(provider).capabilities().get("audiences"):
            raise HTTPException(422, "The provider has no compatible audience capability.")


def rule_response(rule: AdOptimizationRule) -> dict[str, object]:
    data = dict(rule.rule_json or {})
    return {
        "id": rule.id,
        "name": rule.name,
        "campaign_id": rule.campaign_id,
        "provider": rule.provider,
        "objective": rule.objective,
        "enabled": rule.enabled,
        "version": rule.version,
        "mode": rule.mode,
        "metric": data.get("metric"),
        "operator": data.get("operator"),
        "threshold": data.get("threshold"),
        "window_days": rule.metric_window_days,
        "action": data.get("action"),
        "guardrails": rule.guardrails_json,
        "allowed_actions": rule.allowed_actions_json,
        "cooldown_seconds": rule.cooldown_seconds,
        "daily_action_limit": rule.daily_action_limit,
        "archived": rule.archived_at is not None,
        "synthetic": True,
    }


def _condition(value: float | None, operator: str, threshold: float) -> bool:
    if value is None:
        return False
    return {
        "<": value < threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        ">=": value >= threshold,
        "==": value == threshold,
    }[operator]


def recommendation_response(row: AdOptimizationRecommendation) -> dict[str, object]:
    return {
        "id": row.id,
        "provider": row.provider,
        "campaign_id": row.campaign_id,
        "product_id": row.product_id,
        "group_id": row.group_id,
        "ad_id": row.ad_id,
        "creative_id": row.creative_id,
        "rule_id": row.rule_id,
        "type": row.recommendation_type,
        "recommendation_type": row.recommendation_type,
        "severity": row.severity,
        "confidence": row.confidence,
        "confidence_score": (
            float(row.confidence_score) if row.confidence_score is not None else None
        ),
        "status": row.status,
        "evidence": row.evidence_json,
        "explanation": row.explanation_json,
        "current_state": row.current_state_json,
        "proposed_state": row.proposed_state_json,
        "action_options": row.action_options_json,
        "risks": row.explanation_json.get("risks", []),
        "affected_entities": row.explanation_json.get("affected_entities", {}),
        "actionable": bool(row.explanation_json.get("actionable", False)),
        "provider_compatibility": row.explanation_json.get(
            "provider_compatibility", {"provider": row.provider, "status": "compatible"}
        ),
        "metric_window": {"start": row.metric_window_start, "end": row.metric_window_end},
        "fingerprint": row.fingerprint,
        "source": row.source,
        "synthetic": True,
        "stale_reason": row.stale_reason,
    }


def recommendation_context(
    db: Session,
    owner: User,
    campaign: AdCampaign,
    action: str,
    evidence: dict[str, object],
    rule: AdOptimizationRule | None,
) -> dict[str, object]:
    current = campaign_state(db, owner.id, campaign)
    proposed = dict(current)
    risks: list[str] = []
    blockers: list[str] = []
    direction = "review before mutation"
    if action in {"increase_budget", "decrease_budget"}:
        amount = float(str(current.get("daily_budget") or 0))
        proposed["daily_budget"] = (
            round(amount * (1.1 if action == "increase_budget" else 0.9), 2) if amount else None
        )
        direction = (
            "increase bounded delivery opportunity"
            if action == "increase_budget"
            else "reduce spend exposure"
        )
        risks.append("Budget mutations require explicit owner confirmation and server guardrails.")
    elif action in {"pause_campaign", "resume_campaign"}:
        proposed["campaign_state"] = "paused" if action == "pause_campaign" else "active"
        direction = "stop further delivery" if action == "pause_campaign" else "restore delivery"
    elif action in {"pause_ad", "resume_ad"}:
        proposed["ad_state"] = "paused" if action == "pause_ad" else "active"
        direction = "change ad delivery state"
    elif action == "replace_creative":
        direction = "refresh exact creative lineage"
        risks.append("Replacement requires an approved exact creative version.")
    elif action in {
        "rotate_creative",
        "review_destination",
        "review_policy",
        "investigate_tracking",
        "investigate_anomaly",
        "schedule_shift",
    }:
        direction = "create an owner-reviewed follow-up"
        risks.append("This recommendation is advisory and does not mutate a provider.")
    elif action in {
        "change_bid_strategy",
        "adjust_bid_target",
        "increase_keyword_bid",
        "decrease_keyword_bid",
    }:
        direction = "review bidding efficiency"
        risks.append("Provider capability and sufficient metric data are required before mutation.")
    elif action in {"narrow_audience", "broaden_audience", "exclude_underperforming_segment"}:
        direction = "review bounded audience scope"
        risks.append("No raw audience identifiers or PII are exposed by local intelligence.")
    elif action in {"add_negative_keyword", "remove_keyword"}:
        direction = "review Google Search keyword hygiene"
        risks.append("Keyword recommendations are limited to deterministic local evidence.")
    actionable = action in {
        "increase_budget",
        "decrease_budget",
        "pause_campaign",
        "resume_campaign",
        "replace_creative",
    }
    if action in {"pause_ad", "resume_ad"}:
        actionable = False
    return {
        "current": current,
        "proposed": proposed,
        "explanation": {
            "issue": evidence.get("issue", "A deterministic optimization condition was observed."),
            "evidence": evidence,
            "why_it_matters": (
                "The observed local metrics may indicate a bounded optimization opportunity."
            ),
            "expected_direction": direction,
            "risks": risks,
            "affected_entities": {
                "campaign_id": str(campaign.id),
                "product_id": str(campaign.product_id) if campaign.product_id else None,
            },
            "metric_window": {
                "start": (
                    now() - timedelta(days=rule.metric_window_days if rule else 7)
                ).isoformat(),
                "end": now().isoformat(),
            },
            "action_options": [action, "dismiss"],
            "actionable": actionable,
            "provider_compatibility": {
                "provider": campaign.provider,
                "status": (
                    "incompatible"
                    if action
                    in {
                        "add_negative_keyword",
                        "remove_keyword",
                        "increase_keyword_bid",
                        "decrease_keyword_bid",
                    }
                    and campaign.provider != "google"
                    else "compatible" if campaign.provider in {"meta", "google"} else "unavailable"
                ),
            },
        },
        "blockers": blockers,
    }


def create_recommendation(
    db: Session,
    owner: User,
    campaign: AdCampaign,
    action: str,
    evidence: dict[str, object],
    *,
    severity: str = "recommendation",
    confidence: str = "medium",
    rule: AdOptimizationRule | None = None,
) -> AdOptimizationRecommendation:
    context = recommendation_context(db, owner, campaign, action, evidence, rule)
    stamp = now()
    fp = live_fingerprint(db, owner.id, campaign, action, rule.version if rule else 1)
    existing = db.scalar(
        select(AdOptimizationRecommendation).where(
            AdOptimizationRecommendation.owner_id == owner.id,
            AdOptimizationRecommendation.fingerprint == fp,
        )
    )
    if existing is not None:
        return existing
    window_days = rule.metric_window_days if rule else 7
    row = AdOptimizationRecommendation(
        owner_id=owner.id,
        provider=campaign.provider,
        campaign_id=campaign.id,
        product_id=campaign.product_id,
        rule_id=rule.id if rule else None,
        recommendation_type=action,
        severity=severity,
        confidence=confidence,
        confidence_score=(
            Decimal("0.85")
            if confidence == "high"
            else Decimal("0.60") if confidence == "medium" else Decimal("0.35")
        ),
        status="open",
        evidence_json={
            **metric_snapshot(db, owner.id, campaign.id),
            **evidence,
            "availability": "synthetic",
        },
        explanation_json=context["explanation"],
        current_state_json=context["current"],
        proposed_state_json=context["proposed"],
        action_options_json=[action, "dismiss"],
        metric_window_start=stamp - timedelta(days=window_days),
        metric_window_end=stamp,
        fingerprint=fp,
        source="synthetic_local",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    current, proposed = cast(dict[str, object], context["current"]), cast(
        dict[str, object], context["proposed"]
    )
    if action in {"increase_budget", "decrease_budget"}:
        db.add(
            AdBudgetRecommendation(
                owner_id=owner.id,
                recommendation_id=row.id,
                campaign_id=campaign.id,
                provider=campaign.provider,
                current_value=(
                    Decimal(str(current.get("daily_budget")))
                    if current.get("daily_budget") is not None
                    else None
                ),
                proposed_value=(
                    Decimal(str(proposed.get("daily_budget")))
                    if proposed.get("daily_budget") is not None
                    else None
                ),
                currency=str(current.get("currency")) if current.get("currency") else None,
                guardrails_json={"max_percent_change": 20},
                created_at=stamp,
                updated_at=stamp,
            )
        )
    if action in {
        "change_bid_strategy",
        "adjust_bid_target",
        "increase_keyword_bid",
        "decrease_keyword_bid",
    }:
        db.add(
            AdBidRecommendation(
                owner_id=owner.id,
                recommendation_id=row.id,
                campaign_id=campaign.id,
                provider=campaign.provider,
                strategy=campaign.bidding_strategy,
                availability="available" if campaign.provider == "google" else "unavailable",
                created_at=stamp,
                updated_at=stamp,
            )
        )
    record_event(
        db,
        actor_id=owner.id,
        action="ads.optimization_recommendation_generated",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"recommendation_id": str(row.id), "type": action, "source": "synthetic_local"},
    )
    return row


def evaluate_campaigns(
    db: Session, owner: User, campaign_id: uuid.UUID | None = None
) -> list[AdOptimizationRecommendation]:
    stmt = select(AdCampaign).where(AdCampaign.owner_id == owner.id)
    if campaign_id:
        stmt = stmt.where(AdCampaign.id == campaign_id)
    campaigns = list(db.scalars(stmt.order_by(AdCampaign.created_at)))
    rules = list(
        db.scalars(
            select(AdOptimizationRule).where(
                AdOptimizationRule.owner_id == owner.id,
                AdOptimizationRule.enabled.is_(True),
                AdOptimizationRule.archived_at.is_(None),
            )
        )
    )
    generated: list[AdOptimizationRecommendation] = []
    for campaign in campaigns:
        metrics = metric_snapshot(db, owner.id, campaign.id)
        if not metrics:
            continue
        applicable = [
            rule
            for rule in rules
            if (rule.campaign_id is None or rule.campaign_id == campaign.id)
            and (rule.provider is None or rule.provider == campaign.provider)
        ]
        for rule in applicable:
            data = rule.rule_json
            if _condition(
                metrics.get(str(data.get("metric"))),
                str(data.get("operator")),
                float(str(data.get("threshold", 0))),
            ):
                generated.append(
                    create_recommendation(
                        db,
                        owner,
                        campaign,
                        str(data["action"]),
                        {
                            "issue": (
                                str(data.get("metric"))
                                + " "
                                + str(data.get("operator"))
                                + " "
                                + str(data.get("threshold")),
                            ),
                            "rule_version": rule.version,
                        },
                        rule=rule,
                    )
                )
        if not applicable:
            if metrics.get("roas", 0) >= 2 and metrics.get("budget_utilization", 0) < 0.8:
                generated.append(
                    create_recommendation(
                        db,
                        owner,
                        campaign,
                        "increase_budget",
                        {
                            "issue": "Strong ROAS with bounded expansion opportunity.",
                            "roas": metrics.get("roas"),
                            "budget_utilization": metrics.get("budget_utilization"),
                        },
                        confidence="medium",
                    )
                )
            elif metrics.get("budget_utilization", 0) < 0.3 and metrics.get("spend", 0) > 0:
                generated.append(
                    create_recommendation(
                        db,
                        owner,
                        campaign,
                        "decrease_budget",
                        {
                            "issue": "Budget is materially underutilized.",
                            "budget_utilization": metrics.get("budget_utilization"),
                        },
                        confidence="medium",
                    )
                )
            elif metrics.get("spend", 0) > 0 and metrics.get("conversions", 0) == 0:
                generated.append(
                    create_recommendation(
                        db,
                        owner,
                        campaign,
                        "pause_campaign",
                        {
                            "issue": "Campaign has spend and zero conversions.",
                            "spend": metrics.get("spend"),
                            "conversions": 0,
                        },
                        severity="warning",
                        confidence="high",
                    )
                )
            elif metrics.get("impressions", 0) > 0 and metrics.get("ctr", 0) < 0.01:
                generated.append(
                    create_recommendation(
                        db,
                        owner,
                        campaign,
                        "replace_creative",
                        {
                            "issue": "CTR is below the deterministic watch threshold.",
                            "ctr": metrics.get("ctr"),
                        },
                        confidence="medium",
                    )
                )
    for recommendation in generated:
        auto_rule = (
            db.get(AdOptimizationRule, recommendation.rule_id) if recommendation.rule_id else None
        )
        if (
            auto_rule is None
            or auto_rule.mode != "auto_apply_bounded"
            or recommendation.status != "open"
        ):
            continue
        try:
            confirm_recommendation(
                db,
                owner,
                recommendation,
                action=recommendation.recommendation_type,
                preview_fingerprint=recommendation.fingerprint,
                idempotency_key=f"auto:{auto_rule.id}:{recommendation.fingerprint}",
                confirm=True,
            )
            record_event(
                db,
                actor_id=owner.id,
                action="ads.optimization_auto_applied",
                entity_type="ad_campaign",
                entity_id=recommendation.campaign_id,
                metadata={"recommendation_id": str(recommendation.id), "synthetic": True},
            )
        except HTTPException as error:
            recommendation.status = "blocked"
            recommendation.stale_reason = str(error.detail)
    db.commit()
    return generated


def list_recommendations(db: Session, owner: User, **filters: object) -> list[dict[str, object]]:
    stmt = select(AdOptimizationRecommendation).where(
        AdOptimizationRecommendation.owner_id == owner.id
    )
    mapping = {
        "provider": AdOptimizationRecommendation.provider,
        "campaign_id": AdOptimizationRecommendation.campaign_id,
        "product_id": AdOptimizationRecommendation.product_id,
        "recommendation_type": AdOptimizationRecommendation.recommendation_type,
        "severity": AdOptimizationRecommendation.severity,
        "status": AdOptimizationRecommendation.status,
    }
    for key, column in mapping.items():
        if filters.get(key) is not None:
            stmt = stmt.where(column == filters[key])
    return [
        recommendation_response(row)
        for row in db.scalars(stmt.order_by(AdOptimizationRecommendation.created_at.desc()))
    ]


def get_recommendation(
    db: Session, owner: User, recommendation_id: uuid.UUID
) -> AdOptimizationRecommendation:
    row = db.scalar(
        select(AdOptimizationRecommendation).where(
            AdOptimizationRecommendation.owner_id == owner.id,
            AdOptimizationRecommendation.id == recommendation_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Optimization recommendation not found.")
    return row


def ensure_current(db: Session, owner: User, row: AdOptimizationRecommendation) -> AdCampaign:
    campaign = campaign_or_404(db, owner, row.campaign_id)
    rule_version = int(str((row.evidence_json or {}).get("rule_version", 1)))
    if (
        live_fingerprint(db, owner.id, campaign, row.recommendation_type, rule_version)
        != row.fingerprint
    ):
        row.status, row.stale_reason, row.updated_at = (
            "stale",
            "Campaign, metric, creative, or budget context changed; preview again.",
            now(),
        )
        db.commit()
        raise HTTPException(
            409, "This optimization recommendation is stale; preview the current state again."
        )
    return campaign


def preview_recommendation(
    db: Session,
    owner: User,
    row: AdOptimizationRecommendation,
    action: str | None = None,
    replacement_creative_id: uuid.UUID | None = None,
) -> dict[str, object]:
    campaign = ensure_current(db, owner, row)
    selected = action or row.recommendation_type
    if selected not in row.action_options_json and selected != row.recommendation_type:
        raise HTTPException(422, "The selected optimization action is not authorized.")
    proposed = dict(row.proposed_state_json)
    blockers: list[str] = []
    if selected == "replace_creative":
        if replacement_creative_id is None:
            blockers.append("Select an approved exact replacement creative version.")
        else:
            replacement = db.scalar(
                select(AdCreative).where(
                    AdCreative.owner_id == owner.id,
                    AdCreative.id == replacement_creative_id,
                    AdCreative.campaign_id == campaign.id,
                    AdCreative.approval_status == "approved",
                )
            )
            if replacement is None:
                blockers.append("The exact approved replacement creative is unavailable.")
            else:
                proposed.update(
                    {
                        "replacement_creative_id": str(replacement.id),
                        "replacement_fingerprint": replacement.fingerprint,
                    }
                )
    return {
        "recommendation": recommendation_response(row),
        "action": selected,
        "current_state": row.current_state_json,
        "proposed_state": proposed,
        "estimated_effect_direction": row.explanation_json.get("expected_direction"),
        "risks": row.explanation_json.get("risks", []),
        "blockers": blockers,
        "warnings": ["Synthetic / Local Simulation: no live Ads mutation occurs during preview."],
        "fingerprint": row.fingerprint,
        "synthetic": True,
        "mutating": False,
    }


def dismiss_recommendation(
    db: Session, owner: User, row: AdOptimizationRecommendation
) -> dict[str, object]:
    row.status, row.updated_at = "dismissed", now()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.optimization_recommendation_dismissed",
        entity_type="ad_campaign",
        entity_id=row.campaign_id,
        metadata={"recommendation_id": str(row.id), "synthetic": True},
    )
    db.commit()
    return recommendation_response(row)


def confirm_recommendation(
    db: Session,
    owner: User,
    row: AdOptimizationRecommendation,
    *,
    action: str | None,
    preview_fingerprint: str,
    idempotency_key: str,
    confirm: bool,
    replacement_creative_id: uuid.UUID | None = None,
) -> dict[str, object]:
    if not confirm:
        raise HTTPException(
            422, "Explicit confirmation is required before an optimization mutation."
        )
    if preview_fingerprint != row.fingerprint:
        raise HTTPException(409, "The optimization preview is stale; preview again.")
    campaign = ensure_current(db, owner, row)
    selected = action or row.recommendation_type
    if selected not in {row.recommendation_type, *row.action_options_json}:
        raise HTTPException(422, "The selected optimization action is not authorized.")
    rule = db.get(AdOptimizationRule, row.rule_id) if row.rule_id else None
    if rule is not None and rule.mode == "auto_apply_bounded":
        if selected not in LOW_RISK_AUTO_ACTIONS or selected not in set(rule.allowed_actions_json):
            raise HTTPException(422, "The requested auto-action is not whitelisted by the rule.")
        account = db.get(AdAccount, campaign.account_id)
        if account is None or not account.enabled or account.status != "active":
            raise HTTPException(409, "The Ads account is not healthy for bounded auto-action.")
        recovery_conflict = db.scalar(
            select(AdFailureRecord.id)
            .where(
                AdFailureRecord.owner_id == owner.id,
                AdFailureRecord.entity_id == campaign.id,
                AdFailureRecord.code.in_(
                    {"ads.ambiguous_result", "ads.connector_unavailable", "ads.timeout"}
                ),
            )
            .limit(1)
        )
        if recovery_conflict is not None:
            raise HTTPException(409, "A pending Ads recovery conflict blocks bounded auto-action.")
        if rule.cooldown_seconds:
            cutoff = now() - timedelta(seconds=rule.cooldown_seconds)
            recent = db.scalar(
                select(AdOptimizationExecution.id)
                .where(
                    AdOptimizationExecution.owner_id == owner.id,
                    AdOptimizationExecution.action == selected,
                    AdOptimizationExecution.created_at >= cutoff,
                )
                .limit(1)
            )
            if recent is not None:
                raise HTTPException(409, "The optimization cooldown is active.")
        daily_cutoff = now() - timedelta(days=1)
        daily_count = (
            db.scalar(
                select(func.count())
                .select_from(AdOptimizationExecution)
                .where(
                    AdOptimizationExecution.owner_id == owner.id,
                    AdOptimizationExecution.action == selected,
                    AdOptimizationExecution.created_at >= daily_cutoff,
                )
            )
            or 0
        )
        if int(daily_count) >= rule.daily_action_limit:
            raise HTTPException(409, "The optimization daily action limit has been reached.")
    existing = db.scalar(
        select(AdOptimizationExecution).where(
            AdOptimizationExecution.owner_id == owner.id,
            AdOptimizationExecution.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return {
            "execution": {"id": existing.id, "status": existing.status, "idempotent_reuse": True},
            "synthetic": True,
        }
    preview = preview_recommendation(db, owner, row, selected, replacement_creative_id)
    blockers = cast(list[object], preview["blockers"])
    if blockers:
        raise HTTPException(422, str(blockers[0]))
    before = dict(row.current_state_json)
    after = dict(cast(dict[str, object], preview["proposed_state"]))
    entity_type, entity_id = "campaign", campaign.id
    if selected in {"increase_budget", "decrease_budget"}:
        current = db.scalar(
            select(AdBudget)
            .where(AdBudget.owner_id == owner.id, AdBudget.campaign_id == campaign.id)
            .order_by(AdBudget.version.desc())
        )
        if current is None or current.daily_amount is None:
            raise HTTPException(422, "A daily budget is required for this bounded optimization.")
        amount = float(str(after.get("daily_budget") or 0))
        old = float(current.daily_amount)
        guardrails = dict(rule.guardrails_json) if rule is not None else {}
        max_percent = float(str(guardrails.get("max_percent_change", 20)))
        if abs(amount - old) / old * 100 > max_percent:
            raise HTTPException(422, "The proposed budget change exceeds the server guardrail.")
        daily_cap = guardrails.get("daily_spend_cap")
        if daily_cap is not None and amount > float(str(daily_cap)):
            raise HTTPException(422, "The proposed budget exceeds the configured daily spend cap.")
        lifetime_cap = guardrails.get("lifetime_spend_cap")
        if (
            lifetime_cap is not None
            and current.lifetime_amount is not None
            and float(current.lifetime_amount) > float(str(lifetime_cap))
        ):
            raise HTTPException(
                422, "The proposed budget exceeds the configured lifetime spend cap."
            )
        budget = AdBudget(
            owner_id=owner.id,
            campaign_id=campaign.id,
            version=current.version + 1,
            daily_amount=Decimal(str(amount)),
            lifetime_amount=current.lifetime_amount,
            currency=current.currency,
            budget_type=current.budget_type,
            proposed_from_version=current.version,
            confirmed=False,
            created_at=now(),
            updated_at=now(),
        )
        db.add(budget)
        db.flush()
        after["budget_version"] = budget.version
        operation, request = "update_budget", {
            "budget_id": str(budget.id),
            "budget_version": budget.version,
            "daily_amount": amount,
            "currency": budget.currency,
        }
    elif selected in {"pause_campaign", "resume_campaign"}:
        operation, request = ("pause" if selected == "pause_campaign" else "resume"), {
            "campaign_id": str(campaign.id)
        }
    elif selected == "replace_creative":
        replacement_id = replacement_creative_id or uuid.UUID(str(after["replacement_creative_id"]))
        ad = db.scalar(
            select(Ad)
            .where(Ad.owner_id == owner.id, Ad.campaign_id == campaign.id)
            .order_by(Ad.created_at.desc())
        )
        replacement = db.scalar(
            select(AdCreative).where(
                AdCreative.owner_id == owner.id,
                AdCreative.id == replacement_id,
                AdCreative.campaign_id == campaign.id,
                AdCreative.approval_status == "approved",
            )
        )
        if ad is None or replacement is None:
            raise HTTPException(
                422, "An exact approved replacement creative and existing Ads ad are required."
            )
        entity_type, entity_id, operation, request = (
            "ad",
            ad.id,
            "replace_creative",
            {"creative_id": str(replacement.id), "ad_id": str(ad.id)},
        )
    else:
        raise HTTPException(
            422, "This optimization action is advisory and has no local mutation executor."
        )
    correlation = f"ads-opt-{uuid.uuid4().hex[:24]}"
    decision = AdOptimizationDecision(
        owner_id=owner.id,
        recommendation_id=row.id,
        action=selected,
        decision_status="confirmed",
        preview_json=cast(dict[str, object], _json(preview)),
        correlation_id=correlation,
        created_at=now(),
        updated_at=now(),
    )
    db.add(decision)
    db.flush()
    job = queue_job(
        db,
        owner,
        campaign,
        operation,
        idempotency_key,
        request,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    execution = AdOptimizationExecution(
        owner_id=owner.id,
        recommendation_id=row.id,
        decision_id=decision.id,
        job_id=job.id,
        action=selected,
        status="queued",
        idempotency_key=idempotency_key,
        before_state_json=before,
        after_state_json=after,
        rollback_state_json=before,
        result_json={"synthetic": True},
        correlation_id=correlation,
        created_at=now(),
        updated_at=now(),
    )
    db.add(execution)
    row.status, row.updated_at = "confirmed", now()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.optimization_confirmed",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={
            "recommendation_id": str(row.id),
            "execution_id": str(execution.id),
            "action": selected,
            "correlation_id": correlation,
            "synthetic": True,
        },
    )
    db.commit()
    db.refresh(execution)
    return {
        "execution": {
            "id": execution.id,
            "status": execution.status,
            "job_id": job.id,
            "action": selected,
            "correlation_id": correlation,
            "idempotent_reuse": False,
        },
        "job": {"id": job.id, "status": job.status},
        "synthetic": True,
    }


def detect_anomalies(
    db: Session, owner: User, campaign_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    stmt = select(AdCampaign).where(AdCampaign.owner_id == owner.id)
    if campaign_id:
        stmt = stmt.where(AdCampaign.id == campaign_id)
    output: list[dict[str, object]] = []
    for campaign in db.scalars(stmt):
        metrics = metric_snapshot(db, owner.id, campaign.id)
        if not metrics:
            continue
        kind: str | None = None
        severity = "warning"
        if metrics.get("impressions") is None and metrics.get("spend", 0) > 0:
            kind, severity = "missing_metrics_ingestion", "critical"
        elif metrics.get("impressions", 0) == 0 and campaign.state == "active":
            kind, severity = "zero_impressions", "critical"
        elif metrics.get("impressions", 0) == 0 and campaign.state != "paused":
            kind, severity = "delivery_stopped", "critical"
        elif metrics.get("spend", 0) > 0 and metrics.get("conversions", 0) == 0:
            kind = "conversion_collapse"
        elif metrics.get("ctr", 0) < 0.005 and metrics.get("impressions", 0) >= 1000:
            kind = "ctr_collapse"
        elif metrics.get("cpc", 0) > 20:
            kind = "cpc_spike"
        elif metrics.get("cpa", 0) > 100:
            kind = "cpa_spike"
        elif metrics.get("roas") is not None and metrics.get("roas", 0) < 0.5:
            kind = "roas_drop"
        elif metrics.get("budget_utilization", 0) >= 1.0:
            kind, severity = "unexpected_budget_exhaustion", "critical"
        elif metrics.get("budget_utilization", 0) >= 0.8:
            kind = "sudden_spend_spike"
        if not kind:
            active_rows = list(
                db.scalars(
                    select(AdPerformanceAnomaly).where(
                        AdPerformanceAnomaly.owner_id == owner.id,
                        AdPerformanceAnomaly.campaign_id == campaign.id,
                        AdPerformanceAnomaly.status == "open",
                    )
                )
            )
            for active_row in active_rows:
                active_row.status = "resolved"
                active_row.updated_at = now()
            continue
        stamp = now()
        evidence = {
            "metrics": metrics,
            "method": "bounded_deterministic_thresholding",
            "availability": "synthetic",
        }
        fp = fingerprint(
            {"owner": owner.id, "campaign": campaign.id, "type": kind, "metrics": metrics}
        )
        row = db.scalar(
            select(AdPerformanceAnomaly).where(
                AdPerformanceAnomaly.owner_id == owner.id, AdPerformanceAnomaly.fingerprint == fp
            )
        )
        if row is None:
            row = AdPerformanceAnomaly(
                owner_id=owner.id,
                provider=campaign.provider,
                campaign_id=campaign.id,
                product_id=campaign.product_id,
                anomaly_type=kind,
                severity=severity,
                evidence_json=evidence,
                fingerprint=fp,
                detected_at=stamp,
                window_start=stamp - timedelta(days=7),
                window_end=stamp,
                source="synthetic_local",
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(row)
        output.append(
            {
                "id": row.id,
                "provider": row.provider,
                "campaign_id": row.campaign_id,
                "product_id": row.product_id,
                "type": row.anomaly_type,
                "anomaly_type": row.anomaly_type,
                "severity": row.severity,
                "status": row.status,
                "evidence": row.evidence_json,
                "detected_at": row.detected_at,
                "actions": ["investigate_anomaly", "pause_campaign"],
                "synthetic": True,
            }
        )
    db.commit()
    return output


def detect_fatigue(
    db: Session, owner: User, campaign_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    stmt = select(AdCreative).where(AdCreative.owner_id == owner.id)
    if campaign_id:
        stmt = stmt.where(AdCreative.campaign_id == campaign_id)
    output: list[dict[str, object]] = []
    for creative in db.scalars(stmt):
        campaign = db.get(AdCampaign, creative.campaign_id)
        if campaign is None or campaign.owner_id != owner.id:
            continue
        metrics = metric_snapshot(db, owner.id, campaign.id)
        ctr = metrics.get("ctr", 0)
        age = max(0, (now() - creative.created_at).days)
        state = (
            "severe"
            if ctr < 0.003
            else "fatigued" if ctr < 0.01 else "watch" if age > 30 else "healthy"
        )
        fp = fingerprint(
            {
                "owner": owner.id,
                "campaign": campaign.id,
                "creative": creative.id,
                "state": state,
                "metrics": metrics,
            }
        )
        row = db.scalar(
            select(AdCreativeFatigueSignal).where(
                AdCreativeFatigueSignal.owner_id == owner.id,
                AdCreativeFatigueSignal.fingerprint == fp,
            )
        )
        if row is None:
            stamp = now()
            row = AdCreativeFatigueSignal(
                owner_id=owner.id,
                provider=campaign.provider,
                campaign_id=campaign.id,
                creative_id=creative.id,
                fatigue_state=state,
                creative_age_days=age,
                evidence_json={
                    "frequency": metrics.get("frequency"),
                    "ctr": ctr,
                    "method": "bounded_deterministic_thresholding",
                    "availability": "synthetic",
                },
                fingerprint=fp,
                detected_at=stamp,
                source="synthetic_local",
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(row)
        output.append(
            {
                "id": row.id,
                "provider": row.provider,
                "campaign_id": row.campaign_id,
                "creative_id": row.creative_id,
                "state": row.fatigue_state,
                "fatigue_state": row.fatigue_state,
                "age_days": row.creative_age_days,
                "evidence": row.evidence_json,
                "recommendation": (
                    "replace_creative" if row.fatigue_state in {"fatigued", "severe"} else None
                ),
                "synthetic": True,
            }
        )
    db.commit()
    return output


def experiment_response(db: Session, owner: User, experiment: AdExperiment) -> dict[str, object]:
    variants = list(
        db.scalars(
            select(AdExperimentVariant)
            .where(
                AdExperimentVariant.owner_id == owner.id,
                AdExperimentVariant.experiment_id == experiment.id,
            )
            .order_by(AdExperimentVariant.name)
        )
    )
    results = list(
        db.scalars(
            select(AdExperimentResult).where(
                AdExperimentResult.owner_id == owner.id,
                AdExperimentResult.experiment_id == experiment.id,
            )
        )
    )
    return {
        "id": experiment.id,
        "campaign_id": experiment.campaign_id,
        "provider": experiment.provider,
        "name": experiment.name,
        "objective": experiment.objective,
        "hypothesis": experiment.hypothesis,
        "variable": experiment.variable,
        "primary_metric": experiment.primary_metric,
        "status": experiment.status,
        "start_at": experiment.start_at,
        "end_at": experiment.end_at,
        "allocation": experiment.allocation_json,
        "variants": [
            {
                "id": v.id,
                "name": v.name,
                "allocation_percent": float(v.allocation_percent),
                "creative_id": v.creative_id,
                "exact_version": v.exact_version_json,
                "status": v.status,
            }
            for v in variants
        ],
        "results": [
            {
                "variant_id": r.variant_id,
                "metrics": r.metrics_json,
                "relative_difference": (
                    float(r.relative_difference) if r.relative_difference is not None else None
                ),
                "confidence": r.confidence_label,
                "leader": r.is_leader,
                "methodology": r.methodology,
            }
            for r in results
        ],
        "winner_variant_id": experiment.winner_variant_id,
        "insufficient_data": experiment.insufficient_data,
        "confidence_method": experiment.confidence_method,
        "synthetic": True,
    }


def create_experiment(db: Session, owner: User, payload: Any) -> dict[str, object]:
    campaign = campaign_or_404(db, owner, payload.campaign_id)
    if campaign.provider != payload.provider:
        raise HTTPException(422, "Experiment provider must match the campaign provider.")
    if payload.objective not in connector_for(payload.provider).capabilities().get(
        "objectives", []
    ):
        raise HTTPException(422, "The experiment objective is unsupported by this provider.")
    if payload.primary_metric not in SUPPORTED_METRICS:
        raise HTTPException(422, "The experiment metric is unsupported.")
    if payload.start_at and payload.end_at:
        duration = payload.end_at - payload.start_at
        if duration.total_seconds() <= 0 or duration > timedelta(days=90):
            raise HTTPException(422, "The experiment duration is outside the safe bounds.")
    if payload.budget:
        for key in ("daily_amount", "lifetime_amount"):
            if key in payload.budget:
                try:
                    amount = Decimal(str(payload.budget[key]))
                except (TypeError, ValueError):
                    raise HTTPException(422, "The experiment budget is invalid.") from None
                if amount < 0 or amount > Decimal("1000000"):
                    raise HTTPException(422, "The experiment budget exceeds the safe bound.")
    stamp = now()
    experiment = AdExperiment(
        owner_id=owner.id,
        campaign_id=campaign.id,
        name=payload.name,
        provider=payload.provider,
        objective=payload.objective,
        hypothesis=payload.hypothesis,
        variable=payload.variable,
        primary_metric=payload.primary_metric,
        status="draft",
        start_at=payload.start_at,
        end_at=payload.end_at,
        variants_json=[item.model_dump(mode="json") for item in payload.variants],
        allocation_json={item.name: float(item.allocation_percent) for item in payload.variants},
        budget_json=payload.budget,
        confidence_method="bounded_deterministic",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(experiment)
    db.flush()
    for item in payload.variants:
        if item.creative_id is not None:
            creative = db.scalar(
                select(AdCreative).where(
                    AdCreative.owner_id == owner.id,
                    AdCreative.id == item.creative_id,
                    AdCreative.campaign_id == campaign.id,
                    AdCreative.approval_status == "approved",
                )
            )
            if creative is None:
                raise HTTPException(
                    422, "An experiment variant references an unavailable exact creative."
                )
            if item.exact_version and item.exact_version.get("version") not in {
                None,
                creative.artifact_version,
            }:
                raise HTTPException(
                    422, "The experiment variant does not reference the exact creative version."
                )
        db.add(
            AdExperimentVariant(
                owner_id=owner.id,
                experiment_id=experiment.id,
                name=item.name,
                allocation_percent=item.allocation_percent,
                creative_id=item.creative_id,
                exact_version_json=item.exact_version,
                status="ready",
                created_at=stamp,
                updated_at=stamp,
            )
        )
    record_event(
        db,
        actor_id=owner.id,
        action="ads.experiment_created",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"experiment_id": str(experiment.id), "synthetic": True},
    )
    db.commit()
    db.refresh(experiment)
    return experiment_response(db, owner, experiment)


def start_experiment(db: Session, owner: User, experiment: AdExperiment) -> dict[str, object]:
    if experiment.status not in {"draft", "stopped"}:
        raise HTTPException(422, "The experiment is not startable in its current state.")
    campaign = campaign_or_404(db, owner, experiment.campaign_id)
    metrics = metric_snapshot(db, owner.id, campaign.id)
    variants = list(
        db.scalars(
            select(AdExperimentVariant)
            .where(
                AdExperimentVariant.owner_id == owner.id,
                AdExperimentVariant.experiment_id == experiment.id,
            )
            .order_by(AdExperimentVariant.name)
        )
    )
    if len(variants) < 2:
        raise HTTPException(422, "At least two experiment variants are required.")
    base = metrics.get(experiment.primary_metric)
    confidence = (
        "insufficient_data"
        if base is None
        else "low" if metrics.get("impressions", 0) < 1000 else "medium"
    )
    experiment.status, experiment.insufficient_data = "running", base is None
    stamp = now()
    for index, variant in enumerate(variants):
        factor = 1 + ((index - (len(variants) - 1) / 2) * 0.04)
        value = round(float(base or 0) * factor, 6)
        existing = db.scalar(
            select(AdExperimentResult).where(
                AdExperimentResult.owner_id == owner.id,
                AdExperimentResult.experiment_id == experiment.id,
                AdExperimentResult.variant_id == variant.id,
            )
        )
        if existing is None:
            db.add(
                AdExperimentResult(
                    owner_id=owner.id,
                    experiment_id=experiment.id,
                    variant_id=variant.id,
                    metrics_json={
                        experiment.primary_metric: value,
                        "impressions": metrics.get("impressions", 0)
                        * float(variant.allocation_percent)
                        / 100,
                        "availability": "synthetic",
                    },
                    relative_difference=Decimal(str((factor - 1) * 100)),
                    confidence_label=confidence,
                    is_leader=False,
                    methodology="bounded_deterministic",
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
    db.flush()
    results = list(
        db.scalars(
            select(AdExperimentResult)
            .where(
                AdExperimentResult.owner_id == owner.id,
                AdExperimentResult.experiment_id == experiment.id,
            )
            .order_by(AdExperimentResult.relative_difference.desc())
        )
    )
    if results and not experiment.insufficient_data:
        results[0].is_leader, experiment.winner_variant_id = True, results[0].variant_id
    record_event(
        db,
        actor_id=owner.id,
        action="ads.experiment_started",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"experiment_id": str(experiment.id), "synthetic": True},
    )
    db.commit()
    return experiment_response(db, owner, experiment)


def adopt_experiment_winner(
    db: Session, owner: User, experiment: AdExperiment, idempotency_key: str
) -> dict[str, object]:
    if experiment.winner_variant_id is None or experiment.insufficient_data:
        raise HTTPException(422, "No deterministic experiment winner is available.")
    if experiment.status not in {"running", "winner_adopted", "completed"}:
        raise HTTPException(422, "The experiment is not ready for winner adoption.")
    variant = db.scalar(
        select(AdExperimentVariant).where(
            AdExperimentVariant.owner_id == owner.id,
            AdExperimentVariant.id == experiment.winner_variant_id,
            AdExperimentVariant.experiment_id == experiment.id,
        )
    )
    if variant is None or variant.creative_id is None:
        raise HTTPException(422, "The winning variant has no exact approved creative.")
    creative = db.scalar(
        select(AdCreative).where(
            AdCreative.owner_id == owner.id,
            AdCreative.id == variant.creative_id,
            AdCreative.campaign_id == experiment.campaign_id,
            AdCreative.approval_status == "approved",
        )
    )
    if creative is None:
        raise HTTPException(422, "The winning exact creative is unavailable.")
    campaign = campaign_or_404(db, owner, experiment.campaign_id)
    existing = db.scalar(
        select(AdJob).where(
            AdJob.owner_id == owner.id,
            AdJob.idempotency_key == idempotency_key,
        )
    )
    job = existing or queue_job(
        db,
        owner,
        campaign,
        "adopt_experiment_winner",
        idempotency_key,
        {
            "experiment_id": str(experiment.id),
            "variant_id": str(variant.id),
            "creative_id": str(creative.id),
        },
        entity_type="campaign",
        entity_id=campaign.id,
    )
    experiment.status = "winner_adopted"
    record_event(
        db,
        actor_id=owner.id,
        action="ads.experiment_winner_adopted",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={
            "experiment_id": str(experiment.id),
            "variant_id": str(variant.id),
            "job_id": str(job.id),
            "synthetic": True,
        },
    )
    db.commit()
    return {
        "status": experiment.status,
        "winner_variant_id": variant.id,
        "job": {"id": job.id, "status": job.status},
        "synthetic": True,
    }


def compare_providers(
    db: Session, owner: User, product_id: uuid.UUID | None = None
) -> dict[str, object]:
    stmt = select(AdCampaign).where(AdCampaign.owner_id == owner.id)
    if product_id:
        stmt = stmt.where(AdCampaign.product_id == product_id)
    rows = list(db.scalars(stmt))
    currencies: set[str] = set()
    providers: dict[str, dict[str, object]] = {}
    for campaign in rows:
        state = campaign_state(db, owner.id, campaign)
        currency = str(state.get("currency") or "")
        if currency:
            currencies.add(currency)
        metrics = metric_snapshot(db, owner.id, campaign.id)
        providers[campaign.provider] = {
            "campaign_id": campaign.id,
            "objective": campaign.objective,
            "metrics": metrics,
            "currency": currency,
            "synthetic": True,
        }
    compatible = len(currencies) <= 1
    return {
        "product_id": product_id,
        "providers": providers,
        "currency_compatible": compatible,
        "money": "available" if compatible else "Unavailable / incompatible currency",
        "objective_warning": (
            "Campaign objectives may differ; compare directionally only."
            if len({str(item.get("objective")) for item in providers.values()}) > 1
            else None
        ),
        "synthetic": True,
    }


def optimization_history(db: Session, owner: User, limit: int = 100) -> list[dict[str, object]]:
    from vayujit_api.audit.models import AuditEvent

    return [
        {
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "occurred_at": event.occurred_at,
            "metadata": event.metadata_json,
            "synthetic": True,
        }
        for event in db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.action.like("ads.optimization%")
                | AuditEvent.action.like("ads.experiment%"),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(limit)
        )
    ]


def optimization_overview(db: Session, owner: User) -> dict[str, object]:
    recommendations = list_recommendations(db, owner, status="open")
    anomalies = detect_anomalies(db, owner)
    fatigue = detect_fatigue(db, owner)
    rules = list(
        db.scalars(
            select(AdOptimizationRule).where(
                AdOptimizationRule.owner_id == owner.id,
                AdOptimizationRule.enabled.is_(True),
                AdOptimizationRule.archived_at.is_(None),
            )
        )
    )
    experiments = list(
        db.scalars(
            select(AdExperiment).where(
                AdExperiment.owner_id == owner.id, AdExperiment.status.in_(["draft", "running"])
            )
        )
    )
    return {
        "recommendations": recommendations,
        "critical_anomalies": [item for item in anomalies if item["severity"] == "critical"],
        "anomalies": anomalies,
        "creative_fatigue": fatigue,
        "experiments": [experiment_response(db, owner, item) for item in experiments],
        "enabled_rules": len(rules),
        "auto_action": any(item.mode == "auto_apply_bounded" for item in rules),
        "guardrails": {"synthetic": True, "unrestricted_spend": False},
        "synthetic": True,
    }


def preview_rollback(db: Session, owner: User, execution_id: uuid.UUID) -> dict[str, object]:
    execution = db.scalar(
        select(AdOptimizationExecution).where(
            AdOptimizationExecution.owner_id == owner.id,
            AdOptimizationExecution.id == execution_id,
        )
    )
    if execution is None:
        raise HTTPException(404, "Optimization execution not found.")
    if execution.status not in {"succeeded", "queued", "running", "retry_wait"}:
        raise HTTPException(409, "This optimization execution is not eligible for rollback.")
    reversible = {
        "pause_campaign": "resume_campaign",
        "resume_campaign": "pause_campaign",
        "increase_budget": "rollback_budget",
        "decrease_budget": "rollback_budget",
        "replace_creative": "rollback_creative",
    }
    action = reversible.get(execution.action)
    blockers: list[str] = (
        [] if action else ["This optimization action has no safe local rollback executor."]
    )
    return {
        "execution_id": execution.id,
        "action": action,
        "current_state": execution.after_state_json,
        "rollback_state": execution.rollback_state_json,
        "blockers": blockers,
        "warnings": [
            "Rollback is explicit, owner-scoped, and queued through the durable Ads worker."
        ],
        "mutating": False,
        "synthetic": True,
    }


def confirm_rollback(
    db: Session,
    owner: User,
    execution_id: uuid.UUID,
    *,
    confirm: bool,
    idempotency_key: str,
) -> dict[str, object]:
    if not confirm:
        raise HTTPException(422, "Explicit confirmation is required before rollback.")
    preview = preview_rollback(db, owner, execution_id)
    rollback_blockers = cast(list[object], preview["blockers"])
    if rollback_blockers:
        raise HTTPException(422, str(rollback_blockers[0]))
    execution = db.scalar(
        select(AdOptimizationExecution).where(
            AdOptimizationExecution.owner_id == owner.id,
            AdOptimizationExecution.id == execution_id,
        )
    )
    if execution is None:
        raise HTTPException(404, "Optimization execution not found.")
    existing = db.scalar(
        select(AdOptimizationExecution).where(
            AdOptimizationExecution.owner_id == owner.id,
            AdOptimizationExecution.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return {
            "execution": {"id": existing.id, "status": existing.status, "idempotent_reuse": True},
            "synthetic": True,
        }
    campaign = db.scalar(
        select(AdCampaign).where(
            AdCampaign.owner_id == owner.id,
            AdCampaign.id
            == execution.after_state_json.get("campaign_id", execution.recommendation_id),
        )
    )
    if campaign is None:
        recommendation = db.scalar(
            select(AdOptimizationRecommendation).where(
                AdOptimizationRecommendation.id == execution.recommendation_id,
                AdOptimizationRecommendation.owner_id == owner.id,
            )
        )
        campaign = (
            db.scalar(
                select(AdCampaign).where(
                    AdCampaign.owner_id == owner.id, AdCampaign.id == recommendation.campaign_id
                )
            )
            if recommendation
            else None
        )
    if campaign is None:
        raise HTTPException(404, "Ads campaign not found for rollback.")
    operation = "resume" if execution.action == "pause_campaign" else "pause"
    request: dict[str, object] = {"campaign_id": str(campaign.id), "rollback_of": str(execution.id)}
    entity_type = "campaign"
    entity_id = campaign.id
    if execution.action in {"increase_budget", "decrease_budget"}:
        operation = "rollback_budget"
        request.update(
            {
                "daily_amount": execution.before_state_json.get("daily_budget"),
                "currency": execution.before_state_json.get("currency"),
            }
        )
    elif execution.action == "replace_creative":
        operation = "rollback_creative"
        request["creative_id"] = execution.before_state_json.get("creative_id")
        entity_type = "ad"
        ad = db.scalar(
            select(Ad)
            .where(Ad.owner_id == owner.id, Ad.campaign_id == campaign.id)
            .order_by(Ad.created_at.desc())
        )
        if ad is None:
            raise HTTPException(422, "The Ads ad is unavailable for creative rollback.")
        entity_id = ad.id
    job = queue_job(
        db,
        owner,
        campaign,
        operation,
        idempotency_key,
        request,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    execution.status = "rollback_queued"
    execution.result_json = {"rollback_job_id": str(job.id), "synthetic": True}
    execution.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="ads.optimization_rollback_confirmed",
        entity_type="ad_campaign",
        entity_id=campaign.id,
        metadata={"execution_id": str(execution.id), "job_id": str(job.id), "synthetic": True},
    )
    db.commit()
    return {
        "execution": {
            "id": execution.id,
            "status": execution.status,
            "job_id": job.id,
            "idempotent_reuse": False,
        },
        "job": {"id": job.id, "status": job.status},
        "synthetic": True,
    }
