from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import (
    IntelligenceClaim,
    IntelligenceClaimEvidence,
    IntelligenceEvidence,
    IntelligenceOpportunity,
    IntelligenceOpportunityReview,
    IntelligenceResearchProject,
    IntelligenceResearchRun,
    IntelligenceRule,
    IntelligenceRuleCategory,
    IntelligenceRuleEvaluation,
    IntelligenceSource,
)
from vayujit_api.intelligence.policy import (
    DEFAULT_FRESHNESS_POLICIES,
    UNTRUSTED_EXTERNAL_DATA,
    UnsafeURL,
    enforce_access_method,
    freshness_status,
    safe_external_content,
    validate_metadata,
    validate_source_url,
)
from vayujit_api.intelligence.schemas import (
    ClaimCreate,
    EvidenceCreate,
    OpportunityCreate,
    OpportunityReviewRequest,
    ResearchProjectCreate,
    ResearchProjectUpdate,
    ResearchRunCreate,
    RuleCreate,
    RuleUpdate,
    SourceCreate,
    SourceUpdate,
)

DEFAULT_CATEGORIES = (
    ("physical", "Physical"),
    ("logistics", "Logistics"),
    ("safety", "Safety"),
    ("regulatory", "Regulatory"),
    ("economics", "Economics"),
    ("market", "Market"),
    ("competition", "Competition"),
    ("supplier", "Supplier"),
    ("risk", "Risk"),
)


def now() -> datetime:
    return datetime.now(UTC)


def _correlation() -> str:
    return correlation_id() or uuid.uuid4().hex


def _event(
    db: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, object] | None = None,
) -> None:
    record_event(
        db,
        actor_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
    )


def _require_enabled() -> None:
    if not get_settings().intelligence_enabled:
        raise HTTPException(503, "Intelligence is not enabled in this environment.")


def _safe_url(value: str | None) -> str | None:
    try:
        return validate_source_url(value)
    except UnsafeURL as exc:
        raise HTTPException(
            422, "Source URL is not allowed by the Intelligence safety policy."
        ) from exc


def _owner_project(db: Session, user: User, project_id: uuid.UUID) -> IntelligenceResearchProject:
    project = db.scalar(
        select(IntelligenceResearchProject).where(
            IntelligenceResearchProject.id == project_id,
            IntelligenceResearchProject.owner_id == user.id,
        )
    )
    if not project:
        raise HTTPException(404, "Research project not found.")
    return project


def create_project(
    db: Session, user: User, data: ResearchProjectCreate
) -> IntelligenceResearchProject:
    _require_enabled()
    duplicate = db.scalar(
        select(IntelligenceResearchProject).where(
            IntelligenceResearchProject.owner_id == user.id,
            IntelligenceResearchProject.name == data.name,
        )
    )
    if duplicate is not None:
        raise HTTPException(409, "A research project with this name already exists.")
    stamp = now()
    project = IntelligenceResearchProject(
        owner_id=user.id, created_at=stamp, updated_at=stamp, **data.model_dump()
    )
    db.add(project)
    db.flush()
    _event(db, user, "research_project_created", "intelligence_research_project", project.id)
    return project


def update_project(
    db: Session, user: User, project_id: uuid.UUID, data: ResearchProjectUpdate
) -> IntelligenceResearchProject:
    project = _owner_project(db, user, project_id)
    if project.status == "archived":
        raise HTTPException(409, "Archived research projects cannot be edited.")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    project.updated_at = now()
    db.flush()
    return project


def archive_project(db: Session, user: User, project_id: uuid.UUID) -> IntelligenceResearchProject:
    project = _owner_project(db, user, project_id)
    if project.status != "archived":
        project.status = "archived"
        project.archived_at = now()
        project.updated_at = now()
        _event(db, user, "research_project_archived", "intelligence_research_project", project.id)
    return project


