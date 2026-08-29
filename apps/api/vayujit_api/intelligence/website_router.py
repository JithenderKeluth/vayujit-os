"""Owner-scoped durable, single-page website intelligence API."""

from __future__ import annotations

import html
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchReport,
)
from vayujit_api.intelligence.autonomous_service import report as mission_report
from vayujit_api.intelligence.external_projection import (
    website_integrity_projection,
    website_table_inventory,
)
from vayujit_api.intelligence.website_intelligence import (
    WEBSITE_SOURCE_TYPES,
    extract_website_intelligence,
)
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteClaim,
    WebsiteObservation,
    WebsiteOffering,
    WebsiteRefreshJob,
    WebsiteSourceProfile,
    WebsiteSourceProfileVersion,
)
from vayujit_api.intelligence.website_refresh import (
    REFRESH_RECOVERY_FAILURES,
    execute_refresh_job,
    materialize_due_refreshes,
    recover_refresh_job,
    schedule_profile_refresh,
)
from vayujit_api.intelligence.website_service import (
    get_or_create_profile,
    integrity_counts,
    run_website_mission,
)

router = APIRouter(prefix="/api/v1/intelligence/websites", tags=["website-intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


class WebsitePreviewRequest(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    content: str = Field(min_length=1, max_length=50000)
    source_type: str = "SUPPLIER_WEBSITE"


class WebsiteProfileRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=200)
    source_type: str = "SUPPLIER_WEBSITE"
    country: str = ""
    region: str = ""
    enabled: bool = False
    search_allowed: bool = False
    fetch_allowed: bool = False
    freshness_policy: Literal["MANUAL", "DAILY", "WEEKLY", "MONTHLY"] = "MANUAL"
    verification_policy: str = "EVIDENCE_REQUIRED"
    robots_terms_status: str = "UNKNOWN"
    known_mirror_domains: list[str] = Field(default_factory=list, max_length=20)
    business_identity_hints: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=1000)


class WebsiteRefreshScheduleRequest(BaseModel):
    policy: Literal["MANUAL", "DAILY", "WEEKLY", "MONTHLY"]
    timezone: str = "UTC"
    next_refresh_at: datetime | None = None
    target_type: str = "WEBSITE_SOURCE"


class WebsiteRefreshExecuteRequest(BaseModel):
    content: str | None = Field(default=None, max_length=50000)


class WebsiteResearchRequest(WebsitePreviewRequest):
    idempotency_key: str = Field(min_length=3, max_length=180)
    supplier_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None


def _payload(row: WebsiteSourceProfile) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "domain": row.domain,
        "display_name": row.display_name,
        "source_type": row.source_type,
        "country": row.country,
        "region": row.region,
        "classification": row.classification,
        "enabled": row.enabled,
        "search_allowed": row.search_allowed,
        "fetch_allowed": row.fetch_allowed,
        "freshness_policy": row.freshness_policy,
        "refresh_target_type": row.refresh_target_type,
        "timezone": row.timezone,
        "next_refresh_at": row.next_refresh_at,
        "last_refresh_at": row.last_refresh_at,
        "last_success_at": row.last_success_at,
        "last_failure_at": row.last_failure_at,
        "refresh_failure_code": row.refresh_failure_code,
        "verification_policy": row.verification_policy,
        "robots_terms_status": row.robots_terms_status,
        "known_mirror_domains": row.known_mirror_domains,
        "business_identity_hints": row.business_identity_hints,
        "notes": row.notes,
        "version": row.version,
        "archived_at": row.archived_at,
    }


@router.get("/source-types")
def source_types() -> dict[str, object]:
    return {"source_types": list(WEBSITE_SOURCE_TYPES), "read_only": True}


@router.get("/profiles")
def profiles(db: DB, owner: Owner) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(WebsiteSourceProfile)
            .where(
                WebsiteSourceProfile.owner_id == owner.id,
                WebsiteSourceProfile.archived_at.is_(None),
            )
            .order_by(WebsiteSourceProfile.domain)
        )
    )
    return {
        "profiles": [_payload(row) for row in rows],
        "status": "CONFIGURED" if rows else "NOT_CONFIGURED",
        "external_calls": False,
    }


@router.post("/profiles", status_code=201)
def profile_create(data: WebsiteProfileRequest, db: DB, owner: Owner) -> dict[str, object]:
    if data.source_type not in WEBSITE_SOURCE_TYPES:
        raise HTTPException(422, "Unsupported website source type.")
    row = get_or_create_profile(db, owner, data.domain, data.source_type)
    row.display_name = data.display_name
    row.country = data.country
    row.region = data.region
    row.enabled = data.enabled
    row.search_allowed = data.search_allowed
    row.fetch_allowed = data.fetch_allowed
    row.freshness_policy = data.freshness_policy
    row.verification_policy = data.verification_policy
    row.robots_terms_status = data.robots_terms_status
    row.known_mirror_domains = data.known_mirror_domains
    row.business_identity_hints = data.business_identity_hints
    row.notes = data.notes
    db.commit()
    db.refresh(row)
    return _payload(row)


