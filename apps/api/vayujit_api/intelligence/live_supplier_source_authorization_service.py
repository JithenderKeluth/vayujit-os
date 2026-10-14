"""PR-9B execution authorization and HUMAN evidence-review authority.

This module is deliberately thin: PR-9A remains the source approval, fetch,
classification, supplier-correlation, and immutable evidence authority.  PR-9B
only adds the second HUMAN-controlled boundary required before a read is
executed and an append-only review ledger after it completes.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.live_supplier_certification_models import (
    LiveSupplierCertificationExecution,
    LiveSupplierCertificationRun,
    LiveSupplierEvidenceReview,
    LiveSupplierExecutionAuthorization,
    LiveSupplierSourceApproval,
)
from vayujit_api.intelligence.live_supplier_certification_schemas import (
    LiveSupplierCertificationCreate,
)
from vayujit_api.intelligence.live_supplier_certification_service import (
    POLICY_VERSION,
    _context,
    _scope_blockers,
    _settings_blockers,
    certify,
)
from vayujit_api.intelligence.policy import UnsafeURL, validate_source_url


def _now() -> datetime:
    return datetime.now(UTC)


def _fp(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _approval(db: Session, owner: User, approval_id: uuid.UUID) -> LiveSupplierSourceApproval:
    row = db.scalar(
        select(LiveSupplierSourceApproval).where(
            LiveSupplierSourceApproval.id == approval_id,
            LiveSupplierSourceApproval.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Source approval not found.")
    return row


def _scope(
    db: Session,
    owner: User,
    approval: LiveSupplierSourceApproval,
    source_url: str | None,
    goal_id: uuid.UUID | None,
    opportunity_id: uuid.UUID | None,
    provider: str,
) -> tuple[str, list[str]]:
    if provider != "approved_web_fetch":
        return source_url or approval.source_url, ["PROVIDER_NOT_APPROVED"]
    raw = validate_source_url(source_url or approval.source_url)
    if not raw or urlparse(raw).scheme != "https":
        return source_url or approval.source_url, ["HTTPS_REQUIRED"]
    if goal_id is not None and approval.goal_id != goal_id:
        return raw, ["GOAL_SCOPE_MISMATCH"]
    if opportunity_id is not None and approval.opportunity_id != opportunity_id:
        return raw, ["OPPORTUNITY_SCOPE_MISMATCH"]
    if approval.goal_id is not None and opportunity_id is not None:
        _context(db, owner, approval.goal_id, opportunity_id)
    blockers, _profile = _scope_blockers(db, approval, raw, _now())
    settings_blockers = _settings_blockers(get_settings())
    blockers.extend(settings_blockers)
    return raw, list(dict.fromkeys(blockers))


def eligibility(db: Session, owner: User, data: Any) -> dict[str, object]:
    """Inspect, but never execute, the exact scope a HUMAN could authorize."""
    approval = _approval(db, owner, data.approval_id)
    raw, blockers = _scope(
        db, owner, approval, data.source_url, data.goal_id, data.opportunity_id, data.provider
    )
    return {
        "eligible": not blockers,
        "blockers": blockers,
        "owner_id": str(owner.id),
        "approval_id": str(approval.id),
        "approval_version": approval.version,
        "goal_id": (
            str(data.goal_id or approval.goal_id) if (data.goal_id or approval.goal_id) else None
        ),
        "opportunity_id": (
            str(data.opportunity_id or approval.opportunity_id)
            if (data.opportunity_id or approval.opportunity_id)
            else None
        ),
        "source_url": raw,
        "normalized_host": approval.normalized_host,
        "path_scope": approval.path_scope,
        "provider": data.provider,
        "mode": "LIVE_READ_ONLY",
        "external_writes": False,
        "policy_version": POLICY_VERSION,
    }


def _auth_dict(row: LiveSupplierExecutionAuthorization) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "approval_id": str(row.approval_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id) if row.opportunity_id else None,
        "source_url": row.source_url,
        "normalized_host": row.normalized_host,
        "path_scope": row.path_scope,
        "provider": row.provider,
        "mode": row.mode,
        "actor_id": str(row.actor_id),
        "actor_provenance": row.actor_provenance,
        "approval_version": row.approval_version,
        "status": row.status,
        "max_requests": row.max_requests,
        "used_requests": row.used_requests,
        "idempotency_key": row.idempotency_key,
        "fingerprint": row.fingerprint,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "used_at": row.used_at.isoformat() if row.used_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "revocation_reason": row.revocation_reason,
        "execution_id": str(row.execution_id) if row.execution_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_authorization(db: Session, owner: User, data: Any) -> LiveSupplierExecutionAuthorization:
    if str(data.actor_provenance).upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may authorize live execution.")
    approval = _approval(db, owner, data.approval_id)
    raw, blockers = _scope(
        db, owner, approval, data.source_url, data.goal_id, data.opportunity_id, data.provider
    )
    if blockers:
        raise HTTPException(409, "Live execution is not eligible: " + ", ".join(blockers))
    goal_id = data.goal_id or approval.goal_id
    opportunity_id = data.opportunity_id or approval.opportunity_id
    expires_at = data.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= _now():
            raise HTTPException(422, "Execution authorization expiry must be in the future.")
        if approval.expires_at is not None and expires_at > approval.expires_at:
            raise HTTPException(422, "Execution authorization cannot outlive source approval.")
    key = data.idempotency_key or f"pr9b:{uuid.uuid4()}"
    fingerprint = _fp(
        owner.id,
        approval.id,
        approval.version,
        raw,
        provider := data.provider,
        goal_id,
        opportunity_id,
        expires_at.isoformat() if expires_at else "",
    )
    existing = db.scalar(
        select(LiveSupplierExecutionAuthorization).where(
            LiveSupplierExecutionAuthorization.owner_id == owner.id,
            LiveSupplierExecutionAuthorization.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing
    existing = db.scalar(
        select(LiveSupplierExecutionAuthorization).where(
            LiveSupplierExecutionAuthorization.owner_id == owner.id,
            LiveSupplierExecutionAuthorization.fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    stamp = _now()
    row = LiveSupplierExecutionAuthorization(
        owner_id=owner.id,
        approval_id=approval.id,
        goal_id=goal_id,
        opportunity_id=opportunity_id,
        source_url=raw,
        normalized_host=approval.normalized_host,
        path_scope=approval.path_scope,
        provider=provider,
        mode="LIVE_READ_ONLY",
        actor_id=owner.id,
        actor_provenance="HUMAN",
        approval_version=approval.version,
        status="ACTIVE",
        max_requests=1,
        used_requests=0,
        idempotency_key=key,
        fingerprint=fingerprint,
        expires_at=expires_at,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="live_supplier.execution_authorization.created",
        entity_type="live_supplier_execution_authorization",
        entity_id=row.id,
        metadata={"approval_id": str(approval.id), "approval_version": approval.version},
        idempotency_key=f"pr9b-auth:{owner.id}:{fingerprint}",
    )
    return row


def list_authorizations(db: Session, owner: User) -> list[dict[str, object]]:
    rows = db.scalars(
        select(LiveSupplierExecutionAuthorization)
        .where(LiveSupplierExecutionAuthorization.owner_id == owner.id)
        .order_by(
            LiveSupplierExecutionAuthorization.created_at.desc(),
            LiveSupplierExecutionAuthorization.id.desc(),
        )
    )
    return [_auth_dict(row) for row in rows]


def get_authorization(
    db: Session, owner: User, authorization_id: uuid.UUID
) -> LiveSupplierExecutionAuthorization:
    row = db.scalar(
        select(LiveSupplierExecutionAuthorization).where(
            LiveSupplierExecutionAuthorization.id == authorization_id,
            LiveSupplierExecutionAuthorization.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Execution authorization not found.")
    return row


def revoke_authorization(
    db: Session, owner: User, authorization_id: uuid.UUID, reason: str, actor_provenance: str
) -> LiveSupplierExecutionAuthorization:
    if actor_provenance.upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may revoke execution authorization.")
    row = get_authorization(db, owner, authorization_id)
    if row.status == "ACTIVE":
        row.status = "REVOKED"
        row.revoked_at = _now()
        row.revocation_reason = reason.strip()
        row.updated_at = _now()
        record_event(
            db,
            actor_id=owner.id,
            action="live_supplier.execution_authorization.revoked",
            entity_type="live_supplier_execution_authorization",
            entity_id=row.id,
            metadata={"reason": row.revocation_reason},
            idempotency_key=f"pr9b-auth-revoke:{row.id}",
        )
    return row


def execute_authorization(
    db: Session,
    owner: User,
    authorization_id: uuid.UUID,
    actor_provenance: str,
    idempotency_key: str | None,
) -> LiveSupplierCertificationRun:
    if actor_provenance.upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may execute a live read.")
    auth = db.scalar(
        select(LiveSupplierExecutionAuthorization)
        .where(
            LiveSupplierExecutionAuthorization.id == authorization_id,
            LiveSupplierExecutionAuthorization.owner_id == owner.id,
        )
        .with_for_update()
    )
    if auth is None:
        raise HTTPException(404, "Execution authorization not found.")
    now = _now()
    if auth.status != "ACTIVE" or auth.used_requests >= auth.max_requests:
        raise HTTPException(409, "Execution authorization is not available for use.")
    if auth.expires_at is not None and auth.expires_at <= now:
        auth.status = "EXPIRED"
        auth.updated_at = now
        db.commit()
        raise HTTPException(409, "Execution authorization has expired.")
    approval = db.scalar(
        select(LiveSupplierSourceApproval)
        .where(LiveSupplierSourceApproval.id == auth.approval_id)
        .with_for_update()
    )
    if approval is None or approval.owner_id != owner.id:
        raise HTTPException(404, "Source approval not found.")
    if approval.version != auth.approval_version or approval.status != "APPROVED":
        auth.status = "STALE"
        auth.updated_at = now
        db.commit()
        raise HTTPException(409, "Execution authorization is stale; refresh HUMAN approval.")
    _raw, blockers = _scope(
        db, owner, approval, auth.source_url, auth.goal_id, auth.opportunity_id, auth.provider
    )
    if blockers:
        raise HTTPException(
            409, "Execution authorization is no longer eligible: " + ", ".join(blockers)
        )
    auth.status = "USED"
    auth.used_requests = 1
    auth.used_at = now
    auth.updated_at = now
    db.flush()
    try:
        run = certify(
            db,
            owner,
            LiveSupplierCertificationCreate(
                approval_id=approval.id,
                source_url=auth.source_url,
                goal_id=auth.goal_id,
                opportunity_id=auth.opportunity_id,
                correlation_id=f"pr9b:{auth.id}",
                idempotency_key=idempotency_key or f"pr9b-run:{auth.id}",
                refresh=False,
            ),
        )
    except (RuntimeError, UnsafeURL, ValueError) as exc:
        # PR-9A normally converts transport failures into a durable BLOCKED
        # run.  This branch is for an unknown provider outcome: the auth is
        # consumed and callers must create a fresh HUMAN authorization.
        auth.status = "UNKNOWN"
        auth.revocation_reason = str(exc)[:500] or "UNKNOWN_PROVIDER_OUTCOME"
        auth.updated_at = _now()
        db.commit()
        raise HTTPException(502, "Provider outcome is UNKNOWN; no blind retry is allowed.") from exc
    except Exception as exc:
        # A provider/client exception outside the normal PR-9A transport
        # taxonomy is also unknown. Consume the authorization durably rather
        # than allowing a caller to blind-retry the same read.
        auth.status = "UNKNOWN"
        auth.revocation_reason = str(exc)[:500] or "UNKNOWN_PROVIDER_OUTCOME"
        auth.updated_at = _now()
        db.commit()
        raise HTTPException(502, "Provider outcome is UNKNOWN; no blind retry is allowed.") from exc
    if run.external_read_count == 1 and any(
        "unknown" in str(blocker).casefold() for blocker in (run.blockers or [])
    ):
        auth.status = "UNKNOWN"
        auth.revocation_reason = "UNKNOWN_PROVIDER_OUTCOME"
    execution = db.scalar(
        select(LiveSupplierCertificationExecution)
        .where(LiveSupplierCertificationExecution.run_id == run.id)
        .order_by(LiveSupplierCertificationExecution.created_at.desc())
    )
    if execution is not None:
        auth.execution_id = execution.id
    auth.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action="live_supplier.execution_authorization.consumed",
        entity_type="live_supplier_execution_authorization",
        entity_id=auth.id,
        metadata={"run_id": str(run.id), "status": run.status},
        idempotency_key=f"pr9b-auth-consume:{auth.id}",
    )
    return run


def review_evidence(
    db: Session,
    owner: User,
    execution_id: uuid.UUID,
    data: Any,
) -> LiveSupplierEvidenceReview:
    if str(data.actor_provenance).upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may review supplier evidence.")
    execution = db.scalar(
        select(LiveSupplierCertificationExecution).where(
            LiveSupplierCertificationExecution.id == execution_id,
            LiveSupplierCertificationExecution.owner_id == owner.id,
        )
    )
    if execution is None:
        raise HTTPException(404, "Certification execution not found.")
    expected_hash = execution.content_hash or ""
    if expected_hash and data.evidence_hash != expected_hash:
        raise HTTPException(409, "Evidence review is stale: content hash changed.")
    if data.evidence_version != 1:
        raise HTTPException(409, "Evidence review is stale: evidence version changed.")
    allowed = {"ACCEPT", "REQUEST_MORE", "REJECT", "CONTRADICTION", "CORRELATION_ERROR"}
    action = str(data.action).upper()
    if action not in allowed:
        raise HTTPException(422, "Unsupported evidence review action.")
    fp = _fp(owner.id, execution.id, expected_hash, data.evidence_version, action, data.rationale)
    existing = db.scalar(
        select(LiveSupplierEvidenceReview).where(
            LiveSupplierEvidenceReview.owner_id == owner.id,
            LiveSupplierEvidenceReview.fingerprint == fp,
        )
    )
    if existing is not None:
        return existing
    stamp = _now()
    row = LiveSupplierEvidenceReview(
        owner_id=owner.id,
        execution_id=execution.id,
        run_id=execution.run_id,
        evidence_hash=expected_hash,
        evidence_version=1,
        action=action,
        actor_id=owner.id,
        actor_provenance="HUMAN",
        rationale=data.rationale.strip(),
        fingerprint=fp,
        created_at=stamp,
    )
    db.add(row)
    run = db.get(LiveSupplierCertificationRun, execution.run_id)
    if run is not None:
        if action == "ACCEPT":
            if run.status == "PASS":
                run.trust_classification = "HUMAN_REVIEWED"
            else:
                run.status = "BLOCKED"
                run.trust_classification = "HUMAN_REVIEW_REQUIRED"
                run.blockers = list(
                    dict.fromkeys([*(run.blockers or []), "HUMAN_ACCEPT_BLOCKED_RUN"])
                )
        elif action == "REQUEST_MORE":
            run.status = "REVIEW_REQUIRED"
            run.trust_classification = "HUMAN_REVIEW_REQUIRED"
        else:
            run.status = "BLOCKED"
            run.trust_classification = "HUMAN_REVIEW_REQUIRED"
            run.blockers = list(dict.fromkeys([*(run.blockers or []), f"HUMAN_{action}"]))
        run.updated_at = stamp
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="live_supplier.evidence.reviewed",
        entity_type="live_supplier_evidence_review",
        entity_id=row.id,
        metadata={
            "execution_id": str(execution.id),
            "action": action,
            "evidence_hash": expected_hash,
        },
        idempotency_key=f"pr9b-review:{owner.id}:{fp}",
    )
    return row


def list_reviews(
    db: Session, owner: User, execution_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    query = select(LiveSupplierEvidenceReview).where(
        LiveSupplierEvidenceReview.owner_id == owner.id
    )
    if execution_id is not None:
        query = query.where(LiveSupplierEvidenceReview.execution_id == execution_id)
    rows = db.scalars(
        query.order_by(
            LiveSupplierEvidenceReview.created_at.asc(), LiveSupplierEvidenceReview.id.asc()
        )
    )
    return [
        {
            "id": str(row.id),
            "execution_id": str(row.execution_id),
            "run_id": str(row.run_id),
            "evidence_hash": row.evidence_hash,
            "evidence_version": row.evidence_version,
            "action": row.action,
            "actor_id": str(row.actor_id),
            "actor_provenance": row.actor_provenance,
            "rationale": row.rationale,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def authorization_history(
    db: Session, owner: User, authorization_id: uuid.UUID
) -> dict[str, object]:
    row = get_authorization(db, owner, authorization_id)
    execution = None
    run = None
    if row.execution_id is not None:
        execution = db.get(LiveSupplierCertificationExecution, row.execution_id)
        if execution is not None:
            run = db.get(LiveSupplierCertificationRun, execution.run_id)
    return {
        "authorization": _auth_dict(row),
        "run": (
            {
                "id": str(run.id),
                "status": run.status,
                "trust_classification": run.trust_classification,
                "blockers": run.blockers,
                "evidence_refs": run.evidence_refs,
            }
            if run is not None
            else None
        ),
        "execution": (
            {
                "id": str(execution.id),
                "status": execution.status,
                "content_hash": execution.content_hash,
                "provenance": execution.provenance,
            }
            if execution is not None
            else None
        ),
        "reviews": list_reviews(db, owner, execution.id) if execution is not None else [],
    }


def authorization_response(row: LiveSupplierExecutionAuthorization) -> dict[str, object]:
    return _auth_dict(row)


def review_response(row: LiveSupplierEvidenceReview) -> dict[str, object]:
    return {
        "id": str(row.id),
        "execution_id": str(row.execution_id),
        "run_id": str(row.run_id),
        "evidence_hash": row.evidence_hash,
        "evidence_version": row.evidence_version,
        "action": row.action,
        "actor_id": str(row.actor_id),
        "actor_provenance": row.actor_provenance,
        "rationale": row.rationale,
        "created_at": row.created_at.isoformat(),
    }
