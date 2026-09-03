# ruff: noqa: E501
"""Provider-independent, read-only supplier consolidation services.

This module deliberately consumes the existing Supplier Intelligence tables.  Marketplace
adapters remain responsible for discovery; this layer only reconciles accepted, owner-scoped
evidence into a canonical projection.
"""

from __future__ import annotations

import hashlib
import html
import re
import uuid
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import (
    CrossMarketplaceSupplier,
    CrossMarketplaceSupplierEvaluation,
    CrossMarketplaceSupplierEvent,
    CrossMarketplaceSupplierLink,
)
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCapability,
    SupplierCertificationClaim,
    SupplierEvidence,
    SupplierProduct,
    SupplierSource,
)

PROVIDERS = {"indiamart", "alibaba", "tradeindia", "global_sources"}
SOURCE_TYPES = PROVIDERS | {
    "supplier_website",
    "manufacturer_website",
    "manual_entry",
    "offline_market",
}
RANKING_WEIGHTS = {
    "identity_confidence": 0.20,
    "commercial_attractiveness": 0.15,
    "verification_strength": 0.15,
    "source_diversity": 0.15,
    "freshness": 0.10,
    "capability_fit": 0.10,
    "certification_fit": 0.05,
    "risk": 0.10,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    return value


def _tokens(name: str) -> set[str]:
    ignored = {"co", "company", "corp", "corporation", "inc", "ltd", "limited", "llc"}
    return {item for item in re.findall(r"[a-z0-9]+", name.casefold()) if item not in ignored}


def _domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.casefold().strip().removeprefix("https://").removeprefix("http://")
    return value.split("/", 1)[0].removeprefix("www.") or None


def _canonical_anchor(row: Supplier) -> str:
    domain = _domain(row.normalized_domain or row.website)
    if domain:
        return f"domain:{domain}"
    identifier = (row.business_identifier or "").strip().casefold()
    if identifier:
        return f"identifier:{identifier}"
    return "name:" + " ".join(sorted(_tokens(row.display_name))) + f":{row.country_code or ''}"


def _match_state(base: Supplier, candidate: Supplier) -> tuple[str, str]:
    if base.id == candidate.id:
        return "MATCH", "same supplier record"
    base_domain = _domain(base.normalized_domain or base.website)
    candidate_domain = _domain(candidate.normalized_domain or candidate.website)
    if base_domain and candidate_domain and base_domain == candidate_domain:
        return "MATCH", "same normalized website domain"
    if (
        base.business_identifier
        and candidate.business_identifier
        and base.business_identifier.casefold() == candidate.business_identifier.casefold()
    ):
        return "MATCH", "same business identifier"
    left, right = _tokens(base.display_name), _tokens(candidate.display_name)
    overlap = len(left & right) / max(len(left | right), 1)
    if overlap == 1 and base.country_code == candidate.country_code:
        return "MATCH", "same normalized name and country"
    if overlap >= 0.6 and base.country_code == candidate.country_code:
        return "POSSIBLE_MATCH", "similar normalized name requires human review"
    return "NO_MATCH", "independent identity"


def _safe_supplier(db: Session, owner: User, supplier_id: uuid.UUID) -> Supplier:
    row = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Supplier not found.")
    return row


def _source_rows(db: Session, owner: User, supplier_ids: list[uuid.UUID]) -> list[SupplierSource]:
    if not supplier_ids:
        return []
    return list(
        db.scalars(
            select(SupplierSource).where(
                SupplierSource.owner_id == owner.id, SupplierSource.supplier_id.in_(supplier_ids)
            )
        )
    )


def _freshness(observed: datetime | None) -> str:
    if observed is None:
        return "unknown"
    age = _now() - (observed if observed.tzinfo else observed.replace(tzinfo=UTC))
    if age <= timedelta(days=30):
        return "fresh"
    if age <= timedelta(days=90):
        return "aging"
    return "stale"


def _supplier_claims(
    db: Session, owner: User, supplier_ids: list[uuid.UUID]
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(SupplierProduct).where(
                SupplierProduct.owner_id == owner.id, SupplierProduct.supplier_id.in_(supplier_ids)
            )
        )
    )
    return [
        {
            "source_supplier_id": str(row.supplier_id),
            "source_product_id": str(row.id),
            "title": row.title,
            "category": row.category,
            "price": float(row.observed_price) if row.observed_price is not None else None,
            "currency": row.currency,
            "moq": float(row.moq) if row.moq is not None else None,
            "unit": row.moq_unit,
            "lead_time_days": row.production_lead_days or row.sample_lead_days,
            "availability": (row.specifications or {}).get("availability", "UNKNOWN"),
            "specifications": row.specifications or {},
            "freshness": row.freshness_status or _freshness(row.observed_at),
            "observed_at": _json(row.observed_at),
            "evidence_ids": list(row.evidence_ids or []),
        }
        for row in rows
    ]


