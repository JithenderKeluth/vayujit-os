from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCapability,
    SupplierCertificationClaim,
    SupplierCommercialTerm,
    SupplierContact,
    SupplierDecision,
    SupplierDocumentReference,
    SupplierEvidence,
    SupplierHistoryEvent,
    SupplierOpportunityMatch,
    SupplierProduct,
    SupplierRecoveryRecord,
    SupplierRiskAssessment,
    SupplierScoreEvaluation,
    SupplierSearch,
    SupplierSource,
    SupplierVerification,
)
from vayujit_api.intelligence.supplier_schemas import (
    SupplierCertificationClaimCreate,
    SupplierCommercialTermCreate,
    SupplierComparisonRequest,
    SupplierContactCreate,
    SupplierContactUpdate,
    SupplierDecisionRequest,
    SupplierDocumentReferenceCreate,
    SupplierManualCreate,
    SupplierRecoveryRequest,
    SupplierScoreCreate,
    SupplierSearchCreate,
    SupplierVerificationRequest,
)


def now() -> datetime:
    return datetime.now(UTC)


def _correlation() -> str:
    return uuid.uuid4().hex


def _advisory_lock(db: Session, value: str) -> None:
    key = int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big") & ((1 << 63) - 1)
    db.execute(select(func.pg_advisory_xact_lock(key)))


def _event(db: Session, user: User, action: str, entity: Supplier | SupplierSearch) -> None:
    record_event(
        db, actor_id=user.id, action=action, entity_type=entity.__tablename__, entity_id=entity.id
    )


def _identity(
    name: str, country_code: str | None, website: str | None, business_identifier: str | None = None
) -> str:
    value = "|".join(
        (
            name.casefold().strip(),
            (country_code or "").upper(),
            (website or "").casefold().strip(),
            business_identifier or "",
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _fixtures() -> list[dict[str, Any]]:
    return [
        {
            "name": "LOCAL FIXTURE Ã¢â‚¬â€ Pune Craft Labs",
            "type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "city": "Pune",
            "source": "manufacturer_website",
            "price": 420,
            "currency": "INR",
            "moq": 50,
            "lead": 14,
            "private_label": True,
            "customization": True,
            "verification": "partially_verified",
            "score": 88,
            "risk": {"identity": 10, "commercial": 12, "delivery": 15},
            "claims": ["ISO 9001"],
        },
        {
            "name": "LOCAL FIXTURE Ã¢â‚¬â€ Shenzhen Value Trader",
            "type": "trader",
            "country_code": "CN",
            "country": "China",
            "city": "Shenzhen",
            "source": "alibaba",
            "price": 3.2,
            "currency": "USD",
            "moq": 5000,
            "lead": 60,
            "private_label": True,
            "customization": False,
            "verification": "unverified",
            "score": 48,
            "risk": {"identity": 65, "commercial": 72, "delivery": 60},
            "claims": [],
        },
        {
            "name": "LOCAL FIXTURE Ã¢â‚¬â€ Jaipur Offline Wholesale",
            "type": "wholesaler",
            "country_code": "IN",
            "country": "India",
            "city": "Jaipur",
            "source": "offline_market",
            "price": 510,
            "currency": "INR",
            "moq": 20,
            "lead": 10,
            "private_label": False,
            "customization": False,
            "verification": "self_reported",
            "score": 71,
            "risk": {"identity": 30, "commercial": 24, "delivery": 18},
            "claims": [],
        },
        {
            "name": "LOCAL FIXTURE Ã¢â‚¬â€ Trade Fair Components Co.",
            "type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "city": "New Delhi",
            "source": "trade_fair",
            "price": 465,
            "currency": "INR",
            "moq": 100,
            "lead": 28,
            "private_label": True,
            "customization": True,
            "verification": "unverified",
            "score": 76,
            "risk": {"identity": 35, "commercial": 28, "delivery": 30},
            "claims": ["BIS"],
        },
        {
            "name": "LOCAL FIXTURE Ã¢â‚¬â€ Referral Home Goods",
            "type": "distributor",
            "country_code": "IN",
            "country": "India",
            "city": "Bengaluru",
            "source": "referral",
            "price": None,
            "currency": "INR",
            "moq": None,
            "lead": None,
            "private_label": False,
            "customization": False,
            "verification": "unverified",
            "score": 34,
            "risk": {"identity": 55, "commercial": 50, "delivery": 50},
            "claims": [],
        },
    ]


def _score_dimensions(
    item: dict[str, Any], requirements: dict[str, Any]
) -> tuple[dict[str, Any], float, str]:
    target_moq = float(requirements.get("moq_max", 10_000))
    max_lead = float(requirements.get("lead_time_max_days", 180))
    required_private = bool(requirements.get("private_label", False))
    moq_score = 100 if item["moq"] is not None and item["moq"] <= target_moq else 30
    lead_score = 100 if item["lead"] is not None and item["lead"] <= max_lead else 25
    capability_score = 100 if not required_private or item["private_label"] else 20
    verification_score = {
        "high_confidence": 100,
        "verified": 90,
        "partially_verified": 70,
        "self_reported": 45,
        "unverified": 20,
    }.get(item["verification"], 10)
    risk_score = max(0, 100 - max(item["risk"].values()))
    dimensions: dict[str, dict[str, object]] = {
        "product_match": {
            "score": 85,
            "weight": 20,
            "reason": "Fixture category and offering match requirement.",
        },
        "commercial_competitiveness": {
            "score": 80 if item["price"] else 30,
            "weight": 15,
            "reason": "Source price is preserved in source currency.",
        },
        "moq_flexibility": {
            "score": moq_score,
            "weight": 10,
            "reason": "Compared with configured maximum MOQ.",
        },
        "lead_time": {
            "score": lead_score,
            "weight": 10,
            "reason": "Compared with configured maximum lead time.",
        },
        "capability": {
            "score": capability_score,
            "weight": 10,
            "reason": "Private-label requirement evaluated deterministically.",
        },
        "verification": {
            "score": verification_score,
            "weight": 10,
            "reason": "Verification state is never escalated automatically.",
        },
        "quality_evidence": {
            "score": 70 if item["claims"] else 40,
            "weight": 5,
            "reason": "Only fixture evidence is available.",
        },
        "communication": {
            "score": 60,
            "weight": 5,
            "reason": "Contact channel is not automatically contacted.",
        },
        "logistics": {
            "score": lead_score,
            "weight": 5,
            "reason": "Local deterministic lead-time evidence.",
        },
        "risk": {
            "score": risk_score,
            "weight": 10,
            "reason": "Higher deterministic warning signals reduce score.",
        },
    }
    score_total = 0.0
    for value in dimensions.values():
        score_total += float(cast(Any, value["score"])) * float(cast(Any, value["weight"]))
    score = round(score_total / 100, 2)
    if max(item["risk"].values()) >= 80:
        recommendation = "blocked"
    elif score >= 80:
        recommendation = "strong_match"
    elif score >= 65:
        recommendation = "promising"
    elif score >= 45:
        recommendation = "review_required"
    else:
        recommendation = "insufficient_evidence"
    return dimensions, score, recommendation


def _safe_supplier(db: Session, user: User, supplier_id: uuid.UUID) -> Supplier:
    supplier = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.owner_id == user.id)
    )
    if supplier is None:
        raise HTTPException(404, "Supplier not found.")
    return supplier


