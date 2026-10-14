"""Read-only supplier evidence readiness and certification endpoints (PR-9A)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.live_supplier_certification_schemas import (
    LiveSupplierApprovalAction,
    LiveSupplierApprovalCreate,
    LiveSupplierCertificationCreate,
    LiveSupplierEvidenceReviewCreate,
    LiveSupplierExecutionAction,
    LiveSupplierExecutionAuthorizationAction,
    LiveSupplierExecutionAuthorizationCreate,
    LiveSupplierExecutionEligibilityRequest,
)
from vayujit_api.intelligence.live_supplier_certification_service import (
    approval_response,
    certify,
    create_approval,
    list_approvals,
    list_runs,
    review_execution,
    revoke_approval,
    run_response,
)
from vayujit_api.intelligence.live_supplier_source_authorization_service import (
    authorization_history,
    authorization_response,
    create_authorization,
    eligibility,
    execute_authorization,
    get_authorization,
    list_authorizations,
    list_reviews,
    review_evidence,
    review_response,
    revoke_authorization,
)

router = APIRouter(
    prefix="/api/v1/intelligence/live-supplier-certification",
    tags=["live-supplier-certification"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/policy")
def policy() -> dict[str, object]:
    from vayujit_api.core.config import get_settings

    settings = get_settings()
    blockers = []
    if settings.intelligence_external_provider_mode != "LIVE_READ_ONLY":
        blockers.append("MODE_NOT_LIVE_READ_ONLY")
    if not settings.intelligence_enabled or not settings.intelligence_external_research_enabled:
        blockers.append("EXTERNAL_RESEARCH_DISABLED")
    if not settings.intelligence_web_fetch_enabled:
        blockers.append("APPROVED_FETCH_DISABLED")
    if settings.intelligence_external_kill_switch or settings.external_mutations_emergency_stop:
        blockers.append("EXTERNAL_KILL_SWITCH")
    return {
        "policy_version": "pr9a-live-supplier-v1",
        "mode": settings.intelligence_external_provider_mode,
        "provider": "approved_web_fetch",
        "read_only": True,
        "external_writes": False,
        "ready": not blockers,
        "blockers": blockers,
        "max_bytes": settings.intelligence_fetch_max_bytes,
        "max_redirects": settings.intelligence_fetch_max_redirects,
        "timeout_seconds": settings.intelligence_fetch_timeout_seconds,
    }


@router.get("/approvals")
def approvals(db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_approvals(db, owner)


@router.post("/approvals", status_code=201)
def approve(data: LiveSupplierApprovalCreate, db: DB, owner: Owner) -> dict[str, object]:
    row = create_approval(db, owner, data)
    db.commit()
    db.refresh(row)
    return approval_response(row)


@router.post("/approvals/{approval_id}/revoke")
def revoke(
    approval_id: uuid.UUID, data: LiveSupplierApprovalAction, db: DB, owner: Owner
) -> dict[str, object]:
    row = revoke_approval(
        db, owner, approval_id, data.reason or "Revoked by HUMAN actor", data.actor_provenance
    )
    db.commit()
    db.refresh(row)
    return approval_response(row)


@router.post("/runs", status_code=201)
def run_certification(
    data: LiveSupplierCertificationCreate, db: DB, owner: Owner
) -> dict[str, object]:
    row = certify(db, owner, data)
    db.commit()
    db.refresh(row)
    return run_response(db, row)


@router.get("/runs")
def runs(db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_runs(db, owner)


@router.post("/executions/{execution_id}/review")
def review(
    execution_id: uuid.UUID, data: LiveSupplierApprovalAction, db: DB, owner: Owner
) -> dict[str, object]:
    if data.action is not None:
        if not data.rationale:
            raise HTTPException(422, "Evidence review rationale is required.")
        row = review_evidence(db, owner, execution_id, data)
        db.commit()
        db.refresh(row)
        return review_response(row)
    legacy_execution = review_execution(db, owner, execution_id, data.actor_provenance)
    db.commit()
    db.refresh(legacy_execution)
    return {
        "id": str(legacy_execution.id),
        "run_id": str(legacy_execution.run_id),
        "trust_classification": legacy_execution.trust_classification,
        "status": legacy_execution.status,
    }


@router.post("/authorizations/eligibility")
def authorization_eligibility(
    data: LiveSupplierExecutionEligibilityRequest, db: DB, owner: Owner
) -> dict[str, object]:
    """Inspect the exact immutable scope without creating an authorization or fetching."""
    return eligibility(db, owner, data)


@router.post("/authorizations", status_code=201)
def authorize_execution(
    data: LiveSupplierExecutionAuthorizationCreate, db: DB, owner: Owner
) -> dict[str, object]:
    row = create_authorization(db, owner, data)
    db.commit()
    db.refresh(row)
    return authorization_response(row)


@router.get("/authorizations")
def authorizations(db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_authorizations(db, owner)


@router.get("/authorizations/{authorization_id}")
def authorization(authorization_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return authorization_response(get_authorization(db, owner, authorization_id))


@router.get("/authorizations/{authorization_id}/history")
def authorization_history_view(
    authorization_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return authorization_history(db, owner, authorization_id)


@router.post("/authorizations/{authorization_id}/revoke")
def revoke_execution_authorization(
    authorization_id: uuid.UUID,
    data: LiveSupplierExecutionAuthorizationAction,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    row = revoke_authorization(
        db,
        owner,
        authorization_id,
        data.reason or "Revoked by HUMAN actor",
        data.actor_provenance,
    )
    db.commit()
    db.refresh(row)
    return authorization_response(row)


@router.post("/authorizations/{authorization_id}/execute")
def execute_authorized_read(
    authorization_id: uuid.UUID,
    data: LiveSupplierExecutionAction,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    row = execute_authorization(
        db, owner, authorization_id, data.actor_provenance, data.idempotency_key
    )
    db.commit()
    db.refresh(row)
    return run_response(db, row)


@router.post("/executions/{execution_id}/evidence-review")
def evidence_review(
    execution_id: uuid.UUID,
    data: LiveSupplierEvidenceReviewCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    row = review_evidence(db, owner, execution_id, data)
    db.commit()
    db.refresh(row)
    return review_response(row)


@router.get("/executions/{execution_id}/evidence-review")
def evidence_reviews(execution_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_reviews(db, owner, execution_id)