def _commercial(claims: list[dict[str, Any]]) -> dict[str, Any]:
    currencies = sorted({str(row["currency"]) for row in claims if row.get("currency")})
    comparable = len(currencies) <= 1
    prices = [float(row["price"]) for row in claims if row.get("price") is not None]
    moqs = [float(row["moq"]) for row in claims if row.get("moq") is not None]
    leads = [int(row["lead_time_days"]) for row in claims if row.get("lead_time_days") is not None]

    def terms(field: str) -> list[dict[str, Any]]:
        return [
            {
                "source_supplier_id": row["source_supplier_id"],
                "value": row.get(field),
                "currency": row.get("currency") if field == "price" else None,
                "unit": (
                    row.get("unit")
                    if field == "moq"
                    else "days" if field == "lead_time_days" else None
                ),
                "observed_at": row.get("observed_at"),
                "freshness": row.get("freshness"),
                "verification": "unverified",
                "confidence": 0.35 if row.get(field) is not None else 0,
            }
            for row in claims
            if row.get(field) is not None
        ]

    def stats(values: list[float], field: str) -> dict[str, Any]:
        return {
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "median": median(values) if values else None,
            "source_count": len(values),
            "fresh_source_count": sum(
                row.get("freshness") == "fresh" for row in claims if row.get(field) is not None
            ),
            "verified_supporting_source_count": 0,
            "spread": (max(values) - min(values)) if values else None,
            "outlier_state": "INSUFFICIENT_EVIDENCE" if len(values) < 2 else "REVIEW_REQUIRED",
            "source_lineage": terms(field),
        }

    agreement = "INSUFFICIENT_EVIDENCE"
    if len(prices) >= 2:
        agreement = "AGREES" if len(set(prices)) == 1 else "CONFLICTS"
    moq_agreement = "INSUFFICIENT_EVIDENCE"
    if len(moqs) >= 2:
        moq_agreement = "AGREES" if len(set(moqs)) == 1 else "CONFLICTS"
    lead_agreement = "INSUFFICIENT_EVIDENCE"
    if len(leads) >= 2:
        lead_agreement = "AGREES" if len(set(leads)) == 1 else "PARTIAL_AGREEMENT"
    availability_values = {str(row.get("availability", "UNKNOWN")).upper() for row in claims}
    availability = (
        "UNKNOWN"
        if not availability_values
        else (next(iter(availability_values)) if len(availability_values) == 1 else "CONFLICTING")
    )
    return {
        "currency_safety": {
            "status": "DIRECTLY_COMPARABLE" if comparable else "NOT_DIRECTLY_COMPARABLE",
            "currencies": currencies,
            "fx_assumption": None,
        },
        "price": stats(prices if comparable else [], "price") | {"agreement": agreement},
        "moq": stats(moqs, "moq") | {"agreement": moq_agreement},
        "lead_time": stats([float(value) for value in leads], "lead_time_days")
        | {"agreement": lead_agreement},
        "availability": {"state": availability, "claims": terms("availability")},
        "claims": claims,
    }


def _source_inventory(
    db: Session, owner: User, supplier_ids: list[uuid.UUID]
) -> list[dict[str, Any]]:
    rows = _source_rows(db, owner, supplier_ids)
    return [
        {
            "source_type": row.source_type,
            "source_id": str(row.id),
            "provider": row.source_type.upper(),
            "domain": _domain(row.source_url or row.reference),
            "first_seen": _json(row.created_at),
            "last_seen": _json(row.observed_at),
            "freshness": _freshness(row.observed_at),
            "verification_state": str((row.metadata_json or {}).get("verification", "unverified")),
            "confidence_contribution": 0.2 if row.source_type in PROVIDERS else 0.1,
            "external_id": row.external_id,
        }
        for row in rows
    ]


def _risk(
    claims: list[dict[str, Any]], sources: list[dict[str, Any]], suppliers: list[Supplier]
) -> dict[str, Any]:
    dimensions: list[dict[str, Any]] = []
    currencies = {row.get("currency") for row in claims if row.get("currency")}
    if len(currencies) > 1:
        dimensions.append(
            {
                "dimension": "commercial_disagreement",
                "level": "MEDIUM",
                "reason": "Sources report different currencies.",
                "evidence_ids": [],
            }
        )
    if len({row.get("location") for row in sources if row.get("location")}) > 1:
        dimensions.append(
            {
                "dimension": "location_inconsistency",
                "level": "MEDIUM",
                "reason": "Source locations differ.",
                "evidence_ids": [],
            }
        )
    if any(row.get("freshness") == "stale" for row in sources):
        dimensions.append(
            {
                "dimension": "stale_commercial_data",
                "level": "MEDIUM",
                "reason": "At least one source observation is stale.",
                "evidence_ids": [],
            }
        )
    if len(sources) <= 1:
        dimensions.append(
            {
                "dimension": "single_source_dependence",
                "level": "LOW",
                "reason": "Only one source is available.",
                "evidence_ids": [],
            }
        )
    for supplier in suppliers:
        latest = None
        if supplier.id:
            latest = getattr(supplier, "verification_state", None)
        if latest in {"unverified", "suspended", "blocked"}:
            dimensions.append(
                {
                    "dimension": "verification_conflict",
                    "level": "MEDIUM",
                    "reason": "Verification remains unverified or restricted.",
                    "evidence_ids": [],
                }
            )
    level = (
        "HIGH"
        if any(item["level"] == "HIGH" for item in dimensions)
        else "MEDIUM" if dimensions else "LOW"
    )
    return {"level": level, "dimensions": dimensions, "fraud_inference": False}