def _supplier_payload(db: Session, supplier: Supplier) -> dict[str, Any]:
    score = db.scalar(
        select(SupplierScoreEvaluation)
        .where(SupplierScoreEvaluation.supplier_id == supplier.id)
        .order_by(SupplierScoreEvaluation.created_at.desc())
    )
    risk = db.scalar(
        select(SupplierRiskAssessment)
        .where(SupplierRiskAssessment.supplier_id == supplier.id)
        .order_by(SupplierRiskAssessment.created_at.desc())
    )
    return {
        "id": supplier.id,
        "owner_id": supplier.owner_id,
        "display_name": supplier.display_name,
        "legal_name": supplier.legal_name,
        "supplier_type": supplier.supplier_type,
        "country_code": supplier.country_code,
        "country": supplier.country,
        "region": supplier.region,
        "city": supplier.city,
        "address": supplier.address,
        "website": supplier.website,
        "normalized_domain": supplier.normalized_domain,
        "business_identifier": supplier.business_identifier,
        "source_identity": supplier.source_identity,
        "normalized_identity": supplier.normalized_identity,
        "is_offline": supplier.is_offline,
        "verification_state": supplier.verification_state,
        "communication_status": supplier.communication_status,
        "created_at": supplier.created_at,
        "updated_at": supplier.updated_at,
        "score": float(score.final_score) if score else None,
        "recommendation": score.recommendation if score else None,
        "risk": risk.dimensions if risk else {},
        "offering_count": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierProduct)
                .where(SupplierProduct.supplier_id == supplier.id)
            )
            or 0
        ),
        "evidence_count": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierEvidence)
                .where(SupplierEvidence.supplier_id == supplier.id)
            )
            or 0
        ),
        "shortlist_state": db.scalar(
            select(SupplierDecision.decision)
            .where(SupplierDecision.supplier_id == supplier.id)
            .order_by(SupplierDecision.created_at.desc())
        ),
    }


