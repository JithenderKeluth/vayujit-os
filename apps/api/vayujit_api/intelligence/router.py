from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.models import (
    IntelligenceClaim,
    IntelligenceClaimEvidence,
    IntelligenceEvidence,
    IntelligenceOpportunity,
    IntelligenceResearchProject,
    IntelligenceResearchRun,
    IntelligenceRule,
    IntelligenceRuleCategory,
    IntelligenceSource,
)
from vayujit_api.intelligence.recovery import FAILURE_CLASSIFICATIONS, RECOVERY_ACTIONS
from vayujit_api.intelligence.schemas import (
    ClaimCreate,
    ClaimResponse,
    EvidenceCreate,
    EvidenceResponse,
    IntelligenceOverviewResponse,
    OpportunityCreate,
    OpportunityResponse,
    OpportunityReviewRequest,
    ResearchProjectCreate,
    ResearchProjectResponse,
    ResearchProjectUpdate,
    ResearchRunCreate,
    ResearchRunResponse,
    RuleCategoryResponse,
    RuleCategoryUpdate,
    RuleCreate,
    RuleEvaluationResponse,
    RuleResponse,
    RuleUpdate,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)
from vayujit_api.intelligence.service import (
    archive_project,
    create_claim,
    create_evidence,
    create_opportunity,
    create_project,
    create_rule,
    create_run,
    create_source,
    ensure_categories,
    evaluate_opportunity,
    review_opportunity,
    update_category,
    update_project,
    update_rule,
    update_source,
)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/recovery/catalog")
def recovery_catalog() -> dict[str, object]:
    return {
        "failure_classifications": list(FAILURE_CLASSIFICATIONS),
        "actions": RECOVERY_ACTIONS,
        "execution": "operator_only_foundation",
    }


@router.get("/overview", response_model=IntelligenceOverviewResponse)
def overview(db: DB, owner: Owner) -> IntelligenceOverviewResponse:
    opportunity_counts = {
        status: int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceOpportunity)
                .where(
                    IntelligenceOpportunity.owner_id == owner.id,
                    IntelligenceOpportunity.status == status,
                )
            )
            or 0
        )
        for status in (
            "discovered",
            "researching",
            "review",
            "shortlisted",
            "rejected",
            "approved",
            "converted",
        )
    }
    freshness = {
        status: int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceEvidence)
                .where(
                    IntelligenceEvidence.owner_id == owner.id,
                    IntelligenceEvidence.freshness_status == status,
                )
            )
            or 0
        )
        for status in ("fresh", "aging", "stale", "expired", "unknown")
    }
    enabled_sources = int(
        db.scalar(
            select(func.count())
            .select_from(IntelligenceSource)
            .where(IntelligenceSource.owner_id == owner.id, IntelligenceSource.enabled.is_(True))
        )
        or 0
    )
    source_health = {
        "healthy": int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceSource)
                .where(
                    IntelligenceSource.owner_id == owner.id,
                    IntelligenceSource.failure_status.is_(None),
                )
            )
            or 0
        ),
        "failed": int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceSource)
                .where(
                    IntelligenceSource.owner_id == owner.id,
                    IntelligenceSource.failure_status.is_not(None),
                )
            )
            or 0
        ),
    }
    return IntelligenceOverviewResponse(
        active_projects=int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceResearchProject)
                .where(
                    IntelligenceResearchProject.owner_id == owner.id,
                    IntelligenceResearchProject.status == "active",
                )
            )
            or 0
        ),
        recent_runs=int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceResearchRun)
                .where(IntelligenceResearchRun.owner_id == owner.id)
            )
            or 0
        ),
        opportunities=opportunity_counts,
        hard_blocked_candidates=opportunity_counts.get("discovered", 0)
        + opportunity_counts.get("review", 0),
        evidence_freshness=freshness,
        enabled_sources=enabled_sources,
        source_health=source_health,
        rule_counts={
            "categories": int(
                db.scalar(
                    select(func.count())
                    .select_from(IntelligenceRuleCategory)
                    .where(IntelligenceRuleCategory.owner_id == owner.id)
                )
                or 0
            ),
            "rules": int(
                db.scalar(
                    select(func.count())
                    .select_from(IntelligenceRule)
                    .where(IntelligenceRule.owner_id == owner.id)
                )
                or 0
            ),
        },
        recent_failures=int(
            db.scalar(
                select(func.count())
                .select_from(IntelligenceResearchRun)
                .where(
                    IntelligenceResearchRun.owner_id == owner.id,
                    IntelligenceResearchRun.status == "failed",
                )
            )
            or 0
        ),
    )