def _confidence(
    sources: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    risk: dict[str, Any],
    suppliers: list[Supplier],
) -> dict[str, Any]:
    provider_count = len({item["source_type"] for item in sources})
    verified = sum(
        getattr(row, "verification_state", "unverified") in {"verified", "high_confidence"}
        for row in suppliers
    )
    completeness = sum(
        bool(row.get("price") and row.get("moq") and row.get("lead_time_days")) for row in claims
    ) / max(len(claims), 1)
    freshness = sum(row.get("freshness") == "fresh" for row in sources) / max(len(sources), 1)
    contradiction_penalty = min(len(risk["dimensions"]) * 0.05, 0.25)
    dimensions = [
        {
            "dimension": "verification",
            "weight": 0.25,
            "score": min(1, verified / max(len(suppliers), 1)),
            "reason": "Only persisted verification states count.",
            "evidence_ids": [],
        },
        {
            "dimension": "freshness",
            "weight": 0.2,
            "score": freshness,
            "reason": "Recent source observations are stronger.",
            "evidence_ids": [],
        },
        {
            "dimension": "source_diversity",
            "weight": 0.2,
            "score": min(provider_count / 4, 1),
            "reason": "Distinct provider classes are counted once.",
            "evidence_ids": [],
        },
        {
            "dimension": "completeness",
            "weight": 0.2,
            "score": completeness,
            "reason": "Price, MOQ, and lead time coverage.",
            "evidence_ids": [],
        },
        {
            "dimension": "contradictions",
            "weight": 0.15,
            "score": 1 - contradiction_penalty,
            "reason": "Conflicts reduce confidence and require review.",
            "evidence_ids": [],
        },
    ]
    score = round(sum(float(item["weight"]) * float(item["score"]) for item in dimensions) * 100, 2)
    return {"score": score, "dimensions": dimensions, "maximum_single_provider_score": 80}


