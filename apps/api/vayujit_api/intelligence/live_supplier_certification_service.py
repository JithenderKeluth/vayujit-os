"""PR-9A controlled supplier-source certification service.

This module deliberately does not perform search, supplier contact, RFQ, or
procurement. It reuses the existing external source-profile authority and
``ApprovedWebFetcher`` and records the scoped, immutable certification ledger.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.external_models import ExternalFetch, ExternalSourceProfile
from vayujit_api.intelligence.external_provider import ApprovedWebFetcher, host_of
from vayujit_api.intelligence.live_supplier_certification_models import (
    LiveSupplierCertificationExecution,
    LiveSupplierCertificationRun,
    LiveSupplierSourceApproval,
)
from vayujit_api.intelligence.policy import UnsafeURL, validate_source_url
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence, SupplierSource

POLICY_VERSION = "pr9a-live-supplier-v1"
CHECKS = [
    "owner_context",
    "canonical_source_profile",
    "human_approval_scope",
    "runtime_policy",
    "network_safety",
    "immutable_evidence",
    "provenance",
    "supplier_correlation",
    "product_classification",
    "downstream_eligibility",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _utc_or_none(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _path_in_scope(requested_path: str, path_scope: str) -> bool:
    """Treat a scope as one path or a complete descendant path prefix."""
    requested = requested_path or "/"
    scope = path_scope or "/"
    if scope == "/":
        return True
    normalized_scope = scope.rstrip("/")
    return requested == normalized_scope or requested.startswith(normalized_scope + "/")


def _supplier_matches_host(supplier: Supplier, host: str) -> bool:
    """Match canonical suppliers whether legacy data stores a host or URL."""
    raw = str(supplier.normalized_domain or supplier.website or "").strip().lower()
    if not raw:
        return False
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    stored_host = (parsed.hostname or "").lower().rstrip(".")
    return stored_host == host


def _profile_for_host(db: Session, owner: User, host: str) -> ExternalSourceProfile | None:
    rows = db.scalars(
        select(ExternalSourceProfile).where(ExternalSourceProfile.owner_id == owner.id)
    )
    for profile in rows:
        if (
            not profile.enabled
            or profile.robots_policy != "APPROVED"
            or profile.terms_status != "APPROVED"
        ):
            continue
        if profile.access_classification != "APPROVED":
            continue
        domains = [str(item).lower().rstrip(".") for item in (profile.approved_domains or [])]
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return profile
    return None


def _context(
    db: Session,
    owner: User,
    goal_id: uuid.UUID | None,
    opportunity_id: uuid.UUID | None,
) -> tuple[BusinessAgentGoal | None, ProductOpportunity | None]:
    goal = None
    opportunity = None
    if goal_id is not None:
        goal = db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.id == goal_id, BusinessAgentGoal.owner_id == owner.id
            )
        )
        if goal is None:
            raise HTTPException(404, "Business goal not found for this owner.")
    if opportunity_id is not None:
        opportunity = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
            )
        )
        if opportunity is None:
            raise HTTPException(404, "Product opportunity not found for this owner.")
    if goal is not None and opportunity is not None:
        structured = goal.structured_goal if isinstance(goal.structured_goal, dict) else {}
        selected = structured.get("product_opportunity_id") or structured.get(
            "selected_product_opportunity_id"
        )
        if selected and str(selected) != str(opportunity.id):
            raise HTTPException(
                409, "Goal and product opportunity are not the same canonical context."
            )
    return goal, opportunity


def _approval_dict(row: LiveSupplierSourceApproval) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id) if row.opportunity_id else None,
        "source_profile_id": str(row.source_profile_id),
        "source_url": row.source_url,
        "normalized_host": row.normalized_host,
        "path_scope": row.path_scope,
        "candidate_category": row.candidate_category,
        "operation": row.operation,
        "purpose": row.purpose,
        "actor_id": str(row.actor_id),
        "actor_provenance": "HUMAN",
        "status": row.status,
        "version": row.version,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "revocation_reason": row.revocation_reason,
        "fingerprint": row.fingerprint,
    }


def create_approval(db: Session, owner: User, data: Any) -> LiveSupplierSourceApproval:
    if str(data.actor_provenance).upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may approve a supplier source.")
    raw = validate_source_url(data.source_url)
    if not raw or urlparse(raw).scheme != "https":
        raise HTTPException(422, "HTTPS is required for an approved supplier source.")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    profile = _profile_for_host(db, owner, host)
    if profile is None:
        raise HTTPException(
            409,
            "Canonical external source approval is required before PR-9A scope approval.",
        )
    _context(db, owner, data.goal_id, data.opportunity_id)
    path_scope = (data.path_scope or parsed.path or "/").strip() or "/"
    if not path_scope.startswith("/") or "?" in path_scope or "#" in path_scope:
        raise HTTPException(422, "Path scope must be a path prefix without query or fragment.")
    expires_at = _utc_or_none(data.expires_at)
    fp = _fingerprint(owner.id, data.goal_id, data.opportunity_id, raw, path_scope, data.purpose)
    existing = db.scalar(
        select(LiveSupplierSourceApproval).where(
            LiveSupplierSourceApproval.owner_id == owner.id,
            LiveSupplierSourceApproval.fingerprint == fp,
        )
    )
    if existing is not None:
        return existing
    prior_versions = list(
        db.scalars(
            select(LiveSupplierSourceApproval).where(
                LiveSupplierSourceApproval.owner_id == owner.id,
                LiveSupplierSourceApproval.normalized_host == host,
                LiveSupplierSourceApproval.source_url == raw,
            )
        )
    )
    stamp = _now()
    row = LiveSupplierSourceApproval(
        owner_id=owner.id,
        goal_id=data.goal_id,
        opportunity_id=data.opportunity_id,
        source_profile_id=profile.id,
        source_url=raw,
        normalized_host=host,
        path_scope=path_scope,
        candidate_category=data.candidate_category,
        operation="LIVE_READ_ONLY",
        purpose=data.purpose,
        actor_id=owner.id,
        status="APPROVED",
        version=max((item.version for item in prior_versions), default=0) + 1,
        approved_at=stamp,
        expires_at=expires_at,
        fingerprint=fp,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="live_supplier.source_scope.approved",
        entity_type="live_supplier_source_approval",
        entity_id=row.id,
        metadata={"profile_id": str(profile.id), "host": host, "path_scope": path_scope},
        idempotency_key=f"pr9a-approval:{owner.id}:{fp}",
    )
    return row


def revoke_approval(
    db: Session, owner: User, approval_id: uuid.UUID, reason: str, actor_provenance: str
) -> LiveSupplierSourceApproval:
    if actor_provenance.upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may revoke a supplier source.")
    row = db.scalar(
        select(LiveSupplierSourceApproval).where(
            LiveSupplierSourceApproval.id == approval_id,
            LiveSupplierSourceApproval.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Source approval not found.")
    if row.status != "REVOKED":
        row.status = "REVOKED"
        row.revoked_at = _now()
        row.revocation_reason = reason.strip()
        row.updated_at = _now()
        record_event(
            db,
            actor_id=owner.id,
            action="live_supplier.source_scope.revoked",
            entity_type="live_supplier_source_approval",
            entity_id=row.id,
            metadata={"reason": reason.strip(), "version": row.version},
            idempotency_key=f"pr9a-revoke:{row.id}:{row.version}",
        )
    return row


def _settings_blockers(settings: Any) -> list[str]:
    blockers: list[str] = []
    if settings.intelligence_external_provider_mode != "LIVE_READ_ONLY":
        blockers.append("MODE_NOT_LIVE_READ_ONLY")
    if not settings.intelligence_enabled or not settings.intelligence_external_research_enabled:
        blockers.append("EXTERNAL_RESEARCH_DISABLED")
    if not settings.intelligence_web_fetch_enabled:
        blockers.append("APPROVED_FETCH_DISABLED")
    if settings.intelligence_external_kill_switch or settings.external_mutations_emergency_stop:
        blockers.append("EXTERNAL_KILL_SWITCH")
    return blockers


def _classify_page(extracted: dict[str, object], category: str) -> dict[str, object]:
    title = str(extracted.get("title") or "").strip()
    description = str(extracted.get("meta_description") or "").strip()
    text = str(extracted.get("text") or "")
    haystack = f"{title} {description} {text}".casefold()
    supplier_markers = ("manufacturer", "wholesale", "distributor", "oem", "bulk", "moq")
    product_markers = ("add to cart", "buy now", "product", "price", "sku", "model")
    directory_markers = ("directory", "search suppliers", "supplier listing")
    if any(marker in haystack for marker in directory_markers):
        kind = "SUPPLIER_DIRECTORY"
    elif any(marker in haystack for marker in supplier_markers):
        kind = "SUPPLIER_SOURCE"
    elif any(marker in haystack for marker in product_markers) and title:
        kind = "RETAIL_PRODUCT"
    else:
        kind = "UNKNOWN_PAGE"
    return {
        "classification": kind,
        "candidate_category": category,
        "meaningful_title": bool(title),
        "supplier_relevance": kind == "SUPPLIER_SOURCE",
        "product_identity": bool(title and (description or extracted.get("canonical_url"))),
    }


def _execution_dict(row: LiveSupplierCertificationExecution) -> dict[str, object]:
    return {
        "id": str(row.id),
        "run_id": str(row.run_id),
        "approval_id": str(row.approval_id),
        "requested_url": row.requested_url,
        "final_url": row.final_url,
        "domain": row.domain,
        "redirect_chain": list(row.redirect_chain or []),
        "provider": row.provider,
        "mode": row.mode,
        "status": row.status,
        "failure_code": row.failure_code,
        "http_status": row.http_status,
        "content_type": row.content_type,
        "content_length": row.content_length,
        "content_hash": row.content_hash,
        "extracted": row.extracted,
        "provenance": row.provenance,
        "trust_classification": row.trust_classification,
        "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
    }


def _run_dict(
    row: LiveSupplierCertificationRun, execution: LiveSupplierCertificationExecution | None = None
) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id) if row.opportunity_id else None,
        "approval_id": str(row.approval_id),
        "source_url": row.source_url,
        "provider": row.provider,
        "mode": row.mode,
        "policy_version": row.policy_version,
        "requested_checks": row.requested_checks,
        "executed_checks": row.executed_checks,
        "gate_outcomes": row.gate_outcomes,
        "evidence_refs": row.evidence_refs,
        "blockers": row.blockers,
        "external_read_count": row.external_read_count,
        "external_write_count": row.external_write_count,
        "fetch_count": row.fetch_count,
        "status": row.status,
        "trust_classification": row.trust_classification,
        "supplier_correlation": row.supplier_correlation,
        "product_classification": row.product_classification,
        "correlation_id": row.correlation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "execution": _execution_dict(execution) if execution is not None else None,
    }


def _scope_blockers(
    db: Session,
    approval: LiveSupplierSourceApproval,
    normalized_url: str,
    stamp: datetime,
) -> tuple[list[str], ExternalSourceProfile | None]:
    blockers: list[str] = []
    if approval.status != "APPROVED":
        blockers.append("SOURCE_APPROVAL_NOT_ACTIVE")
    if approval.expires_at is not None and approval.expires_at <= stamp:
        blockers.append("SOURCE_APPROVAL_EXPIRED")
    if host_of(normalized_url) != approval.normalized_host:
        blockers.append("HOST_OUTSIDE_APPROVED_SCOPE")
    requested_path = urlparse(normalized_url).path or "/"
    if not _path_in_scope(requested_path, approval.path_scope):
        blockers.append("PATH_OUTSIDE_APPROVED_SCOPE")
    profile = db.get(ExternalSourceProfile, approval.source_profile_id)
    if (
        profile is None
        or not profile.enabled
        or profile.access_classification != "APPROVED"
        or profile.robots_policy != "APPROVED"
        or profile.terms_status != "APPROVED"
    ):
        blockers.append("CANONICAL_SOURCE_PROFILE_NOT_ACTIVE")
    return blockers, profile


def certify(db: Session, owner: User, data: Any) -> LiveSupplierCertificationRun:
    approval = db.scalar(
        select(LiveSupplierSourceApproval).where(
            LiveSupplierSourceApproval.id == data.approval_id,
            LiveSupplierSourceApproval.owner_id == owner.id,
        )
    )
    if approval is None:
        raise HTTPException(404, "Source approval not found.")
    goal_id = data.goal_id if data.goal_id is not None else approval.goal_id
    opportunity_id = (
        data.opportunity_id if data.opportunity_id is not None else approval.opportunity_id
    )
    if opportunity_id is None:
        raise HTTPException(422, "A canonical ProductOpportunity is required for certification.")
    _context(db, owner, goal_id, opportunity_id)
    source_url = data.source_url or approval.source_url
    raw = validate_source_url(source_url)
    if not raw or urlparse(raw).scheme != "https":
        raise HTTPException(422, "HTTPS is required for approved fetch.")
    normalized = raw
    # Include the current approval state in the logical identity. A replay
    # after revocation/expiry must create a new BLOCKED history row rather
    # than returning an earlier PASS result.
    fingerprint = _fingerprint(
        owner.id,
        approval.id,
        approval.version,
        approval.status,
        approval.expires_at.isoformat() if approval.expires_at else "",
        normalized,
        POLICY_VERSION,
        ("refresh:" + (data.idempotency_key or "generated")) if data.refresh else "stable",
    )
    existing = db.scalar(
        select(LiveSupplierCertificationRun).where(
            LiveSupplierCertificationRun.owner_id == owner.id,
            LiveSupplierCertificationRun.fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    stamp = _now()
    correlation_id = data.correlation_id or f"pr9a:{uuid.uuid4()}"
    run = LiveSupplierCertificationRun(
        owner_id=owner.id,
        goal_id=goal_id,
        opportunity_id=opportunity_id,
        approval_id=approval.id,
        source_url=normalized,
        provider="approved_web_fetch",
        mode="LIVE_READ_ONLY",
        policy_version=POLICY_VERSION,
        requested_checks=list(CHECKS),
        executed_checks=[],
        gate_outcomes={},
        evidence_refs=[],
        blockers=[],
        status="NOT_EXECUTED",
        trust_classification="UNKNOWN",
        supplier_correlation={},
        product_classification={},
        correlation_id=correlation_id,
        fingerprint=fingerprint,
        idempotency_key=data.idempotency_key or f"pr9a:{fingerprint}",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(run)
    db.flush()
    gates: dict[str, str] = {"owner_context": "PASS", "human_approval_scope": "PASS"}
    executed = ["owner_context", "canonical_source_profile", "human_approval_scope"]
    blockers, profile = _scope_blockers(db, approval, normalized, stamp)
    gates["canonical_source_profile"] = (
        "PASS"
        if not any(item in blockers for item in ("CANONICAL_SOURCE_PROFILE_NOT_ACTIVE",))
        else "BLOCKED"
    )
    for key in (
        "runtime_policy",
        "network_safety",
        "immutable_evidence",
        "provenance",
        "supplier_correlation",
        "product_classification",
        "downstream_eligibility",
    ):
        gates[key] = "NOT_EXECUTED"
    settings = get_settings()
    settings_blockers = _settings_blockers(settings)
    blockers.extend(settings_blockers)
    gates["runtime_policy"] = "PASS" if not settings_blockers else "BLOCKED"
    executed.append("runtime_policy")
    execution: LiveSupplierCertificationExecution | None = None
    if not blockers:
        # Re-read approval state after policy checks, immediately before the
        # provider boundary. Revocation/expiry between eligibility and fetch
        # must block without issuing a network request.
        db.expire(approval)
        db.refresh(approval)
        revalidated, profile = _scope_blockers(db, approval, normalized, _now())
        if revalidated:
            blockers.extend(revalidated)
            gates["human_approval_scope"] = "BLOCKED"
            gates["network_safety"] = "NOT_EXECUTED"
            run.status = "BLOCKED"
            run.trust_classification = "UNKNOWN"
        else:
            # Count the permitted read attempt before transport invocation so a
            # timeout, redirect block, or unsupported MIME is still observable.
            run.external_read_count = 1
            run.fetch_count = 1
            try:
                result = cast(
                    dict[str, Any],
                    ApprovedWebFetcher(settings).fetch(
                        normalized,
                        allowed_domains=(approval.normalized_host,),
                        blocked_domains=tuple(
                            item.strip().lower().rstrip(".")
                            for item in settings.intelligence_external_blocked_domains.split(",")
                            if item.strip()
                        ),
                    ),
                )
                run.status = "PASS"
                run.trust_classification = "FETCHED_SOURCE"
                extracted_value = result.get("extracted")
                extracted = (
                    cast(dict[str, object], extracted_value)
                    if isinstance(extracted_value, dict)
                    else {}
                )
                classification = _classify_page(extracted, approval.candidate_category)
                run.product_classification = classification
                run.supplier_correlation = {"outcome": "UNMATCHED", "supplier_id": None}
                supplier_source_id: uuid.UUID | None = None
                host = str(result.get("domain") or approval.normalized_host)
                suppliers = [
                    supplier
                    for supplier in db.scalars(
                        select(Supplier).where(Supplier.owner_id == owner.id).order_by(Supplier.id)
                    )
                    if _supplier_matches_host(supplier, host)
                ]
                if len(suppliers) == 1:
                    supplier = suppliers[0]
                    run.supplier_correlation = {
                        "outcome": "CORRELATED",
                        "supplier_id": str(supplier.id),
                        "match": "canonical_normalized_domain",
                    }
                    source_ref = str(result.get("final_url") or normalized)
                    source = db.scalar(
                        select(SupplierSource).where(
                            SupplierSource.owner_id == owner.id,
                            SupplierSource.supplier_id == supplier.id,
                            SupplierSource.source_url == source_ref,
                        )
                    )
                    if source is None:
                        source = SupplierSource(
                            owner_id=owner.id,
                            supplier_id=supplier.id,
                            source_type=(
                                "manufacturer_website"
                                if classification["classification"] == "SUPPLIER_SOURCE"
                                else "manual_entry"
                            ),
                            access_mode="approved_web_fetch",
                            external_id=source_ref,
                            reference=source_ref,
                            source_url=source_ref,
                            status="fetched_source",
                            metadata_json={
                                "evidence_environment": "LIVE_READ_ONLY",
                                "claim_semantics": "SOURCE_PROVIDED",
                                "approval_id": str(approval.id),
                                "approval_version": approval.version,
                            },
                            observed_at=stamp,
                            created_at=stamp,
                        )
                        db.add(source)
                        db.flush()
                    supplier_source_id = source.id
                    evidence_hash = str(result.get("content_hash") or "")
                    evidence_key = f"pr9a:{run.id}:{approval.id}:{approval.version}:{evidence_hash}"
                    evidence = db.scalar(
                        select(SupplierEvidence).where(
                            SupplierEvidence.owner_id == owner.id,
                            SupplierEvidence.idempotency_key == evidence_key,
                        )
                    )
                    if evidence is None:
                        evidence = SupplierEvidence(
                            owner_id=owner.id,
                            supplier_id=supplier.id,
                            source_id=source.id,
                            evidence_kind="observed",
                            reference=source_ref,
                            source_url=source_ref,
                            normalized_value={
                                "extracted": extracted,
                                "classification": classification,
                            },
                            excerpt=str(extracted.get("text") or "")[:2_000],
                            content_hash=evidence_hash,
                            observed_at=stamp,
                            retrieved_at=stamp,
                            freshness_status="unknown",
                            verification_status="unverified",
                            archived=False,
                            updated_at=stamp,
                            idempotency_key=evidence_key,
                        )
                        db.add(evidence)
                        db.flush()
                    run.evidence_refs = [str(evidence.id)]
                    run.trust_classification = "SOURCE_PROVIDED_CLAIM"
                    run.product_classification = classification
                elif len(suppliers) > 1:
                    run.supplier_correlation = {
                        "outcome": "AMBIGUOUS",
                        "supplier_ids": [str(x.id) for x in suppliers],
                    }
                gates["network_safety"] = "PASS"
                gates["immutable_evidence"] = "PASS" if result.get("content_hash") else "BLOCKED"
                gates["provenance"] = "PASS"
                gates["supplier_correlation"] = (
                    "PASS"
                    if run.supplier_correlation.get("outcome")
                    in {"CORRELATED", "UNMATCHED", "AMBIGUOUS"}
                    else "BLOCKED"
                )
                gates["product_classification"] = "PASS"
                gates["downstream_eligibility"] = (
                    "PASS"
                    if run.supplier_correlation.get("outcome") == "CORRELATED"
                    and classification.get("supplier_relevance")
                    else "BLOCKED"
                )
                executed.extend(
                    [
                        "network_safety",
                        "immutable_evidence",
                        "provenance",
                        "supplier_correlation",
                        "product_classification",
                        "downstream_eligibility",
                    ]
                )
                ext_identity = f"pr9a-external-fetch:{fingerprint}"
                ext = db.scalar(
                    select(ExternalFetch).where(
                        ExternalFetch.owner_id == owner.id,
                        ExternalFetch.identity_key == ext_identity,
                    )
                )
                if ext is None:
                    ext = ExternalFetch(
                        owner_id=owner.id,
                        requested_url=str(result.get("requested_url") or normalized),
                        final_url=str(result.get("final_url") or normalized),
                        domain=host,
                        status="COMPLETED",
                        http_status=int(result.get("http_status") or 0),
                        content_type=str(result.get("content_type") or ""),
                        content_length=int(result.get("content_length") or 0),
                        content_hash=str(result.get("content_hash") or ""),
                        source_profile=profile.name if profile else "scoped-approval",
                        provider_mode="LIVE_READ_ONLY",
                        redirect_count=int(result.get("redirect_count") or 0),
                        correlation_id=correlation_id,
                        identity_key=ext_identity,
                        freshness="unknown",
                        extracted=extracted,
                        created_at=stamp,
                        retrieved_at=stamp,
                    )
                    db.add(ext)
                    db.flush()
                execution_fp = _fingerprint(
                    run.id, result.get("content_hash"), result.get("final_url")
                )
                execution = LiveSupplierCertificationExecution(
                    owner_id=owner.id,
                    run_id=run.id,
                    approval_id=approval.id,
                    external_fetch_id=ext.id,
                    supplier_id=(
                        uuid.UUID(str(run.supplier_correlation["supplier_id"]))
                        if run.supplier_correlation.get("supplier_id")
                        else None
                    ),
                    supplier_source_id=supplier_source_id,
                    requested_url=str(result.get("requested_url") or normalized),
                    final_url=str(result.get("final_url") or normalized),
                    domain=host,
                    redirect_chain=(
                        list(result.get("redirect_chain") or [])
                        if isinstance(result.get("redirect_chain"), list)
                        else [
                            str(result.get("requested_url") or normalized),
                            str(result.get("final_url") or normalized),
                        ]
                    ),
                    provider="approved_web_fetch",
                    mode="LIVE_READ_ONLY",
                    status="COMPLETED",
                    http_status=int(result.get("http_status") or 0),
                    content_type=str(result.get("content_type") or ""),
                    content_length=int(result.get("content_length") or 0),
                    content_hash=str(result.get("content_hash") or ""),
                    extracted=extracted,
                    provenance={
                        "approval_id": str(approval.id),
                        "approval_version": approval.version,
                        "profile_id": str(profile.id) if profile else None,
                        "owner_id": str(owner.id),
                        "goal_id": str(goal_id) if goal_id else None,
                        "opportunity_id": str(opportunity_id) if opportunity_id else None,
                        "correlation_id": correlation_id,
                        "environment": "LIVE_READ_ONLY",
                        "source_snapshot_reference": f"sha256:{result.get('content_hash') or ''}",
                    },
                    trust_classification=run.trust_classification,
                    fingerprint=execution_fp,
                    created_at=stamp,
                    retrieved_at=stamp,
                )
                db.add(execution)
                db.flush()
            except (RuntimeError, UnsafeURL, ValueError) as exc:
                code = str(exc) or "FETCH_FAILED"
                blockers.append(code)
                run.status = "BLOCKED"
                run.trust_classification = "UNKNOWN"
                gates["network_safety"] = "BLOCKED"
                execution = LiveSupplierCertificationExecution(
                    owner_id=owner.id,
                    run_id=run.id,
                    approval_id=approval.id,
                    requested_url=normalized,
                    final_url=None,
                    domain=approval.normalized_host,
                    redirect_chain=[],
                    provider="approved_web_fetch",
                    mode="LIVE_READ_ONLY",
                    status="BLOCKED",
                    failure_code=code,
                    extracted={},
                    provenance={
                        "approval_id": str(approval.id),
                        "owner_id": str(owner.id),
                        "goal_id": str(goal_id) if goal_id else None,
                        "opportunity_id": str(opportunity_id) if opportunity_id else None,
                        "correlation_id": correlation_id,
                        "environment": "LIVE_READ_ONLY",
                    },
                    trust_classification="UNKNOWN",
                    fingerprint=_fingerprint(run.id, code),
                    created_at=stamp,
                )
                db.add(execution)
                db.flush()
    else:
        run.status = "BLOCKED"
        run.trust_classification = "UNKNOWN"
    run.executed_checks = executed
    run.gate_outcomes = cast(dict[str, object], gates)
    run.blockers = list(dict.fromkeys(blockers))
    run.completed_at = _now()
    run.updated_at = _now()
    record_event(
        db,
        actor_id=owner.id,
        action="live_supplier.certification.completed",
        entity_type="live_supplier_certification_run",
        entity_id=run.id,
        metadata={
            "status": run.status,
            "external_read_count": run.external_read_count,
            "blockers": run.blockers,
        },
        idempotency_key=f"pr9a-run:{run.id}",
    )
    return run


def review_execution(
    db: Session, owner: User, execution_id: uuid.UUID, actor_provenance: str
) -> LiveSupplierCertificationExecution:
    if actor_provenance.upper() != "HUMAN":
        raise HTTPException(403, "Only HUMAN actors may review external evidence.")
    execution = db.scalar(
        select(LiveSupplierCertificationExecution).where(
            LiveSupplierCertificationExecution.id == execution_id,
            LiveSupplierCertificationExecution.owner_id == owner.id,
        )
    )
    if execution is None:
        raise HTTPException(404, "Certification execution not found.")
    execution.trust_classification = "HUMAN_REVIEWED"
    run = db.get(LiveSupplierCertificationRun, execution.run_id)
    if run is not None and run.status == "PASS":
        run.trust_classification = "HUMAN_REVIEWED"
    return execution


def list_approvals(db: Session, owner: User) -> list[dict[str, object]]:
    rows = db.scalars(
        select(LiveSupplierSourceApproval)
        .where(LiveSupplierSourceApproval.owner_id == owner.id)
        .order_by(
            LiveSupplierSourceApproval.created_at.desc(),
            LiveSupplierSourceApproval.id.desc(),
        )
    )
    return [_approval_dict(row) for row in rows]


def list_runs(db: Session, owner: User) -> list[dict[str, object]]:
    rows = db.scalars(
        select(LiveSupplierCertificationRun)
        .where(LiveSupplierCertificationRun.owner_id == owner.id)
        .order_by(
            LiveSupplierCertificationRun.created_at.desc(),
            LiveSupplierCertificationRun.id.desc(),
        )
    )
    return [
        _run_dict(
            row,
            db.scalar(
                select(LiveSupplierCertificationExecution).where(
                    LiveSupplierCertificationExecution.run_id == row.id
                )
            ),
        )
        for row in rows
    ]


def approval_response(row: LiveSupplierSourceApproval) -> dict[str, object]:
    return _approval_dict(row)


def run_response(db: Session, row: LiveSupplierCertificationRun) -> dict[str, object]:
    execution = db.scalar(
        select(LiveSupplierCertificationExecution).where(
            LiveSupplierCertificationExecution.run_id == row.id
        )
    )
    return _run_dict(row, execution)