def create_manual_supplier(db: Session, user: User, data: SupplierManualCreate) -> Supplier:
    identity = _identity(data.display_name, data.country_code, data.website)
    _advisory_lock(db, f"supplier:{user.id}:{identity}")
    duplicate = db.scalar(
        select(Supplier).where(
            Supplier.owner_id == user.id, Supplier.normalized_identity == identity
        )
    )
    if duplicate:
        cast(Any, duplicate).idempotent_reuse = True
        return duplicate
    stamp = now()
    supplier = Supplier(
        owner_id=user.id,
        display_name=data.display_name,
        legal_name=data.legal_name,
        supplier_type=data.supplier_type,
        country_code=data.country_code.upper(),
        country=data.country,
        region=data.region,
        city=data.city,
        address=data.address,
        website=data.website,
        normalized_domain=data.website,
        source_identity=data.provenance,
        normalized_identity=identity,
        is_offline=True,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(supplier)
    db.flush()
    source = SupplierSource(
        owner_id=user.id,
        supplier_id=supplier.id,
        source_type=data.source_type,
        access_mode="offline" if data.source_type != "manual_entry" else "manual_entry",
        reference=data.provenance,
        status="manual_entry",
        observed_at=stamp,
        created_at=stamp,
    )
    db.flush()
    evidence = SupplierEvidence(
        owner_id=user.id,
        supplier_id=supplier.id,
        source_id=source.id,
        evidence_kind="manual",
        reference=data.provenance,
        normalized_value={"notes": data.notes},
        excerpt=data.notes,
        content_hash=hashlib.sha256(data.provenance.encode()).hexdigest(),
        observed_at=stamp,
        retrieved_at=stamp,
        updated_at=stamp,
        idempotency_key=f"manual:{supplier.id}",
    )
    db.add_all([source, evidence])
    db.flush()
    _event(db, user, "supplier_created", supplier)
    return supplier


def create_search(db: Session, user: User, data: SupplierSearchCreate) -> SupplierSearch:
    if data.opportunity_id:
        opportunity = db.scalar(
            select(IntelligenceOpportunity).where(
                IntelligenceOpportunity.id == data.opportunity_id,
                IntelligenceOpportunity.owner_id == user.id,
            )
        )
        if opportunity is None:
            raise HTTPException(404, "Opportunity not found.")
    key = (
        data.idempotency_key
        or hashlib.sha256(
            f"{user.id}:{data.opportunity_id}:{data.product_id}:{data.requirements}".encode()
        ).hexdigest()
    )
    _advisory_lock(db, f"search:{user.id}:{key}")
    prior = db.scalar(
        select(SupplierSearch).where(
            SupplierSearch.owner_id == user.id, SupplierSearch.idempotency_key == key
        )
    )
    if prior:
        return prior
    stamp = now()
    search = SupplierSearch(
        owner_id=user.id,
        opportunity_id=data.opportunity_id,
        product_id=data.product_id,
        requirements=data.requirements,
        source_policy=data.source_policy,
        ruleset_version=data.ruleset_version,
        correlation_id=_correlation(),
        status="pending",
        idempotency_key=key,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(search)
    db.flush()
    _event(db, user, "supplier_search_created", search)
    return search


def execute_search(db: Session, user: User, search: SupplierSearch) -> SupplierSearch:
    if search.owner_id != user.id:
        raise HTTPException(404, "Supplier search not found.")
    _advisory_lock(db, f"execute-search:{search.id}")
    db.refresh(search)
    if search.status == "completed":
        return search
    if search.provider_execution_id is None:
        search.provider_execution_id = f"supplier-provider:{search.id}"
    search.checkpoint_state = {
        **(search.checkpoint_state or {}),
        "provider_execution_id": search.provider_execution_id,
    }
    stamp = now()
    search.status = "running"
    search.started_at = stamp
    fixtures = _fixtures()
    supplier_count = 0
    for item in fixtures:
        identity = _identity(item["name"], item["country_code"], item["source"])
        supplier = db.scalar(
            select(Supplier).where(
                Supplier.owner_id == user.id, Supplier.normalized_identity == identity
            )
        )
        if supplier is None:
            supplier = Supplier(
                owner_id=user.id,
                display_name=item["name"],
                legal_name=None,
                supplier_type=item["type"],
                country_code=item["country_code"],
                country=item["country"],
                city=item["city"],
                source_identity=item["source"],
                normalized_identity=identity,
                is_offline=item["source"] in {"offline_market", "trade_fair", "referral"},
                verification_state=item["verification"],
                communication_status="not_contacted",
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(supplier)
            db.flush()
        source = db.scalar(
            select(SupplierSource).where(
                SupplierSource.supplier_id == supplier.id,
                SupplierSource.source_type == item["source"],
                SupplierSource.external_id == f"fixture:{item['source']}",
            )
        )
        if source is None:
            source = SupplierSource(
                owner_id=user.id,
                supplier_id=supplier.id,
                source_type=item["source"],
                external_id=f"fixture:{item['source']}",
                access_mode="offline" if supplier.is_offline else "manual_import",
                reference=f"LOCAL FIXTURE/{item['source']}/{supplier.id}",
                status="local_fixture",
                metadata_json={"fixture": True},
                observed_at=stamp,
                created_at=stamp,
            )
            db.add(source)
            db.flush()
        evidence_key = f"search:{search.id}:supplier:{supplier.id}:source:{source.id}"
        evidence = db.scalar(
            select(SupplierEvidence).where(
                SupplierEvidence.owner_id == user.id,
                SupplierEvidence.idempotency_key == evidence_key,
            )
        )
        if evidence is None:
            evidence = SupplierEvidence(
                owner_id=user.id,
                supplier_id=supplier.id,
                source_id=source.id,
                evidence_kind="observed",
                reference=source.reference,
                normalized_value={"fixture": item["name"]},
                excerpt="Deterministic local fixture observation.",
                content_hash=hashlib.sha256(source.reference.encode()).hexdigest(),
                observed_at=stamp,
                retrieved_at=stamp,
                updated_at=stamp,
                idempotency_key=evidence_key,
            )
            db.add(evidence)
            db.flush()
        offering = db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.supplier_id == supplier.id,
                SupplierProduct.source_id == source.id,
            )
        )
        if offering is None:
            offering = SupplierProduct(
                owner_id=user.id,
                supplier_id=supplier.id,
                source_id=source.id,
                source_reference=source.reference,
                title="Fixture product offering",
                category=str(search.requirements.get("category", "general")),
                specifications={"materials": ["documented fixture material"]},
                observed_price=item["price"],
                currency=item["currency"],
                price_kind="displayed_price" if item["price"] else "unknown",
                moq=item["moq"],
                moq_unit="units",
                sample_available=True,
                sample_moq=1,
                sample_lead_days=7,
                production_lead_days=item["lead"],
                dispatch_lead_days=3,
                shipping_lead_days=10,
                private_label=item["private_label"],
                customization=item["customization"],
                packaging="standard fixture packaging",
                evidence_ids=[str(evidence.id)],
                observed_at=stamp,
                freshness_status="fresh",
                created_at=stamp,
            )
            db.add(offering)
            db.flush()
        elif str(evidence.id) not in offering.evidence_ids:
            offering.evidence_ids = [*offering.evidence_ids, str(evidence.id)]
        dimensions, score, recommendation = _score_dimensions(item, search.requirements)
        risk = db.scalar(
            select(SupplierRiskAssessment).where(SupplierRiskAssessment.supplier_id == supplier.id)
        )
        if risk is None:
            risk = SupplierRiskAssessment(
                owner_id=user.id,
                supplier_id=supplier.id,
                dimensions=item["risk"],
                warnings=(
                    ["REQUIRES REVIEW: deterministic fixture warning"]
                    if max(item["risk"].values()) >= 45
                    else []
                ),
                requires_review=max(item["risk"].values()) >= 45,
                created_at=stamp,
            )
            db.add(risk)
        score_eval = db.scalar(
            select(SupplierScoreEvaluation).where(
                SupplierScoreEvaluation.supplier_id == supplier.id,
                SupplierScoreEvaluation.model_version == search.ruleset_version,
            )
        )
        if score_eval is None:
            score_eval = SupplierScoreEvaluation(
                owner_id=user.id,
                supplier_id=supplier.id,
                model_version=search.ruleset_version,
                weights={key: value["weight"] for key, value in dimensions.items()},
                inputs=search.requirements,
                dimensions=dimensions,
                final_score=score,
                recommendation=recommendation,
                evidence_ids=[],
                created_at=stamp,
            )
            db.add(score_eval)
        match = db.scalar(
            select(SupplierOpportunityMatch).where(
                SupplierOpportunityMatch.supplier_product_id == offering.id,
                SupplierOpportunityMatch.requirement_key == str(search.id),
            )
        )
        if match is None:
            match = SupplierOpportunityMatch(
                owner_id=user.id,
                supplier_id=supplier.id,
                supplier_product_id=offering.id,
                search_id=search.id,
                requirement_key=str(search.id),
                match_score=score,
                matched_dimensions={
                    "category": True,
                    "moq": item["moq"] is not None,
                    "lead_time": item["lead"] is not None,
                    "private_label": not search.requirements.get("private_label")
                    or item["private_label"],
                },
                unmatched_requirements=(
                    []
                    if recommendation in {"strong_match", "promising"}
                    else ["verification or commercial evidence requires review"]
                ),
                confidence=0.8 if item["price"] else 0.35,
                explanation=[
                    {
                        "requirement": "private_label",
                        "supplier_capability": item["private_label"],
                        "result": "matched" if item["private_label"] else "unmatched",
                        "score_impact": dimensions["capability"]["score"],
                        "evidence": source.reference,
                    }
                ],
            )
            db.add(match)
        for claim in item["claims"]:
            if not db.scalar(
                select(SupplierCertificationClaim).where(
                    SupplierCertificationClaim.supplier_id == supplier.id,
                    SupplierCertificationClaim.claim == claim,
                )
            ):
                db.add(
                    SupplierCertificationClaim(
                        owner_id=user.id,
                        supplier_id=supplier.id,
                        claim=claim,
                        version=1,
                        is_current=True,
                        source_reference=source.reference,
                        document_reference=None,
                        observed_at=stamp,
                        verification_state="unverified",
                        evidence_ids=[],
                    )
                )
        supplier_count += 1
    search.summary_json = {
        "supplier_count": supplier_count,
        "offering_count": supplier_count,
        "source_mode": "LOCAL FIXTURE",
        "external_connectors": "disabled",
    }
    search.status = "completed"
    search.completed_at = now()
    search.updated_at = now()
    db.flush()
    _event(db, user, "supplier_search_completed", search)
    return search


def list_suppliers(
    db: Session,
    user: User,
    *,
    source: str | None = None,
    country: str | None = None,
    verification: str | None = None,
    offline: bool | None = None,
) -> list[dict[str, Any]]:
    query = select(Supplier).where(Supplier.owner_id == user.id)
    if country:
        query = query.where(Supplier.country_code == country.upper())
    if verification:
        query = query.where(Supplier.verification_state == verification)
    if offline is not None:
        query = query.where(Supplier.is_offline.is_(offline))
    suppliers = list(db.scalars(query.order_by(Supplier.updated_at.desc())))
    if source:
        supplier_ids = set(
            db.scalars(
                select(SupplierSource.supplier_id).where(
                    SupplierSource.owner_id == user.id, SupplierSource.source_type == source
                )
            )
        )
        suppliers = [item for item in suppliers if item.id in supplier_ids]
    return [_supplier_payload(db, item) for item in suppliers]


def supplier_detail(db: Session, user: User, supplier_id: uuid.UUID) -> dict[str, Any]:
    supplier = _safe_supplier(db, user, supplier_id)
    payload = _supplier_payload(db, supplier)
    payload.update(
        {
            "sources": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierSource).where(SupplierSource.supplier_id == supplier.id)
                )
            ],
            "contacts": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierContact).where(SupplierContact.supplier_id == supplier.id)
                )
            ],
            "offerings": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierProduct).where(SupplierProduct.supplier_id == supplier.id)
                )
            ],
            "capabilities": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierCapability).where(SupplierCapability.supplier_id == supplier.id)
                )
            ],
            "commercial_terms": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierCommercialTerm)
                    .where(SupplierCommercialTerm.supplier_id == supplier.id)
                    .order_by(SupplierCommercialTerm.version.desc())
                )
            ],
            "verifications": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierVerification).where(
                        SupplierVerification.supplier_id == supplier.id
                    )
                )
            ],
            "certifications": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierCertificationClaim).where(
                        SupplierCertificationClaim.supplier_id == supplier.id
                    )
                )
            ],
            "risk_assessments": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierRiskAssessment).where(
                        SupplierRiskAssessment.supplier_id == supplier.id
                    )
                )
            ],
            "score_evaluations": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierScoreEvaluation)
                    .where(SupplierScoreEvaluation.supplier_id == supplier.id)
                    .order_by(SupplierScoreEvaluation.created_at.desc())
                )
            ],
            "matches": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierOpportunityMatch).where(
                        SupplierOpportunityMatch.supplier_id == supplier.id
                    )
                )
            ],
            "decisions": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierDecision)
                    .where(SupplierDecision.supplier_id == supplier.id)
                    .order_by(SupplierDecision.created_at.desc())
                )
            ],
            "evidence": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierEvidence).where(SupplierEvidence.supplier_id == supplier.id)
                )
            ],
            "documents": [
                item.__dict__
                for item in db.scalars(
                    select(SupplierDocumentReference).where(
                        SupplierDocumentReference.supplier_id == supplier.id
                    )
                )
            ],
            "history": supplier_history(db, user, supplier.id),
        }
    )
    for section in (
        "sources",
        "contacts",
        "offerings",
        "capabilities",
        "commercial_terms",
        "verifications",
        "certifications",
        "risk_assessments",
        "score_evaluations",
        "matches",
        "decisions",
        "evidence",
        "documents",
    ):
        payload[section] = [
            {key: value for key, value in row.items() if not key.startswith("_")}
            for row in payload[section]
        ]
    return payload