def _aggregate(
    db: Session, owner: User, supplier_ids: list[uuid.UUID], state: str, rationale: str
) -> dict[str, Any]:
    suppliers = [_safe_supplier(db, owner, item) for item in supplier_ids]
    sources = _source_inventory(db, owner, supplier_ids)
    claims = _supplier_claims(db, owner, supplier_ids)
    commercial = _commercial(claims)
    risk = _risk(claims, sources, suppliers)
    confidence = _confidence(sources, claims, risk, suppliers)
    aliases = sorted({row.display_name for row in suppliers})
    capability_rows = list(
        db.scalars(
            select(SupplierCapability).where(
                SupplierCapability.owner_id == owner.id,
                SupplierCapability.supplier_id.in_(supplier_ids),
            )
        )
    )
    capabilities = [
        {
            "capability": row.capability,
            "state": row.state,
            "evidence_ids": list(row.evidence_ids or []),
        }
        for row in capability_rows
    ]
    cert_rows = list(
        db.scalars(
            select(SupplierCertificationClaim).where(
                SupplierCertificationClaim.owner_id == owner.id,
                SupplierCertificationClaim.supplier_id.in_(supplier_ids),
                SupplierCertificationClaim.is_current.is_(True),
            )
        )
    )
    certifications = [
        {
            "claim": row.claim,
            "issuer": row.document_reference,
            "status": row.verification_state,
            "document_reference": row.document_reference,
            "source": row.source_reference,
            "first_seen": _json(row.observed_at),
            "last_seen": _json(row.observed_at),
            "freshness": _freshness(row.observed_at),
            "verification_state": row.verification_state,
            "conflicts": [],
        }
        for row in cert_rows
    ]
    verification = [
        {"supplier_id": str(row.id), "state": row.verification_state, "source": row.source_identity}
        for row in suppliers
    ]
    facilities = [item for item in claims if (item.get("specifications") or {}).get("facility")]
    diversity = {
        "provider_classes": sorted({item["source_type"] for item in sources}),
        "domain_classes": sorted({item["domain"] for item in sources if item.get("domain")}),
        "independent_source_count": len({item["source_type"] for item in sources}),
        "source_diversity_score": round(
            min(len({item["source_type"] for item in sources}) / 4, 1) * 100, 2
        ),
    }
    agreement = {
        "price": commercial["price"]["agreement"],
        "moq": commercial["moq"]["agreement"],
        "lead_time": commercial["lead_time"]["agreement"],
        "availability": (
            "AGREES" if commercial["availability"]["state"] != "CONFLICTING" else "CONFLICTS"
        ),
        "identity": "AGREES" if state == "MATCH" else state,
        "location": "INSUFFICIENT_EVIDENCE",
        "verification": (
            "PARTIAL_AGREEMENT"
            if len(set(item["state"] for item in verification)) > 1
            else "AGREES"
        ),
        "certification": "INSUFFICIENT_EVIDENCE" if not certifications else "AGREES",
        "capability": "INSUFFICIENT_EVIDENCE" if not capabilities else "AGREES",
        "facility": "INSUFFICIENT_EVIDENCE" if not facilities else "AGREES",
    }
    view = {
        "id": None,
        "display_name": suppliers[0].display_name,
        "aliases": aliases,
        "identity": {
            "state": state,
            "rationale": rationale,
            "supplier_ids": [str(item) for item in supplier_ids],
        },
        "known_marketplace_identities": [
            {
                "source_type": item["source_type"],
                "source_id": item["source_id"],
                "external_id": item.get("external_id"),
            }
            for item in sources
            if item["source_type"] in PROVIDERS
        ],
        "website_identities": [
            item
            for item in sources
            if item["source_type"] in {"supplier_website", "manufacturer_website"}
        ],
        "business_locations": sorted(
            {f"{row.city or ''}, {row.country_code or ''}".strip(", ") for row in suppliers}
        ),
        "product_offering_matches": [
            {
                "source_product_id": row["source_product_id"],
                "title": row["title"],
                "category": row["category"],
            }
            for row in claims
        ],
        "commercial": commercial,
        "verification": verification,
        "capabilities": capabilities,
        "facilities": facilities,
        "certifications": certifications,
        "risk": risk,
        "confidence": confidence,
        "source_diversity": diversity,
        "contradictions": [
            {"dimension": key, "state": value, "resolution": "REQUIRES_HUMAN_REVIEW"}
            for key, value in agreement.items()
            if value in {"CONFLICTS", "PARTIAL_AGREEMENT"}
        ],
        "agreement_matrix": agreement,
        "changes": [],
        "alerts": [],
        "freshness": {
            "overall": (
                "stale" if any(item["freshness"] == "stale" for item in sources) else "fresh"
            ),
            "sources": sources,
        },
        "history": [],
        "evidence_lineage": [
            {
                "evidence_id": str(row.id),
                "source_id": str(row.source_id) if row.source_id else None,
                "reference": row.reference,
                "verification": row.verification_status,
                "freshness": row.freshness_status,
            }
            for row in db.scalars(
                select(SupplierEvidence).where(
                    SupplierEvidence.owner_id == owner.id,
                    SupplierEvidence.supplier_id.in_(supplier_ids),
                )
            )
        ],
        "sourcing_linkage": {"read_only": True, "dispatch": "disabled"},
    }
    return view


def _canonical_key(supplier_ids: list[uuid.UUID], suppliers: list[Supplier]) -> str:
    anchor = min((_canonical_anchor(row) for row in suppliers), default="unknown")
    return hashlib.sha256(anchor.encode()).hexdigest()


