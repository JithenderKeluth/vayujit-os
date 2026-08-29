# mypy: ignore-errors
"""Persistence services for bounded website intelligence."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission
from vayujit_api.intelligence.autonomous_schemas import AutonomousMissionCreate
from vayujit_api.intelligence.autonomous_service import (
    create_mission,
    execute_mission,
    record_change,
)
from vayujit_api.intelligence.website_intelligence import (
    WEBSITE_SOURCE_TYPES,
    extract_website_intelligence,
    normalize_domain,
    normalize_identity,
)
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteClaim,
    WebsiteObservation,
    WebsiteOffering,
    WebsiteSourceProfile,
    WebsiteSourceProfileVersion,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _logical_lock(db: Session, identity: str) -> None:
    """Serialize same-key website writes when running on PostgreSQL."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
            {"identity": identity},
        )


def _audit(db: Session, owner: User, action: str, entity_id: uuid.UUID, identity: str) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type="website_intelligence",
        entity_id=entity_id,
        metadata={"bounded": True, "read_only_source": True},
        idempotency_key=f"website:{action}:{identity}",
    )


def profile_identity(domain: str, source_type: str) -> str:
    return f"{normalize_domain(domain)}:{source_type}"


def get_or_create_profile(
    db: Session, owner: User, domain: str, source_type: str
) -> WebsiteSourceProfile:
    logical = profile_identity(domain, source_type)
    _logical_lock(db, f"website-profile:{owner.id}:{logical}")
    row = db.scalar(
        select(WebsiteSourceProfile).where(
            WebsiteSourceProfile.owner_id == owner.id,
            WebsiteSourceProfile.logical_identity == logical,
        )
    )
    if row is not None:
        return row
    stamp = _now()
    row = WebsiteSourceProfile(
        owner_id=owner.id,
        domain=normalize_domain(domain),
        display_name=normalize_domain(domain),
        source_type=source_type,
        logical_identity=logical,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    db.add(
        WebsiteSourceProfileVersion(
            owner_id=owner.id,
            profile_id=row.id,
            version=1,
            rules={"fetch": "single_page", "search_allowed": False},
            created_at=stamp,
        )
    )
    _audit(db, owner, "website.profile.created", row.id, logical)
    return row


def persist_extraction(
    db: Session,
    owner: User,
    result: dict[str, object],
    *,
    mission_id: uuid.UUID | None = None,
    profile: WebsiteSourceProfile | None = None,
    supplier_id: uuid.UUID | None = None,
) -> dict[str, object]:
    domain = str(result.get("domain", ""))
    source_type = str(result.get("source_type", "SUPPLIER_WEBSITE"))
    _logical_lock(db, f"website-extraction:{owner.id}:{profile_identity(domain, source_type)}")
    profile = profile or get_or_create_profile(db, owner, domain, source_type)
    raw_identity = result.get("business_identity", {})
    identity = raw_identity if isinstance(raw_identity, dict) else {}
    name = str(identity.get("name") or domain or "Unknown website")
    candidate_key = f"{normalize_identity(name, domain)}:{domain}"
    candidate = db.scalar(
        select(ManufacturerCandidate).where(
            ManufacturerCandidate.owner_id == owner.id,
            ManufacturerCandidate.logical_identity == candidate_key,
        )
    )
    if candidate is None:
        risks = result.get("risk_signals", [])
        risks = risks if isinstance(risks, list) else []
        candidate = ManufacturerCandidate(
            owner_id=owner.id,
            name=name,
            normalized_name=normalize_identity(name),
            website=str(result.get("source_reference", "")),
            canonical_domain=domain,
            manufacturer_status="claimed",
            verification_state="UNVERIFIED",
            freshness=str(result.get("freshness", "UNKNOWN")),
            confidence=float(result.get("confidence", 0) or 0),
            risk=[str(item) for item in risks],
            source_count=1,
            evidence_count=1,
            logical_identity=candidate_key,
            current_status="REVIEW_REQUIRED",
            last_researched_at=_now(),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(candidate)
        db.flush()
        _audit(db, owner, "website.manufacturer_candidate.created", candidate.id, candidate_key)
    else:
        candidate.last_researched_at = _now()
        candidate.updated_at = _now()
        candidate.source_count = max(candidate.source_count, 1)
        candidate.evidence_count += 1
    if source_type == "SUPPLIER_WEBSITE":
        supplier_key = f"{domain}:{supplier_id or candidate.id}"
        supplier_row = db.scalar(
            select(SupplierWebsiteCandidate).where(
                SupplierWebsiteCandidate.owner_id == owner.id,
                SupplierWebsiteCandidate.logical_identity == supplier_key,
            )
        )
        if supplier_row is None:
            risks = result.get("risk_signals", [])
            risks = risks if isinstance(risks, list) else []
            supplier_row = SupplierWebsiteCandidate(
                owner_id=owner.id,
                supplier_id=supplier_id,
                manufacturer_candidate_id=candidate.id,
                domain=domain,
                source_profile_id=profile.id,
                identity_state="SOURCE_PROVIDED",
                match_state="REVIEW_REQUIRED",
                confidence=float(result.get("confidence", 0) or 0),
                verification_state="UNVERIFIED",
                freshness=str(result.get("freshness", "UNKNOWN")),
                risk=[str(item) for item in risks],
                last_researched_at=_now(),
                lineage={"mission_id": str(mission_id) if mission_id else None},
                logical_identity=supplier_key,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(supplier_row)
            db.flush()
    observations: list[WebsiteObservation] = []
    values: list[tuple[str, str, object]] = [
        ("BUSINESS_IDENTITY", "identity", identity),
        ("CONTACT", "contact", result.get("contacts", {})),
        ("RISK", "risk", result.get("risk_signals", [])),
    ]
    terms = result.get("commercial_terms", {})
    if isinstance(terms, dict):
        values.extend((key.upper(), key, terms.get(key)) for key in terms)
    values.append(("PRODUCT", "products", result.get("products", [])))
    values.append(("CAPABILITY", "capability", result.get("capabilities", [])))
    values.append(("FACILITY", "facility", result.get("facilities", [])))
    values.append(("CERTIFICATION", "certification", result.get("certifications", [])))
    values.append(
        (
            "AVAILABILITY",
            "availability",
            (terms.get("availability") if isinstance(terms, dict) else None),
        )
    )
    for observation_type, claim_type, value in values:
        canonical = json.dumps(value, sort_keys=True, default=str)
        identity_key = (
            f"{candidate.id}:{observation_type}:{hashlib.sha256(canonical.encode()).hexdigest()}"
        )
        existing = db.scalar(
            select(WebsiteObservation).where(
                WebsiteObservation.owner_id == owner.id,
                WebsiteObservation.observation_identity == identity_key,
            )
        )
        if existing is not None:
            observations.append(existing)
            continue
        previous = db.scalar(
            select(WebsiteObservation)
            .where(
                WebsiteObservation.owner_id == owner.id,
                WebsiteObservation.candidate_id == candidate.id,
                WebsiteObservation.observation_type == observation_type,
            )
            .order_by(WebsiteObservation.created_at.desc())
        )
        row = WebsiteObservation(
            owner_id=owner.id,
            mission_id=mission_id,
            source_profile_id=profile.id,
            candidate_id=candidate.id,
            domain=domain,
            page_url=str(result.get("source_reference", "")),
            observation_type=observation_type,
            claim_type=claim_type,
            normalized_value={"value": value} if not isinstance(value, dict) else value,
            verification=str(result.get("verification_state", "UNVERIFIED")),
            freshness=str(result.get("freshness", "UNKNOWN")),
            confidence=float(result.get("confidence", 0) or 0),
            content_hash=str(result.get("content_hash", "")),
            evidence_ids=[str(result.get("content_hash", ""))],
            previous_observation_id=previous.id if previous else None,
            correlation_id=str(mission_id or ""),
            observation_identity=identity_key,
            retrieved_at=_now(),
            created_at=_now(),
        )
        db.add(row)
        db.flush()
        observations.append(row)
    if mission_id is not None:
        mission = db.get(AutonomousResearchMission, mission_id)
        if mission is not None:
            for observation in observations:
                if observation.previous_observation_id is None:
                    continue
                previous = db.get(WebsiteObservation, observation.previous_observation_id)
                if previous is None or previous.verification in {"REJECTED", "UNVERIFIED"}:
                    continue
                change_type = {
                    "AVAILABILITY": "product_availability",
                    "BUSINESS_IDENTITY": "identity",
                }.get(observation.observation_type, observation.observation_type.lower())
                record_change(
                    db,
                    owner,
                    mission,
                    change_type=change_type,
                    previous={"value": previous.normalized_value},
                    current={"value": observation.normalized_value},
                    evidence_ids=list(observation.evidence_ids or []),
                )

    offering_rows: list[WebsiteOffering] = []
    products = result.get("products", [])
    if isinstance(products, list):
        for item in products:
            title = str(item)
            key = f"{candidate.id}:{normalize_identity(title)}"
            offering = db.scalar(
                select(WebsiteOffering).where(
                    WebsiteOffering.owner_id == owner.id, WebsiteOffering.logical_identity == key
                )
            )
            if offering is None:
                offering = WebsiteOffering(
                    owner_id=owner.id,
                    candidate_id=candidate.id,
                    source_profile_id=profile.id,
                    observation_ids=[],
                    correlation_id=str(mission_id or ""),
                    research_candidate_id=None,
                    source_name=title,
                    description=title,
                    details={"source_type": source_type},
                    logical_identity=key,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(offering)
                db.flush()
            offering.source_profile_id = profile.id
            offering.observation_ids = [str(item.id) for item in observations]
            offering.correlation_id = str(mission_id or "")
            offering_rows.append(offering)
    capabilities = result.get("capabilities", [])
    if isinstance(capabilities, list):
        for capability in capabilities:
            cap = str(capability)
            key = f"{candidate.id}:{cap}"
            exists = db.scalar(
                select(WebsiteClaim).where(
                    WebsiteClaim.owner_id == owner.id,
                    WebsiteClaim.candidate_id == candidate.id,
                    WebsiteClaim.claim_type == "CAPABILITY",
                    WebsiteClaim.claim_identity == key,
                )
            )
            if exists is None:
                db.add(
                    WebsiteClaim(
                        owner_id=owner.id,
                        candidate_id=candidate.id,
                        claim_type="CAPABILITY",
                        claim_identity=key,
                        claim_value={"capability": cap},
                        status="CLAIMED",
                        evidence_ids=[str(result.get("content_hash", ""))],
                        observed_at=_now(),
                    )
                )
    active_capabilities = (
        {str(item) for item in capabilities} if isinstance(capabilities, list) else set()
    )
    for prior in db.scalars(
        select(WebsiteClaim).where(
            WebsiteClaim.owner_id == owner.id,
            WebsiteClaim.candidate_id == candidate.id,
            WebsiteClaim.claim_type == "CAPABILITY",
        )
    ):
        prior_name = str((prior.claim_value or {}).get("capability", ""))
        if prior_name and prior_name not in active_capabilities:
            prior.status = "NO_LONGER_OBSERVED"
            prior.last_seen = _now()

    facilities = result.get("facilities", [])
    if isinstance(facilities, list):
        for facility in facilities:
            item = facility if isinstance(facility, dict) else {"type": str(facility)}
            facility_type = str(item.get("type", "UNKNOWN"))
            key = f"{candidate.id}:{facility_type}"
            claim = db.scalar(
                select(WebsiteClaim).where(
                    WebsiteClaim.owner_id == owner.id,
                    WebsiteClaim.candidate_id == candidate.id,
                    WebsiteClaim.claim_type == "FACILITY",
                    WebsiteClaim.claim_identity == key,
                )
            )
            if claim is None:
                db.add(
                    WebsiteClaim(
                        owner_id=owner.id,
                        candidate_id=candidate.id,
                        claim_type="FACILITY",
                        claim_identity=key,
                        claim_value=dict(item),
                        status="CLAIMED",
                        evidence_ids=[str(result.get("content_hash", ""))],
                        source_reference=str(result.get("source_reference", "")),
                        freshness=str(result.get("freshness", "UNKNOWN")),
                        confidence=float(result.get("confidence", 0) or 0),
                        first_seen=_now(),
                        last_seen=_now(),
                        observed_at=_now(),
                    )
                )
            else:
                claim.claim_value = dict(item)
                claim.last_seen = _now()

    certifications = result.get("certifications", [])
    if isinstance(certifications, list):
        for cert in certifications:
            cert_map = cert if isinstance(cert, dict) else {"name": str(cert)}
            cert_name = str(cert_map.get("name", "unknown"))
            key = f"{candidate.id}:{cert_name}"
            exists = db.scalar(
                select(WebsiteClaim).where(
                    WebsiteClaim.owner_id == owner.id,
                    WebsiteClaim.candidate_id == candidate.id,
                    WebsiteClaim.claim_type == "CERTIFICATION",
                    WebsiteClaim.claim_identity == key,
                )
            )
            if exists is None:
                db.add(
                    WebsiteClaim(
                        owner_id=owner.id,
                        candidate_id=candidate.id,
                        claim_type="CERTIFICATION",
                        claim_identity=key,
                        claim_value=cert_map,
                        status=str(cert_map.get("state", "CLAIMED")),
                        evidence_ids=[str(result.get("content_hash", ""))],
                        observed_at=_now(),
                    )
                )
    active_certifications = (
        {
            str((item or {}).get("name", "unknown"))
            for item in certifications
            if isinstance(item, dict)
        }
        if isinstance(certifications, list)
        else set()
    )
    for prior in db.scalars(
        select(WebsiteClaim).where(
            WebsiteClaim.owner_id == owner.id,
            WebsiteClaim.candidate_id == candidate.id,
            WebsiteClaim.claim_type == "CERTIFICATION",
        )
    ):
        prior_name = prior.claim_identity.rsplit(":", 1)[-1]
        if prior_name not in active_certifications:
            prior.status = "NO_LONGER_OBSERVED"
            prior.last_seen = _now()

    return {
        "candidate": candidate,
        "profile": profile,
        "observations": observations,
        "offerings": offering_rows,
    }


def run_website_mission(
    db: Session,
    owner: User,
    *,
    url: str,
    content: str,
    source_type: str,
    idempotency_key: str,
    supplier_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
) -> dict[str, object]:
    if source_type not in WEBSITE_SOURCE_TYPES:
        raise HTTPException(422, "Unsupported website source type.")
    profile = get_or_create_profile(db, owner, url, source_type)
    mission = create_mission(
        db,
        owner,
        AutonomousMissionCreate(
            mission_type=(
                "MANUFACTURER_RESEARCH"
                if source_type == "MANUFACTURER_WEBSITE"
                else "SUPPLIER_WEBSITE_RESEARCH"
            ),
            goal=f"Bounded website research for {normalize_domain(url)}",
            scope={"url": url, "source_type": source_type, "single_page": True},
            supplier_id=supplier_id,
            product_id=product_id,
            idempotency_key=idempotency_key,
        ),
    )
    result = extract_website_intelligence(url=url, text=content, source_type=source_type)
    persisted = persist_extraction(
        db, owner, result, mission_id=mission.id, profile=profile, supplier_id=supplier_id
    )
    execution = execute_mission(db, owner, mission)
    db.commit()
    return {
        "mission_id": str(mission.id),
        "execution": execution,
        "candidate_id": str(persisted["candidate"].id),
        "offering_count": len(persisted["offerings"]),
        "observation_count": len(persisted["observations"]),
        "read_only": True,
    }


def integrity_counts(db: Session, owner: User) -> dict[str, int]:
    models = {
        "profiles": WebsiteSourceProfile,
        "manufacturer_candidates": ManufacturerCandidate,
        "supplier_website_candidates": SupplierWebsiteCandidate,
        "observations": WebsiteObservation,
        "offerings": WebsiteOffering,
        "claims": WebsiteClaim,
    }
    return {
        name: int(
            db.scalar(select(func.count()).select_from(model).where(model.owner_id == owner.id))
            or 0
        )
        for name, model in models.items()
    }