def decide_supplier(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierDecisionRequest
) -> SupplierDecision:
    supplier = _safe_supplier(db, user, supplier_id)
    if data.decision == "approve_for_rfq" and supplier.verification_state in {
        "unverified",
        "blocked",
        "suspended",
    }:
        raise HTTPException(409, "Supplier must be reviewed before RFQ approval.")
    key = data.idempotency_key or f"{supplier.id}:{data.decision}:{data.reason}"
    _advisory_lock(db, f"decision:{user.id}:{key}")
    prior = db.scalar(
        select(SupplierDecision).where(
            SupplierDecision.owner_id == user.id, SupplierDecision.idempotency_key == key
        )
    )
    if prior is not None:
        cast(Any, prior).idempotent_reuse = True
        return prior
    decision = SupplierDecision(
        owner_id=user.id,
        supplier_id=supplier.id,
        decision=data.decision,
        reason=data.reason,
        idempotency_key=key,
        created_at=now(),
    )
    db.add(decision)
    db.flush()
    _event(db, user, f"supplier_{data.decision}", supplier)
    cast(Any, decision).idempotent_reuse = False
    return decision


def verify_supplier(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierVerificationRequest
) -> SupplierVerification:
    supplier = _safe_supplier(db, user, supplier_id)
    allowed = {
        "unverified": {"self_reported", "partially_verified", "verified", "suspended", "blocked"},
        "self_reported": {"partially_verified", "verified", "suspended", "blocked"},
        "partially_verified": {"verified", "high_confidence", "suspended", "blocked"},
        "verified": {"high_confidence", "suspended", "blocked"},
        "high_confidence": {"suspended", "blocked"},
        "suspended": {"verified", "blocked"},
        "blocked": {"blocked"},
    }
    if data.state != supplier.verification_state and data.state not in allowed.get(
        supplier.verification_state, set()
    ):
        raise HTTPException(409, "Verification transition is not allowed.")
    if data.state in {"verified", "high_confidence"} and not data.evidence_ids:
        raise HTTPException(409, "Verification evidence is required for this state.")
    evidence_ids = set(data.evidence_ids)
    if evidence_ids:
        owned_evidence = set(
            db.scalars(
                select(SupplierEvidence.id).where(
                    SupplierEvidence.owner_id == user.id,
                    SupplierEvidence.supplier_id == supplier.id,
                    SupplierEvidence.id.in_(evidence_ids),
                )
            )
        )
        if owned_evidence != evidence_ids:
            raise HTTPException(404, "Verification evidence not found.")
    verification_key = f"{supplier.id}:{data.state}:" + ",".join(
        sorted(str(item) for item in evidence_ids)
    )
    _advisory_lock(db, f"verification:{user.id}:{verification_key}")
    prior = db.scalar(
        select(SupplierVerification).where(
            SupplierVerification.owner_id == user.id,
            SupplierVerification.supplier_id == supplier.id,
            SupplierVerification.idempotency_key == verification_key,
        )
    )
    if prior is not None:
        cast(Any, prior).idempotent_reuse = True
        return prior
    verification = SupplierVerification(
        owner_id=user.id,
        supplier_id=supplier.id,
        state=data.state,
        reason=data.reason,
        idempotency_key=verification_key,
        evidence_ids=[str(item) for item in data.evidence_ids],
        verified_by=user.id,
        observed_at=now(),
        created_at=now(),
    )
    db.add(verification)
    supplier.verification_state = data.state
    supplier.updated_at = now()
    _history(
        db,
        user,
        supplier.id,
        "verification_changed",
        {"state": data.state, "evidence_ids": [str(v) for v in data.evidence_ids]},
    )
    db.flush()
    _event(db, user, "supplier_verification_recorded", supplier)
    cast(Any, verification).idempotent_reuse = False
    return verification


