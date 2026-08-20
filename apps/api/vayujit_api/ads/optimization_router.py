from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ads.models import (
    AdCampaign,
    AdExperiment,
    AdOptimizationExecution,
    AdOptimizationRecommendation,
    AdOptimizationRule,
    AdPerformanceAnomaly,
)
from vayujit_api.ads.optimization import (
    LOW_RISK_AUTO_ACTIONS,
    adopt_experiment_winner,
    compare_providers,
    confirm_recommendation,
    confirm_rollback,
    create_experiment,
    detect_anomalies,
    detect_fatigue,
    dismiss_recommendation,
    evaluate_campaigns,
    experiment_response,
    get_recommendation,
    list_recommendations,
    optimization_history,
    optimization_overview,
    preview_recommendation,
    preview_rollback,
    rule_response,
    start_experiment,
    validate_rule_payload,
)
from vayujit_api.ads.schemas import (
    ExperimentCreateRequest,
    OptimizationConfirmRequest,
    OptimizationPreviewRequest,
    OptimizationRulePatch,
    OptimizationRuleRequest,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user

router = APIRouter(prefix="/api/v1/ads", tags=["ads-optimization"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _rule(db: Session, owner: User, rule_id: uuid.UUID) -> AdOptimizationRule:
    row = db.scalar(
        select(AdOptimizationRule).where(
            AdOptimizationRule.owner_id == owner.id, AdOptimizationRule.id == rule_id
        )
    )
    if row is None:
        raise HTTPException(404, "Optimization rule not found.")
    return row


@router.get("/optimization/overview")
@router.get("/intelligence/overview")
def intelligence_overview(db: DB, owner: Owner) -> dict[str, object]:
    return optimization_overview(db, owner)


@router.post("/optimization/evaluate")
@router.post("/recommendations/evaluate")
def optimization_evaluate(
    db: DB, owner: Owner, campaign_id: uuid.UUID | None = None
) -> dict[str, object]:
    rows = evaluate_campaigns(db, owner, campaign_id)
    return {
        "recommendations": [
            __import__(
                "vayujit_api.ads.optimization", fromlist=["recommendation_response"]
            ).recommendation_response(row)
            for row in rows
        ],
        "synthetic": True,
    }


@router.get("/recommendations")
def recommendations_list(
    db: DB,
    owner: Owner,
    provider: str | None = None,
    campaign_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    return list_recommendations(
        db,
        owner,
        provider=provider,
        campaign_id=campaign_id,
        product_id=product_id,
        recommendation_type=type,
        severity=severity,
        status=status,
    )


@router.get("/recommendations/{recommendation_id}")
def recommendation_detail(recommendation_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.ads.optimization import recommendation_response

    return recommendation_response(get_recommendation(db, owner, recommendation_id))


@router.post("/recommendations/{recommendation_id}/preview")
def recommendation_preview(
    recommendation_id: uuid.UUID, payload: OptimizationPreviewRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return preview_recommendation(
        db,
        owner,
        get_recommendation(db, owner, recommendation_id),
        payload.action,
        payload.replacement_creative_id,
    )


@router.post("/recommendations/{recommendation_id}/confirm")
def recommendation_confirm(
    recommendation_id: uuid.UUID, payload: OptimizationConfirmRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return confirm_recommendation(
        db,
        owner,
        get_recommendation(db, owner, recommendation_id),
        action=payload.action,
        preview_fingerprint=payload.preview_fingerprint,
        idempotency_key=payload.idempotency_key,
        confirm=payload.confirm,
        replacement_creative_id=payload.replacement_creative_id,
    )


@router.post("/recommendations/{recommendation_id}/dismiss")
def recommendation_dismiss(recommendation_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return dismiss_recommendation(db, owner, get_recommendation(db, owner, recommendation_id))


@router.get("/optimization-rules")
def rule_list(db: DB, owner: Owner, include_archived: bool = False) -> list[dict[str, object]]:
    stmt = select(AdOptimizationRule).where(AdOptimizationRule.owner_id == owner.id)
    if not include_archived:
        stmt = stmt.where(AdOptimizationRule.archived_at.is_(None))
    return [
        rule_response(row)
        for row in db.scalars(stmt.order_by(AdOptimizationRule.created_at.desc()))
    ]


@router.post("/optimization-rules", status_code=201)
def rule_create(payload: OptimizationRuleRequest, db: DB, owner: Owner) -> dict[str, object]:
    validate_rule_payload(payload.model_dump(mode="json"), payload.provider)
    if payload.mode == "auto_apply_bounded" and (
        payload.action not in LOW_RISK_AUTO_ACTIONS
        or payload.action not in set(payload.allowed_actions or [payload.action])
    ):
        raise HTTPException(
            422, "Only explicitly whitelisted low-risk actions can be auto-applied."
        )
    from vayujit_api.ads.optimization import now

    row = AdOptimizationRule(
        owner_id=owner.id,
        campaign_id=payload.campaign_id,
        provider=payload.provider,
        objective=payload.objective,
        name=payload.name,
        enabled=payload.enabled,
        version=1,
        mode=payload.mode,
        rule_json={
            "metric": payload.metric,
            "operator": payload.operator,
            "threshold": float(payload.threshold),
            "action": payload.action,
        },
        guardrails_json=payload.guardrails,
        allowed_actions_json=payload.allowed_actions or [payload.action],
        metric_window_days=payload.window_days,
        cooldown_seconds=payload.cooldown_seconds,
        daily_action_limit=payload.daily_action_limit,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return rule_response(row)


@router.get("/optimization-rules/{rule_id}")
def rule_detail(rule_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return rule_response(_rule(db, owner, rule_id))


@router.patch("/optimization-rules/{rule_id}")
def rule_update(
    rule_id: uuid.UUID, payload: OptimizationRulePatch, db: DB, owner: Owner
) -> dict[str, object]:
    row = _rule(db, owner, rule_id)
    values = payload.model_dump(exclude_none=True)
    data = dict(row.rule_json or {})
    changed = False
    for key in ("metric", "operator", "threshold", "action"):
        if key in values:
            data[key] = float(values[key]) if key == "threshold" else values[key]
            changed = True
    validate_rule_payload(
        {**data, "window_days": values.get("window_days", row.metric_window_days)}, row.provider
    )
    for key in (
        "name",
        "enabled",
        "mode",
        "guardrails",
        "allowed_actions",
        "cooldown_seconds",
        "daily_action_limit",
    ):
        if key in values:
            setattr(
                row,
                (
                    "guardrails_json"
                    if key == "guardrails"
                    else "allowed_actions_json" if key == "allowed_actions" else key
                ),
                values[key],
            )
    if "window_days" in values:
        row.metric_window_days = values["window_days"]
    if changed:
        row.version += 1
    row.rule_json, row.updated_at = (
        data,
        __import__("vayujit_api.ads.optimization", fromlist=["now"]).now(),
    )
    db.commit()
    db.refresh(row)
    return rule_response(row)


@router.post("/optimization-rules/{rule_id}/duplicate", status_code=201)
def rule_duplicate(rule_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.ads.optimization import now

    source = _rule(db, owner, rule_id)
    row = AdOptimizationRule(
        owner_id=owner.id,
        campaign_id=source.campaign_id,
        provider=source.provider,
        objective=source.objective,
        name=f"{source.name} copy",
        enabled=False,
        version=source.version + 1,
        mode="recommend_only",
        rule_json=dict(source.rule_json),
        guardrails_json=dict(source.guardrails_json),
        allowed_actions_json=list(source.allowed_actions_json),
        metric_window_days=source.metric_window_days,
        cooldown_seconds=source.cooldown_seconds,
        daily_action_limit=source.daily_action_limit,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return rule_response(row)


def _set_rule_state(
    db: Session,
    owner: User,
    rule_id: uuid.UUID,
    *,
    enabled: bool | None = None,
    archived: bool | None = None,
) -> dict[str, object]:
    from vayujit_api.ads.optimization import now

    row = _rule(db, owner, rule_id)
    if enabled is not None:
        row.enabled = enabled
    if archived is not None:
        row.archived_at = now() if archived else None
    row.updated_at = now()
    db.commit()
    db.refresh(row)
    return rule_response(row)


@router.post("/optimization-rules/{rule_id}/enable")
def rule_enable(rule_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _set_rule_state(db, owner, rule_id, enabled=True)


@router.post("/optimization-rules/{rule_id}/disable")
def rule_disable(rule_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _set_rule_state(db, owner, rule_id, enabled=False)


@router.post("/optimization-rules/{rule_id}/archive")
def rule_archive(rule_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _set_rule_state(db, owner, rule_id, enabled=False, archived=True)


@router.post("/optimization-rules/{rule_id}/restore")
def rule_restore(rule_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _set_rule_state(db, owner, rule_id, archived=False)


@router.get("/anomalies")
def anomaly_list(
    db: DB, owner: Owner, campaign_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    return detect_anomalies(db, owner, campaign_id)


@router.post("/anomalies/detect")
def anomaly_detect(db: DB, owner: Owner, campaign_id: uuid.UUID | None = None) -> dict[str, object]:
    return {"anomalies": detect_anomalies(db, owner, campaign_id), "synthetic": True}


@router.post("/anomalies/{anomaly_id}/acknowledge")
def anomaly_ack(anomaly_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdPerformanceAnomaly).where(
            AdPerformanceAnomaly.owner_id == owner.id, AdPerformanceAnomaly.id == anomaly_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads anomaly not found.")
    row.status = "acknowledged"
    db.commit()
    return {"id": row.id, "status": row.status, "synthetic": True}


@router.post("/anomalies/{anomaly_id}/dismiss")
def anomaly_dismiss(anomaly_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdPerformanceAnomaly).where(
            AdPerformanceAnomaly.owner_id == owner.id, AdPerformanceAnomaly.id == anomaly_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads anomaly not found.")
    row.status = "dismissed"
    db.commit()
    return {"id": row.id, "status": row.status, "synthetic": True}


@router.get("/creative-fatigue")
def fatigue_list(
    db: DB, owner: Owner, campaign_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    return detect_fatigue(db, owner, campaign_id)


@router.post("/creative-fatigue/detect")
def fatigue_detect(db: DB, owner: Owner, campaign_id: uuid.UUID | None = None) -> dict[str, object]:
    return {"signals": detect_fatigue(db, owner, campaign_id), "synthetic": True}


@router.post("/experiments", status_code=201)
def experiment_create(payload: ExperimentCreateRequest, db: DB, owner: Owner) -> dict[str, object]:
    return create_experiment(db, owner, payload)


@router.get("/experiments")
def experiment_list(
    db: DB, owner: Owner, campaign_id: uuid.UUID | None = None, status: str | None = None
) -> list[dict[str, object]]:
    stmt = select(AdExperiment).where(AdExperiment.owner_id == owner.id)
    if campaign_id:
        stmt = stmt.where(AdExperiment.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(AdExperiment.status == status)
    return [
        experiment_response(db, owner, row)
        for row in db.scalars(stmt.order_by(AdExperiment.created_at.desc()))
    ]


@router.get("/experiments/{experiment_id}")
def experiment_detail(experiment_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdExperiment).where(
            AdExperiment.owner_id == owner.id, AdExperiment.id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads experiment not found.")
    return experiment_response(db, owner, row)


@router.post("/experiments/{experiment_id}/start")
def experiment_start(experiment_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdExperiment).where(
            AdExperiment.owner_id == owner.id, AdExperiment.id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads experiment not found.")
    return start_experiment(db, owner, row)


@router.post("/experiments/{experiment_id}/stop")
def experiment_stop(experiment_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdExperiment).where(
            AdExperiment.owner_id == owner.id, AdExperiment.id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads experiment not found.")
    row.status = "stopped"
    db.commit()
    return experiment_response(db, owner, row)


@router.get("/experiments/{experiment_id}/results")
def experiment_results(experiment_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdExperiment).where(
            AdExperiment.owner_id == owner.id, AdExperiment.id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads experiment not found.")
    return {"experiment": experiment_response(db, owner, row), "synthetic": True}


@router.post("/experiments/{experiment_id}/winner/preview")
def experiment_winner_preview(experiment_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AdExperiment).where(
            AdExperiment.owner_id == owner.id, AdExperiment.id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads experiment not found.")
    if row.winner_variant_id is None or row.insufficient_data:
        return {
            "status": "insufficient_data",
            "blockers": ["No deterministic winner is available."],
            "synthetic": True,
        }
    return {
        "status": "preview",
        "winner_variant_id": row.winner_variant_id,
        "warning": "Winner adoption requires explicit confirmation.",
        "synthetic": True,
    }


@router.post("/experiments/{experiment_id}/winner/confirm")
def experiment_winner_confirm(
    experiment_id: uuid.UUID, payload: dict[str, object], db: DB, owner: Owner
) -> dict[str, object]:
    if not payload.get("confirm"):
        raise HTTPException(422, "Explicit confirmation is required before winner adoption.")
    row = db.scalar(
        select(AdExperiment).where(
            AdExperiment.owner_id == owner.id, AdExperiment.id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(404, "Ads experiment not found.")
    if row.winner_variant_id is None or row.insufficient_data:
        raise HTTPException(422, "No deterministic experiment winner is available.")
    return adopt_experiment_winner(
        db,
        owner,
        row,
        str(payload.get("idempotency_key") or f"experiment-winner:{row.id}"),
    )


@router.get("/comparison")
@router.get("/cross-provider/comparison")
def provider_comparison(
    db: DB, owner: Owner, product_id: uuid.UUID | None = None
) -> dict[str, object]:
    return compare_providers(db, owner, product_id)


@router.get("/optimization-history")
@router.get("/history/optimization")
def optimization_history_route(
    db: DB, owner: Owner, limit: int = Query(default=100, ge=1, le=500)
) -> list[dict[str, object]]:
    return optimization_history(db, owner, limit)


@router.get("/optimization/engine/performance")
def engine_performance(db: DB, owner: Owner) -> dict[str, object]:
    started = time.perf_counter()
    campaigns = list(db.scalars(select(AdCampaign).where(AdCampaign.owner_id == owner.id)))
    rules = list(
        db.scalars(select(AdOptimizationRule).where(AdOptimizationRule.owner_id == owner.id))
    )
    recs = evaluate_campaigns(db, owner)
    anomalies = detect_anomalies(db, owner)
    fatigue = detect_fatigue(db, owner)
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "campaigns_evaluated": len(campaigns),
        "rules_evaluated": len(rules),
        "recommendations_generated": len(recs),
        "anomalies_detected": len(anomalies),
        "fatigue_signals": len(fatigue),
        "elapsed_ms": round(elapsed, 3),
        "synthetic": True,
    }


@router.get("/calendar/optimization")
def optimization_calendar(db: DB, owner: Owner) -> dict[str, object]:
    experiments = list(db.scalars(select(AdExperiment).where(AdExperiment.owner_id == owner.id)))
    recommendations = list(
        db.scalars(
            select(AdOptimizationRecommendation).where(
                AdOptimizationRecommendation.owner_id == owner.id,
            )
        )
    )
    events: list[dict[str, object]] = []
    for experiment in experiments:
        if experiment.start_at:
            events.append(
                {
                    "type": "experiment_start",
                    "id": experiment.id,
                    "at": experiment.start_at,
                    "synthetic": True,
                }
            )
        if experiment.end_at:
            events.append(
                {
                    "type": "experiment_end",
                    "id": experiment.id,
                    "at": experiment.end_at,
                    "synthetic": True,
                }
            )
    for recommendation in recommendations:
        events.append(
            {
                "type": "optimization_effective_window",
                "id": recommendation.id,
                "at": recommendation.metric_window_end,
                "action": recommendation.recommendation_type,
                "synthetic": True,
            }
        )
    return {"events": sorted(events, key=lambda item: str(item.get("at") or "")), "synthetic": True}


@router.get("/campaigns/{campaign_id}/intelligence")
def campaign_intelligence(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    experiments = list(
        db.scalars(
            select(AdExperiment).where(
                AdExperiment.owner_id == owner.id,
                AdExperiment.campaign_id == campaign_id,
            )
        )
    )
    return {
        "campaign_id": campaign_id,
        "recommendations": list_recommendations(db, owner, campaign_id=campaign_id),
        "anomalies": detect_anomalies(db, owner, campaign_id),
        "creative_fatigue": detect_fatigue(db, owner, campaign_id),
        "experiments": [experiment_response(db, owner, item) for item in experiments],
        "history": optimization_history(db, owner),
        "synthetic": True,
    }


@router.get("/product-channel/{product_id}/intelligence")
def product_channel_intelligence(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaigns = list(
        db.scalars(
            select(AdCampaign).where(
                AdCampaign.owner_id == owner.id, AdCampaign.product_id == product_id
            )
        )
    )
    experiments = (
        list(
            db.scalars(
                select(AdExperiment).where(
                    AdExperiment.owner_id == owner.id,
                    AdExperiment.campaign_id.in_([campaign.id for campaign in campaigns]),
                )
            )
        )
        if campaigns
        else []
    )
    return {
        "product_id": product_id,
        "campaigns": [
            {
                "id": campaign.id,
                "provider": campaign.provider,
                "objective": campaign.objective,
                "state": campaign.state,
                "synthetic": True,
            }
            for campaign in campaigns
        ],
        "providers": [
            {
                "provider": campaign.provider,
                "campaign_id": campaign.id,
                "objective": campaign.objective,
                "metrics": __import__(
                    "vayujit_api.ads.optimization", fromlist=["metric_snapshot"]
                ).metric_snapshot(db, owner.id, campaign.id),
                "actions": [
                    "open_recommendation",
                    "preview_budget_change",
                    "preview_bid_change",
                    "preview_creative_replacement",
                    "open_experiment",
                    "pause",
                    "resume",
                    "open_recovery",
                ],
                "synthetic": True,
            }
            for campaign in campaigns
        ],
        "recommendations": list_recommendations(db, owner, product_id=product_id),
        "anomalies": [
            item for campaign in campaigns for item in detect_anomalies(db, owner, campaign.id)
        ],
        "creative_fatigue": [
            item for campaign in campaigns for item in detect_fatigue(db, owner, campaign.id)
        ],
        "experiments": [experiment_response(db, owner, item) for item in experiments],
        "budget_opportunities": [
            item
            for item in list_recommendations(db, owner, product_id=product_id)
            if item.get("type") in {"increase_budget", "decrease_budget"}
        ],
        "recovery": {"available": True, "synthetic": True},
        "update_state": "local_simulation",
        "synthetic": True,
    }


@router.post("/optimization/executions/{execution_id}/rollback/preview")
def execution_rollback_preview(execution_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return preview_rollback(db, owner, execution_id)


@router.post("/optimization/executions/{execution_id}/rollback/confirm")
def execution_rollback_confirm(
    execution_id: uuid.UUID, payload: dict[str, object], db: DB, owner: Owner
) -> dict[str, object]:
    return confirm_rollback(
        db,
        owner,
        execution_id,
        confirm=bool(payload.get("confirm")),
        idempotency_key=str(payload.get("idempotency_key") or ""),
    )


@router.get("/alerts")
def optimization_alerts(db: DB, owner: Owner) -> dict[str, object]:
    return {
        "anomalies": detect_anomalies(db, owner),
        "creative_fatigue": detect_fatigue(db, owner),
        "synthetic": True,
    }


@router.get("/optimization/executions")
def execution_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "id": row.id,
            "recommendation_id": row.recommendation_id,
            "job_id": row.job_id,
            "action": row.action,
            "status": row.status,
            "before_state": row.before_state_json,
            "after_state": row.after_state_json,
            "rollback_state": row.rollback_state_json,
            "correlation_id": row.correlation_id,
            "synthetic": True,
        }
        for row in db.scalars(
            select(AdOptimizationExecution)
            .where(AdOptimizationExecution.owner_id == owner.id)
            .order_by(AdOptimizationExecution.created_at.desc())
        )
    ]
