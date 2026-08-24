# ruff: noqa: E501
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.closure import (
    RECOVERY_MATRIX,
    estimate_economics,
    evaluate_physical_rules,
    evaluate_policy_hierarchy,
    rank_opportunities,
    validate_score_weights,
)
from vayujit_api.intelligence.models import (
    IntelligenceClaim,
    IntelligenceClaimEvidence,
    IntelligenceEvidence,
    IntelligenceOpportunity,
    IntelligenceRecoveryRecord,
    IntelligenceResearchCandidate,
    IntelligenceResearchMission,
    IntelligenceResearchProfile,
    IntelligenceResearchProject,
    IntelligenceResearchReport,
    IntelligenceResearchRun,
    IntelligenceResearchSignal,
    IntelligenceRule,
    IntelligenceRuleCategory,
    IntelligenceScoreEvaluation,
    IntelligenceSource,
    IntelligenceTrendObservation,
)
from vayujit_api.intelligence.recovery import FAILURE_CLASSIFICATIONS, RECOVERY_ACTIONS
from vayujit_api.intelligence.research_engine import (
    execute_research_run,
    generate_report,
    run_mission,
)
from vayujit_api.intelligence.scheduler import materialize_due_missions
from vayujit_api.intelligence.schemas import (
    CandidateResponse,
    ClaimCreate,
    ClaimResponse,
    CompareRequest,
    EconomicsEstimateRequest,
    EvidenceCreate,
    EvidenceResponse,
    HistoryResponse,
    IntelligenceOverviewResponse,
    MissionCreate,
    MissionResponse,
    MissionUpdate,
    OpportunityCreate,
    OpportunityResponse,
    OpportunityReviewRequest,
    PhysicalRuleEvaluationRequest,
    PolicySimulationRequest,
    RecoveryRequest,
    ReportResponse,
    ResearchProfileCreate,
    ResearchProfileResponse,
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
    RuleSimulationRequest,
    RuleSimulationResponse,
    RuleUpdate,
    ScheduleRequest,
    ScoreWeightRequest,
    SignalResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
    TrendObservationResponse,
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
    now,
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
    project = create_project(db, owner, data)
    db.commit()
    db.refresh(project)
    return project


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


@router.get("/opportunities/ranked", response_model=list[OpportunityResponse])
def ranked_opportunities(db: DB, owner: Owner) -> list[IntelligenceOpportunity]:
    values = list(
        db.scalars(
            select(IntelligenceOpportunity).where(IntelligenceOpportunity.owner_id == owner.id)
        )
    )
    ranked = rank_opportunities(
        [
            {
                "id": str(item.id),
                "score": float(item.score),
                "confidence": float(item.confidence),
                "risk": 100 if item.hard_blocked else 0,
                "hard_blocked": item.hard_blocked,
            }
            for item in values
        ]
    )
    by_id = {str(item.id): item for item in values}
    return [by_id[item["id"]] for item in ranked]


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
    db.commit()
    return RuleEvaluationResponse(
        opportunity_id=value.id,
        score=float(value.score),
        hard_blocked=value.hard_blocked,
        evaluations=evaluations,
    )


@router.get("/candidates", response_model=list[CandidateResponse])
def list_candidates(
    db: DB,
    owner: Owner,
    status: str | None = None,
    market: str | None = None,
    category: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    freshness: str | None = None,
) -> list[IntelligenceResearchCandidate]:
    query = select(IntelligenceResearchCandidate).where(
        IntelligenceResearchCandidate.owner_id == owner.id
    )
    if status:
        query = query.where(IntelligenceResearchCandidate.status == status)
    if market:
        query = query.where(IntelligenceResearchCandidate.market == market)
    if category:
        query = query.where(IntelligenceResearchCandidate.category == category)
    if min_score is not None:
        query = query.where(
            exists().where(
                IntelligenceScoreEvaluation.owner_id == owner.id,
                IntelligenceScoreEvaluation.candidate_id == IntelligenceResearchCandidate.id,
                IntelligenceScoreEvaluation.score >= min_score,
            )
        )
    if freshness:
        query = query.where(
            exists().where(
                IntelligenceEvidence.owner_id == owner.id,
                IntelligenceEvidence.research_run_id
                == IntelligenceResearchCandidate.research_run_id,
                IntelligenceEvidence.freshness_status == freshness,
            )
        )
    return list(db.scalars(query.order_by(IntelligenceResearchCandidate.updated_at.desc())))


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def candidate_detail(
    candidate_id: uuid.UUID, db: DB, owner: Owner
) -> IntelligenceResearchCandidate:
    value = db.scalar(
        select(IntelligenceResearchCandidate).where(
            IntelligenceResearchCandidate.id == candidate_id,
            IntelligenceResearchCandidate.owner_id == owner.id,
        )
    )
    if not value:
        raise HTTPException(404, "Research candidate not found.")
    return value


@router.get("/candidates/{candidate_id}/signals", response_model=list[SignalResponse])
def candidate_signals(
    candidate_id: uuid.UUID, db: DB, owner: Owner
) -> list[IntelligenceResearchSignal]:
    return list(
        db.scalars(
            select(IntelligenceResearchSignal)
            .where(
                IntelligenceResearchSignal.candidate_id == candidate_id,
                IntelligenceResearchSignal.owner_id == owner.id,
            )
            .order_by(IntelligenceResearchSignal.signal_type)
        )
    )


@router.get("/profiles", response_model=list[ResearchProfileResponse])
def list_profiles(db: DB, owner: Owner) -> list[IntelligenceResearchProfile]:
    return list(
        db.scalars(
            select(IntelligenceResearchProfile)
            .where(IntelligenceResearchProfile.owner_id == owner.id)
            .order_by(IntelligenceResearchProfile.name)
        )
    )


@router.post("/profiles", response_model=ResearchProfileResponse, status_code=201)
def add_profile(data: ResearchProfileCreate, db: DB, owner: Owner) -> IntelligenceResearchProfile:
    stamp = now()
    profile = IntelligenceResearchProfile(
        owner_id=owner.id, created_at=stamp, updated_at=stamp, **data.model_dump()
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/missions", response_model=list[MissionResponse])
def list_missions(db: DB, owner: Owner) -> list[IntelligenceResearchMission]:
    return list(
        db.scalars(
            select(IntelligenceResearchMission)
            .where(IntelligenceResearchMission.owner_id == owner.id)
            .order_by(IntelligenceResearchMission.updated_at.desc())
        )
    )


@router.post("/missions", response_model=MissionResponse, status_code=201)
def add_mission(data: MissionCreate, db: DB, owner: Owner) -> IntelligenceResearchMission:
    project = db.scalar(
        select(IntelligenceResearchProject).where(
            IntelligenceResearchProject.id == data.project_id,
            IntelligenceResearchProject.owner_id == owner.id,
        )
    )
    if not project:
        raise HTTPException(404, "Research project not found.")
    if data.profile_id and not db.scalar(
        select(IntelligenceResearchProfile).where(
            IntelligenceResearchProfile.id == data.profile_id,
            IntelligenceResearchProfile.owner_id == owner.id,
        )
    ):
        raise HTTPException(404, "Research profile not found.")
    stamp = now()
    mission = IntelligenceResearchMission(
        owner_id=owner.id, created_at=stamp, updated_at=stamp, **data.model_dump()
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


@router.patch("/missions/{mission_id}", response_model=MissionResponse)
def edit_mission(
    mission_id: uuid.UUID, data: MissionUpdate, db: DB, owner: Owner
) -> IntelligenceResearchMission:
    mission = db.scalar(
        select(IntelligenceResearchMission).where(
            IntelligenceResearchMission.id == mission_id,
            IntelligenceResearchMission.owner_id == owner.id,
        )
    )
    if not mission:
        raise HTTPException(404, "Research mission not found.")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(mission, key, value)
    mission.updated_at = now()
    db.commit()
    db.refresh(mission)
    return mission


@router.post("/missions/{mission_id}/pause", response_model=MissionResponse)
def pause_mission(mission_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceResearchMission:
    mission = db.scalar(
        select(IntelligenceResearchMission).where(
            IntelligenceResearchMission.id == mission_id,
            IntelligenceResearchMission.owner_id == owner.id,
        )
    )
    if not mission:
        raise HTTPException(404, "Research mission not found.")
    mission.enabled = False
    mission.status = "paused"
    mission.updated_at = now()
    db.commit()
    db.refresh(mission)
    return mission


@router.post("/missions/{mission_id}/resume", response_model=MissionResponse)
def resume_mission(mission_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceResearchMission:
    mission = db.scalar(
        select(IntelligenceResearchMission).where(
            IntelligenceResearchMission.id == mission_id,
            IntelligenceResearchMission.owner_id == owner.id,
        )
    )
    if not mission:
        raise HTTPException(404, "Research mission not found.")
    mission.enabled = True
    mission.status = "active"
    mission.updated_at = now()
    db.commit()
    db.refresh(mission)
    return mission


@router.post("/missions/{mission_id}/run-now", response_model=ResearchRunResponse)
def run_mission_now(
    mission_id: uuid.UUID, db: DB, owner: Owner, idempotency_key: str | None = None
) -> IntelligenceResearchRun:
    mission = db.scalar(
        select(IntelligenceResearchMission).where(
            IntelligenceResearchMission.id == mission_id,
            IntelligenceResearchMission.owner_id == owner.id,
        )
    )
    if not mission:
        raise HTTPException(404, "Research mission not found.")
    return run_mission(db, owner, mission, idempotency_key=idempotency_key)


@router.post("/runs/{run_id}/execute", response_model=ResearchRunResponse)
def execute_run(run_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceResearchRun:
    run = db.scalar(
        select(IntelligenceResearchRun).where(
            IntelligenceResearchRun.id == run_id,
            IntelligenceResearchRun.owner_id == owner.id,
        )
    )
    if not run:
        raise HTTPException(404, "Research run not found.")
    execute_research_run(db, owner, run)
    return run


@router.get("/runs/{run_id}/candidates", response_model=list[CandidateResponse])
def run_candidates(run_id: uuid.UUID, db: DB, owner: Owner) -> list[IntelligenceResearchCandidate]:
    return list(
        db.scalars(
            select(IntelligenceResearchCandidate)
            .where(
                IntelligenceResearchCandidate.research_run_id == run_id,
                IntelligenceResearchCandidate.owner_id == owner.id,
            )
            .order_by(IntelligenceResearchCandidate.updated_at.desc())
        )
    )


@router.post("/runs/{run_id}/reports", response_model=ReportResponse)
def create_report(
    run_id: uuid.UUID, db: DB, owner: Owner, format: str = Query(default="json")
) -> IntelligenceResearchReport:
    return generate_report(db, owner, run_id, format)


@router.get("/reports/{report_id}", response_model=ReportResponse)
def report_detail(report_id: uuid.UUID, db: DB, owner: Owner) -> IntelligenceResearchReport:
    report = db.scalar(
        select(IntelligenceResearchReport).where(
            IntelligenceResearchReport.id == report_id,
            IntelligenceResearchReport.owner_id == owner.id,
        )
    )
    if not report:
        raise HTTPException(404, "Research report not found.")
    return report


@router.post("/rules/simulate", response_model=RuleSimulationResponse)
def simulate_rules(data: RuleSimulationRequest, db: DB, owner: Owner) -> RuleSimulationResponse:
    values = list(
        db.scalars(
            select(IntelligenceResearchCandidate).where(
                IntelligenceResearchCandidate.id.in_(data.candidate_ids),
                IntelligenceResearchCandidate.owner_id == owner.id,
            )
        )
    )
    if len(values) != len(set(data.candidate_ids)):
        raise HTTPException(404, "One or more candidates were not found.")
    counts = {"allowed": 0, "warned": 0, "review_required": 0, "blocked": 0}
    details: list[dict[str, object]] = []
    for value in values:
        evaluation = db.scalar(
            select(IntelligenceScoreEvaluation).where(
                IntelligenceScoreEvaluation.owner_id == owner.id,
                IntelligenceScoreEvaluation.candidate_id == value.id,
                IntelligenceScoreEvaluation.scoring_model_version == data.scoring_model_version,
            )
        )
        recommendation = evaluation.recommendation if evaluation else "RESEARCH_MORE"
        key = (
            "blocked"
            if recommendation == "BLOCKED"
            else (
                "review_required"
                if recommendation in {"REVIEW_REQUIRED", "RESEARCH_MORE"}
                else "allowed"
            )
        )
        counts[key] += 1
        details.append(
            {
                "candidate_id": str(value.id),
                "recommendation": recommendation,
                "score": float(evaluation.score) if evaluation else None,
            }
        )
    return RuleSimulationResponse(**counts, candidates=details)


@router.post("/compare")
def compare_candidates(data: CompareRequest, db: DB, owner: Owner) -> dict[str, object]:
    values = list(
        db.scalars(
            select(IntelligenceResearchCandidate).where(
                IntelligenceResearchCandidate.id.in_(data.candidate_ids),
                IntelligenceResearchCandidate.owner_id == owner.id,
            )
        )
    )
    if len(values) != len(set(data.candidate_ids)):
        raise HTTPException(404, "One or more candidates were not found.")
    candidate_ids = [value.id for value in values]
    evaluations = list(
        db.scalars(
            select(IntelligenceScoreEvaluation)
            .where(
                IntelligenceScoreEvaluation.owner_id == owner.id,
                IntelligenceScoreEvaluation.candidate_id.in_(candidate_ids),
            )
            .order_by(IntelligenceScoreEvaluation.created_at.desc())
        )
    )
    latest_by_candidate: dict[uuid.UUID, IntelligenceScoreEvaluation] = {}
    for evaluation in evaluations:
        latest_by_candidate.setdefault(evaluation.candidate_id, evaluation)
    signals = list(
        db.scalars(
            select(IntelligenceResearchSignal)
            .where(
                IntelligenceResearchSignal.owner_id == owner.id,
                IntelligenceResearchSignal.candidate_id.in_(candidate_ids),
            )
            .order_by(IntelligenceResearchSignal.signal_type)
        )
    )
    signals_by_candidate: dict[uuid.UUID, list[IntelligenceResearchSignal]] = {}
    for signal in signals:
        signals_by_candidate.setdefault(signal.candidate_id, []).append(signal)
    output = []
    for value in values:
        latest_evaluation = latest_by_candidate.get(value.id)
        output.append(
            {
                "candidate": {
                    "id": str(value.id),
                    "title": value.title,
                    "category": value.category,
                },
                "score": float(latest_evaluation.score) if latest_evaluation else None,
                "recommendation": (
                    latest_evaluation.recommendation if latest_evaluation else "RESEARCH_MORE"
                ),
                "dimensions": latest_evaluation.dimension_scores if latest_evaluation else {},
                "signals": [
                    {
                        "type": signal.signal_type,
                        "score": (
                            float(signal.normalized_score)
                            if signal.normalized_score is not None
                            else None
                        ),
                    }
                    for signal in signals_by_candidate.get(value.id, [])
                ],
            }
        )
    return {"items": output, "count": len(output)}


@router.post("/physical-rules/evaluate")
def evaluate_physical(data: PhysicalRuleEvaluationRequest) -> dict[str, object]:
    return evaluate_physical_rules(data.actual, data.thresholds)


@router.post("/policies/simulate")
def simulate_policy(data: PolicySimulationRequest) -> dict[str, object]:
    return evaluate_policy_hierarchy(data.rules, authorized_override=data.authorized_override)


@router.post("/economics/estimate")
def economics_estimate(data: EconomicsEstimateRequest) -> dict[str, object]:
    try:
        return estimate_economics(data.inputs, currency=data.currency)
    except ValueError as exc:
        raise HTTPException(422, "Economic assumptions are invalid.") from exc


@router.post("/scoring/validate")
def validate_scoring(data: ScoreWeightRequest) -> dict[str, object]:
    try:
        value = validate_score_weights(data.weights, data.known_dimensions)
    except ValueError as exc:
        raise HTTPException(422, "Scoring weights are invalid.") from exc
    return {"valid": True, "weights": value, "sum": sum(value.values())}


@router.get("/restrictions/matrix")
def restriction_matrix() -> dict[str, object]:
    return {
        "attributes": [
            "glass",
            "fragile",
            "battery",
            "lithium_battery",
            "liquid",
            "powder",
            "electronics",
            "electrical",
            "wireless",
            "childrens_product",
            "food_contact",
            "cosmetics",
            "medical",
            "sharp_item",
            "magnetic",
            "hazardous",
            "oversized",
            "restricted_category",
            "brand_restricted",
        ],
        "actions": ["ALLOW", "WARN", "REVIEW_REQUIRED", "BLOCK"],
        "configurable": True,
    }


@router.get("/recovery/matrix")
def recovery_matrix() -> dict[str, object]:
    return {"classifications": sorted(RECOVERY_MATRIX), "actions": RECOVERY_MATRIX}


@router.get("/candidates/{candidate_id}/trends", response_model=list[TrendObservationResponse])
def candidate_trends(
    candidate_id: uuid.UUID, db: DB, owner: Owner
) -> list[IntelligenceTrendObservation]:
    candidate = db.scalar(
        select(IntelligenceResearchCandidate).where(
            IntelligenceResearchCandidate.id == candidate_id,
            IntelligenceResearchCandidate.owner_id == owner.id,
        )
    )
    if not candidate:
        raise HTTPException(404, "Research candidate not found.")
    return list(
        db.scalars(
            select(IntelligenceTrendObservation)
            .where(
                IntelligenceTrendObservation.owner_id == owner.id,
                IntelligenceTrendObservation.candidate_id == candidate_id,
            )
            .order_by(IntelligenceTrendObservation.observed_at)
        )
    )


@router.get("/runs/{run_id}/history", response_model=HistoryResponse)
def run_history(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    run = db.scalar(
        select(IntelligenceResearchRun).where(
            IntelligenceResearchRun.id == run_id, IntelligenceResearchRun.owner_id == owner.id
        )
    )
    if not run:
        raise HTTPException(404, "Research run not found.")
    mission = db.scalar(
        select(IntelligenceResearchMission).where(
            IntelligenceResearchMission.last_run_id == run_id,
            IntelligenceResearchMission.owner_id == owner.id,
        )
    )
    recoveries = list(
        db.scalars(
            select(IntelligenceRecoveryRecord)
            .where(
                IntelligenceRecoveryRecord.run_id == run_id,
                IntelligenceRecoveryRecord.owner_id == owner.id,
            )
            .order_by(IntelligenceRecoveryRecord.created_at)
        )
    )
    candidate_count_value = run.summary_json.get("candidates", 0)
    opportunity_count_value = run.summary_json.get("promoted", 0)
    candidate_count = (
        int(candidate_count_value) if isinstance(candidate_count_value, (int, float, str)) else 0
    )
    opportunity_count = (
        int(opportunity_count_value)
        if isinstance(opportunity_count_value, (int, float, str))
        else 0
    )
    return {
        "mission": {
            "id": str(mission.id) if mission else None,
            "name": mission.name if mission else None,
            "status": mission.status if mission else None,
        },
        "run": {
            "id": str(run.id),
            "provider_mode": "local_deterministic",
            "status": run.status,
            "candidate_count": candidate_count,
            "opportunity_count": opportunity_count,
            "score_model": "winning-product-local-v1",
            "ruleset_version": run.ruleset_version,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "failure": run.failure_classification,
            "duration_seconds": (
                (run.completed_at - run.started_at).total_seconds()
                if run.completed_at and run.started_at
                else None
            ),
        },
        "recovery": [
            {
                "id": str(item.id),
                "classification": item.failure_classification,
                "action": item.action,
                "status": item.status,
            }
            for item in recoveries
        ],
    }


@router.post("/missions/{mission_id}/schedule", response_model=MissionResponse)
def schedule_mission(
    mission_id: uuid.UUID, data: ScheduleRequest, db: DB, owner: Owner
) -> IntelligenceResearchMission:
    mission = db.scalar(
        select(IntelligenceResearchMission).where(
            IntelligenceResearchMission.id == mission_id,
            IntelligenceResearchMission.owner_id == owner.id,
        )
    )
    if not mission:
        raise HTTPException(404, "Research mission not found.")
    mission.enabled = True
    mission.status = "active"
    mission.frequency = data.frequency
    mission.timezone = data.timezone
    mission.next_run_at = data.scheduled_for
    mission.updated_at = now()
    db.commit()
    db.refresh(mission)
    return mission


@router.post("/runs/{run_id}/recover")
def recover_run(
    run_id: uuid.UUID, data: RecoveryRequest, db: DB, owner: Owner
) -> dict[str, object]:
    run = db.scalar(
        select(IntelligenceResearchRun).where(
            IntelligenceResearchRun.id == run_id, IntelligenceResearchRun.owner_id == owner.id
        )
    )
    if not run:
        raise HTTPException(404, "Research run not found.")
    actions = RECOVERY_MATRIX.get(data.failure_classification)
    if actions is None or data.action not in actions:
        raise HTTPException(
            422, "Recovery action is not executable for this failure classification."
        )
    prior = db.scalar(
        select(IntelligenceRecoveryRecord).where(
            IntelligenceRecoveryRecord.owner_id == owner.id,
            IntelligenceRecoveryRecord.run_id == run_id,
            IntelligenceRecoveryRecord.idempotency_key == data.idempotency_key,
        )
    )
    if prior:
        return {
            "id": str(prior.id),
            "status": prior.status,
            "idempotent_reuse": True,
            "action": prior.action,
        }
    record = IntelligenceRecoveryRecord(
        owner_id=owner.id,
        run_id=run_id,
        failure_classification=data.failure_classification,
        action=data.action,
        status="completed",
        idempotency_key=data.idempotency_key,
        details={"external_calls": False},
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        prior = db.scalar(
            select(IntelligenceRecoveryRecord).where(
                IntelligenceRecoveryRecord.owner_id == owner.id,
                IntelligenceRecoveryRecord.run_id == run_id,
                IntelligenceRecoveryRecord.idempotency_key == data.idempotency_key,
            )
        )
        if prior is None:
            raise
        return {
            "id": str(prior.id),
            "status": prior.status,
            "idempotent_reuse": True,
            "action": prior.action,
        }
    db.commit()
    return {
        "id": str(record.id),
        "status": record.status,
        "idempotent_reuse": False,
        "action": record.action,
    }


@router.post("/scheduler/materialize-due")
def materialize_due(
    db: DB, owner: Owner, limit: int = Query(default=10, ge=1, le=50)
) -> dict[str, object]:
    runs = materialize_due_missions(db, owner, limit=limit)
    return {"materialized": len(runs), "run_ids": [str(run.id) for run in runs]}