def compare_suppliers(
    db: Session, user: User, data: SupplierComparisonRequest
) -> list[dict[str, Any]]:
    if len(set(data.supplier_ids)) != len(data.supplier_ids):
        raise HTTPException(422, "Supplier comparison requires distinct suppliers.")
    payloads = [
        _supplier_payload(db, _safe_supplier(db, user, supplier_id))
        for supplier_id in data.supplier_ids
    ]
    currencies = set(
        db.scalars(
            select(SupplierProduct.currency).where(
                SupplierProduct.owner_id == user.id,
                SupplierProduct.supplier_id.in_(data.supplier_ids),
                SupplierProduct.currency.is_not(None),
            )
        )
    )
    status = "COMPARABLE" if len(currencies) <= 1 else "NOT COMPARABLE: currencies differ"
    return [dict(payload, comparison_status=status) for payload in payloads]


def supplier_report(db: Session, user: User, supplier_id: uuid.UUID) -> dict[str, Any]:
    detail = supplier_detail(db, user, supplier_id)
    return {
        "supplier": detail,
        "report_version": "supplier-report-v1",
        "generated_at": now(),
        "sections": {
            "Supplier Summary": detail,
            "Product Match": detail["matches"],
            "Capabilities": detail["capabilities"],
            "Commercial Terms": detail["commercial_terms"],
            "MOQ": [item.get("moq") for item in detail["offerings"]],
            "Lead Time": [item.get("production_lead_days") for item in detail["offerings"]],
            "Verification": detail["verifications"],
            "Certifications": detail["certifications"],
            "Risk": detail["risk_assessments"],
            "Score": detail["score_evaluations"],
            "Critic": [
                "Why should we NOT choose this supplier? Review MOQ, verification, "
                "lead time, and evidence quality."
            ],
            "Evidence": detail["evidence"],
            "Recommendation": detail.get("recommendation"),
        },
    }


def supplier_overview(db: Session, user: User) -> dict[str, Any]:
    total = int(
        db.scalar(select(func.count()).select_from(Supplier).where(Supplier.owner_id == user.id))
        or 0
    )
    verified = int(
        db.scalar(
            select(func.count())
            .select_from(Supplier)
            .where(
                Supplier.owner_id == user.id,
                Supplier.verification_state.in_(["verified", "high_confidence"]),
            )
        )
        or 0
    )
    searches = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierSearch)
            .where(SupplierSearch.owner_id == user.id)
        )
        or 0
    )
    failures = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierSearch)
            .where(SupplierSearch.owner_id == user.id, SupplierSearch.status == "failed")
        )
        or 0
    )
    stale = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierProduct)
            .where(
                SupplierProduct.owner_id == user.id,
                SupplierProduct.freshness_status.in_(["stale", "expired"]),
            )
        )
        or 0
    )
    high_risk = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierRiskAssessment)
            .where(
                SupplierRiskAssessment.owner_id == user.id,
                SupplierRiskAssessment.requires_review.is_(True),
            )
        )
        or 0
    )
    shortlisted = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierDecision)
            .where(
                SupplierDecision.owner_id == user.id,
                SupplierDecision.decision.in_(["shortlist", "approve_for_rfq"]),
            )
        )
        or 0
    )
    return {
        "supplier_count": total,
        "verified_count": verified,
        "unverified_count": total - verified,
        "shortlisted_count": shortlisted,
        "high_risk_count": high_risk,
        "stale_count": stale,
        "recent_searches": searches,
        "recent_failures": failures,
        "provider_mode": "local_fixture",
        "external_connectors": {
            "indiamart": "not_configured",
            "alibaba": "not_configured",
            "tradeindia": "not_configured",
            "global_sources": "not_configured",
        },
    }


SUPPLIER_RECOVERY_ACTIONS = {
    "source_unavailable": ("retry", "reconcile", "review_source", "cancel"),
    "source_rate_limited": ("retry", "review_source", "cancel"),
    "source_auth_failed": ("review_source", "cancel"),
    "invalid_supplier": ("review_supplier", "cancel"),
    "invalid_offering": ("review_supplier", "cancel"),
    "unsafe_source": ("review_source", "review_rules", "cancel"),
    "stale_supplier_data": ("refresh_evidence", "review_supplier", "cancel"),
    "verification_failed": ("review_verification", "refresh_evidence", "cancel"),
    "scoring_failed": ("retry", "reconcile", "review_rules", "cancel"),
    "checkpoint_invalid": ("reconcile", "review_rules", "cancel"),
}


def _history(
    db: Session,
    user: User,
    supplier_id: uuid.UUID,
    event_type: str,
    payload: dict[str, object],
    correlation_id: str | None = None,
) -> SupplierHistoryEvent:
    value = SupplierHistoryEvent(
        owner_id=user.id,
        supplier_id=supplier_id,
        event_type=event_type,
        correlation_id=correlation_id or _correlation(),
        payload=payload,
        created_at=now(),
    )
    db.add(value)
    return value


def create_commercial_term(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierCommercialTermCreate
) -> SupplierCommercialTerm:
    supplier = _safe_supplier(db, user, supplier_id)
    offering = db.scalar(
        select(SupplierProduct).where(
            SupplierProduct.id == data.supplier_product_id,
            SupplierProduct.supplier_id == supplier.id,
            SupplierProduct.owner_id == user.id,
        )
    )
    if offering is None:
        raise HTTPException(404, "Supplier offering not found.")
    _advisory_lock(db, f"commercial:{offering.id}:{data.version}")
    prior = db.scalar(
        select(SupplierCommercialTerm).where(
            SupplierCommercialTerm.supplier_product_id == offering.id,
            SupplierCommercialTerm.version == data.version,
        )
    )
    if prior is not None:
        if any(
            (
                (
                    [str(value) for value in getattr(prior, field)]
                    != [str(value) for value in getattr(data, field)]
                )
                if field == "source_evidence_ids"
                else getattr(prior, field) != getattr(data, field)
            )
            for field in (
                "unit_price",
                "currency",
                "moq",
                "lead_time_days",
                "payment_terms",
                "source_evidence_ids",
            )
        ):
            raise HTTPException(409, "Commercial term versions are immutable.")
        return prior
    if data.version > 1:
        latest = db.scalar(
            select(SupplierCommercialTerm)
            .where(SupplierCommercialTerm.supplier_product_id == offering.id)
            .order_by(SupplierCommercialTerm.version.desc())
        )
        if latest is None or data.version != latest.version + 1:
            raise HTTPException(409, "Commercial versions must be appended sequentially.")
        db.query(SupplierCommercialTerm).filter(
            SupplierCommercialTerm.supplier_product_id == offering.id
        ).update({"is_current": False}, synchronize_session=False)
    stamp = now()
    term = SupplierCommercialTerm(
        owner_id=user.id,
        supplier_id=supplier.id,
        supplier_product_id=offering.id,
        version=data.version,
        unit_price=data.unit_price,
        currency=data.currency.upper() if data.currency else None,
        price_tiers=data.price_tiers,
        moq=data.moq,
        sample_price=data.sample_price,
        tooling_fee=data.tooling_fee,
        packaging_fee=data.packaging_fee,
        branding_fee=data.branding_fee,
        payment_terms=data.payment_terms,
        deposit_percent=data.deposit_percent,
        balance_percent=data.balance_percent,
        incoterm=data.incoterm,
        valid_until=data.valid_until,
        lead_time_days=data.lead_time_days,
        sample_lead_days=data.sample_lead_days,
        production_lead_days=data.production_lead_days,
        dispatch_lead_days=data.dispatch_lead_days,
        is_current=True,
        source_evidence_ids=[str(v) for v in data.source_evidence_ids],
        observed_at=stamp,
        created_at=stamp,
    )
    db.add(term)
    db.flush()
    _history(
        db,
        user,
        supplier.id,
        "commercial_term_versioned",
        {"version": data.version, "supplier_product_id": str(offering.id)},
    )
    _event(db, user, "supplier_commercial_term_created", supplier)
    return term