@router.put("/profiles/{profile_id}")
def profile_update(
    profile_id: uuid.UUID, data: WebsiteProfileRequest, db: DB, owner: Owner
) -> dict[str, object]:
    row = db.scalar(
        select(WebsiteSourceProfile).where(
            WebsiteSourceProfile.id == profile_id,
            WebsiteSourceProfile.owner_id == owner.id,
            WebsiteSourceProfile.archived_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(404, "Website source profile not found.")
    row.version += 1
    row.display_name = data.display_name
    row.enabled = data.enabled
    row.fetch_allowed = data.fetch_allowed
    row.freshness_policy = data.freshness_policy
    stamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    row.updated_at = stamp
    db.add(
        WebsiteSourceProfileVersion(
            owner_id=owner.id,
            profile_id=row.id,
            version=row.version,
            rules={"fetch_allowed": row.fetch_allowed, "freshness_policy": row.freshness_policy},
            created_at=stamp,
        )
    )
    db.commit()
    db.refresh(row)
    return _payload(row)


@router.delete("/profiles/{profile_id}")
def profile_archive(profile_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(WebsiteSourceProfile).where(
            WebsiteSourceProfile.id == profile_id,
            WebsiteSourceProfile.owner_id == owner.id,
            WebsiteSourceProfile.archived_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(404, "Website source profile not found.")
    row.archived_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    row.enabled = False
    db.commit()
    return {"archived": True, "id": str(row.id)}


@router.get("/integrity")
def website_integrity(db: DB, owner: Owner) -> dict[str, object]:
    """Return the bounded owner-scoped Website Intelligence integrity ledger."""
    return website_integrity_projection(db, owner)


@router.get("/tables")
def website_tables() -> list[dict[str, object]]:
    return website_table_inventory()


@router.get("/overview")
def overview(db: DB, owner: Owner) -> dict[str, object]:
    counts = integrity_counts(db, owner)
    return {
        "manufacturer_candidates": counts["manufacturer_candidates"],
        "supplier_websites": counts["supplier_website_candidates"],
        "offering_count": counts["offerings"],
        "last_researched": None,
        "status": "LOCAL_CERTIFIED",
        "owner_id": str(owner.id),
        "external_calls": False,
        "queue": 0,
        "running": 0,
        "failed": 0,
        "refresh_backlog": 0,
        "stale_sources": 0,
        "expired_sources": 0,
        "high_risk_suppliers": 0,
        "unresolved_contradictions": 0,
        "recovery": 0,
    }


@router.post("/preview")
def preview(data: WebsitePreviewRequest, owner: Owner) -> dict[str, object]:
    if data.source_type not in WEBSITE_SOURCE_TYPES:
        raise HTTPException(422, "Unsupported website source type.")
    result = extract_website_intelligence(
        url=data.url, text=data.content, source_type=data.source_type
    )
    result.update({"owner_id": str(owner.id), "persisted": False, "read_only": True})
    return result


@router.post("/research", status_code=201)
def research(data: WebsiteResearchRequest, db: DB, owner: Owner) -> dict[str, object]:
    return run_website_mission(
        db,
        owner,
        url=data.url,
        content=data.content,
        source_type=data.source_type,
        idempotency_key=data.idempotency_key,
        supplier_id=data.supplier_id,
        product_id=data.product_id,
    )


@router.get("/manufacturers")
def manufacturer_list(
    db: DB,
    owner: Owner,
    country: str | None = None,
    region: str | None = None,
    category: str | None = None,
    verification: str | None = None,
    freshness: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    risk: str | None = None,
    business_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    statement = select(ManufacturerCandidate).where(ManufacturerCandidate.owner_id == owner.id)
    if country:
        statement = statement.where(ManufacturerCandidate.country == country)
    if region:
        statement = statement.where(ManufacturerCandidate.region == region)
    if verification:
        statement = statement.where(ManufacturerCandidate.verification_state == verification)
    if freshness:
        statement = statement.where(ManufacturerCandidate.freshness == freshness)
    if business_type:
        statement = statement.where(ManufacturerCandidate.business_type == business_type)
    if status:
        statement = statement.where(ManufacturerCandidate.current_status == status)
    rows = list(db.scalars(statement.order_by(ManufacturerCandidate.updated_at.desc())))
    if min_confidence is not None:
        rows = [row for row in rows if float(row.confidence) >= min_confidence]
    if category:
        rows = [row for row in rows if category in row.product_categories]
    if risk:
        rows = [row for row in rows if risk in row.risk]
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "website": row.website,
            "domain": row.canonical_domain,
            "country": row.country,
            "region": row.region,
            "business_type": row.business_type,
            "status": row.current_status,
            "manufacturer_status": row.manufacturer_status,
            "supplier_status": row.supplier_status,
            "exporter_status": row.exporter_status,
            "distributor_status": row.distributor_status,
            "categories": row.product_categories,
            "verification": row.verification_state,
            "freshness": row.freshness,
            "confidence": float(row.confidence),
            "risk": row.risk,
            "source_count": row.source_count,
            "evidence_count": row.evidence_count,
        }
        for row in rows
    ]


@router.get("/manufacturers/{candidate_id}")
def manufacturer_detail(candidate_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(ManufacturerCandidate).where(
            ManufacturerCandidate.id == candidate_id, ManufacturerCandidate.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Manufacturer candidate not found.")
    observations = list(
        db.scalars(
            select(WebsiteObservation)
            .where(
                WebsiteObservation.owner_id == owner.id, WebsiteObservation.candidate_id == row.id
            )
            .order_by(WebsiteObservation.created_at)
        )
    )
    offerings = list(
        db.scalars(
            select(WebsiteOffering).where(
                WebsiteOffering.owner_id == owner.id, WebsiteOffering.candidate_id == row.id
            )
        )
    )
    claims = list(
        db.scalars(
            select(WebsiteClaim).where(
                WebsiteClaim.owner_id == owner.id, WebsiteClaim.candidate_id == row.id
            )
        )
    )
    return {
        "id": str(row.id),
        "name": row.name,
        "identity": {
            "website": row.website,
            "domain": row.canonical_domain,
            "country": row.country,
            "region": row.region,
        },
        "products": [item.source_name for item in offerings],
        "offerings": [
            {
                "id": str(item.id),
                "name": item.source_name,
                "match_state": item.match_state,
                "confidence": float(item.match_confidence),
            }
            for item in offerings
        ],
        "capabilities": [item.claim_value for item in claims if item.claim_type == "CAPABILITY"],
        "facilities": [],
        "commercial": [
            item.normalized_value
            for item in observations
            if item.observation_type in {"PRICE", "MOQ", "LEAD_TIME"}
        ],
        "certifications": [
            dict(item.claim_value, status=item.status)
            for item in claims
            if item.claim_type == "CERTIFICATION"
        ],
        "contacts": [],
        "risk": row.risk,
        "confidence": float(row.confidence),
        "freshness": row.freshness,
        "verification": row.verification_state,
        "history": [
            {
                "type": item.observation_type,
                "value": item.normalized_value,
                "retrieved_at": item.retrieved_at,
            }
            for item in observations
        ],
        "unknowns": ["independent_verification"],
        "report_status": "available_via_autonomous_mission",
    }


@router.get("/suppliers")
def supplier_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    rows = db.scalars(
        select(SupplierWebsiteCandidate)
        .where(SupplierWebsiteCandidate.owner_id == owner.id)
        .order_by(SupplierWebsiteCandidate.updated_at.desc())
    )
    return [
        {
            "id": str(row.id),
            "supplier_id": str(row.supplier_id) if row.supplier_id else None,
            "manufacturer_candidate_id": (
                str(row.manufacturer_candidate_id) if row.manufacturer_candidate_id else None
            ),
            "domain": row.domain,
            "identity": row.identity_state,
            "match_state": row.match_state,
            "confidence": float(row.confidence),
            "verification": row.verification_state,
            "freshness": row.freshness,
            "risk": row.risk,
            "last_researched": row.last_researched_at,
        }
        for row in rows
    ]


@router.get("/suppliers/{candidate_id}")
def supplier_detail(candidate_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(SupplierWebsiteCandidate).where(
            SupplierWebsiteCandidate.id == candidate_id,
            SupplierWebsiteCandidate.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Supplier website candidate not found.")
    return {
        "id": str(row.id),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "domain": row.domain,
        "identity": row.identity_state,
        "match_state": row.match_state,
        "confidence": float(row.confidence),
        "verification": row.verification_state,
        "freshness": row.freshness,
        "risk": row.risk,
        "history": [],
        "changes": [],
    }


def _website_mission_ids(db: Session, owner: User):
    return select(AutonomousResearchMission.id).where(
        AutonomousResearchMission.owner_id == owner.id,
        AutonomousResearchMission.mission_type.in_(
            {"MANUFACTURER_RESEARCH", "SUPPLIER_WEBSITE_RESEARCH", "SOURCE_REFRESH"}
        ),
    )


def _evidence_payload(
    db: Session, owner: User, evidence_id: uuid.UUID | str | None
) -> dict[str, object] | None:
    if not evidence_id:
        return None
    try:
        parsed = uuid.UUID(str(evidence_id))
    except ValueError:
        return None
    row = db.scalar(
        select(AutonomousResearchEvidence).where(
            AutonomousResearchEvidence.id == parsed,
            AutonomousResearchEvidence.owner_id == owner.id,
            AutonomousResearchEvidence.mission_id.in_(_website_mission_ids(db, owner)),
        )
    )
    if row is None:
        return None
    return {
        "id": str(row.id),
        "source": row.source_reference,
        "domain": row.domain,
        "value": row.normalized_value,
        "verification": row.verification_status,
        "freshness": row.freshness_status,
        "confidence": float(row.confidence),
        "observed_at": row.observed_at,
        "retrieved_at": row.retrieved_at,
        "observation_id": (
            row.lineage.get("observation_id") if isinstance(row.lineage, dict) else None
        ),
    }


@router.get("/contradictions")
def website_contradiction_list(
    db: DB,
    owner: Owner,
    candidate_id: uuid.UUID | None = None,
    source: str | None = None,
    resolution_state: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, object]]:
    statement = (
        select(AutonomousResearchContradiction)
        .where(
            AutonomousResearchContradiction.owner_id == owner.id,
            AutonomousResearchContradiction.mission_id.in_(_website_mission_ids(db, owner)),
        )
        .order_by(AutonomousResearchContradiction.created_at.desc())
    )
    if resolution_state:
        statement = statement.where(AutonomousResearchContradiction.status == resolution_state)
    if date_from:
        statement = statement.where(AutonomousResearchContradiction.created_at >= date_from)
    if date_to:
        statement = statement.where(AutonomousResearchContradiction.created_at <= date_to)
    if correlation_id:
        statement = statement.where(
            AutonomousResearchContradiction.correlation_id == correlation_id
        )
    rows = list(db.scalars(statement))
    mission_ids = {row.mission_id for row in rows}
    missions = {
        item.id: item
        for item in db.scalars(
            select(AutonomousResearchMission).where(
                AutonomousResearchMission.id.in_(mission_ids),
                AutonomousResearchMission.owner_id == owner.id,
            )
        )
    }
    output: list[dict[str, object]] = []
    for row in rows:
        mission = missions.get(row.mission_id)
        scope = mission.scope if mission and isinstance(mission.scope, dict) else {}
        candidate = str(scope.get("candidate_id")) if scope.get("candidate_id") else None
        if candidate_id and candidate != str(candidate_id):
            continue
        if source and source not in {row.source_a or "", row.source_b or ""}:
            continue
        output.append(
            {
                "id": str(row.id),
                "candidate": candidate,
                "field": row.claim_key or row.contradiction_type,
                "source_a": row.source_a,
                "source_b": row.source_b,
                "value_a": row.evidence_a_value,
                "value_b": row.evidence_b_value,
                "verification_a": row.verification_a,
                "verification_b": row.verification_b,
                "freshness_a": row.freshness_a,
                "freshness_b": row.freshness_b,
                "resolution_state": row.status,
                "created_at": row.created_at,
                "correlation_id": row.correlation_id,
                "type": row.contradiction_type,
            }
        )
    return output


@router.get("/contradictions/{contradiction_id}")
def website_contradiction_detail(
    contradiction_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    row = db.scalar(
        select(AutonomousResearchContradiction).where(
            AutonomousResearchContradiction.id == contradiction_id,
            AutonomousResearchContradiction.owner_id == owner.id,
            AutonomousResearchContradiction.mission_id.in_(_website_mission_ids(db, owner)),
        )
    )
    if row is None:
        raise HTTPException(404, "Website contradiction not found.")
    mission = db.get(AutonomousResearchMission, row.mission_id)
    scope = mission.scope if mission and isinstance(mission.scope, dict) else {}
    return {
        "id": str(row.id),
        "candidate": scope.get("candidate_id"),
        "field": row.claim_key or row.contradiction_type,
        "source_profile_a": row.source_a,
        "source_profile_b": row.source_b,
        "evidence_a": _evidence_payload(db, owner, row.evidence_a_id),
        "evidence_b": _evidence_payload(db, owner, row.evidence_b_id),
        "observation_a": row.evidence_a_value,
        "observation_b": row.evidence_b_value,
        "value_a": row.evidence_a_value,
        "value_b": row.evidence_b_value,
        "verification_a": row.verification_a,
        "verification_b": row.verification_b,
        "freshness_a": row.freshness_a,
        "freshness_b": row.freshness_b,
        "confidence_a": float(row.confidence_a) if row.confidence_a is not None else None,
        "confidence_b": float(row.confidence_b) if row.confidence_b is not None else None,
        "resolution_state": row.status,
        "reason": row.resolution_note or "Requires human review.",
        "correlation_id": row.correlation_id,
        "created_at": row.created_at,
    }


@router.get("/changes")
def website_change_list(
    db: DB,
    owner: Owner,
    candidate_id: uuid.UUID | None = None,
    field_type: str | None = None,
    materiality: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, object]]:
    statement = (
        select(AutonomousResearchChange)
        .where(
            AutonomousResearchChange.owner_id == owner.id,
            AutonomousResearchChange.mission_id.in_(_website_mission_ids(db, owner)),
        )
        .order_by(AutonomousResearchChange.created_at.desc())
    )
    if field_type:
        statement = statement.where(
            or_(
                AutonomousResearchChange.field_key == field_type,
                AutonomousResearchChange.change_type == field_type,
            )
        )
    if materiality:
        statement = statement.where(AutonomousResearchChange.materiality == materiality)
    if date_from:
        statement = statement.where(AutonomousResearchChange.created_at >= date_from)
    if date_to:
        statement = statement.where(AutonomousResearchChange.created_at <= date_to)
    if correlation_id:
        statement = statement.where(AutonomousResearchChange.correlation_id == correlation_id)
    rows = list(db.scalars(statement))
    mission_ids = {row.mission_id for row in rows}
    missions = {
        item.id: item
        for item in db.scalars(
            select(AutonomousResearchMission).where(
                AutonomousResearchMission.id.in_(mission_ids),
                AutonomousResearchMission.owner_id == owner.id,
            )
        )
    }
    output: list[dict[str, object]] = []
    for row in rows:
        mission = missions.get(row.mission_id)
        scope = mission.scope if mission and isinstance(mission.scope, dict) else {}
        candidate = str(scope.get("candidate_id")) if scope.get("candidate_id") else None
        if candidate_id and candidate != str(candidate_id):
            continue
        output.append(
            {
                "id": str(row.id),
                "entity": row.entity_type,
                "field": row.field_key or row.change_type,
                "type": row.change_type,
                "previous": row.previous_value,
                "current": row.current_value,
                "delta": float(row.delta) if row.delta is not None else None,
                "materiality": row.materiality,
                "material": row.material,
                "reason": row.reason,
                "evidence_ids": row.evidence_ids,
                "candidate": candidate,
                "source_profile": scope.get("url"),
                "created_at": row.created_at,
                "correlation_id": row.correlation_id,
                "alert_id": None,
            }
        )
    return output


@router.get("/changes/{change_id}")
def website_change_detail(change_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AutonomousResearchChange).where(
            AutonomousResearchChange.id == change_id,
            AutonomousResearchChange.owner_id == owner.id,
            AutonomousResearchChange.mission_id.in_(_website_mission_ids(db, owner)),
        )
    )
    if row is None:
        raise HTTPException(404, "Website change not found.")
    mission = db.get(AutonomousResearchMission, row.mission_id)
    scope = mission.scope if mission and isinstance(mission.scope, dict) else {}
    return {
        "id": str(row.id),
        "mission_id": str(row.mission_id),
        "t1": row.previous_value,
        "t2": row.current_value,
        "observation_lineage": {"evidence_ids": row.evidence_ids},
        "evidence_lineage": row.evidence_ids,
        "candidate": scope.get("candidate_id"),
        "source_profile": scope.get("url"),
        "field": row.field_key or row.change_type,
        "materiality": row.materiality,
        "reason": row.reason,
        "alert_linkage": None,
        "correlation_id": row.correlation_id,
        "created_at": row.created_at,
    }


WEBSITE_ALERT_TYPES = (
    "MATERIAL_MOQ_INCREASE",
    "MATERIAL_LEAD_TIME_INCREASE",
    "CERTIFICATION_REMOVED",
    "CERTIFICATION_EXPIRED",
    "BUSINESS_IDENTITY_CHANGED",
    "CRITICAL_CAPABILITY_REMOVED",
    "MATERIAL_FACILITY_CHANGED",
    "CRITICAL_PRODUCT_UNAVAILABLE",
    "HIGH_RISK_CONTRADICTION",
)


@router.get("/alerts")
def website_alert_list(
    db: DB,
    owner: Owner,
    alert_type: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, object]]:
    statement = (
        select(AutonomousResearchAlert)
        .where(
            AutonomousResearchAlert.owner_id == owner.id,
            AutonomousResearchAlert.mission_id.in_(_website_mission_ids(db, owner)),
        )
        .order_by(AutonomousResearchAlert.created_at.desc())
    )
    if alert_type:
        statement = statement.where(AutonomousResearchAlert.alert_type == alert_type)
    if severity:
        statement = statement.where(AutonomousResearchAlert.severity == severity)
    if acknowledged is not None:
        statement = statement.where(AutonomousResearchAlert.acknowledged == acknowledged)
    if correlation_id:
        statement = statement.where(
            AutonomousResearchAlert.lineage["correlation_id"].as_string() == correlation_id
        )
    rows = list(db.scalars(statement))
    output = []
    for row in rows:
        lineage = row.lineage if isinstance(row.lineage, dict) else {}
        output.append(
            {
                "id": str(row.id),
                "type": row.alert_type,
                "alert_type": row.alert_type,
                "severity": row.severity,
                "title": row.title,
                "detail": row.detail,
                "candidate": lineage.get("candidate_id"),
                "source_profile": lineage.get("source_profile"),
                "change_id": lineage.get("change_id"),
                "evidence_ids": lineage.get("evidence_ids", []),
                "acknowledged": row.acknowledged,
                "review_state": "ACKNOWLEDGED" if row.acknowledged else "OPEN",
                "created_at": row.created_at,
                "correlation_id": lineage.get("correlation_id"),
            }
        )
    return output


@router.get("/alerts/{alert_id}")
def website_alert_detail(alert_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AutonomousResearchAlert).where(
            AutonomousResearchAlert.id == alert_id,
            AutonomousResearchAlert.owner_id == owner.id,
            AutonomousResearchAlert.mission_id.in_(_website_mission_ids(db, owner)),
        )
    )
    if row is None:
        raise HTTPException(404, "Website alert not found.")
    lineage = row.lineage if isinstance(row.lineage, dict) else {}
    return {
        "id": str(row.id),
        "type": row.alert_type,
        "severity": row.severity,
        "title": row.title,
        "detail": row.detail,
        "candidate": lineage.get("candidate_id"),
        "source_profile": lineage.get("source_profile"),
        "change_id": lineage.get("change_id"),
        "evidence_ids": lineage.get("evidence_ids", []),
        "acknowledged": row.acknowledged,
        "review_state": "ACKNOWLEDGED" if row.acknowledged else "OPEN",
        "lineage": lineage,
        "correlation_id": lineage.get("correlation_id"),
        "created_at": row.created_at,
    }


@router.get("/reports")
def website_report_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    rows = db.scalars(
        select(AutonomousResearchReport, AutonomousResearchMission)
        .join(
            AutonomousResearchMission,
            AutonomousResearchMission.id == AutonomousResearchReport.mission_id,
        )
        .where(
            AutonomousResearchReport.owner_id == owner.id,
            AutonomousResearchMission.owner_id == owner.id,
            AutonomousResearchMission.mission_type.in_(
                {"MANUFACTURER_RESEARCH", "SUPPLIER_WEBSITE_RESEARCH", "SOURCE_REFRESH"}
            ),
        )
        .order_by(AutonomousResearchReport.created_at.desc())
    )
    return [
        {
            "id": str(report.id),
            "mission_id": str(report.mission_id),
            "run_id": str(report.mission_id),
            "candidate": (
                mission.scope.get("candidate_id") if isinstance(mission.scope, dict) else None
            ),
            "format": report.format.upper(),
            "created_at": report.created_at,
            "status": "AVAILABLE",
            "correlation_id": mission.correlation_id,
        }
        for report, mission in rows
    ]


@router.get("/reports/{report_id}")
def website_report_detail(report_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(AutonomousResearchReport).where(
            AutonomousResearchReport.id == report_id, AutonomousResearchReport.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Website intelligence report not found.")
    mission = db.scalar(
        select(AutonomousResearchMission).where(
            AutonomousResearchMission.id == row.mission_id,
            AutonomousResearchMission.owner_id == owner.id,
            AutonomousResearchMission.mission_type.in_(
                {"MANUFACTURER_RESEARCH", "SUPPLIER_WEBSITE_RESEARCH", "SOURCE_REFRESH"}
            ),
        )
    )
    if mission is None:
        raise HTTPException(404, "Website intelligence report not found.")
    content = html.escape(row.content) if row.format == "html" else row.content
    return {
        "id": str(row.id),
        "mission_id": str(row.mission_id),
        "format": row.format.upper(),
        "content": content,
        "safe_content": content,
        "provenance": row.provenance,
        "created_at": row.created_at,
        "status": "AVAILABLE",
        "correlation_id": mission.correlation_id,
    }


@router.get("/product-channel/{product_id}")
def website_product_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    from vayujit_api.products.models import Product

    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    missions = select(AutonomousResearchMission.id).where(
        AutonomousResearchMission.owner_id == owner.id,
        AutonomousResearchMission.product_id == product_id,
    )
    observations = list(
        db.scalars(
            select(WebsiteObservation).where(
                WebsiteObservation.owner_id == owner.id, WebsiteObservation.mission_id.in_(missions)
            )
        )
    )
    offerings = list(
        db.scalars(
            select(WebsiteOffering).where(
                WebsiteOffering.owner_id == owner.id, WebsiteOffering.product_id == product_id
            )
        )
    )
    candidates = list(
        db.scalars(select(ManufacturerCandidate).where(ManufacturerCandidate.owner_id == owner.id))
    )
    suppliers = list(
        db.scalars(
            select(SupplierWebsiteCandidate).where(SupplierWebsiteCandidate.owner_id == owner.id)
        )
    )
    changes = int(
        db.scalar(
            select(func.count())
            .select_from(AutonomousResearchChange)
            .where(
                AutonomousResearchChange.owner_id == owner.id,
                AutonomousResearchChange.mission_id.in_(missions),
                AutonomousResearchChange.material.is_(True),
            )
        )
        or 0
    )
    contradictions = int(
        db.scalar(
            select(func.count())
            .select_from(AutonomousResearchContradiction)
            .where(
                AutonomousResearchContradiction.owner_id == owner.id,
                AutonomousResearchContradiction.mission_id.in_(missions),
                AutonomousResearchContradiction.status != "RESOLVED",
            )
        )
        or 0
    )
    alerts = int(
        db.scalar(
            select(func.count())
            .select_from(AutonomousResearchAlert)
            .where(
                AutonomousResearchAlert.owner_id == owner.id,
                AutonomousResearchAlert.mission_id.in_(missions),
                AutonomousResearchAlert.acknowledged.is_(False),
            )
        )
        or 0
    )
    last = max((item.retrieved_at for item in observations), default=None)
    confidence = (
        round(sum(float(item.confidence) for item in observations) / len(observations), 4)
        if observations
        else 0
    )
    verification = (
        "VERIFIED"
        if observations and all(item.verification == "VERIFIED" for item in observations)
        else (observations[0].verification if observations else "UNKNOWN")
    )
    freshness = observations[0].freshness if observations else "UNKNOWN"
    risk = sorted({risk for item in candidates for risk in item.risk})
    profiles = list(
        db.scalars(
            select(WebsiteSourceProfile).where(
                WebsiteSourceProfile.owner_id == owner.id,
                WebsiteSourceProfile.archived_at.is_(None),
            )
        )
    )
    next_refresh = min(
        (item.next_refresh_at for item in profiles if item.next_refresh_at), default=None
    )
    return {
        "product_id": str(product_id),
        "website_research_status": "available" if observations else "not_started",
        "manufacturer_candidate_count": len(candidates),
        "supplier_website_candidate_count": len(suppliers),
        "offering_count": len(offerings),
        "last_website_research_at": last,
        "next_website_refresh_at": next_refresh,
        "freshness": freshness,
        "confidence": confidence,
        "risk": risk,
        "verification": verification,
        "material_change_count": changes,
        "open_contradiction_count": contradictions,
        "active_alert_count": alerts,
        "refresh_due": bool(next_refresh and next_refresh <= datetime.now(next_refresh.tzinfo)),
        "follow_up_required": bool(contradictions or alerts or freshness in {"STALE", "EXPIRED"}),
        "references": [{"type": "website_intelligence", "href": "/intelligence/websites"}],
    }


@router.get("/history")
def history(
    db: DB,
    owner: Owner,
    candidate_id: uuid.UUID | None = None,
    event_type: str | None = None,
    source: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, object]]:
    statement = (
        select(WebsiteObservation)
        .where(WebsiteObservation.owner_id == owner.id)
        .order_by(WebsiteObservation.created_at)
    )
    if candidate_id:
        statement = statement.where(WebsiteObservation.candidate_id == candidate_id)
    if event_type:
        statement = statement.where(
            or_(
                WebsiteObservation.observation_type == event_type,
                WebsiteObservation.claim_type == event_type,
            )
        )
    if source:
        statement = statement.where(
            or_(WebsiteObservation.domain == source, WebsiteObservation.page_url.contains(source))
        )
    if date_from:
        statement = statement.where(WebsiteObservation.created_at >= date_from)
    if date_to:
        statement = statement.where(WebsiteObservation.created_at <= date_to)
    if correlation_id:
        statement = statement.where(WebsiteObservation.correlation_id == correlation_id)
    return [
        {
            "id": str(item.id),
            "mission_id": str(item.mission_id) if item.mission_id else None,
            "type": item.observation_type,
            "event_type": item.observation_type,
            "claim_type": item.claim_type,
            "value": item.normalized_value,
            "domain": item.domain,
            "page_url": item.page_url,
            "verification": item.verification,
            "freshness": item.freshness,
            "confidence": float(item.confidence),
            "content_hash": item.content_hash,
            "previous_observation_id": (
                str(item.previous_observation_id) if item.previous_observation_id else None
            ),
            "retrieved_at": item.retrieved_at,
            "created_at": item.created_at,
            "correlation_id": item.correlation_id,
        }
        for item in db.scalars(statement)
    ]


@router.get("/reports/mission/{mission_id}")
def website_report(
    mission_id: uuid.UUID,
    db: DB,
    owner: Owner,
    format: Literal["json", "markdown", "html"] = "json",
) -> dict[str, object]:
    mission = db.scalar(
        select(AutonomousResearchMission).where(
            AutonomousResearchMission.id == mission_id,
            AutonomousResearchMission.owner_id == owner.id,
        )
    )
    if mission is None:
        raise HTTPException(404, "Website intelligence mission not found.")
    row = mission_report(db, owner, mission, format)
    return {
        "id": str(row.id),
        "mission_id": str(row.mission_id),
        "format": row.format,
        "content": row.content,
        "provenance": row.provenance,
        "created_at": row.created_at,
    }


@router.post("/profiles/{profile_id}/refresh/schedule")
def refresh_schedule(
    profile_id: uuid.UUID, data: WebsiteRefreshScheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    profile = db.scalar(
        select(WebsiteSourceProfile).where(
            WebsiteSourceProfile.id == profile_id, WebsiteSourceProfile.owner_id == owner.id
        )
    )
    if profile is None:
        raise HTTPException(404, "Website source profile not found.")
    if data.target_type not in {
        "WEBSITE_SOURCE",
        "MANUFACTURER_CANDIDATE",
        "SUPPLIER_WEBSITE_CANDIDATE",
        "CERTIFICATION_REVIEW",
        "PRICE_RECHECK",
        "MOQ_RECHECK",
        "LEAD_TIME_RECHECK",
        "AVAILABILITY_RECHECK",
    }:
        raise HTTPException(422, "Unsupported website refresh target type.")
    profile = schedule_profile_refresh(
        db,
        owner,
        profile,
        policy=data.policy,
        timezone=data.timezone,
        next_refresh_at=data.next_refresh_at,
        target_type=data.target_type,
    )
    return {
        "id": str(profile.id),
        "policy": profile.freshness_policy,
        "timezone": profile.timezone,
        "next_refresh_at": profile.next_refresh_at,
        "status": "scheduled" if profile.next_refresh_at else "manual",
    }


@router.post("/refresh/materialize-due")
def refresh_materialize_due(
    db: DB, owner: Owner, limit: int = Query(default=50, ge=1, le=100)
) -> dict[str, object]:
    jobs = materialize_due_refreshes(db, owner, limit=limit)
    return {"materialized": len(jobs), "job_ids": [str(job.id) for job in jobs]}


@router.get("/refresh/jobs")
def refresh_jobs(db: DB, owner: Owner) -> list[dict[str, object]]:
    rows = db.scalars(
        select(WebsiteRefreshJob)
        .where(WebsiteRefreshJob.owner_id == owner.id)
        .order_by(WebsiteRefreshJob.scheduled_for.desc())
    )
    return [
        {
            "id": str(row.id),
            "source_profile_id": str(row.source_profile_id),
            "target_type": row.target_type,
            "scheduled_for": row.scheduled_for,
            "status": row.status,
            "failure_code": row.failure_code,
            "mission_id": str(row.mission_id) if row.mission_id else None,
        }
        for row in rows
    ]


@router.post("/refresh/jobs/{job_id}/run")
def refresh_run(
    job_id: uuid.UUID, data: WebsiteRefreshExecuteRequest, db: DB, owner: Owner
) -> dict[str, object]:
    job = db.scalar(
        select(WebsiteRefreshJob).where(
            WebsiteRefreshJob.id == job_id, WebsiteRefreshJob.owner_id == owner.id
        )
    )
    if job is None:
        raise HTTPException(404, "Website refresh job not found.")
    row = execute_refresh_job(db, owner, job, content=data.content)
    return {
        "id": str(row.id),
        "status": row.status,
        "mission_id": str(row.mission_id) if row.mission_id else None,
        "failure_code": row.failure_code,
    }


@router.get("/calendar")
def website_calendar(db: DB, owner: Owner) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(WebsiteSourceProfile).where(
                WebsiteSourceProfile.owner_id == owner.id,
                WebsiteSourceProfile.archived_at.is_(None),
            )
        )
    )
    events: list[dict[str, object]] = []
    for row in rows:
        if row.next_refresh_at is None:
            continue
        events.append(
            {
                "id": str(row.id),
                "type": (
                    "WEBSITE_SOURCE_REFRESH_DUE"
                    if row.refresh_target_type == "WEBSITE_SOURCE"
                    else f"{row.refresh_target_type}_DUE"
                ),
                "target_type": row.refresh_target_type,
                "source_profile_id": str(row.id),
                "domain": row.domain,
                "frequency": row.freshness_policy,
                "scheduled_at": row.next_refresh_at,
                "timezone": row.timezone,
                "correlation_id": None,
                "status": "scheduled" if row.enabled else "disabled",
            }
        )
    return events


@router.get("/refresh/recovery/catalog")
def refresh_recovery_catalog() -> dict[str, object]:
    return {
        "failure_codes": sorted(REFRESH_RECOVERY_FAILURES),
        "actions": sorted(
            {action for actions in REFRESH_RECOVERY_FAILURES.values() for action in actions}
        ),
        "mapping": {key: sorted(value) for key, value in REFRESH_RECOVERY_FAILURES.items()},
    }


@router.post("/refresh/jobs/{job_id}/recover")
def refresh_recover(
    job_id: uuid.UUID, payload: dict[str, object], db: DB, owner: Owner
) -> dict[str, object]:
    job = db.scalar(
        select(WebsiteRefreshJob).where(
            WebsiteRefreshJob.id == job_id, WebsiteRefreshJob.owner_id == owner.id
        )
    )
    if job is None:
        raise HTTPException(404, "Website refresh job not found.")
    action = str(payload.get("action", ""))
    failure_code = str(payload.get("failure_code", job.failure_code or ""))
    idempotency_key = str(payload.get("idempotency_key") or f"{action}:{job.id}:{failure_code}")
    correlation_id = str(payload.get("correlation_id") or job.correlation_id)
    return recover_refresh_job(
        db,
        owner,
        job,
        action=action,
        failure_code=failure_code,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