def create_run(
    db: Session, user: User, project_id: uuid.UUID, data: ResearchRunCreate
) -> IntelligenceResearchRun:
    _require_enabled()
    project = _owner_project(db, user, project_id)
    if project.status == "archived":
        raise HTTPException(409, "Archived research projects cannot run.")
    if not get_settings().intelligence_research_execution_enabled:
        raise HTTPException(409, "Research execution is disabled; configure local execution first.")
    key = (
        data.idempotency_key
        or hashlib.sha256(
            f"{project_id}:{data.ruleset_version}:{data.source_policy_reference}:"
            f"{sorted(map(str, data.source_ids))}".encode()
        ).hexdigest()
    )
    prior = db.scalar(
        select(IntelligenceResearchRun).where(
            IntelligenceResearchRun.owner_id == user.id,
            IntelligenceResearchRun.idempotency_key == key,
        )
    )
    if prior:
        return prior
    sources = []
    for source_id in data.source_ids:
        source = db.scalar(
            select(IntelligenceSource).where(
                IntelligenceSource.id == source_id, IntelligenceSource.owner_id == user.id
            )
        )
        if not source:
            raise HTTPException(404, "Research source not found.")
        if not source.enabled:
            raise HTTPException(409, "Disabled sources cannot be used for a new research run.")
        sources.append(source)
    stamp = now()
    run = IntelligenceResearchRun(
        owner_id=user.id,
        project_id=project.id,
        status="completed",
        started_at=stamp,
        completed_at=stamp,
        correlation_id=_correlation(),
        ruleset_version=data.ruleset_version,
        source_policy_reference=data.source_policy_reference,
        summary_json={"source_count": len(sources), "execution": "local-foundation-only"},
        idempotency_key=key,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(run)
    db.flush()
    _event(
        db,
        user,
        "research_started",
        "intelligence_research_run",
        run.id,
        {"source_count": len(sources)},
    )
    _event(
        db,
        user,
        "research_completed",
        "intelligence_research_run",
        run.id,
        {"source_count": len(sources)},
    )
    return run


def create_source(db: Session, user: User, data: SourceCreate) -> IntelligenceSource:
    _require_enabled()
    url = _safe_url(data.url_or_domain)
    method = enforce_access_method(data.access_method)
    validate_metadata(data.metadata)
    if (
        method in {"api", "approved_web_fetch", "provider_connector"}
        and not get_settings().intelligence_external_research_enabled
    ):
        enabled = False
        configuration_status = "external_research_disabled"
    else:
        enabled = False
        configuration_status = data.configuration_status
    stamp = now()
    source = IntelligenceSource(
        owner_id=user.id,
        source_type=data.source_type,
        display_name=data.display_name,
        provider=data.provider,
        url_or_domain=url,
        enabled=enabled,
        trust_classification=data.trust_classification,
        access_method=method,
        configuration_status=configuration_status,
        terms_policy_status=data.terms_policy_status,
        metadata_json=data.metadata,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(source)
    db.flush()
    _event(db, user, "source_created", "intelligence_source", source.id, {"access_method": method})
    return source


def update_source(
    db: Session, user: User, source_id: uuid.UUID, data: SourceUpdate
) -> IntelligenceSource:
    source = db.scalar(
        select(IntelligenceSource).where(
            IntelligenceSource.id == source_id, IntelligenceSource.owner_id == user.id
        )
    )
    if not source:
        raise HTTPException(404, "Research source not found.")
    payload = data.model_dump(exclude_unset=True)
    if (
        "enabled" in payload
        and payload["enabled"]
        and source.access_method in {"api", "approved_web_fetch", "provider_connector"}
        and not get_settings().intelligence_external_research_enabled
    ):
        raise HTTPException(409, "External research is disabled by configuration.")
    for key, value in payload.items():
        setattr(source, "metadata_json" if key == "metadata" else key, value)
    source.updated_at = now()
    db.flush()
    if "enabled" in payload:
        _event(
            db,
            user,
            "source_enabled" if source.enabled else "source_disabled",
            "intelligence_source",
            source.id,
        )
    return source


def create_evidence(db: Session, user: User, data: EvidenceCreate) -> IntelligenceEvidence:
    _require_enabled()
    source = db.scalar(
        select(IntelligenceSource).where(
            IntelligenceSource.id == data.source_id, IntelligenceSource.owner_id == user.id
        )
    )
    if not source:
        raise HTTPException(404, "Research source not found.")
    if not source.enabled and source.access_method != "manual_entry":
        raise HTTPException(409, "Disabled sources cannot receive new evidence.")
    if data.source_url:
        _safe_url(data.source_url)
    safe_external_content(data.excerpt_summary)
    validate_metadata(data.metadata)
    key = data.idempotency_key or f"{source.id}:{data.content_hash}:{data.observed_at.isoformat()}"
    prior = db.scalar(
        select(IntelligenceEvidence).where(
            IntelligenceEvidence.owner_id == user.id, IntelligenceEvidence.idempotency_key == key
        )
    )
    if prior:
        return prior
    if data.previous_evidence_id:
        previous = db.scalar(
            select(IntelligenceEvidence).where(
                IntelligenceEvidence.id == data.previous_evidence_id,
                IntelligenceEvidence.owner_id == user.id,
            )
        )
        if not previous:
            raise HTTPException(404, "Previous evidence item not found.")
        if previous.source_id != source.id:
            raise HTTPException(422, "Evidence lineage must remain within one source.")
    if data.research_run_id:
        run = db.scalar(
            select(IntelligenceResearchRun).where(
                IntelligenceResearchRun.id == data.research_run_id,
                IntelligenceResearchRun.owner_id == user.id,
            )
        )
        if not run:
            raise HTTPException(404, "Research run not found.")
    policy = DEFAULT_FRESHNESS_POLICIES.get(
        source.source_type, DEFAULT_FRESHNESS_POLICIES["manual"]
    )
    stamp = now()
    evidence = IntelligenceEvidence(
        owner_id=user.id,
        source_id=source.id,
        research_run_id=data.research_run_id,
        previous_evidence_id=data.previous_evidence_id,
        source_reference=data.source_reference,
        source_url=data.source_url,
        observed_at=data.observed_at,
        retrieved_at=stamp,
        content_type=data.content_type,
        normalized_value=data.normalized_value,
        excerpt_summary=data.excerpt_summary,
        content_hash=data.content_hash,
        trust_classification=(
            UNTRUSTED_EXTERNAL_DATA
            if source.access_method != "internal"
            else source.trust_classification
        ),
        verification_status=data.verification_status,
        freshness_status=freshness_status(
            data.observed_at, policy=policy, ttl_seconds=data.freshness_ttl_seconds, now=stamp
        ),
        freshness_ttl_seconds=data.freshness_ttl_seconds,
        metadata_json=data.metadata,
        correlation_id=_correlation(),
        idempotency_key=key,
        created_at=stamp,
    )
    db.add(evidence)
    db.flush()
    return evidence


def create_claim(db: Session, user: User, data: ClaimCreate) -> IntelligenceClaim:
    evidence = list(
        db.scalars(
            select(IntelligenceEvidence).where(
                IntelligenceEvidence.owner_id == user.id,
                IntelligenceEvidence.id.in_(data.evidence_ids),
            )
        )
    )
    if len(evidence) != len(set(data.evidence_ids)):
        raise HTTPException(404, "One or more supporting evidence items were not found.")
    if data.research_run_id:
        run = db.scalar(
            select(IntelligenceResearchRun).where(
                IntelligenceResearchRun.id == data.research_run_id,
                IntelligenceResearchRun.owner_id == user.id,
            )
        )
        if not run:
            raise HTTPException(404, "Research run not found.")
    stamp = now()
    claim = IntelligenceClaim(
        owner_id=user.id,
        research_run_id=data.research_run_id,
        claim_type=data.claim_type,
        normalized_value=data.normalized_value,
        unit=data.unit,
        currency=data.currency,
        confidence=data.confidence,
        verification_state=data.verification_state,
        correlation_id=_correlation(),
        created_at=stamp,
    )
    db.add(claim)
    db.flush()
    for evidence_id in data.evidence_ids:
        db.add(IntelligenceClaimEvidence(claim_id=claim.id, evidence_id=evidence_id))
    return claim


def ensure_categories(db: Session, user: User) -> list[IntelligenceRuleCategory]:
    rows = list(
        db.scalars(
            select(IntelligenceRuleCategory).where(IntelligenceRuleCategory.owner_id == user.id)
        )
    )
    existing = {row.category_key for row in rows}
    stamp = now()
    for key, name in DEFAULT_CATEGORIES:
        if key not in existing:
            row = IntelligenceRuleCategory(
                owner_id=user.id,
                category_key=key,
                display_name=name,
                enabled=True,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(row)
            rows.append(row)
    db.flush()
    return sorted(rows, key=lambda row: row.category_key)


def create_rule(db: Session, user: User, data: RuleCreate) -> IntelligenceRule:
    category = db.scalar(
        select(IntelligenceRuleCategory).where(
            IntelligenceRuleCategory.id == data.category_id,
            IntelligenceRuleCategory.owner_id == user.id,
        )
    )
    if not category:
        raise HTTPException(404, "Rule category not found.")
    prior = db.scalar(
        select(IntelligenceRule)
        .where(
            IntelligenceRule.owner_id == user.id, IntelligenceRule.logical_key == data.logical_key
        )
        .order_by(IntelligenceRule.version.desc())
    )
    version = (prior.version + 1) if prior else 1
    if prior:
        prior.enabled = False
    stamp = now()
    rule = IntelligenceRule(
        owner_id=user.id, version=version, created_at=stamp, updated_at=stamp, **data.model_dump()
    )
    db.add(rule)
    db.flush()
    _event(
        db,
        user,
        "rule_created" if version == 1 else "rule_updated",
        "intelligence_rule",
        rule.id,
        {"version": version},
    )
    return rule


def update_rule(db: Session, user: User, rule_id: uuid.UUID, data: RuleUpdate) -> IntelligenceRule:
    rule = db.scalar(
        select(IntelligenceRule).where(
            IntelligenceRule.id == rule_id, IntelligenceRule.owner_id == user.id
        )
    )
    if not rule:
        raise HTTPException(404, "Rule not found.")
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(rule, key, value)
    rule.updated_at = now()
    db.flush()
    if "enabled" in payload:
        _event(
            db,
            user,
            "rule_enabled" if rule.enabled else "rule_disabled",
            "intelligence_rule",
            rule.id,
        )
    return rule


def update_category(
    db: Session, user: User, category_id: uuid.UUID, enabled: bool
) -> IntelligenceRuleCategory:
    category = db.scalar(
        select(IntelligenceRuleCategory).where(
            IntelligenceRuleCategory.id == category_id, IntelligenceRuleCategory.owner_id == user.id
        )
    )
    if not category:
        raise HTTPException(404, "Rule category not found.")
    category.enabled = enabled
    category.updated_at = now()
    _event(
        db,
        user,
        "rule_category_enabled" if enabled else "rule_category_disabled",
        "intelligence_rule_category",
        category.id,
    )
    return category


def evaluate_opportunity(
    db: Session, user: User, opportunity: IntelligenceOpportunity
) -> list[dict[str, Any]]:
    locked = db.scalar(
        select(IntelligenceOpportunity)
        .where(
            IntelligenceOpportunity.id == opportunity.id,
            IntelligenceOpportunity.owner_id == user.id,
        )
        .with_for_update()
    )
    if locked is None:
        raise HTTPException(404, "Opportunity not found.")
    opportunity = locked
    categories = {
        row.id: row
        for row in db.scalars(
            select(IntelligenceRuleCategory).where(IntelligenceRuleCategory.owner_id == user.id)
        )
    }
    rules = list(
        db.scalars(
            select(IntelligenceRule)
            .where(IntelligenceRule.owner_id == user.id, IntelligenceRule.enabled.is_(True))
            .order_by(IntelligenceRule.priority.asc(), IntelligenceRule.version.desc())
        )
    )
    results: list[dict[str, Any]] = []
    score = 0.0
    blocked = False
    for rule in rules:
        category = categories.get(rule.category_id)
        if not category or not category.enabled:
            continue
        existing = db.scalar(
            select(IntelligenceRuleEvaluation).where(
                IntelligenceRuleEvaluation.owner_id == user.id,
                IntelligenceRuleEvaluation.rule_id == rule.id,
                IntelligenceRuleEvaluation.rule_version == rule.version,
                IntelligenceRuleEvaluation.subject_type == "opportunity",
                IntelligenceRuleEvaluation.subject_id == opportunity.id,
            )
        )
        if existing:
            score += float(existing.score_impact)
            blocked = blocked or existing.hard_block
            results.append(
                {
                    "rule_id": str(existing.rule_id),
                    "rule_version": existing.rule_version,
                    "category": category.category_key,
                    "result": existing.result,
                    "score_impact": float(existing.score_impact),
                    "hard_block": existing.hard_block,
                    "reason": existing.reason,
                }
            )
            continue
        conditions = rule.conditions or {}
        field = str(conditions.get("field", ""))
        expected = conditions.get("value")
        actual: Any = getattr(opportunity, field, None) if field else None
        passed = True
        if rule.operator == "exists":
            passed = actual is not None and actual != ""
        elif rule.operator == "gte":
            passed = (
                isinstance(actual, (int, float))
                and isinstance(expected, (int, float))
                and actual >= expected
            )
        elif rule.operator == "lte":
            passed = (
                isinstance(actual, (int, float))
                and isinstance(expected, (int, float))
                and actual <= expected
            )
        elif rule.operator == "in":
            passed = actual in (expected if isinstance(expected, list) else [])
        else:
            passed = False
        raw_impact = (
            rule.parameters.get("score_impact", 0) if isinstance(rule.parameters, dict) else 0
        )
        impact = float(raw_impact) if isinstance(raw_impact, (int, float, str)) else 0.0
        if not passed:
            score += impact
            blocked = blocked or rule.hard_block
        result = {
            "rule_id": str(rule.id),
            "rule_version": rule.version,
            "category": category.category_key,
            "result": "passed" if passed else "failed",
            "score_impact": impact if not passed else 0,
            "hard_block": rule.hard_block and not passed,
            "reason": rule.reason_template,
        }
        results.append(result)
        try:
            with db.begin_nested():
                db.add(
                    IntelligenceRuleEvaluation(
                        owner_id=user.id,
                        rule_id=rule.id,
                        rule_version=rule.version,
                        subject_type="opportunity",
                        subject_id=opportunity.id,
                        input_evidence_ids=[],
                        result=result["result"],
                        score_impact=result["score_impact"],
                        hard_block=result["hard_block"],
                        reason=rule.reason_template,
                        evaluated_at=now(),
                    )
                )
                db.flush()
        except IntegrityError:
            existing = db.scalar(
                select(IntelligenceRuleEvaluation).where(
                    IntelligenceRuleEvaluation.owner_id == user.id,
                    IntelligenceRuleEvaluation.rule_id == rule.id,
                    IntelligenceRuleEvaluation.rule_version == rule.version,
                    IntelligenceRuleEvaluation.subject_type == "opportunity",
                    IntelligenceRuleEvaluation.subject_id == opportunity.id,
                )
            )
            if existing is None:
                raise
            score += float(existing.score_impact)
            blocked = blocked or existing.hard_block
    opportunity.score = max(0, min(100, float(opportunity.score) + score))
    opportunity.hard_blocked = blocked
    opportunity.updated_at = now()
    return results


def create_opportunity(db: Session, user: User, data: OpportunityCreate) -> IntelligenceOpportunity:
    stamp = now()
    if data.research_run_id:
        run = db.scalar(
            select(IntelligenceResearchRun).where(
                IntelligenceResearchRun.id == data.research_run_id,
                IntelligenceResearchRun.owner_id == user.id,
            )
        )
        if not run:
            raise HTTPException(404, "Research run not found.")
    opportunity = IntelligenceOpportunity(
        owner_id=user.id, created_at=stamp, updated_at=stamp, **data.model_dump()
    )
    db.add(opportunity)
    db.flush()
    return opportunity


def review_opportunity(
    db: Session, user: User, opportunity_id: uuid.UUID, data: OpportunityReviewRequest
) -> IntelligenceOpportunity:
    opportunity = db.scalar(
        select(IntelligenceOpportunity).where(
            IntelligenceOpportunity.id == opportunity_id,
            IntelligenceOpportunity.owner_id == user.id,
        )
    )
    if not opportunity:
        raise HTTPException(404, "Opportunity not found.")
    if data.action == "approve" and opportunity.hard_blocked:
        raise HTTPException(
            409, "Hard-blocked opportunities require rule resolution before approval."
        )
    mapping = {"shortlist": "shortlisted", "reject": "rejected", "approve": "approved"}
    opportunity.status = mapping[data.action]
    opportunity.updated_at = now()
    review = IntelligenceOpportunityReview(
        owner_id=user.id,
        opportunity_id=opportunity.id,
        action=data.action,
        reason=data.reason,
        correlation_id=_correlation(),
        created_at=now(),
    )
    db.add(review)
    audit_action = {
        "shortlist": "opportunity_shortlisted",
        "reject": "opportunity_rejected",
        "approve": "opportunity_approved",
    }[data.action]
    _event(
        db, user, audit_action, "intelligence_opportunity", opportunity.id, {"reason": data.reason}
    )
    return opportunity