def list_commercial_terms(
    db: Session, user: User, supplier_id: uuid.UUID, product_id: uuid.UUID
) -> list[SupplierCommercialTerm]:
    supplier = _safe_supplier(db, user, supplier_id)
    return list(
        db.scalars(
            select(SupplierCommercialTerm)
            .where(
                SupplierCommercialTerm.owner_id == user.id,
                SupplierCommercialTerm.supplier_id == supplier.id,
                SupplierCommercialTerm.supplier_product_id == product_id,
            )
            .order_by(SupplierCommercialTerm.version)
        )
    )


def commercial_term_detail(
    db: Session, user: User, supplier_id: uuid.UUID, product_id: uuid.UUID, version: int
) -> SupplierCommercialTerm:
    supplier = _safe_supplier(db, user, supplier_id)
    value = db.scalar(
        select(SupplierCommercialTerm).where(
            SupplierCommercialTerm.owner_id == user.id,
            SupplierCommercialTerm.supplier_id == supplier.id,
            SupplierCommercialTerm.supplier_product_id == product_id,
            SupplierCommercialTerm.version == version,
        )
    )
    if value is None:
        raise HTTPException(404, "Commercial term version not found.")
    return value


def create_certification_claim(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierCertificationClaimCreate
) -> SupplierCertificationClaim:
    supplier = _safe_supplier(db, user, supplier_id)
    _advisory_lock(db, f"certification:{supplier.id}:{data.claim}:{data.version or 0}")
    evidence_ids = set(data.evidence_ids)
    if evidence_ids:
        owned = set(
            db.scalars(
                select(SupplierEvidence.id).where(
                    SupplierEvidence.owner_id == user.id,
                    SupplierEvidence.supplier_id == supplier.id,
                    SupplierEvidence.id.in_(evidence_ids),
                )
            )
        )
        if owned != evidence_ids:
            raise HTTPException(404, "Certification evidence not found.")
    latest = db.scalar(
        select(SupplierCertificationClaim)
        .where(
            SupplierCertificationClaim.owner_id == user.id,
            SupplierCertificationClaim.supplier_id == supplier.id,
            SupplierCertificationClaim.claim == data.claim,
        )
        .order_by(SupplierCertificationClaim.version.desc())
    )
    version = data.version or ((latest.version + 1) if latest else 1)
    if latest and version <= latest.version:
        if version == latest.version:
            return latest
        raise HTTPException(409, "Certification versions must be append-only.")
    if latest:
        db.query(SupplierCertificationClaim).filter(
            SupplierCertificationClaim.id == latest.id
        ).update({"is_current": False}, synchronize_session=False)
    value = SupplierCertificationClaim(
        owner_id=user.id,
        supplier_id=supplier.id,
        claim=data.claim,
        version=version,
        is_current=True,
        source_reference=data.source_reference,
        document_reference=data.document_reference,
        observed_at=data.observed_at or now(),
        verification_state=data.verification_state,
        expires_at=data.expires_at,
        evidence_ids=[str(item) for item in data.evidence_ids],
    )
    db.add(value)
    db.flush()
    _history(
        db,
        user,
        supplier.id,
        "certification_claim_versioned",
        {
            "claim": data.claim,
            "version": version,
        },
    )
    return value


def list_certification_claims(
    db: Session, user: User, supplier_id: uuid.UUID
) -> list[SupplierCertificationClaim]:
    supplier = _safe_supplier(db, user, supplier_id)
    return list(
        db.scalars(
            select(SupplierCertificationClaim)
            .where(
                SupplierCertificationClaim.owner_id == user.id,
                SupplierCertificationClaim.supplier_id == supplier.id,
            )
            .order_by(SupplierCertificationClaim.claim, SupplierCertificationClaim.version)
        )
    )


def create_score_evaluation(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierScoreCreate
) -> SupplierScoreEvaluation:
    supplier = _safe_supplier(db, user, supplier_id)
    _advisory_lock(db, f"score:{supplier.id}:{data.model_version}")
    if abs(sum(data.weights.values()) - 100.0) > 1e-6 or any(
        value < 0 for value in data.weights.values()
    ):
        raise HTTPException(422, "Score weights must be non-negative and sum to 100.")
    evidence_ids = set(data.evidence_ids)
    if evidence_ids:
        owned = set(
            db.scalars(
                select(SupplierEvidence.id).where(
                    SupplierEvidence.owner_id == user.id,
                    SupplierEvidence.supplier_id == supplier.id,
                    SupplierEvidence.id.in_(evidence_ids),
                )
            )
        )
        if owned != evidence_ids:
            raise HTTPException(404, "Score evidence not found.")
    prior = db.scalar(
        select(SupplierScoreEvaluation).where(
            SupplierScoreEvaluation.owner_id == user.id,
            SupplierScoreEvaluation.supplier_id == supplier.id,
            SupplierScoreEvaluation.model_version == data.model_version,
        )
    )
    if prior is not None:
        if float(prior.final_score) != data.final_score or prior.weights != data.weights:
            raise HTTPException(409, "Score versions are immutable.")
        return prior
    value = SupplierScoreEvaluation(
        owner_id=user.id,
        supplier_id=supplier.id,
        model_version=data.model_version,
        weights=data.weights,
        inputs=data.inputs,
        dimensions=data.dimensions,
        final_score=data.final_score,
        recommendation=data.recommendation,
        evidence_ids=[str(item) for item in data.evidence_ids],
        created_at=now(),
    )
    db.add(value)
    db.flush()
    _history(
        db,
        user,
        supplier.id,
        "score_versioned",
        {
            "model_version": data.model_version,
            "final_score": data.final_score,
        },
    )
    return value