@router.get("/projects", response_model=list[ResearchProjectResponse])
def list_projects(
    db: DB, owner: Owner, include_archived: bool = False
) -> list[IntelligenceResearchProject]:
    query = select(IntelligenceResearchProject).where(
        IntelligenceResearchProject.owner_id == owner.id
    )
    if not include_archived:
        query = query.where(IntelligenceResearchProject.status != "archived")
    return list(db.scalars(query.order_by(IntelligenceResearchProject.updated_at.desc())))


@router.post("/projects", response_model=ResearchProjectResponse, status_code=201)
def add_project(data: ResearchProjectCreate, db: DB, owner: Owner) -> IntelligenceResearchProject:
    return create_project(db, owner, data)


@router.get("/projects/{project_id}", response_model=ResearchProjectResponse)
def project(project_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceResearchProject:
    value = db.scalar(
        select(IntelligenceResearchProject).where(
            IntelligenceResearchProject.id == project_id,
            IntelligenceResearchProject.owner_id == owner.id,
        )
    )
    if not value:
        raise HTTPException(404, "Research project not found.")
    return value


@router.patch("/projects/{project_id}", response_model=ResearchProjectResponse)
def edit_project(
    project_id: uuid.UUID, data: ResearchProjectUpdate, db: DB, owner: Owner
) -> IntelligenceResearchProject:
    return update_project(db, owner, project_id, data)


@router.post("/projects/{project_id}/archive", response_model=ResearchProjectResponse)
def archive(project_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceResearchProject:
    return archive_project(db, owner, project_id)


@router.post("/projects/{project_id}/runs", response_model=ResearchRunResponse, status_code=201)
def run_project(
    project_id: uuid.UUID, data: ResearchRunCreate, db: DB, owner: Owner
) -> IntelligenceResearchRun:
    return create_run(db, owner, project_id, data)


@router.get("/projects/{project_id}/runs", response_model=list[ResearchRunResponse])
def list_runs(project_id: uuid.UUID, db: DB, owner: Owner) -> list[IntelligenceResearchRun]:
    return list(
        db.scalars(
            select(IntelligenceResearchRun)
            .where(
                IntelligenceResearchRun.project_id == project_id,
                IntelligenceResearchRun.owner_id == owner.id,
            )
            .order_by(IntelligenceResearchRun.created_at.desc())
        )
    )


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(db: DB, owner: Owner) -> list[IntelligenceSource]:
    return list(
        db.scalars(
            select(IntelligenceSource)
            .where(IntelligenceSource.owner_id == owner.id)
            .order_by(IntelligenceSource.display_name)
        )
    )


@router.post("/sources", response_model=SourceResponse, status_code=201)
def add_source(data: SourceCreate, db: DB, owner: Owner) -> IntelligenceSource:
    return create_source(db, owner, data)


@router.patch("/sources/{source_id}", response_model=SourceResponse)
def edit_source(
    source_id: uuid.UUID, data: SourceUpdate, db: DB, owner: Owner
) -> IntelligenceSource:
    return update_source(db, owner, source_id, data)


@router.post("/sources/{source_id}/enable", response_model=SourceResponse)
def enable_source(source_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceSource:
    return update_source(db, owner, source_id, SourceUpdate(enabled=True))


@router.post("/sources/{source_id}/disable", response_model=SourceResponse)
def disable_source(source_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceSource:
    return update_source(db, owner, source_id, SourceUpdate(enabled=False))


@router.post("/evidence", response_model=EvidenceResponse, status_code=201)
def add_evidence(data: EvidenceCreate, db: DB, owner: Owner) -> IntelligenceEvidence:
    return create_evidence(db, owner, data)


@router.get("/evidence", response_model=list[EvidenceResponse])
def list_evidence(
    db: DB,
    owner: Owner,
    source_id: uuid.UUID | None = None,
    research_run_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[IntelligenceEvidence]:
    query = select(IntelligenceEvidence).where(IntelligenceEvidence.owner_id == owner.id)
    if source_id:
        query = query.where(IntelligenceEvidence.source_id == source_id)
    if research_run_id:
        query = query.where(IntelligenceEvidence.research_run_id == research_run_id)
    return list(db.scalars(query.order_by(IntelligenceEvidence.observed_at.desc()).limit(limit)))


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def evidence(evidence_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceEvidence:
    value = db.scalar(
        select(IntelligenceEvidence).where(
            IntelligenceEvidence.id == evidence_id, IntelligenceEvidence.owner_id == owner.id
        )
    )
    if not value:
        raise HTTPException(404, "Evidence item not found.")
    return value


@router.post("/claims", response_model=ClaimResponse, status_code=201)
def add_claim(data: ClaimCreate, db: DB, owner: Owner) -> dict[str, object]:
    claim = create_claim(db, owner, data)
    return {**claim.__dict__, "evidence_ids": list(data.evidence_ids)}


@router.get("/claims", response_model=list[ClaimResponse])
def list_claims(
    db: DB, owner: Owner, research_run_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    query = select(IntelligenceClaim).where(IntelligenceClaim.owner_id == owner.id)
    if research_run_id:
        query = query.where(IntelligenceClaim.research_run_id == research_run_id)
    output: list[dict[str, object]] = []
    for claim in db.scalars(query.order_by(IntelligenceClaim.created_at.desc())):
        ids = list(
            db.scalars(
                select(IntelligenceClaimEvidence.evidence_id).where(
                    IntelligenceClaimEvidence.claim_id == claim.id
                )
            )
        )
        output.append({**claim.__dict__, "evidence_ids": ids})
    return output


@router.get("/rules/categories", response_model=list[RuleCategoryResponse])
def categories(db: DB, owner: Owner) -> list[IntelligenceRuleCategory]:
    return ensure_categories(db, owner)


@router.patch("/rules/categories/{category_id}", response_model=RuleCategoryResponse)
def edit_category(
    category_id: uuid.UUID, data: RuleCategoryUpdate, db: DB, owner: Owner
) -> IntelligenceRuleCategory:
    return update_category(db, owner, category_id, data.enabled)


@router.get("/rules", response_model=list[RuleResponse])
def list_rules(
    db: DB, owner: Owner, category_id: uuid.UUID | None = None
) -> list[IntelligenceRule]:
    query = select(IntelligenceRule).where(IntelligenceRule.owner_id == owner.id)
    if category_id:
        query = query.where(IntelligenceRule.category_id == category_id)
    return list(
        db.scalars(
            query.order_by(
                IntelligenceRule.priority,
                IntelligenceRule.logical_key,
                IntelligenceRule.version.desc(),
            )
        )
    )


@router.post("/rules", response_model=RuleResponse, status_code=201)
def add_rule(data: RuleCreate, db: DB, owner: Owner) -> IntelligenceRule:
    return create_rule(db, owner, data)


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
def edit_rule(rule_id: uuid.UUID, data: RuleUpdate, db: DB, owner: Owner) -> IntelligenceRule:
    return update_rule(db, owner, rule_id, data)


@router.post("/opportunities", response_model=OpportunityResponse, status_code=201)
def add_opportunity(data: OpportunityCreate, db: DB, owner: Owner) -> IntelligenceOpportunity:
    return create_opportunity(db, owner, data)


@router.get("/opportunities", response_model=list[OpportunityResponse])
def list_opportunities(
    db: DB, owner: Owner, status: str | None = None
) -> list[IntelligenceOpportunity]:
    query = select(IntelligenceOpportunity).where(IntelligenceOpportunity.owner_id == owner.id)
    if status:
        query = query.where(IntelligenceOpportunity.status == status)
    return list(db.scalars(query.order_by(IntelligenceOpportunity.updated_at.desc())))


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def opportunity(opportunity_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceOpportunity:
    value = db.scalar(
        select(IntelligenceOpportunity).where(
            IntelligenceOpportunity.id == opportunity_id,
            IntelligenceOpportunity.owner_id == owner.id,
        )
    )
    if not value:
        raise HTTPException(404, "Opportunity not found.")
    return value


@router.post("/opportunities/{opportunity_id}/review", response_model=OpportunityResponse)
def review(
    opportunity_id: uuid.UUID, data: OpportunityReviewRequest, db: DB, owner: Owner
) -> IntelligenceOpportunity:
    return review_opportunity(db, owner, opportunity_id, data)


@router.post("/opportunities/{opportunity_id}/evaluate", response_model=RuleEvaluationResponse)
def evaluate(opportunity_id: uuid.UUID, db: DB, owner: Owner) -> RuleEvaluationResponse:
    value = db.scalar(
        select(IntelligenceOpportunity).where(
            IntelligenceOpportunity.id == opportunity_id,
            IntelligenceOpportunity.owner_id == owner.id,
        )
    )
    if not value:
        raise HTTPException(404, "Opportunity not found.")
    evaluations = evaluate_opportunity(db, owner, value)
    return RuleEvaluationResponse(
        opportunity_id=value.id,
        score=float(value.score),
        hard_blocked=value.hard_blocked,
        evaluations=evaluations,
    )