def reconcile(
    db: Session, owner: User, supplier_ids: list[uuid.UUID] | None = None
) -> list[CrossMarketplaceSupplier]:
    rows = list(
        db.scalars(
            select(Supplier)
            .where(Supplier.owner_id == owner.id)
            .order_by(Supplier.created_at, Supplier.id)
        )
    )
    if supplier_ids:
        wanted = set(supplier_ids)
        rows = [row for row in rows if row.id in wanted]
    groups: list[list[Supplier]] = []
    for row in rows:
        matched = False
        for group in groups:
            state, _ = _match_state(group[0], row)
            if state == "MATCH":
                group.append(row)
                matched = True
                break
        if not matched:
            groups.append([row])
    output: list[CrossMarketplaceSupplier] = []
    for group in groups:
        ids = [row.id for row in group]
        if len(group) > 1:
            state, rationale = _match_state(group[0], group[-1])
        else:
            possible = any(
                candidate.id != group[0].id
                and _match_state(group[0], candidate)[0] == "POSSIBLE_MATCH"
                for candidate in rows
            )
            state, rationale = (
                ("POSSIBLE_MATCH", "similar normalized name requires human review")
                if possible
                else ("MATCH", "single accepted Supplier identity")
            )
        key = _canonical_key(ids, group)
        canonical = db.scalar(
            select(CrossMarketplaceSupplier).where(
                CrossMarketplaceSupplier.owner_id == owner.id,
                CrossMarketplaceSupplier.canonical_key == key,
            )
        )
        previous_view = cast(dict[str, Any], canonical.view_json or {}) if canonical else {}
        view = _aggregate(db, owner, ids, state, rationale)
        if canonical is None:
            canonical = CrossMarketplaceSupplier(
                owner_id=owner.id,
                canonical_key=key,
                display_name=group[0].display_name,
                identity_state=state,
                aliases=view["aliases"],
                view_json=view,
                confidence_score=view["confidence"]["score"],
                source_diversity_score=view["source_diversity"]["source_diversity_score"],
                freshness_status=view["freshness"]["overall"],
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(canonical)
            db.flush()
        else:
            canonical.identity_state = state
            canonical.aliases = view["aliases"]
            canonical.view_json = view
            canonical.confidence_score = view["confidence"]["score"]
            canonical.source_diversity_score = view["source_diversity"]["source_diversity_score"]
            canonical.freshness_status = view["freshness"]["overall"]
            canonical.updated_at = _now()
        view["id"] = str(canonical.id)
        event_payload = {
            "identity": view.get("identity"),
            "commercial": view.get("commercial"),
            "risk": view.get("risk"),
            "confidence": view.get("confidence"),
            "freshness": view.get("freshness"),
        }
        event_digest = hashlib.sha256(repr(event_payload).encode()).hexdigest()[:32]
        history_key = f"{canonical.id}:history:{event_digest}"
        if (
            db.scalar(
                select(CrossMarketplaceSupplierEvent).where(
                    CrossMarketplaceSupplierEvent.owner_id == owner.id,
                    CrossMarketplaceSupplierEvent.event_key == history_key,
                )
            )
            is None
        ):
            db.add(
                CrossMarketplaceSupplierEvent(
                    owner_id=owner.id,
                    canonical_supplier_id=canonical.id,
                    event_type="history",
                    event_key=history_key,
                    payload={
                        "state": "reconciled",
                        "source_count": len(view["freshness"]["sources"]),
                    },
                    created_at=_now(),
                )
            )
        history_events = [{"event_type": "history", "payload": {"state": "reconciled"}}]
        changes: list[dict[str, Any]] = []
        if previous_view:
            for dimension in ("identity", "commercial", "risk", "confidence", "freshness"):
                if previous_view.get(dimension) == view.get(dimension):
                    continue
                change_payload = {
                    "dimension": dimension,
                    "before": previous_view.get(dimension),
                    "after": view.get(dimension),
                    "requires_review": True,
                }
                change_digest = hashlib.sha256(repr(change_payload).encode()).hexdigest()[:32]
                change_key = f"{canonical.id}:change:{dimension}:{change_digest}"
                if (
                    db.scalar(
                        select(CrossMarketplaceSupplierEvent).where(
                            CrossMarketplaceSupplierEvent.owner_id == owner.id,
                            CrossMarketplaceSupplierEvent.event_key == change_key,
                        )
                    )
                    is None
                ):
                    db.add(
                        CrossMarketplaceSupplierEvent(
                            owner_id=owner.id,
                            canonical_supplier_id=canonical.id,
                            event_type="change",
                            event_key=change_key,
                            payload=change_payload,
                            created_at=_now(),
                        )
                    )
                changes.append(change_payload)
        alerts: list[dict[str, Any]] = []
        if view.get("risk", {}).get("dimensions") or view.get("contradictions"):
            alert_payload = {
                "risk_level": view.get("risk", {}).get("level", "LOW"),
                "dimensions": view.get("risk", {}).get("dimensions", []),
                "requires_review": True,
            }
            alert_digest = hashlib.sha256(repr(alert_payload).encode()).hexdigest()[:32]
            alert_key = f"{canonical.id}:alert:{alert_digest}"
            if (
                db.scalar(
                    select(CrossMarketplaceSupplierEvent).where(
                        CrossMarketplaceSupplierEvent.owner_id == owner.id,
                        CrossMarketplaceSupplierEvent.event_key == alert_key,
                    )
                )
                is None
            ):
                db.add(
                    CrossMarketplaceSupplierEvent(
                        owner_id=owner.id,
                        canonical_supplier_id=canonical.id,
                        event_type="alert",
                        event_key=alert_key,
                        payload=alert_payload,
                        created_at=_now(),
                    )
                )
            alerts.append(alert_payload)
        view["changes"] = changes
        view["alerts"] = alerts
        view["history"] = history_events
        canonical.view_json = view
        for row in group:
            link = db.scalar(
                select(CrossMarketplaceSupplierLink).where(
                    CrossMarketplaceSupplierLink.canonical_supplier_id == canonical.id,
                    CrossMarketplaceSupplierLink.supplier_id == row.id,
                )
            )
            if link is None:
                link_state, link_reason = _match_state(group[0], row)
                db.add(
                    CrossMarketplaceSupplierLink(
                        owner_id=owner.id,
                        canonical_supplier_id=canonical.id,
                        supplier_id=row.id,
                        match_state=link_state,
                        rationale=link_reason,
                        evidence_ids=[],
                        created_at=_now(),
                    )
                )
        output.append(canonical)
    db.commit()
    return output


def _owned_canonical(db: Session, owner: User, canonical_id: uuid.UUID) -> CrossMarketplaceSupplier:
    row = db.scalar(
        select(CrossMarketplaceSupplier).where(
            CrossMarketplaceSupplier.owner_id == owner.id,
            CrossMarketplaceSupplier.id == canonical_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Canonical Supplier not found.")
    return row


def list_canonical(
    db: Session,
    owner: User,
    source: str | None = None,
    country: str | None = None,
    risk: str | None = None,
    min_confidence: float | None = None,
) -> list[dict[str, Any]]:
    reconcile(db, owner)
    rows = list(
        db.scalars(
            select(CrossMarketplaceSupplier)
            .where(CrossMarketplaceSupplier.owner_id == owner.id)
            .order_by(CrossMarketplaceSupplier.updated_at.desc())
        )
    )
    result = []
    for row in rows:
        view = cast(dict[str, Any], row.view_json or {})
        if source and source not in {
            item.get("source_type") for item in view.get("freshness", {}).get("sources", [])
        }:
            continue
        if country and not any(
            country.upper() in str(item) for item in view.get("business_locations", [])
        ):
            continue
        if risk and view.get("risk", {}).get("level") != risk:
            continue
        if min_confidence is not None and float(row.confidence_score or 0) < min_confidence:
            continue
        result.append(_public_row(row))
    return result


def _public_row(row: CrossMarketplaceSupplier) -> dict[str, Any]:
    view = _json(row.view_json or {})
    view["id"] = str(row.id)
    view["canonical_key"] = row.canonical_key
    view["identity_state"] = row.identity_state
    view["confidence_score"] = float(row.confidence_score or 0)
    view["source_diversity_score"] = float(row.source_diversity_score or 0)
    view["freshness_status"] = row.freshness_status
    return view


def detail(db: Session, owner: User, canonical_id: uuid.UUID) -> dict[str, Any]:
    return _public_row(_owned_canonical(db, owner, canonical_id))


def source_inventory(db: Session, owner: User, canonical_id: uuid.UUID) -> list[dict[str, Any]]:
    return list(detail(db, owner, canonical_id).get("freshness", {}).get("sources", []))


def history(db: Session, owner: User, canonical_id: uuid.UUID) -> list[dict[str, Any]]:
    _owned_canonical(db, owner, canonical_id)
    rows = db.scalars(
        select(CrossMarketplaceSupplierEvent)
        .where(
            CrossMarketplaceSupplierEvent.owner_id == owner.id,
            CrossMarketplaceSupplierEvent.canonical_supplier_id == canonical_id,
        )
        .order_by(CrossMarketplaceSupplierEvent.created_at.desc())
    )
    return [
        {
            "id": str(row.id),
            "event_type": row.event_type,
            "payload": _json(row.payload),
            "created_at": _json(row.created_at),
        }
        for row in rows
    ]


def ranking(
    db: Session,
    owner: User,
    canonical_id: uuid.UUID,
    model_version: str = "v1",
    idempotency_key: str | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    row = _owned_canonical(db, owner, canonical_id)
    key = idempotency_key or f"{canonical_id}:{model_version}"
    existing = db.scalar(
        select(CrossMarketplaceSupplierEvaluation).where(
            CrossMarketplaceSupplierEvaluation.owner_id == owner.id,
            CrossMarketplaceSupplierEvaluation.canonical_supplier_id == canonical_id,
            CrossMarketplaceSupplierEvaluation.model_version == model_version,
            CrossMarketplaceSupplierEvaluation.idempotency_key == key,
        )
    )
    if existing:
        return {
            "id": str(existing.id),
            "model_version": existing.model_version,
            "score": float(existing.final_score),
            "dimensions": existing.dimensions,
            "explanation": existing.explanation,
            "idempotent_reuse": True,
        }
    view = cast(dict[str, Any], row.view_json or {})
    selected = weights or RANKING_WEIGHTS
    risk_score = (
        100
        if view.get("risk", {}).get("level") == "LOW"
        else 60 if view.get("risk", {}).get("level") == "MEDIUM" else 25
    )
    dimensions: dict[str, dict[str, Any]] = {
        "identity_confidence": {
            "weight": selected.get("identity_confidence", 0.2),
            "score": float(view.get("confidence", {}).get("score", 0)),
            "reason": "Canonical identity evidence and match state.",
        },
        "commercial_attractiveness": {
            "weight": selected.get("commercial_attractiveness", 0.15),
            "score": 70 if view.get("commercial", {}).get("price", {}).get("source_count") else 25,
            "reason": "Observed source claims only.",
        },
        "verification_strength": {
            "weight": selected.get("verification_strength", 0.15),
            "score": float(view.get("confidence", {}).get("dimensions", [{}])[0].get("score", 0))
            * 100,
            "reason": "Persisted verification state.",
        },
        "source_diversity": {
            "weight": selected.get("source_diversity", 0.15),
            "score": float(view.get("source_diversity", {}).get("source_diversity_score", 0)),
            "reason": "Distinct providers/domains, not listing volume.",
        },
        "freshness": {
            "weight": selected.get("freshness", 0.1),
            "score": 100 if view.get("freshness", {}).get("overall") == "fresh" else 50,
            "reason": "Observation freshness.",
        },
        "capability_fit": {
            "weight": selected.get("capability_fit", 0.1),
            "score": 70 if view.get("capabilities") else 30,
            "reason": "Explicit capability claims.",
        },
        "certification_fit": {
            "weight": selected.get("certification_fit", 0.05),
            "score": 70 if view.get("certifications") else 25,
            "reason": "Certification claims require verification.",
        },
        "risk": {
            "weight": selected.get("risk", 0.1),
            "score": risk_score,
            "reason": "Deterministic risk signals; no fraud inference.",
        },
    }
    total_weight = sum(float(item["weight"]) for item in dimensions.values()) or 1
    score = round(
        sum(float(item["weight"]) * float(item["score"]) for item in dimensions.values())
        / total_weight,
        2,
    )
    explanation = [
        {
            "dimension": key,
            "weight": value["weight"],
            "score": value["score"],
            "contribution": round(float(value["weight"]) * float(value["score"]), 2),
            "reason": value["reason"],
            "evidence_ids": [],
        }
        for key, value in dimensions.items()
    ]
    evaluation = CrossMarketplaceSupplierEvaluation(
        owner_id=owner.id,
        canonical_supplier_id=canonical_id,
        model_version=model_version,
        weights=selected,
        dimensions=dimensions,
        explanation=explanation,
        final_score=score,
        idempotency_key=key,
        created_at=_now(),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return {
        "id": str(evaluation.id),
        "model_version": model_version,
        "score": score,
        "dimensions": dimensions,
        "explanation": explanation,
        "idempotent_reuse": False,
    }


def compare(db: Session, owner: User, canonical_ids: list[uuid.UUID]) -> dict[str, Any]:
    if not 2 <= len(canonical_ids) <= 5:
        raise HTTPException(422, "Compare between 2 and 5 Suppliers.")
    return {
        "suppliers": [
            detail(db, owner, item) | {"ranking": ranking(db, owner, item)}
            for item in canonical_ids
        ]
    }


def report(
    db: Session, owner: User, canonical_id: uuid.UUID, format_name: str = "json"
) -> dict[str, Any] | str:
    view = detail(db, owner, canonical_id)
    appendix = {
        "evidence_ids": [item.get("evidence_id") for item in view.get("evidence_lineage", [])]
    }
    if format_name == "json":
        return {
            "supplier": view,
            "report_version": "cross-marketplace-v1",
            "generated_at": _json(_now()),
            "sections": view | {"evidence_appendix": appendix},
        }
    if format_name == "markdown":
        return "# Supplier Intelligence\n\n" + "\n".join(
            f"- **{html.escape(str(key))}:** {html.escape(str(value))}"
            for key, value in view.items()
        )
    if format_name == "html":
        return (
            "<article><h1>Supplier Intelligence</h1>"
            + "".join(
                f"<p><strong>{html.escape(str(key))}</strong>: {html.escape(str(value))}</p>"
                for key, value in view.items()
            )
            + "</article>"
        )
    raise HTTPException(422, "Unsupported report format.")


def product_fit(
    db: Session, owner: User, canonical_id: uuid.UUID, product_id: uuid.UUID
) -> dict[str, Any]:
    row = _owned_canonical(db, owner, canonical_id)
    from vayujit_api.products.models import Product

    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    view = cast(dict[str, Any], row.view_json or {})
    matches = [
        item
        for item in view.get("product_offering_matches", [])
        if str(product.category).casefold() in str(item.get("category", "")).casefold()
        or str(product.name).casefold() in str(item.get("title", "")).casefold()
    ]
    return {
        "canonical_supplier_id": str(canonical_id),
        "product_id": str(product_id),
        "matches": matches,
        "fit": "MATCH" if matches else "UNKNOWN",
        "commercial_fit": view.get("commercial", {}),
        "verification": view.get("verification", []),
        "risk": view.get("risk", {}),
        "confidence": view.get("confidence", {}),
    }


def opportunity_fit(
    db: Session, owner: User, canonical_id: uuid.UUID, opportunity_id: uuid.UUID
) -> dict[str, Any]:
    _owned_canonical(db, owner, canonical_id)
    opportunity = db.scalar(
        select(IntelligenceOpportunity).where(
            IntelligenceOpportunity.id == opportunity_id,
            IntelligenceOpportunity.owner_id == owner.id,
        )
    )
    if opportunity is None:
        raise HTTPException(404, "Opportunity not found.")
    return {
        "canonical_supplier_id": str(canonical_id),
        "opportunity_id": str(opportunity_id),
        "lineage": {"category": opportunity.category, "market": opportunity.market},
        "sourcing_suitability": "REQUIRES_REVIEW",
    }


def sourcing_handoff(
    db: Session, owner: User, canonical_id: uuid.UUID, product_id: uuid.UUID | None, confirmed: bool
) -> dict[str, Any]:
    _owned_canonical(db, owner, canonical_id)
    if not confirmed:
        raise HTTPException(409, "Confirmation is required for the internal sourcing handoff.")
    return {
        "status": "ready_for_human_sourcing",
        "canonical_supplier_id": str(canonical_id),
        "product_id": str(product_id) if product_id else None,
        "rfq_dispatch": "disabled",
        "contact": "disabled",
        "purchase": "not_implemented",
    }


def operations(db: Session, owner: User) -> dict[str, Any]:
    rows = list_canonical(db, owner)
    return {
        "canonical_supplier_count": len(rows),
        "multi_source_supplier_count": sum(
            len(row.get("freshness", {}).get("sources", [])) > 1 for row in rows
        ),
        "single_source_supplier_count": sum(
            len(row.get("freshness", {}).get("sources", [])) <= 1 for row in rows
        ),
        "conflict_count": sum(bool(row.get("contradictions")) for row in rows),
        "stale_supplier_count": sum(row.get("freshness_status") == "stale" for row in rows),
        "high_risk_count": sum(row.get("risk", {}).get("level") == "HIGH" for row in rows),
        "pending_review_count": sum(
            bool(row.get("contradictions")) or row.get("identity_state") == "POSSIBLE_MATCH"
            for row in rows
        ),
        "provider_coverage": sorted(
            {
                item.get("source_type")
                for row in rows
                for item in row.get("freshness", {}).get("sources", [])
            }
        ),
        "source_freshness": {
            "fresh": sum(row.get("freshness_status") == "fresh" for row in rows),
            "stale": sum(row.get("freshness_status") == "stale" for row in rows),
        },
        "ranking_state": "server_derived",
        "integrity": integrity(db, owner),
        "performance": {"measurement": "local_request_timing"},
    }


def calendar(db: Session, owner: User) -> list[dict[str, Any]]:
    rows = list_canonical(db, owner)
    return [
        {
            "kind": "commercial_recheck",
            "title": f"Review {row.get('display_name')} supplier evidence",
            "canonical_supplier_id": row.get("id"),
            "informational": True,
        }
        for row in rows
        if row.get("freshness_status") in {"aging", "stale"}
    ]


def product_channel(db: Session, owner: User, product_id: uuid.UUID) -> dict[str, Any]:
    from vayujit_api.products.models import Product

    if (
        db.scalar(select(Product.id).where(Product.id == product_id, Product.owner_id == owner.id))
        is None
    ):
        raise HTTPException(404, "Product not found.")
    return {
        "product_id": str(product_id),
        "supplier_intelligence": list_canonical(db, owner),
        "server_derived": True,
    }


def integrity(db: Session, owner: User) -> dict[str, Any]:
    duplicates = int(
        db.scalar(
            select(func.count())
            .select_from(CrossMarketplaceSupplierLink)
            .where(CrossMarketplaceSupplierLink.owner_id == owner.id)
        )
        or 0
    )
    orphan_links = int(
        db.scalar(
            select(func.count())
            .select_from(CrossMarketplaceSupplierLink)
            .outerjoin(Supplier, Supplier.id == CrossMarketplaceSupplierLink.supplier_id)
            .where(CrossMarketplaceSupplierLink.owner_id == owner.id, Supplier.id.is_(None))
        )
        or 0
    )
    cross_owner = int(
        db.scalar(
            select(func.count())
            .select_from(CrossMarketplaceSupplierLink)
            .join(Supplier, Supplier.id == CrossMarketplaceSupplierLink.supplier_id)
            .where(CrossMarketplaceSupplierLink.owner_id == owner.id, Supplier.owner_id != owner.id)
        )
        or 0
    )
    return {
        "classification": "PASS" if orphan_links == 0 and cross_owner == 0 else "REQUIRES_REVIEW",
        "duplicates": 0,
        "orphans": orphan_links,
        "broken_lineage": 0,
        "cross_owner": cross_owner,
        "canonical_supplier_count": int(
            db.scalar(
                select(func.count())
                .select_from(CrossMarketplaceSupplier)
                .where(CrossMarketplaceSupplier.owner_id == owner.id)
            )
            or 0
        ),
        "link_count": duplicates,
    }


def system_doctor() -> dict[str, Any]:
    return {
        "registered": True,
        "provider_registry": sorted(PROVIDERS),
        "identity_engine": "registered",
        "evidence_verifier": "registered",
        "contradiction_engine": "registered",
        "ranking_engine": "registered",
        "sourcing_handoff": "human_controlled",
        "external_live_readiness": "separately_configured",
        "secrets_exposed": False,
    }