def score_history(db: Session, user: User, supplier_id: uuid.UUID) -> list[SupplierScoreEvaluation]:
    supplier = _safe_supplier(db, user, supplier_id)
    return list(
        db.scalars(
            select(SupplierScoreEvaluation)
            .where(
                SupplierScoreEvaluation.owner_id == user.id,
                SupplierScoreEvaluation.supplier_id == supplier.id,
            )
            .order_by(SupplierScoreEvaluation.created_at)
        )
    )


def create_contact(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierContactCreate
) -> SupplierContact:
    supplier = _safe_supplier(db, user, supplier_id)
    contact = SupplierContact(
        owner_id=user.id,
        supplier_id=supplier.id,
        name=data.name,
        role=data.role,
        email=data.business_email,
        phone=data.business_phone,
        whatsapp=data.whatsapp,
        preferred_method=data.preferred_method,
        provenance=data.source,
        verification_status=data.verification,
        communication_status=data.communication_status,
        archived=False,
        created_at=now(),
        updated_at=now(),
    )
    db.add(contact)
    db.flush()
    _history(db, user, supplier.id, "contact_created", {"contact_id": str(contact.id)})
    return contact


def list_contacts(db: Session, user: User, supplier_id: uuid.UUID) -> list[SupplierContact]:
    supplier = _safe_supplier(db, user, supplier_id)
    return list(
        db.scalars(
            select(SupplierContact)
            .where(
                SupplierContact.owner_id == user.id,
                SupplierContact.supplier_id == supplier.id,
                SupplierContact.archived.is_(False),
            )
            .order_by(SupplierContact.created_at)
        )
    )


def update_contact(
    db: Session,
    user: User,
    supplier_id: uuid.UUID,
    contact_id: uuid.UUID,
    data: SupplierContactUpdate,
) -> SupplierContact:
    supplier = _safe_supplier(db, user, supplier_id)
    contact = db.scalar(
        select(SupplierContact).where(
            SupplierContact.id == contact_id,
            SupplierContact.supplier_id == supplier.id,
            SupplierContact.owner_id == user.id,
        )
    )
    if contact is None:
        raise HTTPException(404, "Supplier contact not found.")
    mapping = {
        "business_email": "email",
        "business_phone": "phone",
        "source": "provenance",
        "verification": "verification_status",
    }
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, mapping.get(key, key), value)
    contact.updated_at = now()
    db.flush()
    _history(db, user, supplier.id, "contact_updated", {"contact_id": str(contact.id)})
    return contact


def create_document_reference(
    db: Session, user: User, supplier_id: uuid.UUID, data: SupplierDocumentReferenceCreate
) -> SupplierDocumentReference:
    supplier = _safe_supplier(db, user, supplier_id)
    if (
        "<" in data.display_name
        or ">" in data.display_name
        or data.display_name.lower().endswith((".exe", ".bat", ".cmd", ".ps1"))
    ):
        raise HTTPException(422, "Unsafe document reference.")
    prior = db.scalar(
        select(SupplierDocumentReference).where(
            SupplierDocumentReference.owner_id == user.id,
            SupplierDocumentReference.supplier_id == supplier.id,
            SupplierDocumentReference.reference_id == data.reference_id,
        )
    )
    if prior is not None:
        return prior
    stamp = data.observed_at or now()
    value = SupplierDocumentReference(
        owner_id=user.id,
        supplier_id=supplier.id,
        reference_id=data.reference_id,
        document_type=data.document_type,
        display_name=data.display_name,
        mime_type=data.mime_type,
        size_bytes=data.size_bytes,
        content_hash=data.content_hash,
        source_reference=data.source_reference,
        verification_state=data.verification_state,
        observed_at=stamp,
        created_at=now(),
    )
    db.add(value)
    db.flush()
    _history(db, user, supplier.id, "document_reference_added", {"reference_id": data.reference_id})
    return value


def source_diversity(db: Session, user: User, supplier_id: uuid.UUID) -> dict[str, object]:
    supplier = _safe_supplier(db, user, supplier_id)
    sources = list(
        db.scalars(
            select(SupplierSource).where(
                SupplierSource.owner_id == user.id, SupplierSource.supplier_id == supplier.id
            )
        )
    )
    profile_keys = {(item.source_type, item.reference.strip().casefold()) for item in sources}
    independent = {item.source_type for item in sources}
    commercial_types = {
        "alibaba",
        "manufacturer_website",
        "trade_fair",
        "offline_market",
        "referral",
    }
    commercial = {item.source_type for item in sources if item.source_type in commercial_types}
    verification = {
        item.source_type for item in sources if item.status in {"verified", "manual_entry"}
    }
    return {
        "independent_source_count": len(independent),
        "supplier_profile_source_count": len(profile_keys),
        "commercial_source_count": len(commercial),
        "verification_source_count": len(verification),
        "source_diversity_score": round(min(1.0, len(independent) / 5), 2),
        "missing_source_types": [
            value
            for value in ("manufacturer_website", "trade_fair", "offline_market", "referral")
            if value not in independent
        ],
    }


def supplier_history(db: Session, user: User, supplier_id: uuid.UUID) -> list[dict[str, object]]:
    supplier = _safe_supplier(db, user, supplier_id)
    rows = list(
        db.scalars(
            select(SupplierHistoryEvent)
            .where(
                SupplierHistoryEvent.owner_id == user.id,
                SupplierHistoryEvent.supplier_id == supplier.id,
            )
            .order_by(SupplierHistoryEvent.created_at)
        )
    )
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "correlation_id": row.correlation_id,
            "payload": row.payload,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def risk_matrix(db: Session, user: User, supplier_id: uuid.UUID) -> dict[str, object]:
    supplier = _safe_supplier(db, user, supplier_id)
    risk = db.scalar(
        select(SupplierRiskAssessment)
        .where(
            SupplierRiskAssessment.owner_id == user.id,
            SupplierRiskAssessment.supplier_id == supplier.id,
        )
        .order_by(SupplierRiskAssessment.created_at.desc())
    )
    values = risk.dimensions if risk else {}
    dimensions = [
        {
            "dimension": key,
            "score": value,
            "status": "REQUIRES REVIEW" if float(cast(Any, value)) >= 45 else "observed",
            "reason": "Deterministic evidence requires human review.",
            "evidence": [],
        }
        for key, value in values.items()
    ]
    for key in (
        "identity",
        "commercial",
        "quality",
        "delivery",
        "verification",
        "communication",
        "compliance",
        "concentration",
        "fraud_signal",
    ):
        if not any(item["dimension"] == key for item in dimensions):
            dimensions.append(
                {
                    "dimension": key,
                    "score": None,
                    "status": "unknown",
                    "reason": "No deterministic evidence available.",
                    "evidence": [],
                }
            )
    return {"dimensions": dimensions, "warnings": risk.warnings if risk else []}


def recover_search(
    db: Session, user: User, search_id: uuid.UUID, data: SupplierRecoveryRequest
) -> SupplierRecoveryRecord:
    search = db.scalar(
        select(SupplierSearch).where(
            SupplierSearch.id == search_id, SupplierSearch.owner_id == user.id
        )
    )
    if search is None:
        raise HTTPException(404, "Supplier search not found.")
    _advisory_lock(db, f"recovery:{user.id}:{data.idempotency_key}")
    allowed = SUPPLIER_RECOVERY_ACTIONS.get(search.failure_classification or "scoring_failed", ())
    if data.action not in allowed:
        raise HTTPException(409, "Recovery action is not executable for this failure.")
    prior = db.scalar(
        select(SupplierRecoveryRecord).where(
            SupplierRecoveryRecord.owner_id == user.id,
            SupplierRecoveryRecord.idempotency_key == data.idempotency_key,
        )
    )
    if prior is not None:
        cast(Any, prior).idempotent_reuse = True
        return prior
    value = SupplierRecoveryRecord(
        owner_id=user.id,
        search_id=search.id,
        action=data.action,
        idempotency_key=data.idempotency_key,
        status="completed",
        reason_code=search.failure_classification,
        correlation_id=search.correlation_id,
        created_at=now(),
    )
    db.add(value)
    db.flush()
    if data.action == "retry":
        search.status = "pending"
        search.lease_token = None
        search.lease_expires_at = None
        search.completed_at = None
    elif data.action == "reconcile":
        if (search.checkpoint_state or {}).get("provider_persisted"):
            execute_search(db, user, search)
        else:
            search.status = "pending"
            search.lease_token = None
            search.lease_expires_at = None
    elif data.action == "cancel":
        search.status = "cancelled"
        search.lease_token = None
        search.lease_expires_at = None
    elif data.action in {"review_source", "review_supplier", "review_verification", "review_rules"}:
        search.status = "review_required"
    elif data.action == "refresh_evidence":
        search.status = "pending"
        search.lease_token = None
        search.lease_expires_at = None
    match = db.scalar(
        select(SupplierOpportunityMatch).where(
            SupplierOpportunityMatch.owner_id == user.id,
            SupplierOpportunityMatch.search_id == search.id,
        )
    )
    if match is not None:
        _history(
            db,
            user,
            match.supplier_id,
            "recovery_completed",
            {
                "search_id": str(search.id),
                "action": data.action,
                "status": search.status,
            },
            search.correlation_id,
        )
    db.flush()
    cast(Any, value).idempotent_reuse = False
    return value


SUPPLIER_TABLES = {
    "intelligence_suppliers": (
        "Owner-scoped supplier identities; normalized identity is " "unique per owner."
    ),
    "intelligence_supplier_sources": "Source observations and access provenance.",
    "intelligence_supplier_contacts": "Business contacts with archive state.",
    "intelligence_supplier_capabilities": "Claimed capabilities and evidence links.",
    "intelligence_supplier_products": "Supplier offering observations and freshness.",
    "intelligence_supplier_evidence": "Observed/manual evidence with hash and retrieval identity.",
    "intelligence_supplier_verifications": "Append-only verification decisions.",
    "intelligence_supplier_commercial_terms": "Append-only versioned commercial terms.",
    "intelligence_supplier_certification_claims": "Versioned certification claims.",
    "intelligence_supplier_document_references": "Safe metadata-only document references.",
    "intelligence_supplier_risk_assessments": "Deterministic risk dimensions and warnings.",
    "intelligence_supplier_score_evaluations": "Versioned weighted score evaluations.",
    "intelligence_supplier_opportunity_matches": "Requirement-to-offering matches.",
    "intelligence_supplier_decisions": "Owner-scoped shortlist/review/reject decisions.",
    "intelligence_supplier_searches": "Durable idempotent searches and checkpoints.",
    "intelligence_supplier_history": "Unified supplier history projection.",
    "intelligence_supplier_recovery": "Idempotent local recovery actions.",
}


def supplier_table_inventory(db: Session, user: User) -> list[dict[str, object]]:
    from sqlalchemy import text

    rows = []
    for table, purpose in SUPPLIER_TABLES.items():
        count = int(
            db.scalar(
                text(f'SELECT COUNT(*) FROM "{table}" WHERE owner_id = :owner'), {"owner": user.id}
            )
            or 0
        )
        rows.append({"table": table, "purpose": purpose, "owner_scoped": True, "count": count})
    return rows


def freshness_matrix(db: Session, user: User, supplier_id: uuid.UUID) -> dict[str, str]:
    supplier = _safe_supplier(db, user, supplier_id)
    offering = db.scalar(
        select(SupplierProduct)
        .where(SupplierProduct.owner_id == user.id, SupplierProduct.supplier_id == supplier.id)
        .order_by(SupplierProduct.observed_at.desc())
    )
    contact = db.scalar(
        select(SupplierContact)
        .where(
            SupplierContact.owner_id == user.id,
            SupplierContact.supplier_id == supplier.id,
            SupplierContact.archived.is_(False),
        )
        .order_by(SupplierContact.updated_at.desc())
    )
    certification = db.scalar(
        select(SupplierCertificationClaim)
        .where(
            SupplierCertificationClaim.owner_id == user.id,
            SupplierCertificationClaim.supplier_id == supplier.id,
        )
        .order_by(SupplierCertificationClaim.observed_at.desc())
    )
    verification = db.scalar(
        select(SupplierVerification)
        .where(
            SupplierVerification.owner_id == user.id,
            SupplierVerification.supplier_id == supplier.id,
        )
        .order_by(SupplierVerification.observed_at.desc())
    )
    capability = db.scalar(
        select(SupplierCapability)
        .where(
            SupplierCapability.owner_id == user.id,
            SupplierCapability.supplier_id == supplier.id,
        )
        .order_by(SupplierCapability.observed_at.desc())
    )
    status = offering.freshness_status if offering else "unknown"
    return {
        "price": status if offering and offering.observed_price is not None else "unknown",
        "moq": status if offering and offering.moq is not None else "unknown",
        "lead_time": (
            status if offering and offering.production_lead_days is not None else "unknown"
        ),
        "contact": "fresh" if contact else "unknown",
        "certification": "fresh" if certification else "unknown",
        "verification": (
            "fresh" if verification and supplier.verification_state != "unverified" else "stale"
        ),
        "capability": "fresh" if capability else "unknown",
        "offering": status,
    }
